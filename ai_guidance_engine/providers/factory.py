from ..config import settings
from .azure_provider import AzureProvider
from .base_provider import BaseProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from ..utils.exceptions import ProviderError


def create_provider(provider_name: str | None = None) -> BaseProvider:
    normalized_name = (provider_name or settings.provider_name or "gemini").lower()
    providers: dict[str, type[BaseProvider]] = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "azure": AzureProvider,
        "azure_openai": AzureProvider,
        "ollama": OllamaProvider,
    }

    provider_cls = providers.get(normalized_name)
    if provider_cls is None:
        raise ProviderError(f"Unsupported provider '{provider_name or settings.provider_name}'")
    return provider_cls()
