"""Docker integration tests for DockerSandboxRuntime.

These tests require a running Docker daemon. They validate:
    - Container is provisioned with correct resource limits
    - --network none blocks all egress
    - PID limit prevents fork bombs
    - Read-only rootfs blocks writes outside /workspace and /tmp
    - Timeout termination works correctly
    - Container is fully removed after teardown (no zombie)
    - stdout/stderr capture fidelity
    - sandbox_id in SandboxExecutionResult matches container short ID

Run with:
    pytest tests/test_sandbox_docker.py -v -m requires_docker

Skip in CI without Docker:
    pytest tests/ -m "not requires_docker"
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

from agentforge.sandbox.base import SandboxRuntimeError
from agentforge.sandbox.docker_runtime import DockerSandboxRuntime


# ---------------------------------------------------------------------------
# Shared fixture: check Docker availability and provide a workspace
# ---------------------------------------------------------------------------

def _is_docker_available() -> bool:
    """Returns True if the Docker daemon is reachable."""
    try:
        import docker  # type: ignore[import-untyped]
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.requires_docker


@pytest.fixture(scope="module", autouse=True)
def require_docker():
    """Module-level guard: skip all tests if Docker is not available."""
    if not _is_docker_available():
        pytest.skip(
            "Docker daemon not available. Run with a Docker-enabled environment "
            "or deselect with: pytest -m 'not requires_docker'"
        )


@pytest.fixture
def sandbox_workspace(tmp_path: Path) -> Path:
    """Provides a temporary workspace directory with a simple test script."""
    (tmp_path / "hello.py").write_text("print('hello from docker sandbox')\n")
    (tmp_path / "test_simple.py").write_text(
        "def test_pass():\n    assert 1 + 1 == 2\n"
    )
    return tmp_path


@pytest.fixture
def runtime(sandbox_workspace: Path):
    """Creates a DockerSandboxRuntime, mounts workspace, creates container,
    and tears down after the test regardless of pass/fail."""
    rt = DockerSandboxRuntime()
    rt.mount_workspace(sandbox_workspace)
    rt.create()
    yield rt
    rt.teardown()


# ===========================================================================
# 1. Basic execution — stdout/stderr capture, exit code, sandbox_id
# ===========================================================================

def test_docker_runtime_executes_python_command(runtime: DockerSandboxRuntime):
    """A simple Python command runs inside the container and output is captured."""
    result = runtime.execute_command("python3 -c \"print('docker works')\"", timeout_seconds=30)

    assert result.exit_code == 0
    assert "docker works" in result.stdout
    assert result.sandbox_id is not None
    assert len(result.sandbox_id) > 0


def test_docker_runtime_captures_stderr(runtime: DockerSandboxRuntime):
    """stderr is captured separately from stdout."""
    result = runtime.execute_command(
        "python3 -c \"import sys; sys.stderr.write('err output')\"",
        timeout_seconds=30,
    )
    assert "err output" in result.stderr


def test_docker_runtime_nonzero_exit_code_captured(runtime: DockerSandboxRuntime):
    """Non-zero exit codes are faithfully propagated."""
    result = runtime.execute_command(
        "python3 -c \"import sys; sys.exit(7)\"",
        timeout_seconds=30,
    )
    assert result.exit_code == 7


def test_docker_sandbox_id_is_container_short_id(runtime: DockerSandboxRuntime):
    """sandbox_id in the result matches the Docker container short ID."""
    result = runtime.execute_command("echo probe", timeout_seconds=30)

    assert result.sandbox_id is not None
    # Docker short IDs are 12 hex chars
    assert len(result.sandbox_id) == 12
    assert all(c in "0123456789abcdef" for c in result.sandbox_id)


# ===========================================================================
# 2. Network isolation — --network none blocks all egress
# ===========================================================================

def test_docker_network_egress_blocked(runtime: DockerSandboxRuntime):
    """Network calls inside the sandbox must fail due to --network none."""
    # Try to reach an external host via Python's urllib — should raise
    result = runtime.execute_command(
        "python3 -c \""
        "import urllib.request, sys\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=5)\n"
        "    sys.exit(0)\n"
        "except Exception:\n"
        "    sys.exit(1)\n"
        "\"",
        timeout_seconds=30,
    )
    assert result.exit_code != 0, "Network egress should be blocked but request succeeded"


def test_docker_result_reports_network_blocked(runtime: DockerSandboxRuntime):
    """SandboxExecutionResult.network_blocked is True for Docker executions."""
    result = runtime.execute_command("echo check", timeout_seconds=30)
    assert result.network_blocked is True


def test_docker_dns_resolution_fails(runtime: DockerSandboxRuntime):
    """DNS resolution should fail inside a --network none container."""
    result = runtime.execute_command(
        "python3 -c \""
        "import socket, sys\n"
        "try:\n"
        "    socket.getaddrinfo('google.com', 80)\n"
        "    sys.exit(0)\n"
        "except socket.gaierror:\n"
        "    sys.exit(1)\n"
        "\"",
        timeout_seconds=30,
    )
    assert result.exit_code != 0, "DNS resolution should be blocked"


# ===========================================================================
# 3. Resource clamping — PID limit prevents fork bombs
# ===========================================================================

def test_docker_pid_limit_prevents_fork_bomb(runtime: DockerSandboxRuntime):
    """A fork bomb hits the pids_limit=100 and cannot consume unbounded PIDs."""
    # Python-based fork bomb that quickly spawns many processes
    result = runtime.execute_command(
        "python3 -c \""
        "import os, time\n"
        "pids = []\n"
        "try:\n"
        "    for _ in range(200):\n"
        "        pid = os.fork()\n"
        "        if pid == 0:\n"
        "            time.sleep(5)\n"
        "            os._exit(0)\n"
        "        pids.append(pid)\n"
        "except BlockingIOError:\n"  # EAGAIN when PID limit hit
        "    print('PID limit enforced')\n"
        "    import sys; sys.exit(42)\n"
        "\"",
        timeout_seconds=15,
    )
    # Either the fork failed (exit 42) or the OS killed some processes
    # The important invariant: the host PID table was NOT exhausted
    assert result.exit_code in (42, 1, -1), (
        f"Fork bomb containment unexpected exit code: {result.exit_code}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_docker_resource_limits_in_result(runtime: DockerSandboxRuntime):
    """resource_limits snapshot in the result contains the expected constraints."""
    result = runtime.execute_command("echo limits", timeout_seconds=30)

    limits = result.resource_limits
    assert limits.get("mem_limit") == "2g"
    assert limits.get("pids_limit") == 100
    assert limits.get("network_disabled") is True
    assert limits.get("read_only") is True
    assert "ALL" in limits.get("cap_drop", [])


# ===========================================================================
# 4. Read-only rootfs — container breakout attempt blocked
# ===========================================================================

def test_docker_readonly_rootfs_blocks_write_to_etc(runtime: DockerSandboxRuntime):
    """Writing to /etc/passwd (outside workspace) is blocked by read-only rootfs."""
    result = runtime.execute_command(
        "python3 -c \""
        "try:\n"
        "    open('/etc/passwd', 'a').write('evil')\n"
        "    import sys; sys.exit(0)\n"
        "except (PermissionError, OSError):\n"
        "    import sys; sys.exit(1)\n"
        "\"",
        timeout_seconds=30,
    )
    assert result.exit_code == 1, "Write to /etc/passwd should be blocked by read-only rootfs"


def test_docker_write_to_workspace_succeeds(runtime: DockerSandboxRuntime):
    """Writes to /workspace (the bind mount) succeed — it's the allowed write area."""
    result = runtime.execute_command(
        "python3 -c \""
        "with open('/workspace/sandbox_output.txt', 'w') as f:\n"
        "    f.write('written inside sandbox')\n"
        "print('write succeeded')\n"
        "\"",
        timeout_seconds=30,
    )
    assert result.exit_code == 0
    assert "write succeeded" in result.stdout


def test_docker_write_to_tmp_succeeds(runtime: DockerSandboxRuntime):
    """Writes to /tmp (tmpfs) succeed — it's the ephemeral scratch area."""
    result = runtime.execute_command(
        "python3 -c \""
        "with open('/tmp/scratch.txt', 'w') as f:\n"
        "    f.write('tmp data')\n"
        "print('tmp write ok')\n"
        "\"",
        timeout_seconds=30,
    )
    assert result.exit_code == 0
    assert "tmp write ok" in result.stdout


# ===========================================================================
# 5. Timeout termination
# ===========================================================================

def test_docker_timeout_terminates_long_running_command(sandbox_workspace: Path):
    """A long-running sleep command is killed at the timeout boundary."""
    rt = DockerSandboxRuntime()
    rt.mount_workspace(sandbox_workspace)
    rt.create()

    start = time.time()
    result = rt.execute_command("sleep 300", timeout_seconds=3.0)
    elapsed = time.time() - start

    rt.teardown()

    assert result.exit_code == -1
    assert "timed out" in result.stderr.lower()
    # Should terminate within 3s + some overhead, not wait for 300s
    assert elapsed < 30, f"Timeout took too long: {elapsed:.1f}s"


# ===========================================================================
# 6. Container cleanup — no zombie after teardown
# ===========================================================================

def test_docker_container_removed_after_teardown(sandbox_workspace: Path):
    """After teardown(), the container is fully removed from Docker."""
    try:
        import docker  # type: ignore[import-untyped]
        import docker.errors  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("docker SDK not installed")

    rt = DockerSandboxRuntime()
    rt.mount_workspace(sandbox_workspace)
    rt.create()
    container_id = rt._container_id
    assert container_id is not None

    rt.teardown()

    # Container must be gone — inspect should raise NotFound
    client = docker.from_env()
    with pytest.raises(docker.errors.NotFound):
        client.containers.get(container_id)


def test_docker_teardown_is_idempotent(sandbox_workspace: Path):
    """teardown() can be called multiple times without raising."""
    rt = DockerSandboxRuntime()
    rt.mount_workspace(sandbox_workspace)
    rt.create()
    rt.teardown()
    rt.teardown()  # Must not raise


# ===========================================================================
# 7. read_artifacts — tar extraction from container
# ===========================================================================

def test_docker_read_artifacts_returns_file_bytes(runtime: DockerSandboxRuntime):
    """read_artifacts extracts a file written inside the container."""
    # First write a file via the sandbox
    runtime.execute_command(
        "python3 -c \"open('/workspace/artifact.txt', 'w').write('artifact data')\"",
        timeout_seconds=30,
    )

    artifacts = runtime.read_artifacts(["artifact.txt"])

    assert "artifact.txt" in artifacts
    assert b"artifact data" in artifacts["artifact.txt"]


def test_docker_read_artifacts_missing_file_skipped(runtime: DockerSandboxRuntime):
    """Missing artifact paths are silently skipped."""
    artifacts = runtime.read_artifacts(["does_not_exist.bin"])
    assert "does_not_exist.bin" not in artifacts


# ===========================================================================
# 8. Error handling — missing workspace
# ===========================================================================

def test_docker_create_without_mount_raises():
    """create() without mount_workspace raises SandboxRuntimeError."""
    rt = DockerSandboxRuntime()
    with pytest.raises(SandboxRuntimeError, match="mount_workspace"):
        rt.create()


def test_docker_execute_without_create_raises(sandbox_workspace: Path):
    """execute_command() without create() raises SandboxRuntimeError."""
    rt = DockerSandboxRuntime()
    rt.mount_workspace(sandbox_workspace)
    with pytest.raises(SandboxRuntimeError, match="create"):
        rt.execute_command("echo fail")
