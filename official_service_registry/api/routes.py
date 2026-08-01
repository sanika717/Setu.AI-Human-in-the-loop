from fastapi import APIRouter, Depends, HTTPException

from .dependencies import get_repository, get_workflow_engine
from ..models.schemas import (
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    MissingDocumentsRequest,
    MissingDocumentsResponse,
    RedirectInfoResponse,
    ServiceDefinition,
    ServiceSummary,
    WorkflowStepsResponse,
)
from ..services.repository import ServiceRepository
from ..services.workflow_engine import WorkflowEngine
from ..utils.exceptions import ServiceNotFoundError

router = APIRouter()


def _not_found(exc: ServiceNotFoundError) -> None:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/services", response_model=list[ServiceSummary], tags=["Services"])
async def list_services(engine: WorkflowEngine = Depends(get_workflow_engine)) -> list[ServiceSummary]:
    """Every government/banking service Sahaay.AI currently knows how to
    guide a user through. Adding a service to services.json makes it show
    up here immediately - no deploy/code change required.
    """
    services = engine.list_services()
    return [
        ServiceSummary(
            service_id=s.service_id,
            service_name=s.service_name,
            category=s.category,
            description=s.description,
            official_url=s.official_url,
            supported_languages=s.supported_languages,
        )
        for s in services
    ]


@router.get("/services/{service_id}", response_model=ServiceDefinition, tags=["Services"])
async def get_service(service_id: str, engine: WorkflowEngine = Depends(get_workflow_engine)) -> ServiceDefinition:
    try:
        return engine.get_service(service_id)
    except ServiceNotFoundError as exc:
        _not_found(exc)


@router.post(
    "/services/{service_id}/missing-documents",
    response_model=MissingDocumentsResponse,
    tags=["Services"],
)
async def missing_documents(
    service_id: str, payload: MissingDocumentsRequest, engine: WorkflowEngine = Depends(get_workflow_engine)
) -> MissingDocumentsResponse:
    try:
        return engine.missing_documents(service_id, payload.submitted_document_types)
    except ServiceNotFoundError as exc:
        _not_found(exc)


@router.post(
    "/services/{service_id}/eligibility",
    response_model=EligibilityCheckResponse,
    tags=["Services"],
)
async def check_eligibility(
    service_id: str, payload: EligibilityCheckRequest, engine: WorkflowEngine = Depends(get_workflow_engine)
) -> EligibilityCheckResponse:
    try:
        return engine.check_eligibility(service_id, payload.applicant_context)
    except ServiceNotFoundError as exc:
        _not_found(exc)


@router.get(
    "/services/{service_id}/redirect",
    response_model=RedirectInfoResponse,
    tags=["Services"],
)
async def redirect_info(service_id: str, engine: WorkflowEngine = Depends(get_workflow_engine)) -> RedirectInfoResponse:
    """Returns exactly the official URL + domain whitelist the caller (the
    System Orchestrator's /portals endpoints, or the Security Shield in
    Phase D) needs to redirect the user and verify they stayed on the real
    site. Sahaay.AI never returns anything else to redirect a user to.
    """
    try:
        return engine.redirect_info(service_id)
    except ServiceNotFoundError as exc:
        _not_found(exc)


@router.get(
    "/services/{service_id}/workflow",
    response_model=WorkflowStepsResponse,
    tags=["Services"],
)
async def workflow_steps(service_id: str, engine: WorkflowEngine = Depends(get_workflow_engine)) -> WorkflowStepsResponse:
    try:
        return engine.workflow_steps(service_id)
    except ServiceNotFoundError as exc:
        _not_found(exc)


@router.post("/admin/reload", tags=["Admin"])
async def reload_registry(repository: ServiceRepository = Depends(get_repository)) -> dict:
    """Re-reads services.json from disk without restarting the process -
    useful when a product/policy owner edits the config file directly.
    """
    repository.reload()
    return {"status": "ok", "service_count": len(repository.list_services())}
