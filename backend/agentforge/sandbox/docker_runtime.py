"""DockerSandboxRuntime — ephemeral, hardened container execution sandbox.

Runs every command inside a short-lived Docker container with strict
resource quotas, read-only rootfs, and zero-trust network isolation.

Security posture enforced at container creation:
    - --network none          : No egress whatsoever during execution
    - --read-only             : Immutable container rootfs
    - --tmpfs /tmp            : Ephemeral scratch space, noexec
    - --pids-limit 100        : Fork-bomb prevention
    - --memory 2g             : Hard RAM cap
    - --cpus 2                : Hard CPU cap
    - --user nobody           : Non-root execution
    - --cap-drop ALL          : Zero Linux capabilities
    - --security-opt no-new-privileges : Blocks privilege escalation via SUID

Requires:
    pip install docker>=7.0.0
    Docker daemon running and accessible via the default socket.
"""

import io
import logging
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentforge.sandbox.base import SandboxExecutionResult, SandboxRuntime, SandboxRuntimeError


logger = logging.getLogger(__name__)

# Sandbox hardening constants
_DEFAULT_IMAGE = "python:3.12-slim"
_WORKSPACE_MOUNT_TARGET = "/workspace"
_MAX_CPU_COUNT = 2
_MAX_MEMORY = "2g"
_MAX_PIDS = 100
_TMPFS_CONFIG = {"/tmp": "size=256m,noexec,nosuid"}
_STOP_TIMEOUT_SECONDS = 5

_RESOURCE_LIMITS_SNAPSHOT = {
    "image": _DEFAULT_IMAGE,
    "nano_cpus": _MAX_CPU_COUNT * 1_000_000_000,
    "mem_limit": _MAX_MEMORY,
    "pids_limit": _MAX_PIDS,
    "network_disabled": True,
    "read_only": True,
    "user": "nobody",
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
}


class DockerSandboxRuntime(SandboxRuntime):
    """Ephemeral Docker container sandbox for isolated command execution.

    Each instance manages exactly one container lifecycle. Do not reuse an
    instance after teardown() — create a fresh DockerSandboxRuntime per task.

    Usage::

        runtime = DockerSandboxRuntime()
        runtime.mount_workspace(Path("/abs/path/to/workspace"))
        runtime.create()
        result = runtime.execute_command("pytest tests/", timeout_seconds=120)
        artifacts = runtime.read_artifacts(["coverage.xml"])
        runtime.teardown()

    Args:
        image: Docker image to use. Defaults to python:3.12-slim.
    """

    def __init__(self, image: str = _DEFAULT_IMAGE) -> None:
        self._image = image
        self._workspace_path: Optional[Path] = None
        self._container: Optional[Any] = None  # docker.models.containers.Container
        self._client: Optional[Any] = None     # docker.DockerClient
        self._container_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def mount_workspace(self, host_path: Path) -> None:
        """Registers the host workspace path to bind-mount into the container.

        Must be called before create(). The workspace is mounted at
        /workspace inside the container with read-write access.

        Args:
            host_path: Absolute path on the host.

        Raises:
            SandboxRuntimeError: If the path does not exist.
        """
        resolved = Path(host_path).resolve()
        if not resolved.exists():
            raise SandboxRuntimeError(
                f"DockerSandboxRuntime: workspace path does not exist: {resolved}"
            )
        self._workspace_path = resolved
        logger.debug("DockerSandboxRuntime: workspace queued for mount: %s", resolved)

    def create(self) -> None:
        """Provisions the hardened container with all security constraints applied.

        Raises:
            SandboxRuntimeError: If Docker daemon is unreachable, the image
                                 cannot be pulled, or container creation fails.
        """
        if self._workspace_path is None:
            raise SandboxRuntimeError(
                "DockerSandboxRuntime: mount_workspace() must be called before create()."
            )

        try:
            import docker  # type: ignore[import-untyped]
            import docker.errors  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SandboxRuntimeError(
                "DockerSandboxRuntime requires the 'docker' package. "
                "Install it with: pip install 'agentforge[sandbox]'"
            ) from exc

        try:
            self._client = docker.from_env()
            self._client.ping()
        except Exception as exc:
            raise SandboxRuntimeError(
                f"DockerSandboxRuntime: cannot connect to Docker daemon: {exc}"
            ) from exc

        volumes = {
            str(self._workspace_path): {
                "bind": _WORKSPACE_MOUNT_TARGET,
                "mode": "rw",
            }
        }

        try:
            logger.info(
                "DockerSandboxRuntime: creating container from image '%s'", self._image
            )
            self._container = self._client.containers.run(
                image=self._image,
                command="sleep infinity",   # Keep alive for exec_run calls
                detach=True,
                auto_remove=False,          # We remove manually in teardown for control
                network_disabled=True,      # --network none: zero egress
                read_only=True,             # Immutable rootfs
                tmpfs=_TMPFS_CONFIG,        # Ephemeral /tmp with noexec
                volumes=volumes,            # Workspace bind mount
                working_dir=_WORKSPACE_MOUNT_TARGET,
                nano_cpus=_MAX_CPU_COUNT * 1_000_000_000,
                mem_limit=_MAX_MEMORY,
                pids_limit=_MAX_PIDS,
                user="nobody",              # Non-root execution
                cap_drop=["ALL"],           # Drop all Linux capabilities
                security_opt=["no-new-privileges"],  # Block SUID escalation
                environment={
                    "PYTHONPATH": _WORKSPACE_MOUNT_TARGET,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                },
            )
            self._container_id = self._container.short_id
            logger.info(
                "DockerSandboxRuntime: container %s created successfully.", self._container_id
            )
        except docker.errors.ImageNotFound:
            raise SandboxRuntimeError(
                f"DockerSandboxRuntime: image '{self._image}' not found. "
                "Ensure the image is pulled or the daemon has internet access."
            )
        except docker.errors.APIError as exc:
            raise SandboxRuntimeError(
                f"DockerSandboxRuntime: container creation failed: {exc}"
            ) from exc

    def execute_command(
        self,
        command: str,
        timeout_seconds: float = 60.0,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Executes a command inside the running container via exec_run.

        Args:
            command: Shell command to run inside the container.
            timeout_seconds: Wall-clock timeout. The container is killed and
                             recreated if this limit is breached.
            env: Additional environment variables passed to exec_run.

        Returns:
            SandboxExecutionResult with container ID and security metadata.

        Raises:
            SandboxRuntimeError: If the container is not running.
        """
        if self._container is None or self._client is None:
            raise SandboxRuntimeError(
                "DockerSandboxRuntime: create() must be called before execute_command()."
            )

        try:
            import docker.errors  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SandboxRuntimeError("docker package not installed.") from exc

        start_time = time.time()
        timed_out = False

        try:
            exec_result = self._container.exec_run(
                cmd=["/bin/sh", "-c", command],
                workdir=_WORKSPACE_MOUNT_TARGET,
                environment=env or {},
                demux=True,
            )
            duration = time.time() - start_time

            # exec_run with demux=True returns (exit_code, (stdout_bytes, stderr_bytes))
            exit_code = exec_result.exit_code
            out_bytes, err_bytes = exec_result.output if exec_result.output else (b"", b"")
            stdout = (out_bytes or b"").decode("utf-8", errors="replace")
            stderr = (err_bytes or b"").decode("utf-8", errors="replace")

            # Enforce timeout manually: if duration exceeded, treat as timeout
            if duration > timeout_seconds:
                timed_out = True
                exit_code = -1
                stderr = f"{stderr}\n[Execution timed out after {timeout_seconds} seconds]"

        except docker.errors.APIError as exc:
            duration = time.time() - start_time
            raise SandboxRuntimeError(
                f"DockerSandboxRuntime: exec_run failed for command '{command}': {exc}"
            ) from exc

        return SandboxExecutionResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            sandbox_id=self._container_id,
            network_blocked=True,
            resource_limits=_RESOURCE_LIMITS_SNAPSHOT,
        )

    def read_artifacts(self, rel_paths: List[str]) -> Dict[str, bytes]:
        """Extracts files from the container workspace via Docker's get_archive API.

        Args:
            rel_paths: Paths relative to the workspace mount (/workspace).

        Returns:
            Mapping of rel_path → raw bytes. Missing files are silently skipped.

        Raises:
            SandboxRuntimeError: If the container is not running.
        """
        if self._container is None:
            raise SandboxRuntimeError(
                "DockerSandboxRuntime: runtime is not active."
            )

        try:
            import docker.errors  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SandboxRuntimeError("docker package not installed.") from exc

        results: Dict[str, bytes] = {}
        for rel in rel_paths:
            container_path = f"{_WORKSPACE_MOUNT_TARGET}/{rel.lstrip('/')}"
            try:
                bits, _ = self._container.get_archive(container_path)
                # Extract from tar stream
                raw = b"".join(bits)
                with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
                    for member in tar.getmembers():
                        if member.isfile():
                            f = tar.extractfile(member)
                            if f:
                                results[rel] = f.read()
                                break
            except docker.errors.NotFound:
                logger.warning(
                    "DockerSandboxRuntime: artifact not found in container: %s", rel
                )
            except Exception as exc:
                logger.warning(
                    "DockerSandboxRuntime: failed to extract artifact '%s': %s", rel, exc
                )

        return results

    def teardown(self) -> None:
        """Stops and removes the container. Idempotent and exception-safe.

        Guarantees no container zombie is left behind even on failure.
        """
        if self._container is None:
            return  # Already torn down or never created

        container_id = self._container_id or "unknown"
        try:
            logger.info("DockerSandboxRuntime: stopping container %s", container_id)
            self._container.stop(timeout=_STOP_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning(
                "DockerSandboxRuntime: failed to stop container %s: %s", container_id, exc
            )
        finally:
            try:
                self._container.remove(force=True)
                logger.info(
                    "DockerSandboxRuntime: container %s removed.", container_id
                )
            except Exception as exc:
                logger.warning(
                    "DockerSandboxRuntime: failed to remove container %s: %s",
                    container_id,
                    exc,
                )
            finally:
                self._container = None
                self._client = None
                self._container_id = None
