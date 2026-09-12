"""Deterministic Execution Agent operating strictly through ToolRegistry.

SECURITY NOTICE:
This agent does NOT have direct filesystem, git, or subprocess access.
All interactions with the workspace and repository MUST be dispatched through
the ToolRegistry, ensuring that BaseTool permissions and validation gates
are strictly enforced.

Sandbox isolation:
Command execution (run_tests tool) is delegated to a SandboxRuntime determined
by the AGENTFORGE_SANDBOX_DRIVER environment variable:
    docker  → DockerSandboxRuntime (ephemeral container, --network none)
    local   → LocalSubprocessRuntime (host subprocess, backwards-compatible)
"""

from typing import Any, Dict, List, Optional, Sequence
from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models.audit import ActionType
from agentforge.models.execution import (
    CommandExecutionResult,
    ExecutionAction,
    ExecutionResult,
    ToolCallRecord,
)
from agentforge.models.state import OrchestratorState
from agentforge.tools.base import ToolPermissionError, ToolRegistry, ToolResult
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager
from agentforge.sandbox.base import SandboxRuntime
from agentforge.sandbox.factory import get_sandbox_runtime


DEFAULT_EXECUTION_TOOLS = [
    "read_file",
    "list_files",
    "search_code",
    "write_file",
    "run_tests",
    "git_status",
    "git_diff",
    "git_commit",
]


class ExecutionAgent(BaseAgent):
    """Deterministic Execution Agent that carries out task plans through controlled tools."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        metadata: Optional[AgentMetadata] = None,
        sandbox: Optional[SandboxRuntime] = None,
    ):
        if metadata is None:
            metadata = AgentMetadata(
                name="ExecutionAgent",
                role="execution",
                description="Executes repository modifications and tests via controlled tools.",
                allowed_tools=list(DEFAULT_EXECUTION_TOOLS),
            )
        super().__init__(metadata=metadata)
        self.tool_registry = tool_registry or get_default_tool_registry()
        # Sandbox runtime used for command execution isolation.
        # Defaults to auto-detection from AGENTFORGE_SANDBOX_DRIVER env var.
        self._sandbox: Optional[SandboxRuntime] = sandbox if sandbox is not None else get_sandbox_runtime()

    def _summarize_output(self, res: ToolResult) -> str:
        """Helper to create a concise summary of a tool execution result."""
        if not res.success:
            return res.error or "Unknown tool error"
        if res.data is None:
            return "Tool completed with no output data"
        
        # Format meaningful summaries for known tools
        data_dict = res.data.model_dump() if hasattr(res.data, "model_dump") else str(res.data)
        if isinstance(data_dict, dict):
            if "bytes_written" in data_dict:
                return f"Wrote {data_dict.get('bytes_written')} bytes to {data_dict.get('file_path')}"
            if "commit_hash" in data_dict:
                return f"Commit created: {data_dict.get('commit_hash')[:8]} - {data_dict.get('message')}"
            if "exit_code" in data_dict:
                return f"Command exit code: {data_dict.get('exit_code')} (duration: {data_dict.get('duration_seconds', 0):.2f}s)"
            if "total_matches" in data_dict:
                return f"Found {data_dict.get('total_matches')} match(es)"
            if "total_count" in data_dict:
                return f"Listed {data_dict.get('total_count')} file(s)"
            if "size_bytes" in data_dict:
                return f"Read {data_dict.get('size_bytes')} bytes from {data_dict.get('file_path')}"
        return str(data_dict)[:200]

    async def run(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
        plan: Optional[Sequence[ExecutionAction]] = None,
        **kwargs: Any,
    ) -> ExecutionResult:
        """Executes a structured sequence of actions deterministically.

        Args:
            state: Current pipeline orchestrator state containing TaskSpecification.
            workspace: WorkspaceManager for the active repository branch.
            plan: Sequence of ExecutionAction steps to carry out.
            **kwargs: Extra parameters.

        Returns:
            ExecutionResult containing execution status, commits, and tool records.
        """
        # Inject the agent's sandbox into the workspace if the workspace has none.
        # This bridges ExecutionAgent._sandbox → WorkspaceManager._sandbox so that
        # run_tests tool calls are transparently routed through the sandbox.
        if self._sandbox is not None and workspace._sandbox is None:
            workspace._sandbox = self._sandbox
            workspace._sandbox_initialized = False  # reset for lazy init

        task_id = state.task_id
        iteration = state.current_iteration

        # Record agent start
        start_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_STARTED,
            description=f"ExecutionAgent started for task '{task_id}' (iteration {iteration})",
            metadata={"plan_length": len(plan) if plan else 0},
        )
        workspace.record_audit(
            action_type=start_event.action_type,
            description=start_event.description,
            status=start_event.status,
            metadata=start_event.metadata,
        )

        if not plan:
            summary = "No execution actions provided in plan."
            result = ExecutionResult(
                task_id=task_id,
                iteration=iteration,
                success=True,
                summary_of_changes=summary,
                modified_files=[],
                commits_created=[],
                test_results=None,
                tool_calls=[],
            )
            state.execution_results.append(result)
            return result

        tool_calls: List[ToolCallRecord] = []
        modified_files: List[str] = []
        commits_created: List[str] = []
        last_test_result: Optional[CommandExecutionResult] = None
        execution_failed = False
        failure_reason: Optional[str] = None

        for action in plan:
            # Enforce least privilege check before calling registry
            if not self.is_tool_allowed(action.tool_name):
                err_msg = f"Agent '{self.name}' ({self.role}) is unauthorized to execute tool '{action.tool_name}'"
                record = ToolCallRecord(
                    tool_name=action.tool_name,
                    arguments=action.arguments,
                    output_summary=err_msg,
                    status="error",
                )
                tool_calls.append(record)
                
                # Log audit failure
                audit_err = self.create_audit_event(
                    task_id=task_id,
                    action_type=ActionType.ERROR_OCCURRED,
                    description=err_msg,
                    status="failure",
                    metadata={"tool_name": action.tool_name, "reason": "unauthorized_tool"},
                )
                workspace.record_audit(
                    action_type=audit_err.action_type,
                    description=audit_err.description,
                    status=audit_err.status,
                    metadata=audit_err.metadata,
                )

                if action.critical:
                    execution_failed = True
                    failure_reason = err_msg
                    break
                continue

            # Execute tool through registry
            try:
                res = self.tool_registry.execute(
                    tool_name=action.tool_name,
                    raw_input=action.arguments,
                    workspace=workspace,
                    agent=self,
                    task_id=task_id,
                )
            except ToolPermissionError as perm_err:
                err_msg = str(perm_err)
                record = ToolCallRecord(
                    tool_name=action.tool_name,
                    arguments=action.arguments,
                    output_summary=err_msg,
                    status="error",
                )
                tool_calls.append(record)
                if action.critical:
                    execution_failed = True
                    failure_reason = err_msg
                    break
                continue
            except Exception as exc:
                err_msg = f"Unexpected exception executing {action.tool_name}: {str(exc)}"
                record = ToolCallRecord(
                    tool_name=action.tool_name,
                    arguments=action.arguments,
                    output_summary=err_msg,
                    status="error",
                )
                tool_calls.append(record)
                if action.critical:
                    execution_failed = True
                    failure_reason = err_msg
                    break
                continue

            # Process tool outcome
            output_summary = self._summarize_output(res)
            record = ToolCallRecord(
                tool_name=action.tool_name,
                arguments=action.arguments,
                output_summary=output_summary,
                status="success" if res.success else "error",
            )
            tool_calls.append(record)

            if not res.success:
                if action.critical:
                    execution_failed = True
                    failure_reason = res.error or f"Action '{action.tool_name}' failed"
                    break
                continue

            # Track domain metadata for successful calls
            if action.tool_name == "write_file" and "file_path" in action.arguments:
                path = action.arguments["file_path"]
                if path not in modified_files:
                    modified_files.append(path)

            elif action.tool_name == "git_commit" and res.data:
                commit_hash = getattr(res.data, "commit_hash", None)
                if commit_hash and commit_hash not in commits_created:
                    commits_created.append(commit_hash)

            elif action.tool_name == "run_tests" and res.data:
                cmd_data = res.data
                last_test_result = CommandExecutionResult(
                    command=getattr(cmd_data, "command", action.arguments.get("command", "")),
                    exit_code=getattr(cmd_data, "exit_code", -1),
                    stdout=getattr(cmd_data, "stdout", ""),
                    stderr=getattr(cmd_data, "stderr", ""),
                    duration_seconds=getattr(cmd_data, "duration_seconds", 0.0),
                    sandbox_id=getattr(cmd_data, "sandbox_id", None),
                )
                # If tests exited with non-zero code and action is critical, mark as failure
                if last_test_result.exit_code != 0 and action.critical:
                    execution_failed = True
                    failure_reason = f"Tests failed with exit code {last_test_result.exit_code}"
                    break

        # Finalize ExecutionResult
        summary_of_changes = (
            f"Execution completed: modified {len(modified_files)} file(s), created {len(commits_created)} commit(s)."
            if not execution_failed
            else f"Execution halted due to failure: {failure_reason}"
        )

        final_result = ExecutionResult(
            task_id=task_id,
            iteration=iteration,
            success=not execution_failed,
            summary_of_changes=summary_of_changes,
            modified_files=modified_files,
            commits_created=commits_created,
            test_results=last_test_result,
            tool_calls=tool_calls,
            error_message=failure_reason if execution_failed else None,
        )

        # Record agent completed event
        end_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_COMPLETED,
            description=f"ExecutionAgent completed for task '{task_id}' with status {'success' if not execution_failed else 'failure'}",
            status="success" if not execution_failed else "failure",
            metadata={
                "success": not execution_failed,
                "modified_files": modified_files,
                "commits_count": len(commits_created),
                "tool_calls_count": len(tool_calls),
            },
        )
        workspace.record_audit(
            action_type=end_event.action_type,
            description=end_event.description,
            status=end_event.status,
            metadata=end_event.metadata,
        )

        state.execution_results.append(final_result)
        return final_result
