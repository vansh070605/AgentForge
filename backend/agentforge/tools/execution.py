"""Controlled test and command execution tool.

NOTE: This is a controlled command interface, NOT a secure container sandbox.
It enforces strict prefix allowlisting, rejects shell operators and chaining,
and executes with process timeouts and scrubbed environments.
True isolation will be added via containerization in future phases.
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from agentforge.tools.base import BaseTool
from agentforge.workspace.manager import WorkspaceManager


# Explicitly authorized test runners and command prefixes for the MVP
ALLOWED_COMMAND_PREFIXES = [
    "pytest",
    "python -m pytest",
    "python -m unittest",
    "npm test",
    "npm run test",
    "cargo test",
    "go test",
]

# Forbidden shell chaining, redirection, escape, and subshell injection patterns
# Specially hardened against Windows cmd.exe and POSIX shell separators
FORBIDDEN_OPERATORS = [
    "&",   # Command separator (&) and conditional AND (&&) in Windows cmd and POSIX
    ";",   # Command separator
    "|",   # Pipe (|) and conditional OR (||)
    ">",   # Output redirection
    "<",   # Input redirection
    "^",   # Windows cmd.exe escape character (prevents character-escaping tricks)
    "%",   # Windows cmd.exe environment variable expansion (%VAR%, %0-%9)
    "!",   # Windows cmd.exe delayed variable expansion (!VAR!)
    "`",   # Command substitution (backticks)
    "$(",  # Subshell command substitution
    "${",  # Environment variable expansion
    "\n",  # Line break injection
    "\r",  # Carriage return injection
    "\x00", # Null byte
]


class RunCommandInput(BaseModel):
    command: str = Field(
        ...,
        description="The test command to execute. Must match recognized test runners (e.g., 'pytest tests/').",
    )
    timeout_seconds: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Maximum execution time in seconds.",
    )


class RunCommandOutput(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    success: bool
    sandbox_id: Optional[str] = None


class RunCommandTool(BaseTool):
    name = "run_tests"
    description = (
        "Executes authorized test suites (pytest, npm test, cargo test, etc.) "
        "within the workspace with timeout and output capture."
    )
    input_schema = RunCommandInput
    output_schema = RunCommandOutput

    def validate_command(self, command: str) -> None:
        """Validates that the command strictly adheres to safe test runner allowlists

        and contains no shell chaining operators.
        """
        trimmed = command.strip()

        # 1. Reject forbidden shell chaining and redirection operators
        for op in FORBIDDEN_OPERATORS:
            if op in trimmed:
                raise ValueError(
                    f"Command contains forbidden shell operator or chaining character '{op}': '{command}'"
                )

        # 2. Enforce allowed test command prefixes
        matches_prefix = False
        for prefix in ALLOWED_COMMAND_PREFIXES:
            # Matches prefix followed by space or end of string
            pattern = rf"^{re.escape(prefix)}(\s+.*)?$"
            if re.match(pattern, trimmed):
                matches_prefix = True
                break

        if not matches_prefix:
            allowed_list_str = ", ".join(f"'{p}'" for p in ALLOWED_COMMAND_PREFIXES)
            raise ValueError(
                f"Command '{command}' is not authorized. Must begin with one of: {allowed_list_str}"
            )

    def _run(self, input_data: RunCommandInput, workspace: WorkspaceManager) -> RunCommandOutput:
        self.validate_command(input_data.command)

        raw_result = workspace.run_command(
            command=input_data.command,
            timeout_seconds=input_data.timeout_seconds,
        )

        timed_out = raw_result.exit_code == -1 and "timed out" in raw_result.stderr
        success = raw_result.exit_code == 0

        return RunCommandOutput(
            command=input_data.command,
            exit_code=raw_result.exit_code,
            stdout=raw_result.stdout,
            stderr=raw_result.stderr,
            duration_seconds=raw_result.duration_seconds,
            timed_out=timed_out,
            success=success,
            sandbox_id=getattr(raw_result, "sandbox_id", None),
        )
