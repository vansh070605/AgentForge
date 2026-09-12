"""Controlled workspace manager for repository inspection, modification, and execution.

Command execution is delegated to a SandboxRuntime implementation selected via the
AGENTFORGE_SANDBOX_DRIVER environment variable:
    - 'docker'  → DockerSandboxRuntime (ephemeral container, --network none)
    - 'local'   → LocalSubprocessRuntime (host subprocess, for CI without Docker)
"""

import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from agentforge.models.audit import ActionType, AuditEvent
from agentforge.models.execution import CommandExecutionResult
from agentforge.sandbox.base import SandboxRuntime


# Environment variables to strip before executing commands in the workspace
SENSITIVE_ENV_KEYS = {
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AZURE_OPENAI_API_KEY",
}


class WorkspaceManager:
    """Manages an isolated working directory for repository inspection, modification,

    testing, and git operations.
    """

    def __init__(
        self,
        workspace_dir: Path,
        task_id: str,
        sandbox: Optional[SandboxRuntime] = None,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.task_id = task_id
        self.base_commit: Optional[str] = None
        self.current_branch: Optional[str] = None
        self._audit_trail: List[AuditEvent] = []
        self._sandbox: Optional[SandboxRuntime] = sandbox
        self._sandbox_initialized: bool = False  # tracks lazy init state

    @property
    def audit_trail(self) -> List[AuditEvent]:
        """Returns the immutable list of recorded audit events."""
        return list(self._audit_trail)

    def record_audit(
        self,
        action_type: ActionType,
        description: str,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        actor: Optional[str] = None,
    ) -> AuditEvent:
        """Records an action into the workspace audit trail."""
        event = AuditEvent(
            task_id=self.task_id,
            actor=actor or "workspace_manager",
            action_type=action_type,
            description=description,
            status=status,
            metadata=metadata or {},
        )
        self._audit_trail.append(event)
        return event

    def resolve_safe_path(self, rel_path: str) -> Path:
        """Resolves a relative path and verifies it cannot escape the workspace directory.

        Raises:
            ValueError: If a path traversal attempt is detected.
        """
        # Strip any leading slashes/backslashes to ensure it's relative
        clean_rel = rel_path.lstrip("/\\")
        target_path = (self.workspace_dir / clean_rel).resolve()
        
        try:
            target_path.relative_to(self.workspace_dir)
        except ValueError:
            self.record_audit(
                action_type=ActionType.ERROR_OCCURRED,
                description=f"Security alert: Path traversal blocked for path '{rel_path}'",
                status="failure",
                metadata={"attempted_path": rel_path},
            )
            raise ValueError(
                f"Security violation: path '{rel_path}' resolves outside workspace '{self.workspace_dir}'"
            )
            
        return target_path

    def initialize_from_source(self, source_path: Path, branch_name: str) -> str:
        """Initializes workspace by cloning or copying a local repository, captures

        the immutable base_commit, and checks out a new task branch.
        """
        source_path = Path(source_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source repository path does not exist: {source_path}")

        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Clone local repo using git CLI
        clone_cmd = ["git", "clone", str(source_path), str(self.workspace_dir)]
        res = subprocess.run(clone_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {res.stderr}")

        # Capture the immutable base_commit
        rev_cmd = ["git", "rev-parse", "HEAD"]
        rev_res = subprocess.run(rev_cmd, cwd=self.workspace_dir, capture_output=True, text=True, check=True)
        self.base_commit = rev_res.stdout.strip()

        # Create and checkout the feature branch
        branch_cmd = ["git", "checkout", "-b", branch_name]
        branch_res = subprocess.run(
            branch_cmd, cwd=self.workspace_dir, capture_output=True, text=True, check=True
        )
        self.current_branch = branch_name

        self.record_audit(
            action_type=ActionType.WORKSPACE_INITIALIZED,
            description=f"Workspace initialized from '{source_path}' at base_commit {self.base_commit}",
            metadata={"base_commit": self.base_commit, "branch": branch_name},
        )
        return self.base_commit

    def read_file(self, rel_path: str, max_size_bytes: int = 5 * 1024 * 1024) -> str:
        """Reads content of a file within the workspace safely."""
        safe_path = self.resolve_safe_path(rel_path)
        if not safe_path.exists() or not safe_path.is_file():
            raise FileNotFoundError(f"File not found: {rel_path}")

        file_size = safe_path.stat().st_size
        if file_size > max_size_bytes:
            raise ValueError(
                f"File '{rel_path}' exceeds maximum read size of {max_size_bytes} bytes (size: {file_size})"
            )

        content = safe_path.read_text(encoding="utf-8", errors="replace")
        self.record_audit(
            action_type=ActionType.FILE_READ,
            description=f"Read file '{rel_path}' ({file_size} bytes)",
            metadata={"path": rel_path, "bytes": file_size},
        )
        return content

    def write_file(self, rel_path: str, content: str, max_size_bytes: int = 5 * 1024 * 1024) -> None:
        """Writes content to a file safely, creating parent directories if needed."""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > max_size_bytes:
            raise ValueError(
                f"File content exceeds maximum write size of {max_size_bytes} bytes (size: {content_bytes})"
            )

        safe_path = self.resolve_safe_path(rel_path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        
        self.record_audit(
            action_type=ActionType.FILE_WRITTEN,
            description=f"Wrote file '{rel_path}' ({len(content)} characters)",
            metadata={"path": rel_path, "chars": len(content), "bytes": content_bytes},
        )

    def list_files(self, rel_dir: str = "", max_depth: int = 5) -> List[str]:
        """Lists tracked and untracked files in the workspace, excluding ignored folders."""
        safe_dir = self.resolve_safe_path(rel_dir)
        if not safe_dir.is_dir():
            raise NotADirectoryError(f"Directory not found: {rel_dir}")

        ignored_patterns = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".egg-info"}
        results = []

        for root, dirs, files in os.walk(safe_dir):
            dirs[:] = [d for d in dirs if d not in ignored_patterns]
            rel_root = Path(root).relative_to(self.workspace_dir)
            
            # Check depth limit
            if len(rel_root.parts) > max_depth:
                continue

            for f in files:
                if f.endswith((".pyc", ".pyo")):
                    continue
                file_rel = (rel_root / f).as_posix()
                results.append(file_rel)

        return sorted(results)

    def git_status(self) -> Dict[str, List[str]]:
        """Returns categorized status of modified, untracked, and staged files."""
        cmd = ["git", "status", "--porcelain"]
        res = subprocess.run(cmd, cwd=self.workspace_dir, capture_output=True, text=True, check=True)
        
        modified = []
        untracked = []
        staged = []

        for line in res.stdout.splitlines():
            if not line:
                continue
            index_status = line[0]
            work_tree_status = line[1]
            path = line[3:].strip()

            if index_status in ("M", "A", "R", "D"):
                staged.append(path)
            if work_tree_status == "M":
                modified.append(path)
            elif work_tree_status == "?":
                untracked.append(path)

        return {
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
        }

    def git_commit(self, message: str) -> str:
        """Stages all changes and creates an atomic commit."""
        # Add all changes
        subprocess.run(["git", "add", "-A"], cwd=self.workspace_dir, check=True)

        commit_cmd = ["git", "commit", "-m", message]
        res = subprocess.run(commit_cmd, cwd=self.workspace_dir, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Git commit failed: {res.stderr or res.stdout}")

        # Retrieve new commit hash
        hash_res = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.workspace_dir, capture_output=True, text=True, check=True
        )
        commit_hash = hash_res.stdout.strip()

        self.record_audit(
            action_type=ActionType.GIT_COMMITTED,
            description=f"Created commit {commit_hash[:8]}: {message}",
            metadata={"commit_hash": commit_hash, "message": message},
        )
        return commit_hash

    def git_diff(self, against_base: bool = True) -> str:
        """Generates unified diff.
        
        If against_base is True, compares base_commit against current working tree,
        ensuring all committed AND uncommitted changes are visible to Proof-of-Work.
        If False, compares current working tree against HEAD.
        """
        if against_base and self.base_commit:
            # Shows all changes since the initial base commit
            cmd = ["git", "diff", self.base_commit]
        else:
            cmd = ["git", "diff", "HEAD"]

        res = subprocess.run(cmd, cwd=self.workspace_dir, capture_output=True, text=True, check=True)
        diff_output = res.stdout

        self.record_audit(
            action_type=ActionType.DIFF_GENERATED,
            description=f"Generated diff (against_base={against_base}, {len(diff_output)} chars)",
            metadata={"against_base": against_base, "chars": len(diff_output)},
        )
        return diff_output

    def run_command(
        self,
        command: str,
        timeout_seconds: float = 60.0,
    ) -> CommandExecutionResult:
        """Executes a command (e.g. test suite) within the workspace.

        When a SandboxRuntime is configured, delegates to the sandbox for
        OS-level isolation (Docker container). Otherwise falls back to the
        host subprocess execution path with env scrubbing and timeout.

        Args:
            command: Shell command to execute.
            timeout_seconds: Maximum wall-clock time in seconds.

        Returns:
            CommandExecutionResult capturing exit code, stdout, stderr,
            duration, and (if sandboxed) the container ID.
        """
        if self._sandbox is not None:
            return self._run_in_sandbox(command, timeout_seconds)
        return self._run_subprocess(command, timeout_seconds)

    def _run_in_sandbox(
        self,
        command: str,
        timeout_seconds: float,
    ) -> CommandExecutionResult:
        """Delegates command execution to the configured SandboxRuntime.

        The sandbox is lazily provisioned on the first command call and reused
        for all subsequent calls within the same workspace lifetime. teardown()
        is called by WorkspaceManager.cleanup(), not per-command.
        """
        assert self._sandbox is not None

        # Lazy provisioning — mount and create only on first command
        if not self._sandbox_initialized:
            try:
                self._sandbox.mount_workspace(self.workspace_dir)
                self._sandbox.create()
                self._sandbox_initialized = True
            except Exception as exc:
                self.record_audit(
                    action_type=ActionType.TEST_EXECUTED,
                    description=f"Sandbox provisioning failed for command '{command}': {exc}",
                    status="failure",
                    metadata={"command": command, "error": str(exc)},
                )
                return CommandExecutionResult(
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"[Sandbox provisioning error]: {exc}",
                    duration_seconds=0.0,
                )

        sandbox_result = self._sandbox.execute_command(command, timeout_seconds)
        self.record_audit(
            action_type=ActionType.TEST_EXECUTED,
            description=(
                f"Executed command '{command}' in sandbox "
                f"(exit_code={sandbox_result.exit_code}, "
                f"duration={sandbox_result.duration_seconds:.2f}s, "
                f"sandbox_id={sandbox_result.sandbox_id})"
            ),
            status="success" if sandbox_result.exit_code == 0 else "failure",
            metadata={
                "command": command,
                "exit_code": sandbox_result.exit_code,
                "duration_seconds": sandbox_result.duration_seconds,
                "sandbox_id": sandbox_result.sandbox_id,
                "network_blocked": sandbox_result.network_blocked,
            },
        )
        # Return as CommandExecutionResult (SandboxExecutionResult is a subtype)
        return sandbox_result

    def _run_subprocess(
        self,
        command: str,
        timeout_seconds: float,
    ) -> CommandExecutionResult:
        """Original host subprocess execution path (no sandbox)."""
        # Scrub sensitive environment variables
        env = {k: v for k, v in os.environ.items() if k not in SENSITIVE_ENV_KEYS}
        # Explicitly ensure subprocess can locate python modules in workspace
        env["PYTHONPATH"] = str(self.workspace_dir)

        start_time = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=self.workspace_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            duration = time.time() - start_time
            result = CommandExecutionResult(
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=duration,
            )
            self.record_audit(
                action_type=ActionType.TEST_EXECUTED,
                description=f"Executed command '{command}' (exit_code={proc.returncode}, duration={duration:.2f}s)",
                status="success" if proc.returncode == 0 else "failure",
                metadata={"command": command, "exit_code": proc.returncode, "duration_seconds": duration},
            )
            return result

        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            self.record_audit(
                action_type=ActionType.TEST_EXECUTED,
                description=f"Command '{command}' timed out after {timeout_seconds}s",
                status="failure",
                metadata={"command": command, "timed_out": True},
            )
            return CommandExecutionResult(
                command=command,
                exit_code=-1,
                stdout=stdout,
                stderr=f"{stderr}\n[Execution timed out after {timeout_seconds} seconds]",
                duration_seconds=duration,
            )

    def cleanup(self) -> None:
        """Removes the workspace directory and tears down the sandbox upon completion."""
        if self._sandbox is not None and self._sandbox_initialized:
            try:
                self._sandbox.teardown()
            except Exception:
                pass  # Best-effort cleanup
            self._sandbox_initialized = False
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
