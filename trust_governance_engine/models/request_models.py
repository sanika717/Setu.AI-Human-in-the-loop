from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .enums import ReportFormat


class FieldIntake(BaseModel):
    """A single field coming out of the AI Guidance Engine (Phase 2), handed
    to governance for human review. Shape intentionally mirrors
    ai_guidance_engine.models.field_models.ExtractedField so the frontend
    can forward an extraction response's `fields` list here almost as-is.
    """

    field: str = Field(..., min_length=1)
    value: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str = Field(..., min_length=1)
    source_document: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    required: bool | None = Field(
        None,
        description="Whether this field must be approved before the application can be "
        "submitted. Defaults to config.field_required_by_default when omitted.",
    )


class ApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    applicant_id: str = Field(..., min_length=1)
    service_id: str | None = Field(
        None,
        validation_alias=AliasChoices("service_id", "pension_type"),
        description=(
            "Official Service Registry service identifier this application is for "
            "(e.g. 'nsap_old_age_pension'). Formerly named 'pension_type', which is "
            "still accepted as an input alias."
        ),
    )
    fields: list[FieldIntake] = Field(..., min_length=1)

    @field_validator("fields")
    @classmethod
    def unique_field_names(cls, fields: list[FieldIntake]) -> list[FieldIntake]:
        seen = set()
        duplicates = set()
        for item in fields:
            if item.field in seen:
                duplicates.add(item.field)
            seen.add(item.field)
        if duplicates:
            raise ValueError(f"Duplicate field name(s) in intake: {sorted(duplicates)}")
        return fields


class FieldApproveRequest(BaseModel):
    actor: str = Field(..., min_length=1, description="Caseworker/reviewer identifier")
    note: str | None = None


class FieldRejectRequest(BaseModel):
    actor: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class FieldEditRequest(BaseModel):
    actor: str = Field(..., min_length=1)
    new_value: str = Field(..., description="Corrected value the reviewer wants to store")
    reason: str = Field(..., min_length=1, description="Why this field is being corrected")


class OTPRequestRequest(BaseModel):
    destination: str | None = Field(
        None, description="Where the OTP would be delivered (phone/e-mail). Informational only "
        "today since no real delivery provider is wired in yet."
    )


class OTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=1)


class SubmitApplicationRequest(BaseModel):
    actor: str = Field(..., min_length=1, description="Caseworker/reviewer performing final submission")


class ReportRequestParams(BaseModel):
    format: ReportFormat = ReportFormat.JSON


class TrustedDelegateRegisterRequest(BaseModel):
    """Registers a Trusted Person for this application (Phase F). Recording
    `consent_given_by` here is the applicant's explicit, scoped consent to
    share this specific application with this specific delegate (Phase G) -
    it is never inferred or defaulted.
    """

    delegate_name: str = Field(..., min_length=1)
    relationship_to_applicant: str = Field(..., min_length=1, description="e.g. 'son', 'caregiver', 'NGO volunteer'")
    contact: str = Field(..., min_length=1, description="Phone/e-mail Sahaay.AI can reach the delegate at")
    approval_required: bool = Field(
        True, description="If true, this delegate's approval is required before the application can be submitted"
    )
    consent_given_by: str = Field(..., min_length=1, description="Applicant or caseworker recording the consent")


class TrustedDelegateApproveRequest(BaseModel):
    actor: str = Field(..., min_length=1, description="The Trusted Delegate (or caseworker acting on their behalf)")


class TrustedDelegateRevokeRequest(BaseModel):
    actor: str = Field(..., min_length=1)
