from datetime import datetime

from pydantic import BaseModel, Field


class GovernedFieldResponse(BaseModel):
    field: str
    original_value: str | None
    current_value: str | None
    confidence: float
    confidence_level: str
    source_document: str
    reason: str
    required: bool
    decision_status: str
    is_edited: bool
    decision_note: str | None
    decided_by: str | None
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    engine: str = "Trust & Governance Engine"
    application_id: str
    applicant_id: str
    service_id: str | None
    status: str
    otp_verified: bool
    submission_hash: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    fields: list[GovernedFieldResponse]

    model_config = {"from_attributes": True}


class ApplicationStatusResponse(BaseModel):
    application_id: str
    status: str
    otp_verified: bool
    submitted_at: datetime | None
    pending_fields: int
    approved_fields: int
    rejected_fields: int


class ApplicationSummary(BaseModel):
    application_id: str
    applicant_id: str
    service_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AuditLogEntryResponse(BaseModel):
    sequence_number: int
    action: str
    field_name: str | None
    actor: str
    details: dict
    previous_hash: str
    entry_hash: str
    created_at: datetime


class AuditChainVerificationResponse(BaseModel):
    application_id: str
    is_valid: bool
    entries_checked: int
    first_broken_sequence_number: int | None = None
    detail: str


class OTPRequestResponse(BaseModel):
    application_id: str
    delivery_channel: str
    destination: str | None
    expires_at: datetime
    otp_code: str | None = Field(
        None,
        description="Only populated when config.otp_dev_mode_expose_code is True — i.e. there is "
        "no real SMS/e-mail provider configured yet. Never populated in a real deployment.",
    )


class OTPVerifyResponse(BaseModel):
    application_id: str
    verified: bool
    otp_verified: bool
    attempts_remaining: int | None = None
    detail: str


class SubmissionValidationResponse(BaseModel):
    application_id: str
    can_submit: bool
    blocking_reasons: list[str] = Field(default_factory=list)


class TrustedDelegateResponse(BaseModel):
    application_id: str
    delegate_name: str
    relationship_to_applicant: str
    contact: str
    approval_required: bool
    consent_given_by: str
    consent_given_at: datetime
    approved: bool
    approved_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class FinalSubmissionResponse(BaseModel):
    application_id: str
    submitted_by: str
    submission_hash: str
    submitted_at: datetime
    field_snapshot: dict
