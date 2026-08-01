from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    document_id: str = Field(..., description="Unique ID supplied by the client")
    text: str = Field(..., description="Raw text or document content to extract from")
    schema: Dict[str, Any] = Field(..., description="Extraction schema defining the expected fields")
    source: Optional[str] = Field(None, description="Optional source metadata")


class ExtractionResponse(BaseModel):
    document_id: str
    extracted: Dict[str, Any]
    confidence: float
    provider_name: str
    metrics: Dict[str, Any]


class DocumentCreateRequest(BaseModel):
    title: str
    source: Optional[str]
    content: str


class DocumentResponse(BaseModel):
    id: int
    title: str
    source: Optional[str]
    content_hash: str
    created_at: datetime
    updated_at: datetime


class PortalInfo(BaseModel):
    id: str
    name: str
    description: str
    url: str


class PortalConfirmRequest(BaseModel):
    portal_id: str
    permission_given: bool = True
    user_note: Optional[str] = None
    api_key: Optional[str] = None


class PortalConfirmResponse(BaseModel):
    portal_id: str
    redirect_url: str
    message: str
    risk_verified: bool = True
    risk_findings: list[str] = []


class EvaluationRequest(BaseModel):
    document_id: str
    predicted: Dict[str, Any]
    ground_truth: Dict[str, Any]


class EvaluationResponse(BaseModel):
    document_id: str
    precision: float
    recall: float
    f1: float
    details: Dict[str, Any]


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = Field(3, ge=1, le=10)


class RAGDocument(BaseModel):
    document_id: int
    title: str
    source: Optional[str]
    score: float
    snippet: Optional[str]


class RAGResponse(BaseModel):
    query: str
    results: List[RAGDocument]


class ConversationMessageRequest(BaseModel):
    """Forwarded verbatim to intent_service's POST /api/v1/conversation/message.

    Same shape as intent_service.models.conversation_models.ConversationMessageRequest
    (not imported across the service boundary - this architecture never
    shares code between microservices, only HTTP contracts - so this is
    kept as a small, independent mirror of that shape).
    """

    text: str = Field(..., min_length=1, description="The citizen's message for this turn")
    conversation_id: Optional[str] = Field(
        None, description="Omit to start a new conversation; pass back on every later turn."
    )
    applicant_id: Optional[str] = Field(None, description="Optional identifier, carried through for correlation only")
    language: Optional[str] = Field(None, description="Optional ISO 639-1 language override for this turn")


class ConversationTurnResponse(BaseModel):
    """intent_service's conversation response, relayed as-is.

    Deliberately loose (`Any`/`Dict`/`List` for the nested fields, plus
    `extra = "allow"`) rather than a field-for-field re-declaration of
    intent_service's ConversationTurnResponse - system_orchestrator doesn't
    interpret or branch on these fields, it only relays them to the
    frontend, so a tight duplicate schema would just be one more place to
    keep in sync for zero behavioral benefit. The one field the existing
    portal flow actually cares about, `resolved_service.service_id`, is a
    plain dict key here and is used exactly as-is with the existing
    POST /portals/confirm - no new linking model.
    """

    conversation_id: str
    state: str
    turn_count: int
    message: str
    language: str
    language_name: str
    detected_intent: Optional[str] = None
    label: Optional[str] = None
    confidence: Optional[float] = None
    service_category: Optional[str] = None
    candidate_matches: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_service: Optional[Dict[str, Any]] = Field(
        None, description="Contains service_id - reuse with the existing POST /portals/confirm to redirect."
    )
    collected_context: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    pending_field: Optional[str] = None
    eligibility_result: Optional[Dict[str, Any]] = None
    is_complete: bool = False
    registry_available: bool = True
    notes: List[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}
