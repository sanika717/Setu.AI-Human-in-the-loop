from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    field: str
    value: str | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str
    source_document: str
    reason: str
