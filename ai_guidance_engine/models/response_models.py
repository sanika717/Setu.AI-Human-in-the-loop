from pydantic import BaseModel, Field
from .field_models import ExtractedField


class ExtractionResponse(BaseModel):
    status: str = Field(default="success")
    provider: str
    engine: str = "AI Guidance Engine"
    fields: list[ExtractedField]
    content_risk_verified: bool = Field(
        default=True,
        description="False only when the Risk Engine could not be reached to run the content scan",
    )
    should_pause_guidance: bool = Field(
        default=False,
        description="True if the content scan found sensitive-field indicators; fields[].value is redacted",
    )
    risk_findings: list[dict] = Field(default_factory=list)
