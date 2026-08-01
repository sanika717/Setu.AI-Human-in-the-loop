from abc import ABC, abstractmethod

from pydantic import BaseModel


class IntentScore(BaseModel):
    """One (intent_id, label, raw_score) candidate before normalization to a confidence."""

    intent_id: str
    label: str
    raw_score: float


class BaseIntentClassifier(ABC):
    """Common interface for all intent classifiers.

    Mirrors ai_guidance_engine.providers.base_provider.BaseProvider's shape
    deliberately: swapping the classification strategy (keyword-based today,
    an LLM-backed or multilingual one later in Phase C3) should never
    require touching IntentService, the API route, or the response model.
    """

    @abstractmethod
    async def score_intents(self, text: str) -> list[IntentScore]:
        """Return every intent with a non-zero raw score, unsorted."""
        raise NotImplementedError
