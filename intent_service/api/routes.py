from fastapi import APIRouter, Depends

from ..models.request_models import IntentClassifyRequest
from ..models.response_models import IntentClassifyResponse, IntentResolveResponse
from ..services.intent_service import IntentService
from ..services.service_lookup_service import ServiceLookupService
from .dependencies import get_intent_service, get_service_lookup_service

router = APIRouter()


@router.post("/intent/classify", response_model=IntentClassifyResponse, tags=["Intent"])
async def classify_intent(
    request: IntentClassifyRequest,
    service: IntentService = Depends(get_intent_service),
) -> IntentClassifyResponse:
    """Phase C1: text-only natural-language intent classification.

    Does not look up or return an Official Service Registry match yet -
    that mapping (intent -> service_id, with ranking/confidence over the
    registry catalog) is Phase C2, at POST /intent/resolve below. This
    endpoint only answers "what does the citizen seem to want", not
    "which exact service is that".

    Phase C3: if `request.language` is omitted, the language is
    auto-detected from `text`; if provided, it's treated as authoritative.
    See `language_source`/`language_supported` on the response.
    """
    return await service.classify(request.text, language=request.language)


@router.post("/intent/resolve", response_model=IntentResolveResponse, tags=["Intent"])
async def resolve_intent(
    request: IntentClassifyRequest,
    service: ServiceLookupService = Depends(get_service_lookup_service),
) -> IntentResolveResponse:
    """Phase C2: classifies the request (same logic as /intent/classify)
    and additionally ranks Official Service Registry entries in that
    intent's category against the request text, returning up to
    `INTENT_MAX_SERVICE_MATCHES` candidates most-confident-first.

    Degrades gracefully: an unclassified intent, an intent with no
    associated service category (e.g. a greeting), an unsupported
    language, or an unreachable registry all come back as a 200 with an
    empty `matches` list and a `resolution_note` explaining why - never a
    5xx, per the Phase A "every microservice runs independently"
    requirement.

    Phase C3: candidates are preferred by whether they declare support for
    the resolved language; see ServiceLookupService.resolve's docstring.
    """
    return await service.resolve(request.text, language=request.language)
