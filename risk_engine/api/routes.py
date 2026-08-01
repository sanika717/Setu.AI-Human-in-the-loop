from fastapi import APIRouter, Depends

from ..models.request_models import ContentRiskScanRequest, RedirectRiskCheckRequest
from ..models.response_models import ContentRiskScanResponse, RedirectRiskCheckResponse
from ..services.risk_assessment_service import RiskAssessmentService
from .dependencies import get_risk_assessment_service

router = APIRouter()


@router.post("/risk/redirect-check", response_model=RedirectRiskCheckResponse, tags=["Risk"])
async def redirect_check(
    payload: RedirectRiskCheckRequest,
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> RedirectRiskCheckResponse:
    """Verifies HTTPS + the official domain whitelist (sourced live from the
    Official Service Registry) for a redirect Sahaay.AI is about to make,
    plus any intermediate hops already observed. Called by
    system_orchestrator's POST /api/v1/portals/confirm before it hands the
    URL back to the browser.
    """

    return await service.check_redirect(payload.service_id, payload.target_url, payload.redirect_chain)


@router.post("/risk/content-scan", response_model=ContentRiskScanResponse, tags=["Risk"])
async def content_scan(
    payload: ContentRiskScanRequest,
    service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> ContentRiskScanResponse:
    """Scans guidance-step text/labels for sensitive-field indicators (OTP,
    password, PIN, CVV) so the AI Guidance Engine / UI knows to pause and
    let the human act directly on the official site instead.
    """

    return service.scan_content(payload.page_text)
