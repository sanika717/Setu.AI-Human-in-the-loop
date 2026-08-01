from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Common interface for all LLM providers."""

    @abstractmethod
    async def extract(self, prompt: str) -> dict:
        """Send a prompt to the provider and return a structured response."""
        raise NotImplementedError
