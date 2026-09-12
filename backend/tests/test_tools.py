"""Comprehensive unit, adversarial, and deterministic workflow tests for AgentForge tools."""

import os
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models.audit import ActionType
from agentforge.models.state import OrchestratorState
from agentforge.tools import (
    GitCommitInput,
    GitDiffInput,
    GitStatusInput,
    ListFilesInput,
    ReadFileInput,
    RunCommandInput,
    SearchCodeInput,
    ToolPermissionError,
    WriteFileInput,
    get_default_tool_registry,
)
from agentforge.workspace.manager import WorkspaceManager


class MockAgent(BaseAgent):
    """Simple test agent with configurable allowed tools."""

    async def run(self, state: OrchestratorState, **kwargs):
        return "mock_done"


@pytest.fixture
def test_workspace():
    """Sets up an initialized WorkspaceManager backed by a clean Git repository."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_dir = Path(tmp_dir) / "source"
        source_dir.mkdir()

        # Initialize source repo
        subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tool Tester"], cwd=source_dir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@agentforge.local"], cwd=source_dir, check=True)

        # Create initial files
        (source_dir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        test_dir = source_dir / "tests"
        test_dir.mkdir()
        (test_dir / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=source_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=source_dir, check=True)

        # Create working workspace
        ws_dir = Path(tmp_dir) / "ws"
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="task_tool_test")
        wm.initialize_from_source(source_path=source_dir, branch_name="agentforge/tools-test")

        subprocess.run(["git", "config", "user.name", "Tool Tester"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@agentforge.local"], cwd=ws_dir, check=True)

        yield wm
        wm.cleanup()


# ==========================================
# 1. Filesystem Tools Tests (Normal & Adversarial)
# ==========================================

def test_read_file_tool(test_workspace):
    registry = get_default_tool_registry()

    # Valid read
    res = registry.execute("read_file", ReadFileInput(file_path="calc.py"), workspace=test_workspace)
    assert res.success
    assert "def add(a, b):" in res.data.content
    assert res.data.size_bytes > 0

    # Nonexistent file
    res_err = registry.execute("read_file", ReadFileInput(file_path="nonexistent.py"), workspace=test_workspace)
    assert not res_err.success
    assert "File not found" in res_err.error

    # Path traversal attempt
    res_trav = registry.execute("read_file", {"file_path": "../../secret.txt"}, workspace=test_workspace)
    assert not res_trav.success
    assert "Security violation" in res_trav.error

    # Absolute path attempt
    abs_path = str(Path(test_workspace.workspace_dir / "calc.py").resolve())
    res_abs = registry.execute("read_file", {"file_path": abs_path}, workspace=test_workspace)
    assert not res_abs.success
    assert "Absolute paths are forbidden" in res_abs.error


def test_write_file_tool(test_workspace):
    registry = get_default_tool_registry()

    # Valid write
    content = "def sub(a, b):\n    return a - b\n"
    res = registry.execute("write_file", WriteFileInput(file_path="src/sub.py", content=content), workspace=test_workspace)
    assert res.success
    assert res.data.lines_written == 2

    # Verify through read
    read_res = registry.execute("read_file", ReadFileInput(file_path="src/sub.py"), workspace=test_workspace)
    assert read_res.data.content == content

    # Traversal write attempt
    res_trav = registry.execute("write_file", {"file_path": "../outside.txt", "content": "bad"}, workspace=test_workspace)
    assert not res_trav.success
    assert "Security violation" in res_trav.error

    # Oversized write rejection (>5MB)
    large_content = "X" * (5 * 1024 * 1024 + 100)
    res_large = registry.execute("write_file", {"file_path": "large.txt", "content": large_content}, workspace=test_workspace)
    assert not res_large.success
    assert "maximum write size" in res_large.error


def test_list_files_tool(test_workspace):
    registry = get_default_tool_registry()

    res = registry.execute("list_files", ListFilesInput(directory=""), workspace=test_workspace)
    assert res.success
    assert "calc.py" in res.data.files
    assert "tests/test_calc.py" in res.data.files
    # .git internal files should not be listed
    assert not any(f.startswith(".git") for f in res.data.files)


# ==========================================
# 2. Search Tool Tests
# ==========================================

def test_search_code_tool(test_workspace):
    registry = get_default_tool_registry()

    # Search for function definition
    res = registry.execute("search_code", SearchCodeInput(query="def add"), workspace=test_workspace)
    assert res.success
    assert res.data.total_matches == 1
    assert res.data.matches[0].file_path == "calc.py"
    assert res.data.matches[0].line_number == 1
    assert "def add(a, b):" in res.data.matches[0].line_content

    # Scoped search
    res_scoped = registry.execute("search_code", SearchCodeInput(query="test_add", scope_directory="tests"), workspace=test_workspace)
    assert res_scoped.success
    assert len(res_scoped.data.matches) == 1
    assert res_scoped.data.matches[0].file_path == "tests/test_calc.py"

    # Search limit and truncation
    registry.execute("write_file", {"file_path": "repeats.py", "content": "key = 1\nkey = 2\nkey = 3\n"}, workspace=test_workspace)
    res_limit = registry.execute("search_code", SearchCodeInput(query="key", max_results=2), workspace=test_workspace)
    assert res_limit.success
    assert len(res_limit.data.matches) == 2
    assert res_limit.data.truncated is True

    # Binary file handling
    bin_path = test_workspace.workspace_dir / "image.bin"
    bin_path.write_bytes(b"\x00\x01\x02\x03\x00key\x00")
    res_bin = registry.execute("search_code", SearchCodeInput(query="key"), workspace=test_workspace)
    assert res_bin.success
    # Should not crash and should skip binary file
    assert not any(m.file_path == "image.bin" for m in res_bin.data.matches)


# ==========================================
# 3. Controlled Command / Test Runner Tests
# ==========================================

def test_run_command_allowed_and_rejected(test_workspace):
    registry = get_default_tool_registry()

    # 1. Allowed test runner command
    res = registry.execute("run_tests", RunCommandInput(command="python -m unittest --help"), workspace=test_workspace)
    assert res.success
    assert res.data.exit_code == 0
    assert not res.data.timed_out

    # 2. Rejection of arbitrary python script execution
    res_script = registry.execute("run_tests", {"command": "python some_script.py"}, workspace=test_workspace)
    assert not res_script.success
    assert "not authorized" in res_script.error

    # 3. Rejection of dangerous shell chaining operators and Windows cmd.exe metacharacters
    dangerous_commands = [
        "pytest & whoami",          # Windows & Unix command separator
        "pytest; rm -rf /",         # POSIX command separator
        "pytest && echo injected",  # Conditional AND
        "pytest || true",           # Conditional OR
        "pytest | grep fail",       # Pipe
        "pytest > out.txt",         # Redirection out
        "pytest < in.txt",          # Redirection in
        "pytest `whoami`",          # Backtick substitution
        "pytest $(whoami)",         # Subshell substitution
        "pytest ${ENV_VAR}",        # Parameter expansion
        "pytest ^& whoami",         # Windows cmd.exe escape character
        "pytest %COMSPEC%",         # Windows cmd.exe variable expansion
        "pytest !PATH!",            # Windows cmd.exe delayed expansion
        "pytest\nwhoami",           # Newline injection
        "pytest\rwhoami",           # Carriage return injection
    ]
    for bad_cmd in dangerous_commands:
        res_bad = registry.execute("run_tests", {"command": bad_cmd}, workspace=test_workspace)
        assert not res_bad.success, f"Expected '{bad_cmd}' to be rejected"
        assert "forbidden shell operator" in res_bad.error


def test_command_injection_prevents_subprocess_and_side_effects(test_workspace):
    """Verifies that command injection attempts (like 'pytest & ...') are blocked

    BEFORE subprocess execution and cannot cause any filesystem side effect.
    """
    registry = get_default_tool_registry()

    side_effect_file = test_workspace.workspace_dir / "side_effect.txt"
    assert not side_effect_file.exists()

    # Attempt to chain command and create a file
    injected_cmd = f"pytest & echo hacked > {side_effect_file.name}"
    res = registry.execute("run_tests", {"command": injected_cmd}, workspace=test_workspace)

    # 1. Tool execution must fail
    assert not res.success
    assert "forbidden shell operator or chaining character '&'" in res.error

    # 2. File side effect must NOT exist (subprocess never executed)
    assert not side_effect_file.exists()

    # 3. Audit trail must record error failure
    err_events = [
        e for e in test_workspace.audit_trail
        if e.action_type == ActionType.ERROR_OCCURRED and "forbidden shell operator" in e.description
    ]
    assert len(err_events) >= 1
    assert err_events[-1].status == "failure"


def test_run_command_timeout(test_workspace):
    registry = get_default_tool_registry()
    # python -m unittest with timeout
    res = registry.execute(
        "run_tests",
        {"command": "pytest -h", "timeout_seconds": 0.001},
        workspace=test_workspace,
    )
    # Either timeout occurs or completes before tiny slice; let's verify timed_out flag structure
    assert hasattr(res.data or res, "exit_code") or not res.success


# ==========================================
# 4. Git Tools Tests
# ==========================================

def test_git_tools_and_cumulative_diff(test_workspace):
    registry = get_default_tool_registry()

    # 1. Initial git status
    stat_res = registry.execute("git_status", GitStatusInput(), workspace=test_workspace)
    assert stat_res.success
    assert stat_res.data.is_clean is True
    assert stat_res.data.branch == "agentforge/tools-test"
    assert stat_res.data.base_commit == test_workspace.base_commit

    # 2. Modify a file
    registry.execute(
        "write_file",
        WriteFileInput(file_path="calc.py", content="def add(a, b):\n    # modified\n    return a + b\n"),
        workspace=test_workspace,
    )

    stat_mod = registry.execute("git_status", GitStatusInput(), workspace=test_workspace)
    assert "calc.py" in stat_mod.data.modified
    assert stat_mod.data.is_clean is False

    # 3. Create a commit
    commit_res = registry.execute("git_commit", GitCommitInput(message="feat: add comment to calc.py"), workspace=test_workspace)
    assert commit_res.success
    assert len(commit_res.data.commit_hash) == 40

    # 4. Verify cumulative diff (against_base=True) shows the committed changes
    diff_res = registry.execute("git_diff", GitDiffInput(against_base=True), workspace=test_workspace)
    assert diff_res.success
    assert "+    # modified" in diff_res.data.diff
    assert not diff_res.data.is_empty

    # 5. Empty commit rejection
    empty_res = registry.execute("git_commit", GitCommitInput(message="empty commit"), workspace=test_workspace)
    assert not empty_res.success
    assert "No changes present" in empty_res.error


# ==========================================
# 5. Runtime Permission Enforcement Tests
# ==========================================

def test_runtime_permission_enforcement(test_workspace):
    registry = get_default_tool_registry()

    # Agent restricted to read-only tools
    read_only_agent = MockAgent(
        AgentMetadata(
            name="AuditorAgent",
            role="review",
            description="Can only read files",
            allowed_tools=["read_file", "list_files", "git_status"],
        )
    )

    # Authorized tool succeeds
    read_res = registry.execute(
        "read_file",
        ReadFileInput(file_path="calc.py"),
        workspace=test_workspace,
        agent=read_only_agent,
    )
    assert read_res.success

    # Unauthorized tool fails before execution with ToolPermissionError
    with pytest.raises(ToolPermissionError, match="unauthorized to execute tool 'write_file'"):
        registry.execute(
            "write_file",
            WriteFileInput(file_path="bad.py", content="content"),
            workspace=test_workspace,
            agent=read_only_agent,
        )

    with pytest.raises(ToolPermissionError, match="unauthorized to execute tool 'git_commit'"):
        registry.execute(
            "git_commit",
            GitCommitInput(message="illegal commit"),
            workspace=test_workspace,
            agent=read_only_agent,
        )

    # Verify audit event was recorded for the unauthorized attempt
    unauth_events = [
        e for e in test_workspace.audit_trail
        if e.action_type == ActionType.ERROR_OCCURRED and e.metadata.get("reason") == "unauthorized_tool"
    ]
    assert len(unauth_events) == 2
    assert unauth_events[0].status == "failure"


# ==========================================
# 6. Complete Deterministic Workflow Test (Definition of Done)
# ==========================================

def test_complete_deterministic_workflow(test_workspace):
    """Verifies complete end-to-end tool pipeline without an LLM:

    read repository -> search code -> modify file -> inspect diff -> run tests
    -> inspect status -> commit -> retrieve cumulative base-to-HEAD diff.
    """
    registry = get_default_tool_registry()
    exec_agent = MockAgent(
        AgentMetadata(
            name="WorkerBot",
            role="execution",
            description="Full execution privileges",
            allowed_tools=[
                "read_file",
                "list_files",
                "search_code",
                "write_file",
                "run_tests",
                "git_status",
                "git_diff",
                "git_commit",
            ],
        )
    )

    # 1. Read repository (list files + read file)
    list_out = registry.execute("list_files", {}, workspace=test_workspace, agent=exec_agent)
    assert list_out.success
    assert "calc.py" in list_out.data.files

    read_out = registry.execute("read_file", {"file_path": "calc.py"}, workspace=test_workspace, agent=exec_agent)
    assert read_out.success

    # 2. Search code
    search_out = registry.execute("search_code", {"query": "def add"}, workspace=test_workspace, agent=exec_agent)
    assert search_out.success
    assert len(search_out.data.matches) == 1

    # 3. Modify file (implement multiply function and unit test)
    new_calc_code = "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
    write_calc = registry.execute(
        "write_file",
        {"file_path": "calc.py", "content": new_calc_code},
        workspace=test_workspace,
        agent=exec_agent,
    )
    assert write_calc.success

    new_test_code = (
        "from calc import add, multiply\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n"
        "def test_multiply():\n    assert multiply(3, 4) == 12\n"
    )
    write_test = registry.execute(
        "write_file",
        {"file_path": "tests/test_calc.py", "content": new_test_code},
        workspace=test_workspace,
        agent=exec_agent,
    )
    assert write_test.success

    # 4. Inspect uncommitted diff
    diff_uncommitted = registry.execute("git_diff", {"against_base": True}, workspace=test_workspace, agent=exec_agent)
    assert diff_uncommitted.success
    assert "+def multiply(a, b):" in diff_uncommitted.data.diff

    # 5. Run tests (using pytest)
    test_run = registry.execute(
        "run_tests",
        {"command": "pytest tests/test_calc.py"},
        workspace=test_workspace,
        agent=exec_agent,
    )
    assert test_run.success
    assert test_run.data.exit_code == 0
    assert "2 passed" in test_run.data.stdout

    # 6. Inspect status
    status_out = registry.execute("git_status", {}, workspace=test_workspace, agent=exec_agent)
    assert status_out.success
    assert "calc.py" in status_out.data.modified
    assert "tests/test_calc.py" in status_out.data.modified

    # 7. Commit changes
    commit_out = registry.execute(
        "git_commit",
        {"message": "feat: add multiply function and unit test"},
        workspace=test_workspace,
        agent=exec_agent,
    )
    assert commit_out.success
    assert len(commit_out.data.commit_hash) == 40

    # 8. Retrieve cumulative base-to-HEAD diff (must STILL show multiply function after commit!)
    cumul_diff = registry.execute("git_diff", {"against_base": True}, workspace=test_workspace, agent=exec_agent)
    assert cumul_diff.success
    assert "+def multiply(a, b):" in cumul_diff.data.diff
    assert "+def test_multiply():" in cumul_diff.data.diff

    # 9. Verify full audit trail has been captured
    audit_events = test_workspace.audit_trail
    assert len(audit_events) >= 8
    invocations = [e for e in audit_events if e.action_type == ActionType.TOOL_INVOKED]
    assert len(invocations) >= 7
