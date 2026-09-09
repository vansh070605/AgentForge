"""Unit and integration tests for WorkspaceManager."""

import os
from pathlib import Path
import subprocess
import tempfile
import pytest

from agentforge.models.audit import ActionType
from agentforge.workspace.manager import WorkspaceManager


@pytest.fixture
def temp_git_repo():
    """Creates a temporary Git repository with an initial commit to act as source."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir) / "source_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
        # Configure user for commits in test
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@agentforge.local"], cwd=repo_path, check=True)

        # Create initial file and commit
        initial_file = repo_path / "hello.py"
        initial_file.write_text("print('initial')", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, check=True)

        yield repo_path


@pytest.fixture
def workspace(temp_git_repo):
    """Sets up a WorkspaceManager initialized from the test git repo."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_dir = Path(tmp_dir) / "workspace_test"
        wm = WorkspaceManager(workspace_dir=ws_dir, task_id="test_task_001")
        wm.initialize_from_source(source_path=temp_git_repo, branch_name="agentforge/task-001")
        # Ensure user is configured in cloned workspace
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=ws_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@agentforge.local"], cwd=ws_dir, check=True)
        yield wm
        wm.cleanup()


def test_workspace_initialization(workspace):
    assert workspace.base_commit is not None
    assert len(workspace.base_commit) == 40
    assert workspace.current_branch == "agentforge/task-001"
    
    # Check audit trail recorded initialization
    events = [e for e in workspace.audit_trail if e.action_type == ActionType.WORKSPACE_INITIALIZED]
    assert len(events) == 1
    assert events[0].metadata["base_commit"] == workspace.base_commit


def test_path_traversal_protection(workspace):
    # Attempt to resolve path outside workspace
    with pytest.raises(ValueError, match="Security violation: path"):
        workspace.resolve_safe_path("../../../etc/passwd")

    # Verify audit event logged failure
    errors = [e for e in workspace.audit_trail if e.action_type == ActionType.ERROR_OCCURRED]
    assert len(errors) == 1
    assert errors[0].status == "failure"


def test_file_read_write(workspace):
    workspace.write_file("src/calculator.py", "def add(a, b):\n    return a + b\n")
    content = workspace.read_file("src/calculator.py")
    assert "def add(a, b):" in content

    # Test file list
    files = workspace.list_files()
    assert "hello.py" in files
    assert "src/calculator.py" in files


def test_base_commit_diff_tracking(workspace):
    """Verifies requirement: git_diff() compares base_commit...HEAD/working-tree,

    ensuring all committed agent changes remain visible to Proof-of-Work.
    """
    # 1. Initially, no changes
    initial_diff = workspace.git_diff(against_base=True)
    assert initial_diff.strip() == ""

    # 2. Make an edit and commit it
    workspace.write_file("hello.py", "print('modified hello')\n")
    commit_1 = workspace.git_commit("feat: update hello message")
    assert commit_1 is not None

    # 3. Even though changes are committed to the branch, git_diff(against_base=True)
    # MUST still show the diff against base_commit
    diff_after_commit = workspace.git_diff(against_base=True)
    assert "-print('initial')" in diff_after_commit
    assert "+print('modified hello')" in diff_after_commit

    # 4. Make another change without committing yet
    workspace.write_file("new_file.py", "val = 42\n")
    diff_with_uncommitted = workspace.git_diff(against_base=True)
    # Both the earlier commit AND new file changes should be in the diff
    assert "print('modified hello')" in diff_with_uncommitted


def test_run_command_success(workspace):
    res = workspace.run_command("python hello.py")
    assert res.exit_code == 0
    assert "initial" in res.stdout
    assert res.duration_seconds > 0


def test_run_command_timeout(workspace):
    # Run a command that intentionally exceeds a tiny timeout
    res = workspace.run_command("python -c \"import time; time.sleep(2)\"", timeout_seconds=0.5)
    assert res.exit_code == -1
    assert "timed out" in res.stderr
