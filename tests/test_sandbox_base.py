"""Unit tests for the sandbox package.

Tests SandboxRuntime contract enforcement, LocalSubprocessRuntime correctness,
factory driver resolution, and SandboxRuntimeError propagation.

No Docker daemon required — all tests use LocalSubprocessRuntime or mocks.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from agentforge.sandbox.base import (
    SandboxExecutionResult,
    SandboxRuntime,
    SandboxRuntimeError,
)
from agentforge.sandbox.factory import get_sandbox_runtime
from agentforge.sandbox.local_runtime import LocalSubprocessRuntime


# On Windows, sys.executable may contain spaces (e.g. C:\Users\Vansh Agrawal\...)
# We must quote it when constructing shell commands.
_PY = f'"{sys.executable}"'


# ===========================================================================
# 1. SandboxRuntime ABC enforcement
# ===========================================================================

def test_sandbox_runtime_is_abstract():
    """SandboxRuntime cannot be instantiated directly."""
    with pytest.raises(TypeError):
        SandboxRuntime()  # type: ignore[abstract]


def test_concrete_runtime_must_implement_all_hooks():
    """A partial implementation missing any hook raises TypeError."""

    class PartialRuntime(SandboxRuntime):
        def create(self) -> None: ...
        def mount_workspace(self, host_path: Path) -> None: ...
        def execute_command(self, command: str, timeout_seconds: float = 60.0,
                            env: Optional[Dict] = None) -> SandboxExecutionResult: ...
        # Missing read_artifacts and teardown

    with pytest.raises(TypeError):
        PartialRuntime()  # type: ignore[abstract]


# ===========================================================================
# 2. SandboxExecutionResult model
# ===========================================================================

def test_sandbox_execution_result_defaults():
    """SandboxExecutionResult has correct optional field defaults."""
    result = SandboxExecutionResult(
        command="echo hello",
        exit_code=0,
        stdout="hello\n",
        stderr="",
        duration_seconds=0.01,
    )
    assert result.sandbox_id is None
    assert result.network_blocked is False
    assert result.resource_limits == {}


def test_sandbox_execution_result_with_fields():
    """SandboxExecutionResult stores sandbox metadata correctly."""
    result = SandboxExecutionResult(
        command="pytest",
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_seconds=1.23,
        sandbox_id="abc123",
        network_blocked=True,
        resource_limits={"mem_limit": "2g", "pids_limit": 100},
    )
    assert result.sandbox_id == "abc123"
    assert result.network_blocked is True
    assert result.resource_limits["pids_limit"] == 100


def test_sandbox_execution_result_is_subtype_of_command_execution_result():
    """SandboxExecutionResult is a CommandExecutionResult (Liskov substitution)."""
    from agentforge.models.execution import CommandExecutionResult

    result = SandboxExecutionResult(
        command="echo",
        exit_code=0,
        stdout="",
        stderr="",
        duration_seconds=0.0,
        sandbox_id="local",
    )
    assert isinstance(result, CommandExecutionResult)


# ===========================================================================
# 3. LocalSubprocessRuntime — lifecycle
# ===========================================================================

@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Creates a temporary workspace directory with a simple Python script."""
    (tmp_path / "hello.py").write_text("print('hello from sandbox')\n")
    return tmp_path


def test_local_runtime_requires_mount_before_create(tmp_workspace: Path):
    """create() raises SandboxRuntimeError if mount_workspace was not called."""
    runtime = LocalSubprocessRuntime()
    with pytest.raises(SandboxRuntimeError, match="mount_workspace"):
        runtime.create()


def test_local_runtime_requires_create_before_execute(tmp_workspace: Path):
    """execute_command() raises SandboxRuntimeError if create() was not called."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    with pytest.raises(SandboxRuntimeError, match="create"):
        runtime.execute_command("echo hello")


def test_local_runtime_full_lifecycle_success(tmp_workspace: Path):
    """Full create → execute → teardown lifecycle produces correct result."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    result = runtime.execute_command(
        f"{_PY} hello.py",
        timeout_seconds=10.0,
    )

    runtime.teardown()

    assert result.exit_code == 0
    assert "hello from sandbox" in result.stdout
    assert result.sandbox_id == "local"
    assert result.network_blocked is False
    assert result.duration_seconds >= 0


def test_local_runtime_captures_nonzero_exit_code(tmp_workspace: Path):
    """Non-zero exit codes are captured correctly."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    result = runtime.execute_command(
        f"{_PY} -c \"import sys; sys.exit(42)\"",
        timeout_seconds=10.0,
    )
    runtime.teardown()

    assert result.exit_code == 42
    assert result.sandbox_id == "local"


def test_local_runtime_captures_stderr(tmp_workspace: Path):
    """stderr output is captured separately from stdout."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    result = runtime.execute_command(
        f"{_PY} -c \"import sys; sys.stderr.write('error output')\"",
        timeout_seconds=10.0,
    )
    runtime.teardown()

    assert "error output" in result.stderr


def test_local_runtime_timeout_returns_exit_minus_one(tmp_workspace: Path):
    """Commands exceeding the timeout return exit_code=-1 with a timeout message."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    result = runtime.execute_command(
        f"{_PY} -c \"import time; time.sleep(60)\"",
        timeout_seconds=0.3,
    )
    runtime.teardown()

    assert result.exit_code == -1
    assert "timed out" in result.stderr.lower()


def test_local_runtime_scrubs_sensitive_env_vars(tmp_workspace: Path):
    """Sensitive environment variables are not passed to the subprocess."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    with patch.dict(os.environ, {"GITHUB_TOKEN": "super_secret_token_12345"}):
        result = runtime.execute_command(
            f"{_PY} -c \"import os; print(os.environ.get('GITHUB_TOKEN', 'NOT_FOUND'))\"",
            timeout_seconds=10.0,
        )

    runtime.teardown()

    assert "super_secret_token_12345" not in result.stdout
    assert "NOT_FOUND" in result.stdout


def test_local_runtime_mount_requires_existing_path():
    """mount_workspace raises SandboxRuntimeError for a non-existent path."""
    runtime = LocalSubprocessRuntime()
    with pytest.raises(SandboxRuntimeError, match="does not exist"):
        runtime.mount_workspace(Path("/this/path/does/not/exist"))


def test_local_runtime_teardown_is_idempotent(tmp_workspace: Path):
    """teardown() can be called multiple times without raising."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()
    runtime.teardown()
    runtime.teardown()  # Must not raise


def test_local_runtime_read_artifacts(tmp_workspace: Path):
    """read_artifacts returns correct file contents from the workspace."""
    (tmp_workspace / "output.txt").write_bytes(b"artifact content")

    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    artifacts = runtime.read_artifacts(["output.txt"])
    runtime.teardown()

    assert "output.txt" in artifacts
    assert artifacts["output.txt"] == b"artifact content"


def test_local_runtime_read_artifacts_missing_file(tmp_workspace: Path):
    """Missing files are silently skipped in read_artifacts."""
    runtime = LocalSubprocessRuntime()
    runtime.mount_workspace(tmp_workspace)
    runtime.create()

    artifacts = runtime.read_artifacts(["does_not_exist.txt"])
    runtime.teardown()

    assert "does_not_exist.txt" not in artifacts


# ===========================================================================
# 4. Factory — driver resolution
# ===========================================================================

def test_factory_returns_local_runtime_by_default():
    """get_sandbox_runtime() returns LocalSubprocessRuntime when driver unset."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AGENTFORGE_SANDBOX_DRIVER", None)
        runtime = get_sandbox_runtime()
    assert isinstance(runtime, LocalSubprocessRuntime)


def test_factory_returns_local_runtime_when_env_set_to_local():
    """get_sandbox_runtime() returns LocalSubprocessRuntime when DRIVER=local."""
    runtime = get_sandbox_runtime(driver="local")
    assert isinstance(runtime, LocalSubprocessRuntime)


def test_factory_explicit_driver_overrides_env_var():
    """Explicit driver= kwarg takes precedence over the env var."""
    with patch.dict(os.environ, {"AGENTFORGE_SANDBOX_DRIVER": "local"}):
        runtime = get_sandbox_runtime(driver="local")
    assert isinstance(runtime, LocalSubprocessRuntime)


def test_factory_raises_for_unknown_driver():
    """get_sandbox_runtime() raises SandboxRuntimeError for unknown driver values."""
    with pytest.raises(SandboxRuntimeError, match="Unknown sandbox driver"):
        get_sandbox_runtime(driver="kubernetes")


def test_factory_reads_env_var_for_driver():
    """get_sandbox_runtime() reads AGENTFORGE_SANDBOX_DRIVER correctly."""
    with patch.dict(os.environ, {"AGENTFORGE_SANDBOX_DRIVER": "local"}):
        runtime = get_sandbox_runtime()
    assert isinstance(runtime, LocalSubprocessRuntime)


# ===========================================================================
# 5. WorkspaceManager integration with LocalSubprocessRuntime
# ===========================================================================

def test_workspace_manager_with_local_sandbox_executes_command():
    """WorkspaceManager with an injected LocalSubprocessRuntime routes
    run_command() through the sandbox correctly."""
    from agentforge.workspace.manager import WorkspaceManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        (ws_path / "dummy.py").write_text("x = 1\n")

        sandbox = LocalSubprocessRuntime()
        wm = WorkspaceManager(workspace_dir=ws_path, task_id="test_sandbox_wm", sandbox=sandbox)

        result = wm.run_command(f"{_PY} -c \"print('sandboxed')\"", timeout_seconds=10)
        wm.cleanup()

        assert result.exit_code == 0
        assert "sandboxed" in result.stdout
        assert result.sandbox_id == "local"


def test_workspace_manager_without_sandbox_uses_subprocess():
    """WorkspaceManager with no sandbox falls back to the original subprocess path."""
    from agentforge.workspace.manager import WorkspaceManager

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        wm = WorkspaceManager(workspace_dir=ws_path, task_id="test_no_sandbox")

        result = wm.run_command(f"{_PY} -c \"print('local')\"", timeout_seconds=10)

        assert result.exit_code == 0
        assert "local" in result.stdout
        # No sandbox_id when using raw subprocess path
        assert result.sandbox_id is None
