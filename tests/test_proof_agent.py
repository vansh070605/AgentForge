"""Unit and security tests for deterministic ProofOfWorkAgent."""

import ast
import asyncio
import inspect
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.agents.base import AgentMetadata
from agentforge.agents.proof import ProofOfWorkAgent, DEFAULT_PROOF_TOOLS
import agentforge.agents.proof as proof_module
from agentforge.models import (
    AcceptanceCriterion,
    ActionType,
    CommandExecutionResult,
    CriterionStatus,
    ExecutionResult,
    OrchestratorState,
    TaskSpecification,
    TaskStatus,
    VerificationReport,
    VerificationStatus,
)
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def proof_workspace():
    """Sets up a test git workspace with an initial Python file and test file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Proof"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "proof@agentforge.local"], cwd=source_dir, check=True)

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
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_proof_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/proof-test")

        subprocess.run(["git", "config", "user.name", "Agent Proof"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "proof@agentforge.local"], cwd=ws_dir, check=True)

        yield wm
        wm.cleanup()


@pytest.fixture
def proof_state():
    """Creates a basic OrchestratorState with a TaskSpecification and successful ExecutionResult."""
    return OrchestratorState(
        task_id="task_proof_test",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add health check function and tests",
        status=TaskStatus.VERIFYING,
        task_spec=TaskSpecification(
            task_id="task_proof_test",
            title="Add health check function",
            description="Add health() function returning status ok",
            target_files=["service.py", "tests/test_service.py"],
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-1",
                    description="service.py defines health function returning status",
                    verification_method="unit_test",
                )
            ],
            suggested_test_command="pytest tests/test_service.py",
        ),
        execution_results=[
            ExecutionResult(
                task_id="task_proof_test",
                iteration=1,
                success=True,
                summary_of_changes="Added health() function to service.py and corresponding test",
                modified_files=["service.py", "tests/test_service.py"],
                commits_created=["commit_xyz789"],
            )
        ],
    )


# ==================================================================
# 1. Security Architecture Verification (No Subprocess/Direct IO)
# ==================================================================

def test_proof_agent_has_no_direct_os_subprocess_imports():
    """Verifies that ProofOfWorkAgent does not import or invoke os, subprocess,
    shutil, or open directly. All interactions MUST route through ToolRegistry.
    """
    source_code = inspect.getsource(proof_module)
    tree = ast.parse(source_code)

    forbidden_modules = {"subprocess", "shutil", "os"}
    forbidden_calls = {"open", "system", "popen", "spawn"}

    for node in ast.walk(tree):
        # Check forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    alias.name not in forbidden_modules
                ), f"Forbidden import '{alias.name}' detected in proof agent!"
        elif isinstance(node, ast.ImportFrom):
            assert (
                node.module not in forbidden_modules
            ), f"Forbidden import from '{node.module}' detected in proof agent!"

        # Check forbidden direct calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert (
                    node.func.id not in forbidden_calls
                ), f"Forbidden direct call '{node.func.id}()' in proof agent!"


def test_proof_agent_least_privilege_boundary():
    """Verifies that ProofOfWorkAgent defaults to read-only inspection plus run_tests."""
    agent = ProofOfWorkAgent()
    assert agent.role == "proof"
    assert "write_file" not in agent.metadata.allowed_tools
    assert "git_commit" not in agent.metadata.allowed_tools
    assert "run_command" not in agent.metadata.allowed_tools
    assert agent.is_tool_allowed("read_file")
    assert agent.is_tool_allowed("git_diff")
    assert agent.is_tool_allowed("run_tests")


# ==================================================================
# 2. Objective Verification - Passing Evidence
# ==================================================================

def test_proof_agent_verifies_valid_implementation(proof_workspace, proof_state):
    """Verifies that a genuine implementation with passing tests and AST proof is VERIFIED."""
    # Add genuine implementation
    proof_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'ok'}\n",
    )
    proof_workspace.write_file(
        "tests/test_service.py",
        "from service import ping, health\n\ndef test_ping():\n    assert ping() == 'pong'\n\ndef test_health():\n    assert health()['status'] == 'ok'\n",
    )
    proof_workspace.git_commit("feat: implement health check")

    agent = ProofOfWorkAgent()
    report = asyncio.run(agent.run(state=proof_state, workspace=proof_workspace, execute_tests=True))

    assert isinstance(report, VerificationReport)
    assert report.status == VerificationStatus.VERIFIED
    assert report.confidence_score >= 0.8
    assert report.tests_passed >= 2
    assert report.tests_failed == 0
    assert report.unrelated_changes_detected is False
    assert len(report.requirements) == 1
    assert report.requirements[0].status == CriterionStatus.SATISFIED
    assert any("AST node verified" in e for e in report.requirements[0].evidence_items)
    assert any("Automated test verification passed" in e for e in report.requirements[0].evidence_items)
    assert proof_state.verification_report is report


# ==================================================================
# 3. Objective Verification - Failing Test Rejection
# ==================================================================

def test_proof_agent_rejects_failing_tests(proof_workspace, proof_state):
    """Verifies that if tests fail, the ProofOfWork agent rejects the work."""
    # Write implementation that fails test
    proof_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'broken'}\n",
    )
    proof_workspace.write_file(
        "tests/test_service.py",
        "from service import health\n\ndef test_health():\n    assert health()['status'] == 'ok'\n",
    )
    proof_workspace.git_commit("feat: broken implementation")

    agent = ProofOfWorkAgent()
    report = asyncio.run(agent.run(state=proof_state, workspace=proof_workspace, execute_tests=True))

    assert report.status == VerificationStatus.REJECTED
    assert report.tests_failed >= 1
    assert report.confidence_score <= 0.5
    assert report.requirements[0].status == CriterionStatus.UNMET


# ==================================================================
# 4. Scope & Unrelated Files Detection
# ==================================================================

def test_proof_agent_detects_unrelated_file_modifications(proof_workspace, proof_state):
    """Verifies that touching files outside target_files is detected and penalized."""
    # Genuine implementation + unrelated file
    proof_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'ok'}\n",
    )
    proof_workspace.write_file("unrelated_backdoor.py", "# backdoor code\n")
    proof_workspace.git_commit("feat: add health and extra file")

    agent = ProofOfWorkAgent()
    report = asyncio.run(agent.run(state=proof_state, workspace=proof_workspace, execute_tests=True))

    assert report.unrelated_changes_detected is True
    assert "unrelated_backdoor.py" in report.unrelated_files
    # Confidence must reflect penalty
    assert report.confidence_score < 1.0


# ==================================================================
# 5. Missing AST Symbol Evidence
# ==================================================================

def test_proof_agent_unmet_when_symbol_missing(proof_workspace, proof_state):
    """Verifies that if requested function does not exist in AST, criterion is not satisfied."""
    # Implementation touched service.py, but didn't implement health()
    proof_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef unrelated_foo():\n    return True\n",
    )
    proof_workspace.git_commit("feat: implemented wrong function")

    agent = ProofOfWorkAgent()
    # Skip running tests, rely on diff and AST
    report = asyncio.run(agent.run(state=proof_state, workspace=proof_workspace, execute_tests=False))

    assert report.requirements[0].status == CriterionStatus.UNMET
    assert report.status == VerificationStatus.REJECTED


# ==================================================================
# 6. Audit Trail Verification
# ==================================================================

def test_proof_agent_records_audit_trail(proof_workspace, proof_state):
    """Verifies that ProofOfWorkAgent records structured audit events in workspace."""
    proof_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'ok'}\n",
    )
    proof_workspace.git_commit("feat: implement health")

    agent = ProofOfWorkAgent()
    asyncio.run(agent.run(state=proof_state, workspace=proof_workspace, execute_tests=True))

    events = proof_workspace.audit_trail
    action_types = [e.action_type for e in events]

    assert ActionType.AGENT_STARTED in action_types
    assert ActionType.PROOF_EVALUATED in action_types
    assert ActionType.AGENT_COMPLETED in action_types

    proof_event = next(e for e in events if e.action_type == ActionType.PROOF_EVALUATED)
    assert proof_event.actor.startswith("proof:")
    assert "verification_status" in proof_event.metadata
    assert "confidence_score" in proof_event.metadata
