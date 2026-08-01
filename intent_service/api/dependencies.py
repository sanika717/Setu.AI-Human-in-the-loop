from ..config import settings
from ..providers.base_classifier import BaseIntentClassifier
from ..providers.factory import create_classifier_for_language
from ..services.conversation_manager import ConversationManager
from ..services.conversation_store import get_default_store
from ..services.intent_service import IntentService
from ..services.registry_client import RegistryClient
from ..services.service_lookup_service import ServiceLookupService

_PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "keyword": "Keyword",
}


def _classifier_factory(language: str) -> BaseIntentClassifier | None:
    """Phase C3: resolves a classifier per detected/declared language.

    Only the `keyword` engine is localized today (see
    providers/factory.create_classifier_for_language) - if `INTENT_CLASSIFIER`
    is ever set to something else, this returns None for every language
    until that engine gets a matching per-language branch, same caveat as
    `create_classifier_for_language` itself documents.
    """

    if (settings.classifier_name or "keyword").lower() != "keyword":
        return None
    return create_classifier_for_language(language)


def get_intent_service() -> IntentService:
    display_name = _PROVIDER_DISPLAY_NAMES.get(settings.classifier_name.lower(), settings.classifier_name)
    return IntentService(classifier_factory=_classifier_factory, provider_display_name=display_name)


def get_service_lookup_service() -> ServiceLookupService:
    return ServiceLookupService(intent_service=get_intent_service(), registry_client=RegistryClient())


def get_conversation_manager() -> ConversationManager:
    """Phase C4. Uses the same process-wide in-memory session store for
    every request (see conversation_store.get_default_store) so a
    conversation started on one request can be continued on the next -
    tests construct a ConversationManager directly with their own store
    instead of going through this factory, so they never share state.

    Builds a single RegistryClient and reuses it for both the
    ServiceLookupService (Phase C2's intent -> service ranking) and the
    ConversationManager itself (Phase C4's get_service/check_eligibility
    calls) rather than constructing two separate clients pointed at the
    same registry_base_url - one client per request is enough.
    """

    registry_client = RegistryClient()
    lookup_service = ServiceLookupService(intent_service=get_intent_service(), registry_client=registry_client)
    store = get_default_store(ttl_seconds=settings.conversation_session_ttl_seconds)
    return ConversationManager(
        store=store,
        service_lookup_service=lookup_service,
        registry_client=registry_client,
    )
