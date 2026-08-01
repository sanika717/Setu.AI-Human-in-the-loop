import json
import httpx
from typing import Any, Dict
from ..core.config import settings


class ProviderError(Exception):
    pass


class OpenAIProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.name = "openai"

    async def extract(self, text: str, schema: dict) -> dict:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured")

        prompt = self._build_prompt(text, schema)
        payload = {
            "model": "gpt-4o-mini",
            "input": prompt,
            "max_output_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _build_prompt(self, text: str, schema: dict) -> str:
        return (
            "Extract the requested fields from the following text using JSON format. "
            "If a field is missing, return null. Text:\n" + text + "\nSchema:\n" + str(schema)
        )

    def _parse_response(self, data: dict) -> dict:
        output = data.get("output", [])
        if not output:
            raise ProviderError("No output returned from OpenAI")
        content = output[0].get("content", "")
        try:
            return json.loads(content)
        except Exception as exc:
            raise ProviderError("Failed to parse OpenAI response") from exc
