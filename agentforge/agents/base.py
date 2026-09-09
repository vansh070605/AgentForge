"""Base agent interface and contract for all AgentForge agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agentforge.models.audit import ActionType, AuditEvent
from agentforge.models.state import OrchestratorState


class AgentMetadata(BaseModel):
    """Metadata describing an agent's identity and boundaries."""

    name: str = Field(..., description="Display name of the agent.")
    role: str = Field(..., description="Role key (e.g., 'identity', 'execution', 'review', 'proof').")
    description: str = Field(..., description="Purpose and scope of this agent.")
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="Explicit list of tool names this agent is authorized to invoke.",
    )


class BaseAgent(ABC):
    """Lightweight abstract base class for all AgentForge agents."""

    def __init__(self, metadata: AgentMetadata):
        self.metadata = metadata

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def role(self) -> str:
        return self.metadata.role

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Enforces least privilege: checks if a tool is within the agent's authorized tools."""
        return tool_name in self.metadata.allowed_tools

    def create_audit_event(
        self,
        task_id: str,
        action_type: ActionType,
        description: str,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Generates a structured audit event tagged with this agent's identity."""
        return AuditEvent(
            task_id=task_id,
            actor=f"{self.role}:{self.name}",
            action_type=action_type,
            description=description,
            status=status,
            metadata=metadata or {},
        )

    @abstractmethod
    async def run(self, state: OrchestratorState, **kwargs: Any) -> Any:
        """Executes the agent's core responsibility and returns its primary output.
        
        Args:
            state: The current orchestrator pipeline state.
            **kwargs: Additional runtime arguments (e.g. tools, feedback).

        Returns:
            The agent's primary output model (e.g., TaskSpecification, ExecutionResult, etc.).
        """
        pass
