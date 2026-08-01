import json
from typing import Any

import httpx

from ..config import settings
from .base_provider import BaseProvider
from ..utils.exceptions import InvalidResponseError, ProviderError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseProvider):
    """Local Ollama provider using the /api/chat endpoint in JSON mode.

    Ollama runs locally and does not require an API key, so unlike the
    other providers there is no ProviderConfigurationError path here - an
    unreachable Ollama daemon surfaces as a ProviderError instead, which is
    retryable (the daemon may still be starting up).
    """

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.request_timeout_seconds

    async def extract(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert document extraction engine. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
        }
        url = f"{self.base_url.rstrip('/')}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("Ollama request timed out")
            raise ProviderError("Ollama request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("Ollama request failed")
            raise ProviderError(f"Ollama request failed - is Ollama running at {self.base_url}?") from exc

        try:
            data = response.json()
            text = data["message"]["content"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.exception("Ollama returned an invalid response")
            raise InvalidResponseError("Ollama returned an invalid response") from exc
