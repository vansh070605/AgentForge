"""Unit and integration tests for PipelineOrchestrator and FastAPI server."""

import asyncio
from pathlib import Path
import subprocess
import tempfile
import pytest
from fastapi.testclient import TestClient

from agentforge.api import create_app
from agentforge.models import (
    AcceptanceCriterion,
    ExecutionAction,
    OrchestratorState,
    ReviewIssue,
    ReviewReport,
    ReviewStatus,
    SeverityLevel,
    TaskSpecification,
    TaskStatus,
    VerificationReport,
    VerificationStatus,
)
from agentforge.orchestrator import PipelineOrchestrator
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def test_repo_and_workspace():
    """Sets up a test git workspace with an initial Python file and test file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Orchestrator"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "orch@agentforge.local"], cwd=source_dir, check=True)

        # Initial source files
        (source_dir / "service.py").write_text("def ping():\n    return 'pong'\n", encoding="utf-8")
        test_dir = source_dir / "tests"
        test_dir.mkdir()
        (test_dir / "test_service.py").write_text(
            "from service import ping\n\ndef test_ping():\n    assert ping() == 'pong'\n",
            encoding="utf-8",
        )

        subprocess.run(["git", "add", "."], cwd=source_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=source_dir, check=True)

        # Working workspace
        ws_dir = Path(tmp_dir) / "ws"
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_orch_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/orch-test")

        subprocess.run(["git", "config", "user.name", "Agent Orchestrator"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "orch@agentforge.local"], cwd=ws_dir, check=True)

        yield source_dir, wm
        wm.cleanup()


# ==================================================================
# 1. PipelineOrchestrator End-to-End Execution
# ==================================================================

def test_orchestrator_full_successful_lifecycle(test_repo_and_workspace):
    """Verifies that Orchestrator runs full 4-agent cycle and transitions to READY_FOR_PR."""
    source_dir, workspace = test_repo_and_workspace

    state = OrchestratorState(
        task_id="task_full_test",
        repo_url_or_path=str(source_dir),
        user_prompt="Add health() function in service.py and tests in tests/test_service.py",
        status=TaskStatus.PENDING,
    )

    # Define deterministic actions to implement health() cleanly
    def execution_planner(s, ws):
        updated_service = "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'ok'}\n"
        updated_tests = "from service import ping, health\n\ndef test_ping():\n    assert ping() == 'pong'\n\ndef test_health():\n    assert health()['status'] == 'ok'\n"
        return [
            ExecutionAction(tool_name="write_file", arguments={"file_path": "service.py", "content": updated_service}),
            ExecutionAction(tool_name="write_file", arguments={"file_path": "tests/test_service.py", "content": updated_tests}),
            ExecutionAction(tool_name="run_tests", arguments={"command": "pytest tests/test_service.py"}),
            ExecutionAction(tool_name="git_commit", arguments={"message": "feat: implement health check and tests"}),
        ]

    recorded_events = []
    def event_collector(event_type, data):
        recorded_events.append((event_type, data.get("status") or data.get("task_id")))

    orchestrator = PipelineOrchestrator(execution_plan_generator=execution_planner)
    orchestrator.add_event_listener(event_collector)

    final_state = asyncio.run(orchestrator.run(state=state, workspace=workspace))

    if final_state.status != TaskStatus.READY_FOR_PR:
        summary = final_state.verification_report.verification_summary if final_state.verification_report else "No report"
        print(f"DEBUG VERIFICATION FAILURE: {summary}")

    assert final_state.status == TaskStatus.READY_FOR_PR
    assert final_state.task_spec is not None
    assert len(final_state.execution_results) >= 1
    assert len(final_state.review_reports) >= 1
    assert final_state.review_reports[-1].status == ReviewStatus.APPROVED
    assert final_state.verification_report is not None
    assert final_state.verification_report.status == VerificationStatus.VERIFIED
    assert final_state.verification_report.confidence_score >= 0.8

    # Verify event timeline
    event_names = [e[0] for e in recorded_events]
    assert "pipeline_started" in event_names
    assert "identity_completed" in event_names
    assert "execution_completed" in event_names
    assert "review_completed" in event_names
    assert "proof_completed" in event_names
    assert "pipeline_completed" in event_names


def test_orchestrator_iteration_feedback_loop(test_repo_and_workspace):
    """Verifies that when ReviewAgent requests changes, Orchestrator loops to FIXING."""
    source_dir, workspace = test_repo_and_workspace

    state = OrchestratorState(
        task_id="task_loop_test",
        repo_url_or_path=str(source_dir),
        user_prompt="Add health() function",
        status=TaskStatus.PENDING,
        max_iterations=2,
    )

    iteration_counter = {"count": 0}

    def execution_planner(s, ws):
        iteration_counter["count"] += 1
        if iteration_counter["count"] == 1:
            # Iteration 1: Insecure change using eval() triggering HIGH severity in ReviewAgent
            content = "def ping():\n    return 'pong'\n\ndef health():\n    return eval('1')\n"
        else:
            # Iteration 2 (fixing): Clean fix without eval()
            content = "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'ok'}\n"

        return [
            ExecutionAction(tool_name="write_file", arguments={"file_path": "service.py", "content": content}),
            ExecutionAction(tool_name="git_commit", arguments={"message": f"feat: iteration {iteration_counter['count']}"}),
        ]

    transitions = []
    def track_transitions(event_type, data):
        if event_type == "state_transition":
            transitions.append(data.get("status"))

    orchestrator = PipelineOrchestrator(execution_plan_generator=execution_planner)
    orchestrator.add_event_listener(track_transitions)

    final_state = asyncio.run(orchestrator.run(state=state, workspace=workspace))

    # Expect transitions through FIXING
    assert "fixing" in transitions
    assert final_state.current_iteration == 2
    assert len(final_state.review_reports) == 2
    assert final_state.review_reports[0].status == ReviewStatus.NEEDS_CHANGES
    assert final_state.review_reports[1].status == ReviewStatus.APPROVED


# ==================================================================
# 2. FastAPI API Endpoint Tests
# ==================================================================

import httpx

def test_fastapi_endpoints_create_and_query(test_repo_and_workspace):
    """Tests the REST endpoints for task creation, query, and merge gate approval."""
    source_dir, _ = test_repo_and_workspace

    app = create_app()

    async def _run_api_tests():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Create task
            req_payload = {
                "user_prompt": "Add health endpoint in service.py",
                "repo_url_or_path": str(source_dir),
                "max_iterations": 2,
            }
            create_res = await client.post("/api/tasks", json=req_payload)
            assert create_res.status_code == 202
            data = create_res.json()
            task_id = data["task_id"]
            assert task_id.startswith("task_")

            # 2. List tasks
            list_res = await client.get("/api/tasks")
            assert list_res.status_code == 200
            task_list = list_res.json()
            assert any(t["task_id"] == task_id for t in task_list)

            # 3. Get single task state
            get_res = await client.get(f"/api/tasks/{task_id}")
            assert get_res.status_code == 200
            task_state = get_res.json()
            assert task_state["task_id"] == task_id
            assert "status" in task_state
            assert "diff" in task_state

            # 4. Get audit trail
            audit_res = await client.get(f"/api/tasks/{task_id}/audit")
            assert audit_res.status_code == 200
            assert isinstance(audit_res.json(), list)

            # 5. Approve merge gate
            approve_res = await client.post(f"/api/tasks/{task_id}/approve")
            if approve_res.status_code == 200:
                approve_data = approve_res.json()
                assert approve_data["status"] == "completed"
                assert "pull_request_url" in approve_data
            else:
                assert approve_res.status_code == 400

            # 6. Direct test of 404 on nonexistent task
            bad_res = await client.get("/api/tasks/nonexistent_123")
            assert bad_res.status_code == 404

    asyncio.run(_run_api_tests())
