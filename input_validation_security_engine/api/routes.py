from fastapi import APIRouter, Depends, HTTPException

from .dependencies import get_registry_client, get_validation_orchestrator
from ..models.document_types import SUPPORTED_DOCUMENT_TYPES
from ..models.request_models import DocumentValidationRequest
from ..models.response_models import ValidationResponse
from ..services.registry_client import RegistryClient, RegistryUnavailableError
from ..services.validation_orchestrator import ValidationOrchestrator
from ..utils.exceptions import DocumentValidationError

router = APIRouter()


@router.post("/validate", response_model=ValidationResponse, tags=["Validation"])
async def validate_documents(
    request: DocumentValidationRequest,
    orchestrator: ValidationOrchestrator = Depends(get_validation_orchestrator),
) -> ValidationResponse:
    try:
        return orchestrator.validate(request)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/document-types", tags=["Reference"])
async def list_document_types() -> dict:
    """Reference endpoint describing the supported document catalog, so callers
    (frontend, the Trust & Governance Engine, or the AI Guidance Engine) don't
    have to hardcode document type lists independently.

    As of Phase B, required-document lists and eligibility rules are no
    longer part of this catalog - they are per-service and owned by the
    Official Service Registry. See GET /api/v1/services below.
    """
    return {"supported_document_types": sorted(SUPPORTED_DOCUMENT_TYPES)}


@router.get("/services", tags=["Reference"])
async def list_services(registry_client: RegistryClient = Depends(get_registry_client)) -> list[dict]:
    """Thin pass-through to the Official Service Registry's service catalog,
    so a caller only needs to know about this engine's base URL to discover
    which `service_id` values are valid for `POST /validate`.
    """
    try:
        return registry_client.list_services()
    except RegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Official Service Registry unavailable: {exc}") from exc
