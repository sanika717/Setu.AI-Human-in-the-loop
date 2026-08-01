from typing import Any

from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    """A single, standardized validation problem."""

    code: str = Field(..., description="Machine-readable issue code, e.g. UNSUPPORTED_DOCUMENT_TYPE")
    message: str = Field(..., description="Human-readable explanation of the issue")
    severity: str = Field(..., description="'error' blocks the document/application, 'warning' does not")


class DocumentValidationResult(BaseModel):
    """Standardized validation outcome for a single submitted document."""

    type: str
    is_supported_type: bool
    metadata_valid: bool
    ocr_valid: bool
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class EligibilityRuleResult(BaseModel):
    """Outcome of one Official Service Registry eligibility rule."""

    field: str
    operator: str
    passed: bool | None = Field(None, description="None if the field was not present in applicant_context")
    message: str


class EligibilityPreCheck(BaseModel):
    """Lightweight, non-authoritative eligibility signal sourced from the
    Official Service Registry's generic, data-driven eligibility rules
    (see `official_service_registry/services/eligibility_engine.py`).

    This is a pre-check only - it flags obvious disqualifiers early so the
    applicant/caseworker isn't waiting on AI extraction or a human reviewer
    to discover them. Final eligibility remains the responsibility of the
    Trust & Governance Engine.
    """

    service_id: str
    is_eligible: bool | None = Field(
        None, description="None when one or more rules could not be evaluated (missing context fields)"
    )
    rule_results: list[EligibilityRuleResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    """Standardized response for POST /api/v1/validate."""

    status: str = Field(..., description="'valid', 'invalid', or 'manual_review'")
    engine: str = "Input Validation & Security Engine"
    applicant_id: str
    overall_valid: bool
    documents: list[DocumentValidationResult]
    missing_required_documents: list[str] = Field(default_factory=list)
    eligibility_pre_check: EligibilityPreCheck | None = None
    issues_summary: list[ValidationIssue] = Field(default_factory=list)
