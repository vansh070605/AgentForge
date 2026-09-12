"""Sandbox runtime factory — resolves the active runtime from the environment.

Reads the AGENTFORGE_SANDBOX_DRIVER environment variable and returns the
appropriate SandboxRuntime implementation:

    AGENTFORGE_SANDBOX_DRIVER=docker  →  DockerSandboxRuntime (production)
    AGENTFORGE_SANDBOX_DRIVER=local   →  LocalSubprocessRuntime (CI / testing)
    (unset)                           →  LocalSubprocessRuntime (default)

Usage::

    from agentforge.sandbox import get_sandbox_runtime

    runtime = get_sandbox_runtime()
    runtime.mount_workspace(workspace.workspace_dir)
    runtime.create()
    ...
    runtime.teardown()
"""

import os
from typing import Optional

from agentforge.sandbox.base import SandboxRuntime, SandboxRuntimeError


_DRIVER_ENV_VAR = "AGENTFORGE_SANDBOX_DRIVER"
_VALID_DRIVERS = ("docker", "local")


def get_sandbox_runtime(driver: Optional[str] = None) -> SandboxRuntime:
    """Instantiates and returns the configured SandboxRuntime.

    Args:
        driver: Explicit driver override ('docker' or 'local'). When None,
                the value is read from the AGENTFORGE_SANDBOX_DRIVER env var.
                Falls back to 'local' if the env var is also unset.

    Returns:
        A fresh, un-created SandboxRuntime instance. Callers are responsible
        for calling mount_workspace() and create() before use.

    Raises:
        SandboxRuntimeError: If an unknown driver string is provided.
    """
    resolved_driver = driver or os.environ.get(_DRIVER_ENV_VAR, "local")

    if resolved_driver == "docker":
        from agentforge.sandbox.docker_runtime import DockerSandboxRuntime
        return DockerSandboxRuntime()

    if resolved_driver == "local":
        from agentforge.sandbox.local_runtime import LocalSubprocessRuntime
        return LocalSubprocessRuntime()

    raise SandboxRuntimeError(
        f"Unknown sandbox driver: '{resolved_driver}'. "
        f"Valid values for {_DRIVER_ENV_VAR}: {_VALID_DRIVERS}. "
        "Set the environment variable or pass driver= explicitly."
    )
