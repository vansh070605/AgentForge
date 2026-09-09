"""Unit tests for AgentForge domain models and BaseAgent interface."""

import pytest
from datetime import datetime, timezone

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models import (
    ActionType,
    AuditEvent,
    AcceptanceCriterion,
    TaskSpecification,
    ToolCallRecord,
    CommandExecutionResult,
    ExecutionResult,
    SeverityLevel,
    ReviewIssue,
    ReviewStatus,
    ReviewReport,
    VerificationStatus,
    CriterionStatus,
    RequirementProof,
    VerificationReport,
    TaskStatus,
    OrchestratorState,
)


def test_audit_event_creation():
    event = AuditEvent(
        task_id="task_123",
        actor="execution_agent",
        action_type=ActionType.FILE_WRITTEN,
        description="Wrote auth.py",
        metadata={"file": "auth.py", "lines": 45},
    )
    assert event.event_id.startswith("evt_")
    assert event.task_id == "task_123"
    assert event.action_type == ActionType.FILE_WRITTEN
    assert event.status == "success"
    assert event.metadata["file"] == "auth.py"
    assert isinstance(event.timestamp, datetime)

    # Test serialization roundtrip
    data = event.model_dump_json()
    loaded = AuditEvent.model_validate_json(data)
    assert loaded.event_id == event.event_id
    assert loaded.action_type == ActionType.FILE_WRITTEN


def test_task_specification_schema():
    spec = TaskSpecification(
        task_id="task_001",
        title="Add password hashing",
        description="Hash user passwords with bcrypt before saving.",
        target_files=["src/auth.py", "tests/test_auth.py"],
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC-1",
                description="Passwords stored in database must be bcrypt hashes.",
                verification_method="unit_test",
            ),
            AcceptanceCriterion(
                id="AC-2",
                description="Plaintext passwords must never appear in logs.",
                verification_method="code_inspection",
            ),
        ],
        suggested_test_command="pytest tests/test_auth.py",
        constraints=["Use standard bcrypt library", "Do not alter User schema fields"],
    )

    assert spec.task_id == "task_001"
    assert len(spec.acceptance_criteria) == 2
    assert spec.acceptance_criteria[0].id == "AC-1"


def test_execution_result_schema():
    tool_rec = ToolCallRecord(
        tool_name="write_file",
        arguments={"path": "src/auth.py"},
        output_summary="Successfully wrote 120 lines",
    )
    cmd_res = CommandExecutionResult(
        command="pytest tests/",
        exit_code=0,
        stdout="2 passed in 0.05s",
        stderr="",
        duration_seconds=0.15,
    )
    exec_res = ExecutionResult(
        task_id="task_001",
        iteration=1,
        summary_of_changes="Implemented bcrypt password hashing in auth.py",
        modified_files=["src/auth.py", "tests/test_auth.py"],
        commits_created=["commit_abc123"],
        test_results=cmd_res,
        tool_calls=[tool_rec],
    )
    assert exec_res.task_id == "task_001"
    assert exec_res.test_results.exit_code == 0
    assert len(exec_res.tool_calls) == 1


def test_review_report_schema():
    issue = ReviewIssue(
        file="src/auth.py",
        line=42,
        severity=SeverityLevel.HIGH,
        problem="Password salt rounds are too low (cost factor 4).",
        recommendation="Increase rounds to at least 12.",
    )
    report = ReviewReport(
        task_id="task_001",
        iteration=1,
        status=ReviewStatus.NEEDS_CHANGES,
        summary="Implementation is mostly complete but has a security concern.",
        issues=[issue],
    )
    assert report.status == ReviewStatus.NEEDS_CHANGES
    assert len(report.issues) == 1
    assert report.issues[0].severity == SeverityLevel.HIGH


def test_verification_report_schema():
    req_proof = RequirementProof(
        criterion_id="AC-1",
        description="Passwords must be bcrypt hashes.",
        status=CriterionStatus.SATISFIED,
        evidence_items=[
            "diff: src/auth.py bcrypt.hashpw called",
            "test: tests/test_auth.py::test_hash_format PASSED",
        ],
    )
    v_report = VerificationReport(
        task_id="task_001",
        status=VerificationStatus.VERIFIED,
        confidence_score=0.96,
        requirements=[req_proof],
        tests_passed=5,
        tests_failed=0,
        unrelated_changes_detected=False,
        verification_summary="All acceptance criteria satisfied with passing tests and verified diffs.",
    )
    assert v_report.status == VerificationStatus.VERIFIED
    assert v_report.confidence_score == 0.96
    assert not v_report.unrelated_changes_detected


def test_orchestrator_state():
    state = OrchestratorState(
        task_id="task_001",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add password hashing",
    )
    assert state.status == TaskStatus.PENDING
    assert state.current_iteration == 1
    assert state.max_iterations == 2


class DummyAgent(BaseAgent):
    async def run(self, state: OrchestratorState, **kwargs):
        return "done"


def test_base_agent_interface():
    meta = AgentMetadata(
        name="ReviewBot",
        role="review",
        description="Reviews code diffs",
        allowed_tools=["read_file", "view_diff"],
    )
    agent = DummyAgent(meta)
    assert agent.name == "ReviewBot"
    assert agent.role == "review"
    assert agent.is_tool_allowed("read_file")
    assert not agent.is_tool_allowed("write_file")

    evt = agent.create_audit_event("task_999", ActionType.REVIEW_SUBMITTED, "Approved with no issues")
    assert evt.actor == "review:ReviewBot"
    assert evt.action_type == ActionType.REVIEW_SUBMITTED
