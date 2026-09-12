"""Proof-of-work models for objective evidence verification."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    INDETERMINATE = "indeterminate"


class CriterionStatus(str, Enum):
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    UNMET = "unmet"


class RequirementProof(BaseModel):
    """Direct connection between an acceptance criterion and verifiable evidence."""

    criterion_id: str = Field(..., description="ID matching the TaskSpecification criterion.")
    description: str = Field(..., description="The requirement being verified.")
    status: CriterionStatus = Field(..., description="Verification status.")
    evidence_items: List[str] = Field(
        default_factory=list,
        description="Objective evidence (e.g. diff hunks, passing test names, commit hashes).",
    )
    notes: Optional[str] = Field(default=None, description="Observations or explanations of gaps.")


class VerificationReport(BaseModel):
    """Evidence-backed verification report produced by the Proof-of-Work Agent."""

    task_id: str
    status: VerificationStatus = Field(..., description="Overall verification verdict.")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 based on available evidence.",
    )
    requirements: List[RequirementProof] = Field(
        default_factory=list,
        description="Per-criterion proof breakdown.",
    )
    tests_passed: int = Field(default=0, description="Total count of passing tests.")
    tests_failed: int = Field(default=0, description="Total count of failing tests.")
    unrelated_changes_detected: bool = Field(
        default=False,
        description="True if changes exist in files unrelated to the task specification.",
    )
    unrelated_files: List[str] = Field(
        default_factory=list,
        description="List of files modified that were not part of target_files or justified.",
    )
    verification_summary: str = Field(..., description="Summary of evidence analysis.")
