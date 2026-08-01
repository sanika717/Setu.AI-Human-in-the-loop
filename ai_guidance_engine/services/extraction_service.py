from typing import Any

from ..config import settings
from ..providers.base_provider import BaseProvider
from .confidence_service import ConfidenceService
from .fallback_service import FallbackService
from .parser_service import ParserService
from .prompt_builder import PromptBuilder
from .retry_service import RetryService
from .risk_client import RiskClient, RiskEngineUnavailableError
from ..utils.exceptions import AIExtractionError, InvalidResponseError, ProviderError, RetryExhaustedError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExtractionService:
    """Coordinates prompt building, provider execution, parsing, retries, fallback,
    and a Phase D content-risk scan of whatever text comes out the other end.

    That last step matters because the extraction/fallback output is
    AI-generated (or copied straight out of a source document) free text -
    a field's `value` or `reason` could echo a document that itself
    contains something that looks like an OTP, password, PIN, or CVV. This
    is the guidance-content-generation counterpart to the redirect-time
    check system_orchestrator already runs through risk_engine.
    """

    def __init__(
        self,
        provider: BaseProvider,
        prompt_builder: PromptBuilder | None = None,
        parser_service: ParserService | None = None,
        confidence_service: ConfidenceService | None = None,
        retry_service: RetryService | None = None,
        fallback_service: FallbackService | None = None,
        risk_client: RiskClient | None = None,
    ) -> None:
        self.provider = provider
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser_service = parser_service or ParserService()
        self.confidence_service = confidence_service or ConfidenceService()
        self.retry_service = retry_service or RetryService()
        self.fallback_service = fallback_service or FallbackService(self.confidence_service)
        self.risk_client = risk_client or RiskClient()
        # Populated by _scan_fields_for_risk() on every extract() call, so
        # the API route can surface it on the response without changing
        # extract()'s return type for existing callers/tests.
        self.last_content_risk: dict[str, Any] = {
            "content_risk_verified": True,
            "should_pause_guidance": False,
            "findings": [],
        }

    async def _scan_fields_for_risk(self, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not settings.content_scan_enabled or not fields:
            return fields

        page_text = "\n".join(
            f"{field.get('field', '')}: {field.get('value') or ''} ({field.get('reason', '')})" for field in fields
        )
        if not page_text.strip():
            return fields

        try:
            scan = await self.risk_client.content_scan(page_text)
        except RiskEngineUnavailableError as exc:
            # Fail open, same choice system_orchestrator makes for
            # redirects: one extra microservice being offline shouldn't
            # block every extraction, but it's logged loudly and surfaced
            # via content_risk_verified=False rather than silently ignored.
            logger.warning("Risk Engine unreachable during content scan; failing open: %s", exc)
            self.last_content_risk = {"content_risk_verified": False, "should_pause_guidance": False, "findings": []}
            return fields

        self.last_content_risk = {
            "content_risk_verified": True,
            "should_pause_guidance": scan.get("should_pause_guidance", False),
            "findings": scan.get("findings", []),
        }

        if scan.get("should_pause_guidance"):
            logger.warning(
                "Content scan flagged sensitive-field indicators %s; redacting extracted values",
                scan.get("sensitive_fields_detected"),
            )
            for field in fields:
                field["value"] = None
                field["reason"] = (
                    "Guidance paused: this field's extracted content matched a sensitive-field "
                    "indicator (OTP/password/PIN/CVV). Please review this field directly with the "
                    "applicant instead of via AI extraction."
                )
        return fields

    async def extract(
        self,
        applicant_id: str,
        documents: list[dict[str, Any]],
        service_id: str | None = None,
        target_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        prompt = self.prompt_builder.build_prompt(
            documents, applicant_id, service_id=service_id, target_fields=target_fields
        )

        async def _call_provider() -> dict[str, Any]:
            return await self.provider.extract(prompt)

        try:
            payload = await self.retry_service.execute(_call_provider)
            if not isinstance(payload, dict):
                raise InvalidResponseError("Provider returned a non-object payload")
            source_document = documents[0].get("type", "Unknown") if documents else "Unknown"
            fields = self.parser_service.parse(payload, source_document, self.confidence_service)
            result = [field.model_dump() for field in fields]
        except (RetryExhaustedError, ProviderError, InvalidResponseError) as exc:
            logger.warning("Extraction failed; returning manual review output: %s", exc)
            fields = self.fallback_service.build_manual_review_response(documents, applicant_id)
            result = [field.model_dump() for field in fields]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected extraction failure")
            raise AIExtractionError("Unexpected failure during extraction") from exc

        return await self._scan_fields_for_risk(result)
