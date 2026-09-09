"""Review agent models for independent code inspection."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewIssue(BaseModel):
    """Specific finding or problem identified during code review."""

    file: str = Field(..., description="File where the problem was found.")
    line: Optional[int] = Field(default=None, description="Line number if applicable.")
    severity: SeverityLevel = Field(..., description="Severity of the defect.")
    problem: str = Field(..., description="Description of the bug, flaw, or missing requirement.")
    recommendation: str = Field(..., description="Actionable suggestion on how to fix it.")


class ReviewStatus(str, Enum):
    APPROVED = "approved"
    NEEDS_CHANGES = "needs_changes"


class ReviewReport(BaseModel):
    """Structured review evaluation produced by the Review Agent."""

    task_id: str
    iteration: int = Field(default=1, description="Which review cycle this evaluation belongs to.")
    status: ReviewStatus = Field(..., description="Overall review decision.")
    summary: str = Field(..., description="High-level evaluation of code quality and correctness.")
    issues: List[ReviewIssue] = Field(default_factory=list, description="List of detected issues.")
    criteria_satisfaction_notes: Optional[str] = Field(
        default=None,
        description="Assessment on whether acceptance criteria were addressed.",
    )
