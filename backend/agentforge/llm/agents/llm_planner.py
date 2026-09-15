"""LLM-powered Execution Planner callable.

Implements the ``execution_plan_generator`` hook expected by PipelineOrchestrator:
    Callable[[OrchestratorState, WorkspaceManager], List[ExecutionAction]]

When an LLMClient is available, this reads relevant files, builds context from the
TaskSpecification and any prior review feedback, asks the LLM to produce a structured
list of ExecutionActions, validates them, and returns the plan. On failure it falls
back to the orchestrator's _default_plan_generator logic.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agentforge.llm.base import LLMClient, LLMError, ChatMessage, _strip_code_fences
from agentforge.llm.prompts import (
    PLANNER_SYSTEM,
    PLANNER_USER_INITIAL_TEMPLATE,
    PLANNER_USER_FIXING_TEMPLATE,
)
from agentforge.models.execution import ExecutionAction
from agentforge.models.state import OrchestratorState, TaskStatus
from agentforge.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

# Tools the LLM is allowed to reference in plans
ALLOWED_PLAN_TOOLS = {
    "read_file",
    "list_files",
    "search_code",
    "write_file",
    "run_tests",
    "git_status",
    "git_diff",
    "git_commit",
}

# Hard limits to prevent runaway plans
MAX_PLAN_ACTIONS = 40
MAX_FILE_CONTENT_BYTES = 6000  # per file, to stay within context limits


# ---------------------------------------------------------------------------
# Pydantic schema for the LLM's plan output
# ---------------------------------------------------------------------------


class _LLMAction(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    critical: bool = True


class _LLMPlan(BaseModel):
    actions: List[_LLMAction]


# ---------------------------------------------------------------------------
# LLMExecutionPlanner
# ---------------------------------------------------------------------------


class LLMExecutionPlanner:
    """Callable that generates a list of ExecutionActions using an LLM.

    Usage (wire into PipelineOrchestrator):
        from agentforge.llm import get_llm_client
        from agentforge.llm.agents.llm_planner import LLMExecutionPlanner
        from agentforge.orchestrator import PipelineOrchestrator

        llm = get_llm_client()
        orchestrator = PipelineOrchestrator(
            execution_plan_generator=LLMExecutionPlanner(llm)
        )
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    # ------------------------------------------------------------------
    # Public callable — matches execution_plan_generator signature
    # ------------------------------------------------------------------

    def __call__(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
    ) -> List[ExecutionAction]:
        """Synchronous wrapper over the async LLM call."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self._async_plan(state, workspace), loop
            )
            return future.result(timeout=180)
        except RuntimeError:
            return asyncio.run(self._async_plan(state, workspace))
        except Exception as exc:
            logger.warning(
                "LLMExecutionPlanner failed (%s), falling back to default plan: %s",
                type(exc).__name__,
                exc,
            )
            return self._default_fallback(state)

    # ------------------------------------------------------------------
    # Async implementation
    # ------------------------------------------------------------------

    async def _async_plan(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
    ) -> List[ExecutionAction]:
        spec = state.task_spec
        if not spec:
            logger.warning("LLMExecutionPlanner: no task_spec found, returning empty plan")
            return []

        file_listing = _get_file_listing(workspace)
        file_contents = _read_target_files(workspace, spec.target_files)

        is_fixing = state.status == TaskStatus.FIXING and state.review_reports

        if is_fixing:
            last_review = state.review_reports[-1]
            review_issues_text = _format_review_issues(last_review.issues)
            diff_text = _get_diff(workspace)
            user_content = PLANNER_USER_FIXING_TEMPLATE.format(
                title=spec.title,
                description=spec.description,
                review_issues=review_issues_text,
                diff_text=diff_text or "(no diff)",
                file_listing=file_listing,
                file_contents=file_contents,
            )
        else:
            user_content = PLANNER_USER_INITIAL_TEMPLATE.format(
                title=spec.title,
                description=spec.description,
                target_files=", ".join(spec.target_files) or "(to be determined)",
                test_command=spec.suggested_test_command or "pytest",
                constraints="\n".join(f"- {c}" for c in spec.constraints),
                file_listing=file_listing,
                file_contents=file_contents,
            )

        # The planner outputs a JSON array directly (not an object)
        # We'll wrap it in a schema that has an "actions" key
        messages = [
            ChatMessage(role="system", content=PLANNER_SYSTEM),
            ChatMessage(role="user", content=user_content),
            ChatMessage(
                role="user",
                content=(
                    'Respond with a JSON object with a single key "actions" whose value is '
                    "the ordered array of action objects. Example:\n"
                    '{"actions": [{"tool_name": "read_file", "arguments": {"file_path": "src/main.py"}, '
                    '"description": "Read main.py", "critical": false}]}'
                ),
            ),
        ]

        llm_plan: _LLMPlan = await self._llm.complete_with_json(
            messages=messages,
            schema=_LLMPlan,
            temperature=0.1,
            max_tokens=8192,
        )

        actions = _validate_and_convert_actions(llm_plan.actions)
        logger.info(
            "LLMExecutionPlanner generated %d valid actions (is_fixing=%s)",
            len(actions),
            is_fixing,
        )
        return actions

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _default_fallback(self, state: OrchestratorState) -> List[ExecutionAction]:
        """Minimal safe plan when LLM fails."""
        actions: List[ExecutionAction] = [
            ExecutionAction(
                tool_name="git_status",
                arguments={},
                description="Inspect working tree status",
                critical=False,
            )
        ]
        spec = state.task_spec
        if spec:
            for f in spec.target_files[:5]:
                actions.append(ExecutionAction(
                    tool_name="read_file",
                    arguments={"file_path": f},
                    description=f"Read {f}",
                    critical=False,
                ))
            if spec.suggested_test_command:
                actions.append(ExecutionAction(
                    tool_name="run_tests",
                    arguments={"command": spec.suggested_test_command},
                    description="Run test suite",
                    critical=False,
                ))
        return actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_and_convert_actions(raw_actions: List[_LLMAction]) -> List[ExecutionAction]:
    """Filter out unknown tools and convert to ExecutionAction, capped at MAX_PLAN_ACTIONS."""
    valid: List[ExecutionAction] = []
    for raw in raw_actions[:MAX_PLAN_ACTIONS]:
        if raw.tool_name not in ALLOWED_PLAN_TOOLS:
            logger.warning("LLM plan referenced unknown tool '%s', skipping", raw.tool_name)
            continue
        valid.append(ExecutionAction(
            tool_name=raw.tool_name,
            arguments=raw.arguments,
            description=raw.description,
            critical=raw.critical,
        ))
    return valid


def _get_file_listing(workspace: WorkspaceManager) -> str:
    try:
        files = workspace.list_files(rel_dir="")
        lines = [str(f) for f in files[:200]]
        return "\n".join(lines) or "(empty workspace)"
    except Exception:
        return "(could not list files)"


def _read_target_files(workspace: WorkspaceManager, target_files: List[str]) -> str:
    """Read contents of target files for LLM context, truncated per file."""
    if not target_files:
        return "(no target files specified)"
    parts: List[str] = []
    for path in target_files[:8]:  # limit to 8 files
        try:
            content = workspace.read_file(rel_path=path)
            if len(content) > MAX_FILE_CONTENT_BYTES:
                content = content[:MAX_FILE_CONTENT_BYTES] + f"\n... (truncated, {len(content)} bytes total)"
            parts.append(f"### {path}\n```\n{content}\n```")
        except FileNotFoundError:
            parts.append(f"### {path}\n(file does not exist yet — create it)")
        except Exception as exc:
            parts.append(f"### {path}\n(could not read: {exc})")
    return "\n\n".join(parts)


def _get_diff(workspace: WorkspaceManager) -> str:
    try:
        return workspace.git_diff(against_base=True) or ""
    except Exception:
        return ""


def _format_review_issues(issues: list) -> str:
    if not issues:
        return "(no specific issues listed)"
    lines = []
    for i, issue in enumerate(issues, 1):
        lines.append(
            f"{i}. [{issue.severity.upper() if hasattr(issue.severity, 'upper') else issue.severity}] "
            f"{issue.file}: {issue.problem}\n   Fix: {issue.recommendation}"
        )
    return "\n".join(lines)
