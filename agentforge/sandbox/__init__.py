"""AgentForge sandbox package.

Provides the SandboxRuntime abstraction and concrete implementations for
isolated command execution during agent task runs.

Quick start::

    from agentforge.sandbox import get_sandbox_runtime

    runtime = get_sandbox_runtime()           # Reads AGENTFORGE_SANDBOX_DRIVER
    runtime.mount_workspace(workspace_dir)
    runtime.create()
    result = runtime.execute_command("pytest tests/")
    runtime.teardown()

Driver selection via environment variable:
    AGENTFORGE_SANDBOX_DRIVER=docker   → DockerSandboxRuntime (production)
    AGENTFORGE_SANDBOX_DRIVER=local    → LocalSubprocessRuntime (CI/testing)
"""

from agentforge.sandbox.base import (
    SandboxExecutionResult,
    SandboxRuntime,
    SandboxRuntimeError,
)
from agentforge.sandbox.factory import get_sandbox_runtime
from agentforge.sandbox.local_runtime import LocalSubprocessRuntime

__all__ = [
    "SandboxRuntime",
    "SandboxExecutionResult",
    "SandboxRuntimeError",
    "LocalSubprocessRuntime",
    "get_sandbox_runtime",
]

# DockerSandboxRuntime is intentionally NOT imported at package level to avoid
# requiring the docker SDK just by importing agentforge.sandbox. It is
# loaded lazily by get_sandbox_runtime() when driver='docker'.
