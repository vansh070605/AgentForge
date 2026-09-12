"""Unit and security tests for deterministic ExecutionAgent."""

import ast
import asyncio
import inspect
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.agents.base import AgentMetadata
from agentforge.agents.execution import ExecutionAgent
import agentforge.agents.execution as execution_module
from agentforge.models import (
    ActionType,
    ExecutionAction,
    ExecutionResult,
    OrchestratorState,
    TaskSpecification,
    TaskStatus,
)
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def agent_workspace():
    """Sets up a test git workspace with an initial Python file and test file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Tester"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "agent@agentforge.local"], cwd=source_dir, check=True)

        # Initial source files
        (source_dir / "service.py").write_text("def ping():\n    return 'pong'\n", encoding="utf-8")
        test_dir = source_dir / "tests"
        test_dir.mkdir()
        (test_dir / "test_service.py").write_text("from service import ping\n\ndef test_ping():\n    assert ping() == 'pong'\n", encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=source_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=source_dir, check=True)

        # Working workspace
        ws_dir = Path(tmp_dir) / "ws"
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_exec_agent_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/exec-agent-test")

        subprocess.run(["git", "config", "user.name", "Agent Tester"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "agent@agentforge.local"], cwd=ws_dir, check=True)

        yield wm
        wm.cleanup()


@pytest.fixture
def base_state():
    """Creates a basic OrchestratorState with a TaskSpecification."""
    return OrchestratorState(
        task_id="task_exec_agent_test",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add health check endpoint and tests",
        status=TaskStatus.EXECUTING,
        task_spec=TaskSpecification(
            task_id="task_exec_agent_test",
            title="Add health check endpoint",
            description="Add health() function returning status ok",
            target_files=["service.py", "tests/test_service.py"],
            suggested_test_command="pytest tests/test_service.py",
        ),
    )


# ==================================================================
# 1. Security Architecture Verification (No Subprocess/Direct IO)
# ==================================================================

def test_execution_agent_has_no_direct_os_subprocess_imports():
    """Verifies that ExecutionAgent does not import or invoke os, subprocess,

    shutil, or open directly. All interactions MUST route through ToolRegistry.
    """
    source_code = inspect.getsource(execution_module)
    tree = ast.parse(source_code)

    forbidden_modules = {"subprocess", "shutil", "os"}
    forbidden_calls = {"open", "system", "popen", "spawn"}

    for node in ast.walk(tree):
        # Check forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules, f"Forbidden import '{alias.name}' detected in execution agent!"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules, f"Forbidden import from '{node.module}' detected in execution agent!"

        # Check forbidden direct calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, f"Forbidden direct call '{node.func.id}()' in execution agent!"


# ==================================================================
# 2. Deterministic Operations (Read, Write, List, Search)
# ==================================================================

def test_agent_deterministic_read_operation(agent_workspace, base_state):
    agent = ExecutionAgent()
    plan = [
        ExecutionAction(
            tool_name="read_file",
            arguments={"file_path": "service.py"},
            description="Read initial service file",
        )
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is True
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].tool_name == "read_file"
    assert res.tool_calls[0].status == "success"
    assert "Read" in res.tool_calls[0].output_summary
    assert len(base_state.execution_results) == 1


def test_agent_deterministic_write_operation(agent_workspace, base_state):
    agent = ExecutionAgent()
    new_content = "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'healthy'}\n"
    plan = [
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "service.py", "content": new_content},
            description="Update service.py with health function",
        )
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is True
    assert "service.py" in res.modified_files
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].status == "success"

    # Verify content was written via tool
    file_content = agent_workspace.read_file("service.py")
    assert "def health():" in file_content


# ==================================================================
# 3. Permission Enforcement & Least Privilege
# ==================================================================

def test_agent_unauthorized_tool_rejected(agent_workspace, base_state):
    # Agent restricted to only read_file
    restricted_agent = ExecutionAgent(
        metadata=AgentMetadata(
            name="ReadOnlyExecutionAgent",
            role="execution",
            description="Only allowed to read",
            allowed_tools=["read_file"],
        )
    )

    plan = [
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "service.py", "content": "bad"},
            critical=True,
        )
    ]

    res = asyncio.run(restricted_agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    # Must fail
    assert res.success is False
    assert "unauthorized to execute tool 'write_file'" in res.error_message
    assert res.tool_calls[0].status == "error"

    # File must NOT have changed
    original_content = agent_workspace.read_file("service.py")
    assert "def ping():" in original_content
    assert "bad" not in original_content


# ==================================================================
# 4. Failure Handling and Critical vs Non-Critical Steps
# ==================================================================

def test_agent_critical_failure_halts_execution(agent_workspace, base_state):
    agent = ExecutionAgent()
    plan = [
        ExecutionAction(
            tool_name="read_file",
            arguments={"file_path": "nonexistent_file.py"},
            critical=True,
        ),
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "should_never_run.py", "content": "test"},
            critical=True,
        ),
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is False
    assert "File not found" in res.error_message
    # Execution must halt immediately: second action should never run
    assert len(res.tool_calls) == 1
    assert "should_never_run.py" not in res.modified_files


def test_agent_test_failure_represented_as_execution_failure(agent_workspace, base_state):
    agent = ExecutionAgent()
    # Write failing test
    failing_test = "def test_fail():\n    assert False\n"
    plan = [
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "tests/test_fail.py", "content": failing_test},
        ),
        ExecutionAction(
            tool_name="run_tests",
            arguments={"command": "pytest tests/test_fail.py"},
            critical=True,
        ),
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is False
    assert "Tests failed with exit code" in res.error_message
    assert res.test_results is not None
    assert res.test_results.exit_code != 0
    assert "1 failed" in res.test_results.stdout


# ==================================================================
# 5. Deterministic Ordering & Multi-Tool End-to-End Execution
# ==================================================================

def test_agent_preserves_deterministic_order_and_audit(agent_workspace, base_state):
    """Executes a full pipeline of actions and verifies order and audit trail."""
    agent = ExecutionAgent()

    updated_service = (
        "def ping():\n    return 'pong'\n\n"
        "def health():\n    return 'healthy'\n"
    )
    updated_tests = (
        "from service import ping, health\n\n"
        "def test_ping():\n    assert ping() == 'pong'\n\n"
        "def test_health():\n    assert health() == 'healthy'\n"
    )

    plan = [
        ExecutionAction(tool_name="list_files", arguments={"directory": ""}),
        ExecutionAction(tool_name="read_file", arguments={"file_path": "service.py"}),
        ExecutionAction(tool_name="write_file", arguments={"file_path": "service.py", "content": updated_service}),
        ExecutionAction(tool_name="write_file", arguments={"file_path": "tests/test_service.py", "content": updated_tests}),
        ExecutionAction(tool_name="git_status", arguments={}),
        ExecutionAction(tool_name="run_tests", arguments={"command": "pytest tests/test_service.py"}),
        ExecutionAction(tool_name="git_diff", arguments={"against_base": True}),
        ExecutionAction(tool_name="git_commit", arguments={"message": "feat: add health endpoint and tests"}),
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is True
    assert len(res.tool_calls) == 8

    # Verify exact ordering preserved
    expected_order = [
        "list_files", "read_file", "write_file", "write_file",
        "git_status", "run_tests", "git_diff", "git_commit"
    ]
    actual_order = [call.tool_name for call in res.tool_calls]
    assert actual_order == expected_order

    # Verify commits and files
    assert "service.py" in res.modified_files
    assert "tests/test_service.py" in res.modified_files
    assert len(res.commits_created) == 1
    assert res.test_results.exit_code == 0

    # Verify audit trail contains AGENT_STARTED, TOOL_INVOKED, and AGENT_COMPLETED
    audit = agent_workspace.audit_trail
    action_types = [e.action_type for e in audit]
    assert ActionType.AGENT_STARTED in action_types
    assert ActionType.AGENT_COMPLETED in action_types
    assert action_types.count(ActionType.TOOL_INVOKED) >= 8


# ==================================================================
# 6. Sandbox Integration (LocalSubprocessRuntime injected)
# ==================================================================

def test_execution_agent_routes_run_tests_through_injected_sandbox(agent_workspace, base_state):
    """When a sandbox is injected into ExecutionAgent, the run_tests tool
    delegates command execution through the sandbox runtime."""
    from agentforge.sandbox.local_runtime import LocalSubprocessRuntime

    sandbox = LocalSubprocessRuntime()
    agent = ExecutionAgent(sandbox=sandbox)

    plan = [
        ExecutionAction(
            tool_name="run_tests",
            arguments={"command": "pytest tests/test_service.py"},
            critical=True,
        )
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is True
    assert res.test_results is not None
    assert res.test_results.exit_code == 0
    # LocalSubprocessRuntime sets sandbox_id='local'
    assert res.test_results.sandbox_id == "local"


def test_execution_agent_sandbox_id_present_in_test_results(agent_workspace, base_state):
    """sandbox_id is propagated through the tool chain into ExecutionResult.test_results."""
    from agentforge.sandbox.local_runtime import LocalSubprocessRuntime

    agent = ExecutionAgent(sandbox=LocalSubprocessRuntime())

    failing_test = "def test_fail():\n    assert False\n"
    plan = [
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "tests/test_sandbox_check.py", "content": failing_test},
        ),
        ExecutionAction(
            tool_name="run_tests",
            arguments={"command": "pytest tests/test_sandbox_check.py"},
            critical=False,
        ),
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    # Test ran (even if it failed), sandbox_id must be set
    assert res.test_results is not None
    assert res.test_results.sandbox_id == "local"
    assert res.test_results.network_blocked is False


def test_execution_agent_local_sandbox_driver_env_var_produces_identical_behaviour(
    agent_workspace, base_state, monkeypatch
):
    """ExecutionAgent with AGENTFORGE_SANDBOX_DRIVER=local produces results
    indistinguishable from the no-sandbox baseline for the same plan."""
    monkeypatch.setenv("AGENTFORGE_SANDBOX_DRIVER", "local")

    # Re-create agent so it picks up the env var via get_sandbox_runtime()
    agent = ExecutionAgent()

    new_content = "def ping():\n    return 'pong'\n\ndef health():\n    return 'ok'\n"
    plan = [
        ExecutionAction(
            tool_name="write_file",
            arguments={"file_path": "service.py", "content": new_content},
        ),
        ExecutionAction(
            tool_name="run_tests",
            arguments={"command": "pytest tests/test_service.py"},
            critical=True,
        ),
    ]

    res = asyncio.run(agent.run(state=base_state, workspace=agent_workspace, plan=plan))

    assert res.success is True
    assert "service.py" in res.modified_files
    assert res.test_results is not None
    assert res.test_results.exit_code == 0
    assert res.test_results.sandbox_id == "local"
