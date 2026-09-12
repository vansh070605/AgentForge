"""Task specification models defining what should be done."""

from typing import List, Optional
from pydantic import BaseModel, Field


class AcceptanceCriterion(BaseModel):
    """An individual testable requirement."""

    id: str = Field(..., description="Unique criterion ID (e.g., 'AC-1').")
    description: str = Field(..., description="Clear description of the expected behavior.")
    verification_method: str = Field(
        ...,
        description="How this will be verified (e.g., 'unit_test', 'code_inspection', 'diff_analysis').",
    )


class TaskSpecification(BaseModel):
    """Structured specification produced by the Identity Agent."""

    task_id: str = Field(..., description="Unique identifier for the task.")
    title: str = Field(..., description="Short title describing the task.")
    description: str = Field(..., description="Detailed explanation of the requirements.")
    target_files: List[str] = Field(
        default_factory=list,
        description="Files expected to be created or modified.",
    )
    acceptance_criteria: List[AcceptanceCriterion] = Field(
        default_factory=list,
        description="List of verifiable acceptance criteria.",
    )
    suggested_test_command: Optional[str] = Field(
        default=None,
        description="Suggested command to run tests (e.g., 'pytest tests/test_auth.py').",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Architectural or convention constraints the execution agent must respect.",
    )
