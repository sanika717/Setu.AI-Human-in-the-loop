import re

from ..config import settings
from ..models.response_models import IntentResolveResponse, ServiceMatch
from ..utils.exceptions import RegistryUnavailableError
from ..utils.logger import get_logger
from .intent_category_map import category_hint_for_intent
from .intent_service import UNCLASSIFIED_INTENT_ID, IntentService
from .registry_client import RegistryClient

logger = get_logger(__name__)

# Common words that carry no service-distinguishing signal - excluded from
# the word-overlap ranking so "update", "my", "for", etc. don't inflate a
# match score just because they appear in almost every request and almost
# every service description. English-only: non-English requests are ranked
# using the same word-overlap logic against each service's (English)
# service_name/description, so an unfiltered non-English stopword list
# would do nothing useful there anyway - see `_significant_words`.
_STOPWORDS = {
    "a", "an", "and", "apply", "at", "for", "how", "i", "in", "is", "it",
    "me", "my", "need", "of", "on", "or", "please", "the", "to", "want",
    "update", "with",
}


def _significant_words(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", text.lower())
    return {word for word in normalized.split() if word and word not in _STOPWORDS}


class ServiceLookupService:
    """Phase C2: given classified-intent output, ranks Official Service
    Registry entries in that intent's `service_category_hint` category
    against the original request text.

    Ranking is a simple, deterministic word-overlap score - the count of
    significant words shared between the request text and each service's
    `service_name` + `description` + `service_id` (underscores split into
    words), normalized the same "share of total score" way
    IntentService.classify() normalizes intent scores, so confidence means
    the same thing in both endpoints. If nothing distinguishes the
    candidates (no word overlap with any of them), every service in the
    category is still returned, in registry order, with a "Low" confidence
    and a `match_reason` that says so explicitly rather than pretending a
    ranking exists where none does.

    Phase C3: `resolve()` now accepts an optional `language`, threaded
    straight through to `IntentService.classify()` for detection/routing.
    Once a category is known, candidates are further preferred by whether
    the service declares that language in its own `supported_languages`
    (official_service_registry/data/services.json) - a service the citizen
    can't actually be guided through in their language is a worse match
    than one that supports it, even if the word-overlap score is equal.
    If *no* service in the category supports the resolved language, the
    full unfiltered category list is used instead (with a note explaining
    why) rather than returning nothing - a citizen guided in English is
    still better served than being told no service exists at all.
    """

    def __init__(self, intent_service: IntentService, registry_client: RegistryClient | None = None) -> None:
        self.intent_service = intent_service
        self.registry_client = registry_client or RegistryClient()

    def _score_candidate(self, query_words: set[str], service: dict) -> tuple[int, list[str]]:
        candidate_words = _significant_words(
            f"{service.get('service_name', '')} {service.get('description', '')} "
            f"{service.get('service_id', '').replace('_', ' ')}"
        )
        overlap = sorted(query_words & candidate_words)
        return len(overlap), overlap

    async def resolve(self, text: str, language: str | None = None) -> IntentResolveResponse:
        classification = await self.intent_service.classify(text, language=language)

        base_kwargs = dict(
            text=classification.text,
            language=classification.language,
            language_name=classification.language_name,
            language_source=classification.language_source,
            language_detection_confidence=classification.language_detection_confidence,
            language_supported=classification.language_supported,
            detected_intent=classification.detected_intent,
            label=classification.label,
            confidence=classification.confidence,
            confidence_level=classification.confidence_level,
        )

        if not classification.language_supported:
            return IntentResolveResponse(
                **base_kwargs,
                service_category=None,
                matches=[],
                registry_available=True,
                resolution_note=(
                    f"Language '{classification.language}' is not supported for intent "
                    "classification yet, so no service category could be determined."
                ),
            )

        if classification.detected_intent == UNCLASSIFIED_INTENT_ID:
            return IntentResolveResponse(
                **base_kwargs,
                service_category=None,
                matches=[],
                registry_available=True,
                resolution_note="Intent could not be classified, so no service category to search.",
            )

        category = category_hint_for_intent(classification.detected_intent)
        if category is None:
            return IntentResolveResponse(
                **base_kwargs,
                service_category=None,
                matches=[],
                registry_available=True,
                resolution_note=(
                    f"Intent '{classification.detected_intent}' has no associated service "
                    "category (e.g. greeting, general help, status check) - there is no "
                    "single service to direct the citizen to."
                ),
            )

        try:
            services = await self.registry_client.list_services(category=category)
        except RegistryUnavailableError:
            logger.warning(
                "Official Service Registry unreachable; cannot resolve services for category=%s",
                category,
            )
            return IntentResolveResponse(
                **base_kwargs,
                service_category=category,
                matches=[],
                registry_available=False,
                resolution_note=(
                    "Could not reach the Official Service Registry, so no service matches "
                    "could be looked up right now."
                ),
            )

        if not services:
            return IntentResolveResponse(
                **base_kwargs,
                service_category=category,
                matches=[],
                registry_available=True,
                resolution_note=f"No registered services found in category '{category}'.",
            )

        language_note = ""
        language_filtered = [
            service
            for service in services
            if classification.language in (service.get("supported_languages") or [])
        ]
        if language_filtered:
            services = language_filtered
        elif classification.language != "en":
            language_note = (
                f" No '{category}' service declares support for "
                f"'{classification.language_name}' yet, so every '{category}' service is "
                "shown instead."
            )

        query_words = _significant_words(text)
        scored: list[tuple[int, list[str], dict]] = [
            (*self._score_candidate(query_words, service), service) for service in services
        ]
        total_overlap = sum(score for score, _, _ in scored)
        scored.sort(key=lambda item: item[0], reverse=True)

        matches: list[ServiceMatch] = []
        for score, overlap_words, service in scored[: settings.max_service_matches]:
            if total_overlap > 0:
                confidence = score / total_overlap if score > 0 else 0.0
                reason = (
                    f"Matched on: {', '.join(overlap_words)}"
                    if overlap_words
                    else "In the matched category, but no shared keywords with this request"
                )
            else:
                # Nobody in the category shares a word with the request text -
                # fall back to an even, low-confidence listing of the whole
                # category rather than fabricating a ranking.
                confidence = round(1.0 / len(services), 4)
                reason = f"No distinguishing keywords found; showing all '{category}' services"
            matches.append(
                ServiceMatch(
                    service_id=service["service_id"],
                    service_name=service["service_name"],
                    category=service["category"],
                    description=service.get("description", ""),
                    official_url=service["official_url"],
                    match_confidence=round(confidence, 4),
                    match_reason=reason,
                )
            )

        note = (
            "" if total_overlap > 0
            else f"No keyword overlap within category '{category}'; showing all matches evenly ranked."
        )
        note = f"{note}{language_note}".strip()

        return IntentResolveResponse(
            **base_kwargs,
            service_category=category,
            matches=matches,
            registry_available=True,
            resolution_note=note,
        )
