from ..models.field_models import ExtractedField
from .confidence_service import ConfidenceService


class FallbackService:
    """Provides a conservative fallback output when provider fails."""

    def __init__(self, confidence_service: ConfidenceService | None = None) -> None:
        self.confidence_service = confidence_service or ConfidenceService()

    def build_manual_review_response(self, documents: list[dict], applicant_id: str) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        for document in documents:
            doc_type = document.get("type", "Unknown")
            fields.append(
                self.confidence_service.build_field(
                    field_name="Manual Review Required",
                    value=None,
                    source_document=doc_type,
                    reason=f"Provider unavailable for {applicant_id}; human review required",
                )
            )
        return fields
