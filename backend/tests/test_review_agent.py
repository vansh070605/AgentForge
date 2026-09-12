"""Unit and security tests for deterministic ReviewAgent."""

import ast
import asyncio
import inspect
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.agents.base import AgentMetadata
from agentforge.agents.review import ReviewAgent, DEFAULT_REVIEW_TOOLS
import agentforge.agents.review as review_module
from agentforge.models import (
    AcceptanceCriterion,
    ActionType,
    CommandExecutionResult,
    ExecutionResult,
    OrchestratorState,
    ReviewIssue,
    ReviewReport,
    ReviewStatus,
    SeverityLevel,
    TaskSpecification,
    TaskStatus,
)
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def review_workspace():
    """Sets up a test git workspace with an initial Python file and test file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Reviewer"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "review@agentforge.local"], cwd=source_dir, check=True)

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
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_review_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/review-test")

        subprocess.run(["git", "config", "user.name", "Agent Reviewer"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "review@agentforge.local"], cwd=ws_dir, check=True)

        yield wm
        wm.cleanup()


@pytest.fixture
def review_state():
    """Creates a basic OrchestratorState with a TaskSpecification and successful ExecutionResult."""
    return OrchestratorState(
        task_id="task_review_test",
        repo_url_or_path="https://github.com/example/repo",
        user_prompt="Add health check endpoint and tests",
        status=TaskStatus.REVIEWING,
        task_spec=TaskSpecification(
            task_id="task_review_test",
            title="Add health check endpoint",
            description="Add health() function returning status ok",
            target_files=["service.py", "tests/test_service.py"],
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-1",
                    description="service.py exports health() function",
                    verification_method="unit_test",
                )
            ],
            suggested_test_command="pytest tests/test_service.py",
        ),
        execution_results=[
            ExecutionResult(
                task_id="task_review_test",
                iteration=1,
                success=True,
                summary_of_changes="Added health() function to service.py and corresponding test",
                modified_files=["service.py", "tests/test_service.py"],
                commits_created=["commit_abc123"],
                test_results=CommandExecutionResult(
                    command="pytest tests/test_service.py",
                    exit_code=0,
                    stdout="2 passed in 0.05s",
                    stderr="",
                    duration_seconds=0.05,
                ),
            )
        ],
    )


# ==================================================================
# 1. Security Architecture Verification (No Subprocess/Direct IO)
# ==================================================================

def test_review_agent_has_no_direct_os_subprocess_imports():
    """Verifies that ReviewAgent does not import or invoke os, subprocess,
    shutil, or open directly. All interactions MUST route through ToolRegistry.
    """
    source_code = inspect.getsource(review_module)
    tree = ast.parse(source_code)

    forbidden_modules = {"subprocess", "shutil", "os"}
    forbidden_calls = {"open", "system", "popen", "spawn"}

    for node in ast.walk(tree):
        # Check forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    alias.name not in forbidden_modules
                ), f"Forbidden import '{alias.name}' detected in review agent!"
        elif isinstance(node, ast.ImportFrom):
            assert (
                node.module not in forbidden_modules
            ), f"Forbidden import from '{node.module}' detected in review agent!"

        # Check forbidden direct calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert (
                    node.func.id not in forbidden_calls
                ), f"Forbidden direct call '{node.func.id}()' in review agent!"


def test_review_agent_least_privilege_boundary():
    """Verifies that ReviewAgent defaults to strictly read-only tools."""
    agent = ReviewAgent()
    assert agent.role == "review"
    assert "write_file" not in agent.metadata.allowed_tools
    assert "git_commit" not in agent.metadata.allowed_tools
    assert "run_command" not in agent.metadata.allowed_tools
    assert agent.is_tool_allowed("read_file")
    assert agent.is_tool_allowed("git_diff")
    assert agent.is_tool_allowed("search_code")


# ==================================================================
# 2. Clean Code Approval
# ==================================================================

def test_review_agent_approves_clean_implementation(review_workspace, review_state):
    """Verifies that a valid code modification with passing tests receives approval."""
    # Apply clean changes
    review_workspace.write_file(
        "service.py",
        "def ping():\n    return 'pong'\n\ndef health():\n    return {'status': 'healthy'}\n",
    )
    review_workspace.git_commit("feat: add health endpoint")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert isinstance(report, ReviewReport)
    assert report.status == ReviewStatus.APPROVED
    assert len(report.issues) == 0
    assert "Review passed" in report.summary
    assert len(review_state.review_reports) == 1


# ==================================================================
# 3. Python Syntax Error Detection
# ==================================================================

def test_review_agent_flags_python_syntax_error(review_workspace, review_state):
    """Verifies that unparseable Python code triggers a CRITICAL issue and rejection."""
    # Write invalid Python syntax
    review_workspace.write_file("service.py", "def health(:\n    return broken\n")
    review_workspace.git_commit("fix: attempt broken change")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    syntax_issues = [i for i in report.issues if i.severity == SeverityLevel.CRITICAL]
    assert len(syntax_issues) >= 1
    assert "syntax error" in syntax_issues[0].problem.lower()
    assert syntax_issues[0].file == "service.py"


# ==================================================================
# 4. Security & Secret Leak Detection
# ==================================================================

def test_review_agent_detects_hardcoded_aws_and_github_secrets(review_workspace, review_state):
    """Verifies that hardcoded secrets are caught and flagged with CRITICAL severity."""
    leaked_code = (
        "AWS_KEY = 'AKIA1234567890ABCDEF'\n"
        "GH_TOKEN = 'ghp_123456789012345678901234567890123456'\n"
        "def health():\n    return 'ok'\n"
    )
    review_workspace.write_file("service.py", leaked_code)
    review_workspace.git_commit("feat: add credentials")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    critical_issues = [i for i in report.issues if i.severity == SeverityLevel.CRITICAL]
    assert len(critical_issues) >= 2
    descriptions = [i.problem for i in critical_issues]
    assert any("AWS Access Key" in d for d in descriptions)
    assert any("GitHub token" in d for d in descriptions)


def test_review_agent_detects_dangerous_eval_calls(review_workspace, review_state):
    """Verifies that eval() calls are flagged with HIGH severity."""
    insecure_code = (
        "def compute(user_input):\n"
        "    return eval(user_input)\n"
    )
    review_workspace.write_file("service.py", insecure_code)
    review_workspace.git_commit("feat: add dynamic compute")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    eval_issues = [i for i in report.issues if "eval()" in i.problem]
    assert len(eval_issues) == 1
    assert eval_issues[0].severity == SeverityLevel.HIGH


def test_review_agent_detects_debug_breakpoints(review_workspace, review_state):
    """Verifies that leftover breakpoints are flagged."""
    debug_code = (
        "def health():\n"
        "    breakpoint()\n"
        "    return 'ok'\n"
    )
    review_workspace.write_file("service.py", debug_code)
    review_workspace.git_commit("debug: add breakpoint")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    bp_issues = [i for i in report.issues if "breakpoint" in i.problem]
    assert len(bp_issues) == 1
    assert bp_issues[0].severity == SeverityLevel.MEDIUM


# ==================================================================
# 5. Execution & Test Failure Handling
# ==================================================================

def test_review_agent_rejects_when_execution_tests_failed(review_workspace, review_state):
    """Verifies that failing test results in ExecutionResult block review approval."""
    review_state.execution_results[-1].test_results = CommandExecutionResult(
        command="pytest tests/test_service.py",
        exit_code=1,
        stdout="",
        stderr="FAILED tests/test_service.py::test_ping - AssertionError",
        duration_seconds=0.1,
    )

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    test_issues = [i for i in report.issues if i.file == "tests"]
    assert len(test_issues) >= 1
    assert test_issues[0].severity == SeverityLevel.HIGH
    assert "exit code 1" in test_issues[0].problem


def test_review_agent_rejects_when_execution_failed(review_workspace, review_state):
    """Verifies that an execution failure status blocks review approval."""
    review_state.execution_results[-1].success = False
    review_state.execution_results[-1].error_message = "Tool timeout during write_file"

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    exec_issues = [i for i in report.issues if i.file == "execution"]
    assert len(exec_issues) == 1
    assert "Tool timeout" in exec_issues[0].problem


# ==================================================================
# 6. Target Files Boundary Enforcement
# ==================================================================

def test_review_agent_flags_unauthorized_out_of_scope_files(review_workspace, review_state):
    """Verifies that modifying files outside target_files creates an issue."""
    # Write to a file not in target_files: ["service.py", "tests/test_service.py"]
    review_workspace.write_file("unauthorized_script.py", "print('unauthorized')\n")
    review_workspace.git_commit("chore: add unauthorized file")

    agent = ReviewAgent()
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    scope_issues = [i for i in report.issues if i.file == "unauthorized_script.py"]
    assert len(scope_issues) >= 1
    assert scope_issues[0].severity == SeverityLevel.MEDIUM
    assert "not listed in target_files" in scope_issues[0].problem


# ==================================================================
# 7. Custom Inspector Hook
# ==================================================================

def test_review_agent_custom_inspector_hook(review_workspace, review_state):
    """Verifies that an injected custom inspector hook is executed."""
    def custom_rule(state, diff_text):
        return [
            ReviewIssue(
                file="service.py",
                severity=SeverityLevel.HIGH,
                problem="Custom rule: missing type annotations",
                recommendation="Add type annotations to all public functions.",
            )
        ]

    agent = ReviewAgent(custom_inspector=custom_rule)
    report = asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    assert report.status == ReviewStatus.NEEDS_CHANGES
    custom_issues = [i for i in report.issues if "type annotations" in i.problem]
    assert len(custom_issues) == 1


# ==================================================================
# 8. Audit Trail Verification
# ==================================================================

def test_review_agent_records_audit_trail(review_workspace, review_state):
    """Verifies that ReviewAgent emits structured audit events into the workspace log."""
    agent = ReviewAgent()
    asyncio.run(agent.run(state=review_state, workspace=review_workspace))

    events = review_workspace.audit_trail
    action_types = [e.action_type for e in events]

    assert ActionType.AGENT_STARTED in action_types
    assert ActionType.REVIEW_SUBMITTED in action_types
    assert ActionType.AGENT_COMPLETED in action_types

    review_event = next(e for e in events if e.action_type == ActionType.REVIEW_SUBMITTED)
    assert review_event.actor.startswith("review:")
    assert "review_status" in review_event.metadata
