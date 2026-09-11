"""Unit and security tests for deterministic IdentityAgent."""

import ast
import asyncio
import inspect
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.agents.base import AgentMetadata
from agentforge.agents.identity import IdentityAgent, DEFAULT_IDENTITY_TOOLS
import agentforge.agents.identity as identity_module
from agentforge.models import (
    AcceptanceCriterion,
    ActionType,
    OrchestratorState,
    TaskSpecification,
    TaskStatus,
)
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def identity_workspace():
    """Sets up a test git workspace with an initial Python file and test file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Identity"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "identity@agentforge.local"], cwd=source_dir, check=True)

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
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_identity_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/identity-test")

        subprocess.run(["git", "config", "user.name", "Agent Identity"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "identity@agentforge.local"], cwd=ws_dir, check=True)

        yield wm
        wm.cleanup()


@pytest.fixture
def identity_state():
    """Creates a basic OrchestratorState with a user prompt."""
    return OrchestratorState(
        task_id="task_identity_test",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add health() endpoint in service.py and tests in tests/test_service.py",
        status=TaskStatus.PENDING,
    )


# ==================================================================
# 1. Security Architecture Verification (No Subprocess/Direct IO)
# ==================================================================

def test_identity_agent_has_no_direct_os_subprocess_imports():
    """Verifies that IdentityAgent does not import or invoke os, subprocess,
    shutil, or open directly. All interactions MUST route through ToolRegistry.
    """
    source_code = inspect.getsource(identity_module)
    tree = ast.parse(source_code)

    forbidden_modules = {"subprocess", "shutil", "os"}
    forbidden_calls = {"open", "system", "popen", "spawn"}

    for node in ast.walk(tree):
        # Check forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    alias.name not in forbidden_modules
                ), f"Forbidden import '{alias.name}' detected in identity agent!"
        elif isinstance(node, ast.ImportFrom):
            assert (
                node.module not in forbidden_modules
            ), f"Forbidden import from '{node.module}' detected in identity agent!"

        # Check forbidden direct calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert (
                    node.func.id not in forbidden_calls
                ), f"Forbidden direct call '{node.func.id}()' in identity agent!"


def test_identity_agent_least_privilege_boundary():
    """Verifies that IdentityAgent is restricted strictly to read-only exploration."""
    agent = IdentityAgent()
    assert agent.role == "identity"
    assert "write_file" not in agent.metadata.allowed_tools
    assert "git_commit" not in agent.metadata.allowed_tools
    assert "run_command" not in agent.metadata.allowed_tools
    assert "run_tests" not in agent.metadata.allowed_tools
    assert agent.is_tool_allowed("read_file")
    assert agent.is_tool_allowed("list_files")
    assert agent.is_tool_allowed("search_code")


# ==================================================================
# 2. Specification Synthesis Tests
# ==================================================================

def test_identity_agent_synthesizes_specification(identity_workspace, identity_state):
    """Verifies that IdentityAgent parses user requirements into a structured TaskSpecification."""
    agent = IdentityAgent()
    spec = asyncio.run(agent.run(state=identity_state, workspace=identity_workspace))

    assert isinstance(spec, TaskSpecification)
    assert spec.task_id == identity_state.task_id
    assert "health()" in spec.title or "health" in spec.title
    assert "service.py" in spec.target_files
    assert "tests/test_service.py" in spec.target_files

    # Criteria verification
    criteria_ids = [c.id for c in spec.acceptance_criteria]
    assert "AC-1" in criteria_ids
    assert any("health" in c.description for c in spec.acceptance_criteria)
    assert any("test" in c.description for c in spec.acceptance_criteria)

    # Command & constraints
    assert "pytest" in spec.suggested_test_command
    assert len(spec.constraints) >= 2
    assert identity_state.task_spec is spec
    assert identity_state.status == TaskStatus.SPECIFYING


def test_identity_agent_infers_files_when_not_explicit(identity_workspace):
    """Verifies that IdentityAgent infers files from codebase layout when prompt lacks filenames."""
    state = OrchestratorState(
        task_id="task_infer_test",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add function health() returning status code ok",
        status=TaskStatus.PENDING,
    )

    agent = IdentityAgent()
    spec = asyncio.run(agent.run(state=state, workspace=identity_workspace))

    assert len(spec.target_files) >= 1
    # Picked service.py or created a test pair
    assert any(f.endswith(".py") for f in spec.target_files)
    assert any("health" in c.description for c in spec.acceptance_criteria)


# ==================================================================
# 3. Custom Generator Hook
# ==================================================================

def test_identity_agent_custom_generator_hook(identity_workspace, identity_state):
    """Verifies that an injected custom generator callback is executed."""
    def custom_gen(state, ws):
        return TaskSpecification(
            task_id=state.task_id,
            title="Custom Specification",
            description="Custom Generated Spec",
            target_files=["service.py"],
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-CUSTOM-1",
                    description="Custom acceptance criterion",
                    verification_method="code_inspection",
                )
            ],
            suggested_test_command="pytest",
        )

    agent = IdentityAgent(custom_generator=custom_gen)
    spec = asyncio.run(agent.run(state=identity_state, workspace=identity_workspace))

    assert spec.title == "Custom Specification"
    assert len(spec.acceptance_criteria) == 1
    assert spec.acceptance_criteria[0].id == "AC-CUSTOM-1"
    assert identity_state.task_spec is spec


# ==================================================================
# 4. Audit Trail Verification
# ==================================================================

def test_identity_agent_records_audit_trail(identity_workspace, identity_state):
    """Verifies that IdentityAgent emits structured audit events into the workspace log."""
    agent = IdentityAgent()
    asyncio.run(agent.run(state=identity_state, workspace=identity_workspace))

    events = identity_workspace.audit_trail
    action_types = [e.action_type for e in events]

    assert ActionType.AGENT_STARTED in action_types
    assert ActionType.AGENT_COMPLETED in action_types

    agent_events = [e for e in events if e.actor == "identity:IdentityAgent"]
    assert len(agent_events) >= 2
    completed_event = next(e for e in agent_events if e.action_type == ActionType.AGENT_COMPLETED)
    assert "criteria_count" in completed_event.metadata
