"""Unit tests for LLM agent callables (LLMIdentityGenerator, LLMExecutionPlanner, LLMReviewInspector).

All tests use a mocked LLMClient — zero real API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Type
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from agentforge.llm.base import ChatMessage, LLMClient, LLMError
from agentforge.models.state import OrchestratorState, TaskStatus
from agentforge.models.task import AcceptanceCriterion, TaskSpecification


# ---------------------------------------------------------------------------
# Reusable mock LLM client
# ---------------------------------------------------------------------------


class MockLLMClient(LLMClient):
    """Programmatic mock that returns preset responses."""

    def __init__(self, response_json: dict | list | None = None, should_raise: bool = False):
        self._response_json = response_json or {}
        self._should_raise = should_raise

    async def complete(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        if self._should_raise:
            raise LLMError("Simulated LLM failure")
        import json
        return json.dumps(self._response_json)

    async def complete_with_json(
        self, messages: list[ChatMessage], schema: Type[BaseModel], **kwargs: Any
    ) -> BaseModel:
        if self._should_raise:
            raise LLMError("Simulated LLM failure")
        import json
        data = self._response_json
        return schema.model_validate(data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(prompt: str = "Add a ping() function", task_id: str = "test_task") -> OrchestratorState:
    return OrchestratorState(
        task_id=task_id,
        repo_url_or_path=".",
        user_prompt=prompt,
        status=TaskStatus.PENDING,
        max_iterations=2,
    )


def _make_workspace():
    ws = MagicMock()
    ws.list_files.return_value = ["src/main.py", "tests/test_main.py"]
    ws.read_file.side_effect = FileNotFoundError("not found")
    ws.git_diff.return_value = "+def ping():\n+    return 'pong'\n"
    return ws


# ---------------------------------------------------------------------------
# LLMIdentityGenerator tests
# ---------------------------------------------------------------------------


class TestLLMIdentityGenerator:
    """Tests for the LLM-based TaskSpecification generator."""

    def _make_llm_spec_response(self) -> dict:
        return {
            "title": "Add ping function to main.py",
            "description": "Implement a ping() function that returns 'pong'.",
            "target_files": ["src/main.py", "tests/test_main.py"],
            "acceptance_criteria": [
                {
                    "id": "AC-1",
                    "description": "ping() function exists and returns 'pong'",
                    "verification_method": "unit_test",
                }
            ],
            "suggested_test_command": "pytest tests/test_main.py",
            "constraints": ["Do not modify other files."],
        }

    def test_successful_generation(self):
        from agentforge.llm.agents.llm_identity import LLMIdentityGenerator

        llm = MockLLMClient(response_json=self._make_llm_spec_response())
        gen = LLMIdentityGenerator(llm)
        state = _make_state()
        workspace = _make_workspace()

        spec = gen(state, workspace)

        assert isinstance(spec, TaskSpecification)
        assert spec.task_id == "test_task"
        assert "ping" in spec.title.lower() or "ping" in spec.description.lower()
        assert len(spec.acceptance_criteria) == 1
        assert spec.acceptance_criteria[0].id == "AC-1"
        assert "src/main.py" in spec.target_files

    def test_llm_failure_triggers_fallback(self):
        from agentforge.llm.agents.llm_identity import LLMIdentityGenerator

        llm = MockLLMClient(should_raise=True)
        gen = LLMIdentityGenerator(llm)
        state = _make_state("Add a ping function")
        workspace = _make_workspace()

        # Must not raise — falls back to heuristic
        spec = gen(state, workspace)

        assert isinstance(spec, TaskSpecification)
        assert spec.task_id == "test_task"
        assert len(spec.acceptance_criteria) >= 1  # heuristic fallback produces at least 1 criterion


# ---------------------------------------------------------------------------
# LLMExecutionPlanner tests
# ---------------------------------------------------------------------------


class TestLLMExecutionPlanner:
    """Tests for the LLM-based execution plan generator."""

    def _make_plan_response(self) -> dict:
        return {
            "actions": [
                {
                    "tool_name": "read_file",
                    "arguments": {"file_path": "src/main.py"},
                    "description": "Read main.py",
                    "critical": False,
                },
                {
                    "tool_name": "write_file",
                    "arguments": {
                        "file_path": "src/main.py",
                        "content": "def ping():\n    return 'pong'\n",
                    },
                    "description": "Write ping function",
                    "critical": True,
                },
                {
                    "tool_name": "run_tests",
                    "arguments": {"command": "pytest tests/test_main.py"},
                    "description": "Run tests",
                    "critical": True,
                },
                {
                    "tool_name": "git_commit",
                    "arguments": {"message": "feat: add ping()"},
                    "description": "Commit changes",
                    "critical": True,
                },
            ]
        }

    def _make_state_with_spec(self) -> OrchestratorState:
        state = _make_state()
        state.task_spec = TaskSpecification(
            task_id="test_task",
            title="Add ping function",
            description="Implement ping().",
            target_files=["src/main.py"],
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-1", description="ping() exists", verification_method="unit_test")
            ],
            suggested_test_command="pytest tests/test_main.py",
            constraints=[],
        )
        return state

    def test_successful_plan_generation(self):
        from agentforge.llm.agents.llm_planner import LLMExecutionPlanner
        from agentforge.models.execution import ExecutionAction

        llm = MockLLMClient(response_json=self._make_plan_response())
        planner = LLMExecutionPlanner(llm)
        state = self._make_state_with_spec()
        workspace = _make_workspace()

        actions = planner(state, workspace)

        assert len(actions) == 4
        assert all(isinstance(a, ExecutionAction) for a in actions)
        tool_names = [a.tool_name for a in actions]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "run_tests" in tool_names
        assert "git_commit" in tool_names

    def test_unknown_tool_in_plan_is_filtered(self):
        from agentforge.llm.agents.llm_planner import LLMExecutionPlanner

        response = {
            "actions": [
                {"tool_name": "dangerous_rm_rf", "arguments": {}, "description": "bad", "critical": True},
                {"tool_name": "read_file", "arguments": {"file_path": "f.py"}, "description": "ok", "critical": False},
            ]
        }
        llm = MockLLMClient(response_json=response)
        planner = LLMExecutionPlanner(llm)
        state = self._make_state_with_spec()
        workspace = _make_workspace()

        actions = planner(state, workspace)

        assert len(actions) == 1
        assert actions[0].tool_name == "read_file"

    def test_llm_failure_triggers_fallback(self):
        from agentforge.llm.agents.llm_planner import LLMExecutionPlanner

        llm = MockLLMClient(should_raise=True)
        planner = LLMExecutionPlanner(llm)
        state = self._make_state_with_spec()
        workspace = _make_workspace()

        # Must not raise — returns fallback plan
        actions = planner(state, workspace)
        assert isinstance(actions, list)

    def test_no_spec_returns_empty_plan(self):
        from agentforge.llm.agents.llm_planner import LLMExecutionPlanner

        llm = MockLLMClient(response_json={"actions": []})
        planner = LLMExecutionPlanner(llm)
        state = _make_state()  # no task_spec
        workspace = _make_workspace()

        actions = planner(state, workspace)
        assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# LLMReviewInspector tests
# ---------------------------------------------------------------------------


class TestLLMReviewInspector:
    """Tests for the LLM-based review inspector."""

    def _make_issue_response(self) -> dict:
        return {
            "issues": [
                {
                    "file": "src/main.py",
                    "line": 5,
                    "severity": "HIGH",
                    "problem": "Off-by-one error in loop boundary.",
                    "recommendation": "Change < to <= in the loop condition.",
                }
            ]
        }

    def test_successful_inspection(self):
        from agentforge.llm.agents.llm_reviewer import LLMReviewInspector
        from agentforge.models.review import ReviewIssue, SeverityLevel

        llm = MockLLMClient(response_json=self._make_issue_response())
        inspector = LLMReviewInspector(llm)
        state = _make_state()

        issues = inspector(state, "+def ping():\n+    return 'wrong'\n")

        assert len(issues) == 1
        assert isinstance(issues[0], ReviewIssue)
        assert issues[0].severity == SeverityLevel.HIGH
        assert "Off-by-one" in issues[0].problem
        assert "[LLM]" in issues[0].problem  # prefixed to distinguish from static checks

    def test_empty_diff_returns_empty_list(self):
        from agentforge.llm.agents.llm_reviewer import LLMReviewInspector

        llm = MockLLMClient(response_json={"issues": []})
        inspector = LLMReviewInspector(llm)
        state = _make_state()

        issues = inspector(state, "")
        assert issues == []

    def test_llm_failure_returns_empty_list(self):
        from agentforge.llm.agents.llm_reviewer import LLMReviewInspector

        llm = MockLLMClient(should_raise=True)
        inspector = LLMReviewInspector(llm)
        state = _make_state()

        # Must not raise — conservative empty return
        issues = inspector(state, "+def ping(): pass\n")
        assert issues == []

    def test_severity_normalisation(self):
        """Severity strings from LLM (case-insensitive) must map to SeverityLevel enum."""
        from agentforge.llm.agents.llm_reviewer import LLMReviewInspector
        from agentforge.models.review import SeverityLevel

        response = {
            "issues": [
                {"file": "x.py", "line": None, "severity": "critical", "problem": "P", "recommendation": "R"},
                {"file": "y.py", "line": 1, "severity": "LOW", "problem": "P2", "recommendation": "R2"},
            ]
        }
        llm = MockLLMClient(response_json=response)
        inspector = LLMReviewInspector(llm)
        state = _make_state()

        issues = inspector(state, "+code_change\n")

        assert issues[0].severity == SeverityLevel.CRITICAL
        assert issues[1].severity == SeverityLevel.LOW
