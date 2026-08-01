from typing import Callable

from ..config import settings
from ..models.response_models import IntentCandidate, IntentClassifyResponse
from ..providers.base_classifier import BaseIntentClassifier
from ..providers.language_detector import LANGUAGE_NAMES, detect_language
from ..utils.logger import get_logger

logger = get_logger(__name__)

UNCLASSIFIED_INTENT_ID = "unclassified"
UNCLASSIFIED_LABEL = "Could not confidently determine intent"
UNSUPPORTED_LANGUAGE_LABEL = "This language is not supported for intent classification yet"
UNRECOGNIZED_LANGUAGE_LABEL = "Unrecognized language code; could not classify"

HIGH_CONFIDENCE_THRESHOLD = 0.7
MEDIUM_CONFIDENCE_THRESHOLD = 0.4

# A per-language classifier factory: given an ISO 639-1 code, returns a
# classifier built for that language's taxonomy, or None if Sahaay.AI has
# no taxonomy for it yet. See providers/factory.create_classifier_for_language.
ClassifierFactory = Callable[[str], BaseIntentClassifier | None]


def _confidence_level(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "High"
    if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "Medium"
    return "Low"


class IntentService:
    """Coordinates a classifier provider, normalizes its raw scores into
    confidences, and applies the minimum-confidence threshold below which
    a request is reported as "unclassified" rather than guessed at.

    Normalization is a simple share-of-total-score (raw_score / sum of all
    raw scores) rather than a true probability model - appropriate for a
    deterministic keyword classifier, and easy to swap out alongside the
    classifier itself later without changing this class's public shape.

    Phase C3 adds language routing: `classify()` now detects (or accepts a
    declared) language and asks a per-language classifier for the score.
    Two construction modes are supported so Phase C1/C2 callers don't
    break:

    - `classifier=` (legacy, still usable by anything not yet language-aware):
      a single fixed classifier, used only when the resolved language is
      "en" - the language that classifier's taxonomy was built for. Any
      other detected/declared language reports unsupported rather than
      silently scoring foreign-language text against English keywords.
    - `classifier_factory=` (Phase C3): a callable that resolves the right
      classifier per detected/declared language, returning None when a
      language isn't supported yet. This is what api/dependencies.py wires
      up now; see `providers.factory.create_classifier_for_language`.
    """

    def __init__(
        self,
        classifier: BaseIntentClassifier | None = None,
        classifier_factory: ClassifierFactory | None = None,
        provider_display_name: str = "Keyword",
    ) -> None:
        if classifier is None and classifier_factory is None:
            raise ValueError("IntentService requires either `classifier` or `classifier_factory`")
        self._fixed_classifier = classifier
        self._classifier_factory = classifier_factory
        self.provider_display_name = provider_display_name

    def _classifier_for(self, language: str) -> BaseIntentClassifier | None:
        if self._classifier_factory is not None:
            return self._classifier_factory(language)
        return self._fixed_classifier if language == "en" else None

    async def classify(self, text: str, language: str | None = None) -> IntentClassifyResponse:
        if language:
            normalized_code = language.strip().lower()
            if normalized_code not in LANGUAGE_NAMES:
                logger.info("Declared language '%s' is not a recognized code; reporting unclassified", language)
                return IntentClassifyResponse(
                    provider=self.provider_display_name,
                    text=text,
                    language=normalized_code,
                    language_name=normalized_code,
                    language_source="declared",
                    language_detection_confidence=1.0,
                    language_supported=False,
                    detected_intent=UNCLASSIFIED_INTENT_ID,
                    label=UNRECOGNIZED_LANGUAGE_LABEL,
                    confidence=0.0,
                    confidence_level="Low",
                    alternate_intents=[],
                )
            resolved_language = normalized_code
            resolved_language_name = LANGUAGE_NAMES[normalized_code]
            language_source = "declared"
            language_detection_confidence = 1.0
        else:
            detection = detect_language(text)
            resolved_language = detection.language
            resolved_language_name = detection.language_name
            language_source = "detected"
            language_detection_confidence = detection.confidence

        classifier = self._classifier_for(resolved_language)
        if classifier is None:
            logger.info("No taxonomy available for language '%s'; reporting unclassified", resolved_language)
            return IntentClassifyResponse(
                provider=self.provider_display_name,
                text=text,
                language=resolved_language,
                language_name=resolved_language_name,
                language_source=language_source,
                language_detection_confidence=language_detection_confidence,
                language_supported=False,
                detected_intent=UNCLASSIFIED_INTENT_ID,
                label=UNSUPPORTED_LANGUAGE_LABEL,
                confidence=0.0,
                confidence_level="Low",
                alternate_intents=[],
            )

        raw_scores = await classifier.score_intents(text)

        common_kwargs = dict(
            provider=self.provider_display_name,
            text=text,
            language=resolved_language,
            language_name=resolved_language_name,
            language_source=language_source,
            language_detection_confidence=language_detection_confidence,
            language_supported=True,
        )

        if not raw_scores:
            return IntentClassifyResponse(
                **common_kwargs,
                detected_intent=UNCLASSIFIED_INTENT_ID,
                label=UNCLASSIFIED_LABEL,
                confidence=0.0,
                confidence_level="Low",
                alternate_intents=[],
            )

        total = sum(score.raw_score for score in raw_scores)
        ranked = sorted(raw_scores, key=lambda score: score.raw_score, reverse=True)
        candidates = [
            IntentCandidate(intent_id=score.intent_id, label=score.label, confidence=score.raw_score / total)
            for score in ranked
        ]

        top = candidates[0]
        alternates = candidates[1:]

        if top.confidence < settings.min_confidence_threshold:
            logger.info(
                "Top intent '%s' scored %.2f, below the %.2f threshold; reporting unclassified",
                top.intent_id,
                top.confidence,
                settings.min_confidence_threshold,
            )
            return IntentClassifyResponse(
                **common_kwargs,
                detected_intent=UNCLASSIFIED_INTENT_ID,
                label=UNCLASSIFIED_LABEL,
                confidence=top.confidence,
                confidence_level=_confidence_level(top.confidence),
                alternate_intents=candidates,
            )

        return IntentClassifyResponse(
            **common_kwargs,
            detected_intent=top.intent_id,
            label=top.label,
            confidence=top.confidence,
            confidence_level=_confidence_level(top.confidence),
            alternate_intents=alternates,
        )
