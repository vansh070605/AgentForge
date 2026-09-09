"""Audit event schemas for tracking actions across agents and workspace."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    WORKSPACE_INITIALIZED = "workspace_initialized"
    BRANCH_CREATED = "branch_created"
    FILE_READ = "file_read"
    FILE_WRITTEN = "file_written"
    TEST_EXECUTED = "test_executed"
    GIT_COMMITTED = "git_committed"
    DIFF_GENERATED = "diff_generated"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    REVIEW_SUBMITTED = "review_submitted"
    PROOF_EVALUATED = "proof_evaluated"
    ERROR_OCCURRED = "error_occurred"


class AuditEvent(BaseModel):
    """Immutable record of an action taken by an agent, tool, or workspace."""

    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}",
        description="Unique identifier for this audit event.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC when the event occurred.",
    )
    task_id: str = Field(..., description="The ID of the task being executed.")
    actor: str = Field(..., description="Identity of the component or agent initiating the event.")
    action_type: ActionType = Field(..., description="Category of action performed.")
    description: str = Field(..., description="Human-readable summary of the action.")
    status: str = Field(
        default="success",
        description="Execution status: 'success', 'failure', or 'warning'.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value metadata relevant to the event.",
    )
