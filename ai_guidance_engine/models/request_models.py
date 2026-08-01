from pydantic import BaseModel, Field


class DocumentInput(BaseModel):
    type: str = Field(..., min_length=1, description="Type of the source document")
    text: str = Field(..., min_length=1, description="OCR extracted text for the document")


class ExtractionRequest(BaseModel):
    applicant_id: str = Field(..., min_length=1, description="Applicant identifier")
    documents: list[DocumentInput] = Field(..., min_length=1, description="Documents to extract from")
    service_id: str | None = Field(
        None,
        description=(
            "Optional Official Service Registry service identifier (e.g. 'nsap_old_age_pension') "
            "used to give the extraction prompt context about which service the applicant is "
            "applying for. Omitting it keeps the default, service-agnostic extraction schema."
        ),
    )
    target_fields: list[str] | None = Field(
        None,
        description=(
            "Optional list of field names to extract (e.g. from the applicable service's "
            "required documents). Defaults to a generic Applicant Name / Date of Birth / "
            "Service Type / Address schema when omitted."
        ),
    )
