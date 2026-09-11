"""LocalSubprocessRuntime — backwards-compatible subprocess sandbox.

This runtime is a direct behavioral port of the original
WorkspaceManager.run_command() logic. It performs NO container isolation —
it exists purely to:

    1. Satisfy the SandboxRuntime interface so unit tests and CI pipelines
       without Docker can run unchanged.
    2. Serve as the default when AGENTFORGE_SANDBOX_DRIVER is unset or 'local'.

SECURITY NOTE: This runtime provides no OS-level isolation. It is intentionally
restricted to non-Docker CI environments. Never use it in production multi-tenant
deployments. Set AGENTFORGE_SANDBOX_DRIVER=docker for real isolation.
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from agentforge.sandbox.base import SandboxExecutionResult, SandboxRuntime, SandboxRuntimeError


logger = logging.getLogger(__name__)

# Environment variables stripped before executing commands to prevent credential leakage
_SENSITIVE_ENV_KEYS = {
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AZURE_OPENAI_API_KEY",
}


class LocalSubprocessRuntime(SandboxRuntime):
    """Subprocess-based runtime satisfying the SandboxRuntime interface.

    Wraps the host subprocess execution model behind the standard lifecycle
    hooks. No container is created — commands run directly on the host in the
    mounted workspace directory.

    Usage::

        runtime = LocalSubprocessRuntime()
        runtime.mount_workspace(Path("/path/to/workspace"))
        runtime.create()
        result = runtime.execute_command("pytest tests/", timeout_seconds=60)
        runtime.teardown()
    """

    def __init__(self) -> None:
        self._workspace_path: Optional[Path] = None
        self._active: bool = False

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def create(self) -> None:
        """No-op for the local runtime — no container to provision."""
        if self._workspace_path is None:
            raise SandboxRuntimeError(
                "LocalSubprocessRuntime: mount_workspace() must be called before create()."
            )
        self._active = True
        logger.debug("LocalSubprocessRuntime: activated (no container, host subprocess mode).")

    def mount_workspace(self, host_path: Path) -> None:
        """Records the workspace path to use as the subprocess working directory.

        Args:
            host_path: Absolute path to the workspace on the host.

        Raises:
            SandboxRuntimeError: If the path does not exist.
        """
        resolved = Path(host_path).resolve()
        if not resolved.exists():
            raise SandboxRuntimeError(
                f"LocalSubprocessRuntime: workspace path does not exist: {resolved}"
            )
        self._workspace_path = resolved
        logger.debug("LocalSubprocessRuntime: workspace mounted at %s", resolved)

    def execute_command(
        self,
        command: str,
        timeout_seconds: float = 60.0,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Executes command via subprocess in the workspace directory.

        Strips sensitive env vars, sets PYTHONPATH, and enforces the timeout.

        Args:
            command: Shell command to execute.
            timeout_seconds: Maximum wall-clock time before SIGKILL.
            env: Optional env overrides merged on top of the sanitised host env.

        Returns:
            SandboxExecutionResult with sandbox_id='local' and network_blocked=False.

        Raises:
            SandboxRuntimeError: If the runtime has not been created yet.
        """
        if not self._active:
            raise SandboxRuntimeError(
                "LocalSubprocessRuntime: create() must be called before execute_command()."
            )

        # Build sanitised environment
        clean_env = {k: v for k, v in os.environ.items() if k not in _SENSITIVE_ENV_KEYS}
        clean_env["PYTHONPATH"] = str(self._workspace_path)
        if env:
            clean_env.update(env)

        start_time = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=self._workspace_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=clean_env,
            )
            duration = time.time() - start_time
            return SandboxExecutionResult(
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=duration,
                sandbox_id="local",
                network_blocked=False,
                resource_limits={},
            )

        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            return SandboxExecutionResult(
                command=command,
                exit_code=-1,
                stdout=stdout,
                stderr=f"{stderr}\n[Execution timed out after {timeout_seconds} seconds]",
                duration_seconds=duration,
                sandbox_id="local",
                network_blocked=False,
                resource_limits={},
            )

    def read_artifacts(self, rel_paths: List[str]) -> Dict[str, bytes]:
        """Reads files directly from the workspace directory.

        Args:
            rel_paths: Paths relative to the mounted workspace root.

        Returns:
            Mapping of rel_path → raw bytes. Missing paths are silently skipped.
        """
        if not self._active or self._workspace_path is None:
            raise SandboxRuntimeError(
                "LocalSubprocessRuntime: runtime is not active."
            )
        results: Dict[str, bytes] = {}
        for rel in rel_paths:
            target = self._workspace_path / rel
            if target.exists() and target.is_file():
                results[rel] = target.read_bytes()
            else:
                logger.warning("LocalSubprocessRuntime: artifact not found: %s", rel)
        return results

    def teardown(self) -> None:
        """Deactivates the local runtime. Idempotent — safe to call multiple times."""
        if self._active:
            logger.debug("LocalSubprocessRuntime: teardown complete.")
        self._active = False
        self._workspace_path = None
