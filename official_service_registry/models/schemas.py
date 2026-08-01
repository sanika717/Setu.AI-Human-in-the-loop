from typing import Any, Literal

from pydantic import BaseModel, Field

# Supported eligibility-rule comparison operators. The evaluator in
# services/eligibility_engine.py is the ONLY place that branches on these -
# every service's actual eligibility logic is data (values in services.json),
# never code, so a new service with different eligibility criteria never
# requires a code change, only a new/edited registry entry.
EligibilityOperator = Literal["gte", "lte", "gt", "lt", "eq", "ne", "in", "exists"]


class EligibilityRule(BaseModel):
    """One generic, data-driven eligibility criterion.

    Evaluated against a caller-supplied `applicant_context` dict, e.g.
    `{"field": "applicant_age", "operator": "gte", "value": 60}` checks
    `applicant_context["applicant_age"] >= 60`.
    """

    field: str = Field(..., min_length=1, description="Key to look up in the applicant context")
    operator: EligibilityOperator
    value: Any = Field(..., description="Value to compare the context field against")
    message: str = Field(..., min_length=1, description="Human-readable explanation shown when this rule fails")


class WorkflowStep(BaseModel):
    """One generic step in a service's guided workflow.

    `action_type` is a small closed vocabulary the AI Guidance Engine and
    frontend already know how to render (intent_confirmation,
    official_site_verification, redirect_official_site, collect_documents,
    ai_guidance, human_review, otp_submission). Steps are pure data - the
    Workflow Engine just walks whatever list a service defines, so adding a
    service with a different step sequence never requires a code change.
    """

    step_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)


class ServiceDefinition(BaseModel):
    """One entry in the Official Service Registry.

    This is the single, config-driven source of truth Sahaay.AI uses for
    every government/banking service it can guide a user through -
    everything a code module needs to validate documents, pre-check
    eligibility, verify the official site, and drive the guided workflow,
    without any service-specific branching in code.
    """

    service_id: str = Field(..., min_length=1)
    service_name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, description="e.g. pension, identity, banking, tax, insurance")
    description: str = ""
    official_url: str = Field(..., min_length=1, description="The ONLY site Sahaay.AI ever redirects users to for this service")
    allowed_domains: list[str] = Field(..., min_length=1, description="Domain whitelist used by the Security Shield")
    required_documents: list[str] = Field(default_factory=list)
    eligibility_rules: list[EligibilityRule] = Field(default_factory=list)
    workflow_steps: list[WorkflowStep] = Field(default_factory=list)
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])


class ServiceSummary(BaseModel):
    """Lightweight listing shape for GET /api/v1/services."""

    service_id: str
    service_name: str
    category: str
    description: str = ""
    official_url: str
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])


class MissingDocumentsRequest(BaseModel):
    submitted_document_types: list[str] = Field(default_factory=list)


class MissingDocumentsResponse(BaseModel):
    service_id: str
    required_documents: list[str]
    missing_documents: list[str]


class EligibilityCheckRequest(BaseModel):
    applicant_context: dict[str, Any] = Field(default_factory=dict)


class EligibilityRuleResult(BaseModel):
    field: str
    operator: EligibilityOperator
    passed: bool | None = Field(None, description="None if the field was not present in applicant_context")
    message: str


class EligibilityCheckResponse(BaseModel):
    service_id: str
    is_eligible: bool | None = Field(
        None, description="None when one or more rules could not be evaluated (missing context fields)"
    )
    rule_results: list[EligibilityRuleResult]
    notes: list[str] = Field(default_factory=list)


class RedirectInfoResponse(BaseModel):
    service_id: str
    service_name: str
    official_url: str
    allowed_domains: list[str]


class WorkflowStepsResponse(BaseModel):
    service_id: str
    workflow_steps: list[WorkflowStep]
