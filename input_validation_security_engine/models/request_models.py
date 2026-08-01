from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class DocumentMetadata(BaseModel):
    """Optional file-level metadata supplied alongside OCR text."""

    file_name: str = Field(..., min_length=1, description="Original uploaded file name")
    mime_type: str = Field(..., min_length=1, description="MIME type reported for the uploaded file")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    page_count: int | None = Field(None, ge=1, description="Number of pages, if applicable (e.g. PDFs)")


class DocumentValidationInput(BaseModel):
    """A single document submitted for validation.

    Mirrors `ai_guidance_engine.models.request_models.DocumentInput`
    (`type` + `text`) with an added optional `metadata` block, so a document
    that passes validation here can be forwarded to the extraction engine
    without any reshaping.
    """

    type: str = Field(..., min_length=1, description="Type of the source document")
    text: str = Field(..., description="OCR extracted text for the document")
    metadata: DocumentMetadata | None = Field(None, description="Optional file metadata for the document")

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value.strip().lower()


class DocumentValidationRequest(BaseModel):
    """Request payload for POST /api/v1/validate.

    As of Phase B, required-document and eligibility pre-checks are driven
    by the Official Service Registry (`official_service_registry`) rather
    than a hardcoded pension catalog, so this engine works unmodified for
    ANY registered service. `service_id` replaces the old `pension_type`
    field; `pension_type` is still accepted as an input alias so existing
    callers keep working unmodified.
    """

    model_config = ConfigDict(populate_by_name=True)

    applicant_id: str = Field(..., min_length=1, description="Applicant identifier")
    service_id: str | None = Field(
        None,
        validation_alias=AliasChoices("service_id", "pension_type"),
        description=(
            "Official Service Registry service identifier (e.g. 'nsap_old_age_pension', "
            "'aadhaar_update', 'sbi_kyc_update'). Enables required-document and eligibility "
            "pre-checks. Formerly named 'pension_type', which is still accepted as an alias."
        ),
    )
    applicant_age: int | None = Field(None, ge=0, le=150, description="Applicant age, folded into applicant_context")
    applicant_context: dict[str, Any] | None = Field(
        None,
        description=(
            "Optional structured context (e.g. income, applicant_age) evaluated against the "
            "service's eligibility_rules by the Official Service Registry. applicant_age, if "
            "supplied, is merged in automatically under the 'applicant_age' key."
        ),
    )
    documents: list[DocumentValidationInput] = Field(..., min_length=1, description="Documents to validate")

    @field_validator("service_id")
    @classmethod
    def normalize_service_id(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value

    def resolved_applicant_context(self) -> dict[str, Any]:
        """Merges applicant_age into applicant_context for eligibility evaluation."""
        context = dict(self.applicant_context or {})
        if self.applicant_age is not None:
            context.setdefault("applicant_age", self.applicant_age)
        return context
