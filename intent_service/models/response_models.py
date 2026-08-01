from pydantic import BaseModel, Field


class IntentCandidate(BaseModel):
    intent_id: str
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class IntentClassifyResponse(BaseModel):
    engine: str = "Intent Service"
    provider: str
    text: str
    language: str = Field(
        ..., description="ISO 639-1 code the request was classified in - declared or auto-detected"
    )
    language_name: str = Field(..., description="Human-readable name for `language`, e.g. 'Hindi'")
    language_source: str = Field(
        ..., description="'declared' if the caller passed `language` on the request, else 'detected'"
    )
    language_detection_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "1.0 when `language_source` is 'declared' (the caller's word is taken as "
            "authoritative); otherwise the script-detector's confidence (see "
            "providers/language_detector.py)."
        ),
    )
    language_supported: bool = Field(
        ...,
        description=(
            "False if no keyword taxonomy exists yet for `language` - when False, "
            "`detected_intent` is always 'unclassified' since there is nothing to classify against."
        ),
    )
    detected_intent: str = Field(
        ...,
        description=(
            "'unclassified' when no intent clears the minimum confidence threshold, "
            "or when `language_supported` is False"
        ),
    )
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str = Field(..., description="'High', 'Medium', or 'Low'")
    alternate_intents: list[IntentCandidate] = Field(
        default_factory=list,
        description=(
            "Other candidate intents that scored above zero, most confident first, "
            "excluding the top pick."
        ),
    )


class ServiceMatch(BaseModel):
    """One ranked Official Service Registry candidate for a classified intent."""

    service_id: str
    service_name: str
    category: str
    description: str = ""
    official_url: str
    match_confidence: float = Field(..., ge=0.0, le=1.0)
    match_reason: str = Field(
        ..., description="Human-readable explanation of why this service was ranked here"
    )


class IntentResolveResponse(BaseModel):
    """Response for POST /api/v1/intent/resolve (Phase C2).

    Wraps the same classification IntentClassifyResponse would have
    produced, plus the ranked Official Service Registry candidates for that
    intent's `service_category_hint`.
    """

    engine: str = "Intent Service"
    text: str
    language: str = Field(
        ..., description="ISO 639-1 code the request was classified in - declared or auto-detected"
    )
    language_name: str = Field(..., description="Human-readable name for `language`, e.g. 'Hindi'")
    language_source: str = Field(
        ..., description="'declared' if the caller passed `language` on the request, else 'detected'"
    )
    language_detection_confidence: float = Field(..., ge=0.0, le=1.0)
    language_supported: bool = Field(
        ..., description="False if no keyword taxonomy exists yet for `language`"
    )
    detected_intent: str
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str
    service_category: str | None = Field(
        None, description="The service_category_hint used to filter the registry catalog, if any"
    )
    matches: list[ServiceMatch] = Field(default_factory=list)
    registry_available: bool = Field(
        True, description="False if the Official Service Registry could not be reached"
    )
    resolution_note: str = Field(
        "", description="Explains an empty `matches` list: no category, registry down, or no overlap"
    )
