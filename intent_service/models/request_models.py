from pydantic import BaseModel, Field


class IntentClassifyRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Free-form text the citizen typed, e.g. 'I want to apply for old age pension'",
    )
    applicant_id: str | None = Field(
        None,
        description=(
            "Optional applicant identifier, carried through for logging/audit correlation "
            "only - not used in classification itself."
        ),
    )
    language: str | None = Field(
        None,
        description=(
            "Phase C3: optional ISO 639-1 language code (e.g. 'hi', 'mr', 'bn', 'ta', 'te', "
            "'en') the caller already knows `text` is written in. When omitted, the language "
            "is auto-detected from `text` (see providers/language_detector.py). Declaring it "
            "is treated as authoritative and skips detection entirely - useful when the "
            "caller's UI already has a language selector."
        ),
    )
