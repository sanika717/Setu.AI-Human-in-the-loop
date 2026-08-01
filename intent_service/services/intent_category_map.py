from ..providers.keyword_classifier import load_taxonomy


def _build_intent_category_map() -> dict[str, str | None]:
    return {intent["intent_id"]: intent.get("service_category_hint") for intent in load_taxonomy()}


_INTENT_CATEGORY_MAP: dict[str, str | None] = _build_intent_category_map()


def category_hint_for_intent(intent_id: str) -> str | None:
    """Returns the `service_category_hint` declared in data/intents.json for
    `intent_id`, or None if the intent has no category (e.g. "greeting",
    "general_help", "application_status_check") or isn't recognized at all
    (e.g. "unclassified").
    """

    return _INTENT_CATEGORY_MAP.get(intent_id)
