from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    DocumentCreateRequest,
    DocumentResponse,
    PortalConfirmRequest,
    PortalConfirmResponse,
    PortalInfo,
    EvaluationRequest,
    EvaluationResponse,
    RAGQueryRequest,
    RAGResponse,
    RAGDocument,
    ConversationMessageRequest,
    ConversationTurnResponse,
)
from ..services.provider_client import OpenAIProvider, ProviderError
from ..services.extraction_service import ExtractionService
from ..services.evaluation import compute_precision_recall_f1
from ..services.rag import retrieve_documents
from ..services.registry_client import RegistryClient, RegistryUnavailableError
from ..services.risk_client import RiskClient, RiskEngineUnavailableError
from ..services.intent_client import IntentClient, IntentServiceUnavailableError
from ..db.session import AsyncSessionLocal
from ..db.models import Document, PortalEvent
from ..utils.crypto import encrypt_text, compute_document_hash
from ..utils.security import detect_prompt_injection
from ..core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def get_registry_client() -> RegistryClient:
    return RegistryClient()


def get_risk_client() -> RiskClient:
    return RiskClient()


def get_intent_client() -> IntentClient:
    return IntentClient()


# Used ONLY if the Official Service Registry cannot be reached at all, so
# this microservice can still run independently (Phase A requirement) even
# when official_service_registry is down. GET /portals and POST
# /portals/confirm otherwise always source their data live from the
# registry (official_service_registry/data/services.json) - adding a new
# government/banking service is a data change there, never a code change
# here.
FALLBACK_PORTAL_LIST = [
    {
        "id": "gov-banking-a",
        "name": "Government Banking Portal A",
        "description": "Official banking services, account verification, and public financial workflows.",
        "url": "https://www.example.gov/banking-a",
    },
    {
        "id": "gov-banking-b",
        "name": "Government Banking Portal B",
        "description": "Secure official portal for government-backed loans and banking assistance.",
        "url": "https://www.example.gov/banking-b",
    },
    {
        "id": "gov-support",
        "name": "Government Support Portal",
        "description": "Government compliance, benefit, and public banking resource center.",
        "url": "https://www.example.gov/banking-support",
    },
]


async def _list_portals_from_registry(registry_client: RegistryClient) -> list[dict]:
    services = await registry_client.list_services()
    return [
        {
            "id": service["service_id"],
            "name": service["service_name"],
            "description": service.get("description", ""),
            "url": service["official_url"],
        }
        for service in services
    ]


async def _find_portal(registry_client: RegistryClient, portal_id: str) -> dict | None:
    try:
        redirect = await registry_client.redirect_info(portal_id)
    except RegistryUnavailableError:
        logger.warning("Official Service Registry unreachable; falling back to static portal list for confirm")
        return next((item for item in FALLBACK_PORTAL_LIST if item["id"] == portal_id), None)
    if redirect is None:
        return None
    return {
        "id": redirect["service_id"],
        "name": redirect["service_name"],
        "url": redirect["official_url"],
    }


@router.post("/extract", response_model=ExtractionResponse)
async def extract_data(payload: ExtractionRequest, db: AsyncSession = Depends(get_db)):
    provider = OpenAIProvider(settings.openai_api_key)
    extraction = ExtractionService(provider)
    try:
        result = await extraction.extract(payload.text, payload.schema)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    encrypted_payload = encrypt_text(settings.encryption_key or settings.secret_key, payload.text)
    content_hash = compute_document_hash(payload.text)

    doc = Document(
        title=payload.document_id,
        source=payload.source,
        content_hash=content_hash,
        encrypted_payload=encrypted_payload,
        provider_name=provider.name,
        confidence=result.get("confidence", 0.0),
        extraction_result=str(result.get("extracted", {})),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    metrics = {
        "provider_calls": 1,
        "confidence": result.get("confidence", 0.0),
        "fallback_used": "errors" in result,
    }

    return ExtractionResponse(
        document_id=payload.document_id,
        extracted=result.get("extracted", {}),
        confidence=result.get("confidence", 0.0),
        provider_name=provider.name,
        metrics=metrics,
    )


@router.post("/documents", response_model=DocumentResponse)
async def create_document(request: DocumentCreateRequest, db: AsyncSession = Depends(get_db)):
    if detect_prompt_injection(request.content):
        raise HTTPException(status_code=400, detail="Potential prompt injection detected in document content")

    encrypted_payload = encrypt_text(settings.encryption_key or settings.secret_key, request.content)
    content_hash = compute_document_hash(request.content)

    document = Document(
        title=request.title,
        source=request.source,
        content_hash=content_hash,
        encrypted_payload=encrypted_payload,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@router.get("/portals", response_model=list[PortalInfo])
async def list_portals(registry_client: RegistryClient = Depends(get_registry_client)):
    try:
        portals = await _list_portals_from_registry(registry_client)
    except RegistryUnavailableError:
        logger.warning("Official Service Registry unreachable; falling back to static portal list for /portals")
        portals = FALLBACK_PORTAL_LIST
    return [PortalInfo(**portal) for portal in portals]


@router.post("/portals/confirm", response_model=PortalConfirmResponse)
async def confirm_portal_access(
    payload: PortalConfirmRequest,
    db: AsyncSession = Depends(get_db),
    registry_client: RegistryClient = Depends(get_registry_client),
    risk_client: RiskClient = Depends(get_risk_client),
):
    portal = await _find_portal(registry_client, payload.portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")
    if not payload.permission_given:
        raise HTTPException(status_code=403, detail="User denied permission to access portal")

    # Phase D Security Shield: verify HTTPS + the official domain whitelist
    # for this exact redirect before handing it back to the browser. Fails
    # open (logs + proceeds with risk_verified=False) only if risk_engine
    # itself is unreachable - it never silently treats a real risk finding
    # as safe; that verdict always comes from risk_engine.
    risk_verified = True
    risk_findings: list[str] = []
    try:
        risk_result = await risk_client.redirect_check(portal["id"], portal["url"])
    except RiskEngineUnavailableError:
        logger.warning("Risk Engine unreachable; proceeding without a Security Shield check for portal=%s", portal["id"])
        risk_verified = False
    else:
        if risk_result.get("should_pause_guidance"):
            reasons = [finding["message"] for finding in risk_result.get("findings", [])]
            event = PortalEvent(
                portal_id=portal["id"],
                portal_name=portal["name"],
                action="redirect_blocked_by_risk_shield",
                user_note="; ".join(reasons) or None,
            )
            db.add(event)
            await db.commit()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Redirect blocked by the Security Shield.",
                    "findings": reasons,
                },
            )
        risk_findings = [finding["message"] for finding in risk_result.get("findings", [])]

    note = payload.user_note
    if not note and payload.api_key:
        note = f"Portal access key provided, stored securely client-side."

    event = PortalEvent(
        portal_id=portal["id"],
        portal_name=portal["name"],
        action="redirect_confirmed",
        user_note=note,
    )
    db.add(event)
    await db.commit()
    return PortalConfirmResponse(
        portal_id=portal["id"],
        redirect_url=portal["url"],
        message=f"Permission granted for {portal['name']}.",
        risk_verified=risk_verified,
        risk_findings=risk_findings,
    )


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_payload(payload: EvaluationRequest):
    metrics = compute_precision_recall_f1(payload.predicted, payload.ground_truth)
    details = {
        "predicted_fields": list(payload.predicted.keys()),
        "ground_truth_fields": list(payload.ground_truth.keys()),
    }
    return EvaluationResponse(document_id=payload.document_id, **metrics, details=details)


@router.post("/rag", response_model=RAGResponse)
async def rag_search(payload: RAGQueryRequest, db: AsyncSession = Depends(get_db)):
    results = await retrieve_documents(db, payload.query, payload.top_k)
    return RAGResponse(query=payload.query, results=[RAGDocument(**result) for result in results])


# --- Phase D: Intent Service integration -----------------------------------
#
# system_orchestrator is the single integration point between the frontend
# and intent_service (Phase C1-C4), per the approved Phase D plan. These
# three routes are thin proxies only - no business logic is duplicated here,
# and intent_service itself is untouched. A completed conversation's
# `resolved_service.service_id` is the same identifier the existing
# GET /portals / POST /portals/confirm flow already uses as `portal_id`, so
# the frontend hands that id straight to /portals/confirm to redirect - no
# new linking model was introduced. The existing portal-card flow (GET
# /portals, POST /portals/confirm called directly from a clicked card)
# keeps working unmodified; this is an additive second path into the same
# confirm step, not a replacement for it.


@router.post("/conversation/message", response_model=ConversationTurnResponse, tags=["Conversation"])
async def send_conversation_message(
    payload: ConversationMessageRequest,
    intent_client: IntentClient = Depends(get_intent_client),
):
    """Proxies one turn of a conversation to intent_service. Omit
    `conversation_id` to start a new conversation; pass the one returned
    back on every later turn. Once the response's `state` is "completed"
    and `resolved_service` is set, call POST /portals/confirm with
    `resolved_service["service_id"]` as `portal_id` to redirect the citizen,
    exactly as the existing portal-card flow already does.
    """

    try:
        result = await intent_client.send_message(
            text=payload.text,
            conversation_id=payload.conversation_id,
            applicant_id=payload.applicant_id,
            language=payload.language,
        )
    except IntentServiceUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Intent Service unavailable: {exc}") from exc
    return ConversationTurnResponse(**result)


@router.get("/conversation/{conversation_id}", response_model=ConversationTurnResponse, tags=["Conversation"])
async def get_conversation_state(
    conversation_id: str,
    intent_client: IntentClient = Depends(get_intent_client),
):
    """Read-only: returns an existing conversation's current state without
    advancing it - useful for resuming a conversation after a page reload.
    """

    try:
        result = await intent_client.get_conversation_state(conversation_id)
    except IntentServiceUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Intent Service unavailable: {exc}") from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"No conversation found with id '{conversation_id}'")
    return ConversationTurnResponse(**result)


@router.delete("/conversation/{conversation_id}", tags=["Conversation"])
async def reset_conversation(
    conversation_id: str,
    intent_client: IntentClient = Depends(get_intent_client),
):
    """Discards a conversation's state - lets the citizen explicitly
    restart instead of waiting for the idle session to expire.
    """

    try:
        deleted = await intent_client.reset_conversation(conversation_id)
    except IntentServiceUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Intent Service unavailable: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No conversation found with id '{conversation_id}'")
    return {"status": "ok", "conversation_id": conversation_id, "deleted": True}
