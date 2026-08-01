import json
import os
from typing import Any

import httpx

from ..config import settings
from .base_provider import BaseProvider
from ..utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GeminiProvider(BaseProvider):
    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model = settings.gemini_model
        self.base_url = settings.gemini_base_url
        self.timeout = settings.request_timeout_seconds

    async def extract(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("GEMINI_API_KEY is not configured")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("Gemini request timed out")
            raise ProviderError("Gemini request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("Gemini request failed")
            raise ProviderError("Gemini request failed") from exc

        try:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.exception("Gemini returned an invalid response")
            raise InvalidResponseError("Gemini returned an invalid response") from exc
