import json
from typing import Any

import httpx

from ..config import settings
from .base_provider import BaseProvider
from ..utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI Chat Completions provider using JSON-mode structured output."""

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url
        self.timeout = settings.request_timeout_seconds

    async def extract(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert document extraction engine. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("OpenAI request timed out")
            raise ProviderError("OpenAI request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("OpenAI request failed")
            raise ProviderError("OpenAI request failed") from exc

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.exception("OpenAI returned an invalid response")
            raise InvalidResponseError("OpenAI returned an invalid response") from exc
