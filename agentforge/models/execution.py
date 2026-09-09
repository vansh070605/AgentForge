"""Execution agent output and tool call models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """Record of an individual tool executed by the Execution Agent."""

    tool_name: str = Field(..., description="Name of the tool invoked.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool.")
    output_summary: str = Field(..., description="Short summary or snippet of the tool output.")
    status: str = Field(default="success", description="'success' or 'error'.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandExecutionResult(BaseModel):
    """Result of running a test or shell command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class ExecutionResult(BaseModel):
    """Summary of work produced by the Execution Agent."""

    task_id: str
    iteration: int = Field(default=1, description="Which iteration of execution this is.")
    summary_of_changes: str = Field(..., description="Explanation of what was modified.")
    modified_files: List[str] = Field(default_factory=list, description="Paths of all files modified or created.")
    commits_created: List[str] = Field(default_factory=list, description="Commit hashes created during this execution.")
    test_results: Optional[CommandExecutionResult] = Field(
        default=None,
        description="Outcome of the final test execution run.",
    )
    tool_calls: List[ToolCallRecord] = Field(
        default_factory=list,
        description="Audit list of all tool operations attempted.",
    )
