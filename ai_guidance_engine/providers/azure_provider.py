import json
from typing import Any

import httpx

from ..config import settings
from .base_provider import BaseProvider
from ..utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AzureProvider(BaseProvider):
    """Azure OpenAI Chat Completions provider (deployment-based routing)."""

    def __init__(self) -> None:
        self.api_key = settings.azure_openai_api_key
        self.endpoint = settings.azure_openai_endpoint
        self.deployment = settings.azure_openai_deployment
        self.api_version = settings.azure_openai_api_version
        self.timeout = settings.request_timeout_seconds

    async def extract(self, prompt: str) -> dict[str, Any]:
        if not self.api_key or not self.endpoint or not self.deployment:
            raise ProviderConfigurationError(
                "AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT must all be configured"
            )

        payload = {
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
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        base = self.endpoint.rstrip("/")
        url = f"{base}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("Azure OpenAI request timed out")
            raise ProviderError("Azure OpenAI request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("Azure OpenAI request failed")
            raise ProviderError("Azure OpenAI request failed") from exc

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.exception("Azure OpenAI returned an invalid response")
            raise InvalidResponseError("Azure OpenAI returned an invalid response") from exc
