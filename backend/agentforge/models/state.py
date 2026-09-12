"""Orchestrator workflow state model."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from agentforge.models.audit import AuditEvent
from agentforge.models.execution import ExecutionResult
from agentforge.models.proof import VerificationReport
from agentforge.models.review import ReviewReport
from agentforge.models.task import TaskSpecification


class TaskStatus(str, Enum):
    PENDING = "pending"
    SPECIFYING = "specifying"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    FIXING = "fixing"
    VERIFYING = "verifying"
    READY_FOR_PR = "ready_for_pr"
    COMPLETED = "completed"
    FAILED = "failed"


class OrchestratorState(BaseModel):
    """Encapsulates the state of a single AgentForge pipeline run."""

    task_id: str
    repo_url_or_path: str
    user_prompt: str
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    current_iteration: int = Field(default=1)
    max_iterations: int = Field(default=2)
    branch_name: Optional[str] = None
    base_commit: Optional[str] = None
    
    task_spec: Optional[TaskSpecification] = None
    execution_results: List[ExecutionResult] = Field(default_factory=list)
    review_reports: List[ReviewReport] = Field(default_factory=list)
    verification_report: Optional[VerificationReport] = None
    pull_request_url: Optional[str] = None
    
    audit_trail: List[AuditEvent] = Field(default_factory=list)
    error_message: Optional[str] = None
