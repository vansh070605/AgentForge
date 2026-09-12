"""Base tool contract, typed execution results, permission enforcement, and registry."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import inspect
import time
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel, Field

from agentforge.agents.base import BaseAgent
from agentforge.models.audit import ActionType
from agentforge.workspace.manager import WorkspaceManager


class ToolPermissionError(Exception):
    """Raised when an agent attempts to execute an unauthorized tool."""
    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails unexpectedly."""
    pass


T = TypeVar("T", bound=BaseModel)


class ToolResult(BaseModel, Generic[T]):
    """Standardized wrapper for all tool execution outputs."""

    tool_name: str
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    execution_time_seconds: float = 0.0


class BaseTool(ABC):
    """Abstract base class for all AgentForge controlled tools."""

    name: str = ""
    description: str = ""
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    def validate_input(self, raw_input: Union[BaseModel, Dict[str, Any]]) -> BaseModel:
        """Validates raw input against the tool's input schema."""
        if isinstance(raw_input, self.input_schema):
            return raw_input
        if isinstance(raw_input, dict):
            return self.input_schema.model_validate(raw_input)
        raise ValueError(f"Invalid input type: expected {self.input_schema.__name__} or dict, got {type(raw_input)}")

    @abstractmethod
    def _run(self, input_data: Any, workspace: WorkspaceManager) -> Any:
        """Executes the tool logic using the WorkspaceManager. Must be implemented by subclasses."""
        pass

    def execute(
        self,
        raw_input: Union[BaseModel, Dict[str, Any]],
        workspace: WorkspaceManager,
        agent: Optional[BaseAgent] = None,
        task_id: Optional[str] = None,
    ) -> ToolResult:
        """Enforces runtime permissions, validates input, records audit events,

        and executes the tool.
        """
        start_time = time.time()
        effective_task_id = task_id or workspace.task_id
        actor_name = f"{agent.role}:{agent.name}" if agent else "system:orchestrator"

        # 1. Runtime Permission Gate
        if agent is not None and not agent.is_tool_allowed(self.name):
            error_msg = f"Security error: Agent '{agent.name}' ({agent.role}) is unauthorized to execute tool '{self.name}'"
            workspace.record_audit(
                action_type=ActionType.ERROR_OCCURRED,
                description=error_msg,
                status="failure",
                metadata={
                    "tool_name": self.name,
                    "agent": agent.name,
                    "role": agent.role,
                    "reason": "unauthorized_tool",
                },
            )
            raise ToolPermissionError(error_msg)

        # 2. Input Validation
        try:
            validated_input = self.validate_input(raw_input)
        except Exception as exc:
            duration = time.time() - start_time
            error_msg = f"Input validation failed for tool '{self.name}': {str(exc)}"
            workspace.record_audit(
                action_type=ActionType.ERROR_OCCURRED,
                description=error_msg,
                status="failure",
                metadata={"tool_name": self.name, "raw_input": str(raw_input)},
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error_msg,
                execution_time_seconds=duration,
            )

        # 3. Tool Execution
        try:
            output_data = self._run(validated_input, workspace)
            duration = time.time() - start_time

            # Record audit event
            # Sanitize inputs to avoid storing long text in metadata
            sanitized_meta = {"tool_name": self.name}
            if hasattr(validated_input, "model_dump"):
                dumped = validated_input.model_dump()
                # Truncate large string values in audit logs
                for k, v in dumped.items():
                    if isinstance(v, str) and len(v) > 200:
                        sanitized_meta[k] = v[:200] + "... [truncated]"
                    else:
                        sanitized_meta[k] = v

            workspace.record_audit(
                action_type=ActionType.TOOL_INVOKED,
                description=f"Tool '{self.name}' executed successfully by {actor_name}",
                status="success",
                metadata=sanitized_meta,
            )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data=output_data,
                execution_time_seconds=duration,
            )

        except Exception as exc:
            duration = time.time() - start_time
            error_msg = f"Tool '{self.name}' failed during execution: {str(exc)}"
            workspace.record_audit(
                action_type=ActionType.ERROR_OCCURRED,
                description=error_msg,
                status="failure",
                metadata={"tool_name": self.name, "error": str(exc)},
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error_msg,
                execution_time_seconds=duration,
            )


class ToolRegistry:
    """Registry maintaining active tools and providing centralized dispatch."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool instance."""
        if not tool.name:
            raise ValueError("Tool name cannot be empty")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieves tool by name."""
        return self._tools.get(name)

    def list_tool_names(self) -> List[str]:
        """Returns list of all registered tool names."""
        return sorted(list(self._tools.keys()))

    def execute(
        self,
        tool_name: str,
        raw_input: Union[BaseModel, Dict[str, Any]],
        workspace: WorkspaceManager,
        agent: Optional[BaseAgent] = None,
        task_id: Optional[str] = None,
    ) -> ToolResult:
        """Looks up a tool and executes it with permission checks."""
        tool = self.get(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' is not registered in ToolRegistry"
            workspace.record_audit(
                action_type=ActionType.ERROR_OCCURRED,
                description=error_msg,
                status="failure",
                metadata={"tool_name": tool_name},
            )
            raise ValueError(error_msg)

        return tool.execute(raw_input=raw_input, workspace=workspace, agent=agent, task_id=task_id)
