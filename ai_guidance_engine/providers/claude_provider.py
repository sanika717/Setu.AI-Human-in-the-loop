import json
from typing import Any

import httpx

from ..config import settings
from .base_provider import BaseProvider
from ..utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _strip_code_fence(text: str) -> str:
    """Claude does not have a strict JSON-mode like Gemini/OpenAI, so it can
    occasionally wrap output in a ```json ... ``` fence despite instructions
    not to. Strip that defensively before parsing.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()


class ClaudeProvider(BaseProvider):
    """Anthropic Messages API provider."""

    def __init__(self) -> None:
        self.api_key = settings.claude_api_key
        self.model = settings.claude_model
        self.base_url = settings.claude_base_url
        self.api_version = settings.claude_api_version
        self.timeout = settings.request_timeout_seconds

    async def extract(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("CLAUDE_API_KEY (or ANTHROPIC_API_KEY) is not configured")

        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "system": (
                "You are an expert document extraction engine. Respond only with "
                "valid JSON - no prose, no markdown code fences."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/messages"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("Claude request timed out")
            raise ProviderError("Claude request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("Claude request failed")
            raise ProviderError("Claude request failed") from exc

        try:
            data = response.json()
            text = data["content"][0]["text"]
            return json.loads(_strip_code_fence(text))
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.exception("Claude returned an invalid response")
            raise InvalidResponseError("Claude returned an invalid response") from exc
