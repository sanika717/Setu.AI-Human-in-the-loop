from ..providers.factory import create_provider
from ..services.extraction_service import ExtractionService


def get_extraction_service() -> ExtractionService:
    provider = create_provider()
    return ExtractionService(provider=provider)
