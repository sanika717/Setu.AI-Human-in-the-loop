from fastapi import APIRouter, Depends, HTTPException

from .dependencies import get_extraction_service
from ..models.request_models import ExtractionRequest
from ..models.response_models import ExtractionResponse
from ..services.extraction_service import ExtractionService
from ..utils.exceptions import AIExtractionError

router = APIRouter()

_PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "GeminiProvider": "Gemini",
    "OpenAIProvider": "OpenAI",
    "ClaudeProvider": "Claude",
    "AzureProvider": "Azure OpenAI",
    "OllamaProvider": "Ollama",
}


@router.post("/extract", response_model=ExtractionResponse, tags=["Extraction"])
async def extract_documents(
    request: ExtractionRequest,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResponse:
    try:
        fields = await service.extract(
            request.applicant_id,
            [document.model_dump() for document in request.documents],
            service_id=request.service_id,
            target_fields=request.target_fields,
        )
        provider_class_name = service.provider.__class__.__name__
        risk = service.last_content_risk
        return ExtractionResponse(
            status="success",
            provider=_PROVIDER_DISPLAY_NAMES.get(provider_class_name, provider_class_name),
            fields=fields,
            content_risk_verified=risk.get("content_risk_verified", True),
            should_pause_guidance=risk.get("should_pause_guidance", False),
            risk_findings=risk.get("findings", []),
        )
    except AIExtractionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
