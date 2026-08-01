import json
from typing import Any, Dict
from .provider_client import OpenAIProvider, ProviderError
from ..core.config import settings


class ExtractionService:
    def __init__(self, provider: OpenAIProvider):
        self.provider = provider

    async def extract(self, text: str, schema: dict) -> dict:
        errors = []
        for attempt in range(settings.provider_retries + 1):
            try:
                result = await self.provider.extract(text, schema)
                if not isinstance(result, dict):
                    raise ProviderError("Provider returned invalid data")
                return self._normalize(result)
            except ProviderError as exc:
                errors.append(str(exc))
                if attempt < settings.provider_retries:
                    continue
                break

        if settings.provider_fallback:
            return self._fallback(text, schema, errors)

        raise ProviderError("Provider extraction failed: " + " | ".join(errors))

    def _normalize(self, data: dict) -> dict:
        if "extracted" in data and isinstance(data["extracted"], dict):
            return data
        return {"extracted": data, "confidence": 0.0}

    def _fallback(self, text: str, schema: dict, errors: list[str]) -> dict:
        return {
            "extracted": {key: None for key in schema.keys()},
            "confidence": 0.0,
            "provider_name": self.provider.name,
            "errors": errors,
        }
