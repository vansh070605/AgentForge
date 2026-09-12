"""Agent interfaces and definitions."""

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.agents.execution import ExecutionAgent
from agentforge.agents.identity import IdentityAgent
from agentforge.agents.proof import ProofOfWorkAgent
from agentforge.agents.review import ReviewAgent

__all__ = [
    "AgentMetadata",
    "BaseAgent",
    "ExecutionAgent",
    "IdentityAgent",
    "ProofOfWorkAgent",
    "ReviewAgent",
]

