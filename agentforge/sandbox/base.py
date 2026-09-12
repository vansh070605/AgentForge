"""Abstract sandbox runtime interface for AgentForge command execution isolation.

Defines the SandboxRuntime lifecycle contract that all concrete sandbox
implementations (Docker, local subprocess, future k8s) must satisfy.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agentforge.models.execution import CommandExecutionResult


class SandboxRuntimeError(Exception):
    """Raised when a sandbox lifecycle operation fails unrecoverably."""
    pass


class SandboxExecutionResult(CommandExecutionResult):
    """Extends CommandExecutionResult with sandbox-specific telemetry fields.

    All fields are backwards-compatible: sandbox_id and network_blocked have
    defaults so existing code constructing CommandExecutionResult directly
    continues to work without modification.
    """

    sandbox_id: Optional[str] = Field(
        default=None,
        description="Container short-ID, or 'local' for the subprocess runtime.",
    )
    network_blocked: bool = Field(
        default=False,
        description="True when the runtime enforced --network none during execution.",
    )
    resource_limits: Dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of resource constraints applied to this execution.",
    )


class SandboxRuntime(ABC):
    """Abstract lifecycle contract for all AgentForge sandbox implementations.

    Implementors must satisfy the following lifecycle order::

        runtime.create()
        runtime.mount_workspace(host_path)
        result = runtime.execute_command(command, timeout_seconds)
        artifacts = runtime.read_artifacts(["path/to/file"])
        runtime.teardown()

    Implementations MUST be safe to call teardown() even if create() never
    succeeded — teardown should be idempotent and not raise.
    """

    @abstractmethod
    def create(self) -> None:
        """Provisions the sandbox environment (e.g. starts a container).

        Raises:
            SandboxRuntimeError: If provisioning fails.
        """
        pass

    @abstractmethod
    def mount_workspace(self, host_path: Path) -> None:
        """Registers the workspace path to be mounted into the sandbox.

        This MUST be called before create() or immediately after, depending on
        the implementation. DockerSandboxRuntime applies the mount at create()
        time via the volumes parameter, so mount_workspace should be called
        before create().

        Args:
            host_path: Absolute path to the workspace directory on the host.

        Raises:
            SandboxRuntimeError: If the path does not exist.
        """
        pass

    @abstractmethod
    def execute_command(
        self,
        command: str,
        timeout_seconds: float = 60.0,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Executes a command inside the sandbox and returns the result.

        Args:
            command: Shell command string to execute.
            timeout_seconds: Hard wall-clock timeout. Must be enforced by the
                             implementation — the container/process is killed
                             if this elapses.
            env: Optional environment variable overrides.

        Returns:
            SandboxExecutionResult with stdout, stderr, exit_code, duration,
            and sandbox-specific metadata.

        Raises:
            SandboxRuntimeError: If the sandbox is not yet created or the
                                 execution infrastructure fails.
        """
        pass

    @abstractmethod
    def read_artifacts(self, rel_paths: List[str]) -> Dict[str, bytes]:
        """Reads file artifacts produced inside the sandbox.

        Args:
            rel_paths: Paths relative to the workspace mount point.

        Returns:
            Mapping of rel_path → raw file bytes. Missing paths are omitted.

        Raises:
            SandboxRuntimeError: If the sandbox is not active.
        """
        pass

    @abstractmethod
    def teardown(self) -> None:
        """Destroys the sandbox and releases all associated resources.

        Must be idempotent — calling teardown() on an already-torn-down
        sandbox must not raise. Implementations should log warnings but
        swallow errors during cleanup.
        """
        pass
