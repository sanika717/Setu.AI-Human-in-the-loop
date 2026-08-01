import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Intent Service")
    api_version: str = os.getenv("API_VERSION", "v1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    allowed_origins: list[str] = field(default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["*"]))

    # Which IntentClassifier implementation to use. "keyword" (the Phase C1
    # default) needs no external API and no network - it scores text
    # against a hand-authored keyword taxonomy. This is the same
    # provider-factory shape as ai_guidance_engine's AI providers, so a
    # future LLM-backed classifier can be dropped in later (e.g. for Phase
    # C3 multilingual support) without changing IntentService or the API.
    classifier_name: str = os.getenv("INTENT_CLASSIFIER", "keyword")

    # Below this confidence, the top-scoring intent is reported as
    # "unclassified" rather than guessed at - Phase C2 (service lookup)
    # should not be handed a low-confidence guess to act on.
    min_confidence_threshold: float = _env_float("INTENT_MIN_CONFIDENCE", 0.2)

    # Phase C2: Official Service Registry (official_service_registry) - the
    # live catalog POST /api/v1/intent/resolve ranks against. This service
    # calls it fresh on every /resolve request rather than caching its own
    # copy, so a new/edited service in services.json is matchable
    # immediately with no redeploy of intent_service.
    registry_base_url: str = os.getenv("REGISTRY_BASE_URL", "http://127.0.0.1:8004")
    registry_timeout_seconds: float = _env_float("REGISTRY_TIMEOUT_SECONDS", 5.0)

    # Maximum number of ranked service candidates POST /api/v1/intent/resolve
    # returns, most confident first.
    max_service_matches: int = int(os.getenv("INTENT_MAX_SERVICE_MATCHES", "3"))

    # Phase C4: conversation layer (services/conversation_manager.py).
    # How long an idle conversation session is kept in memory before the
    # in-memory store treats it as gone (see services/conversation_store.py).
    conversation_session_ttl_seconds: float = _env_float("CONVERSATION_SESSION_TTL_SECONDS", 1800.0)

    # How many consecutive turns the conversation layer will keep asking
    # "what do you need help with" before giving up and reporting
    # needs_human_help, rather than looping on an unclassifiable request
    # forever.
    conversation_max_clarification_attempts: int = int(os.getenv("CONVERSATION_MAX_CLARIFICATION_ATTEMPTS", "3"))

    # Same idea, but for "which of these services did you mean" during
    # disambiguation - after this many unmatched replies, the top-ranked
    # candidate is used automatically so the conversation can still finish.
    conversation_max_disambiguation_attempts: int = int(os.getenv("CONVERSATION_MAX_DISAMBIGUATION_ATTEMPTS", "3"))

    # Same idea again, per eligibility field - after this many
    # unparseable answers to the same follow-up question, that field is
    # recorded as unknown (None) and the conversation moves on rather than
    # blocking indefinitely on one question.
    conversation_max_field_attempts: int = int(os.getenv("CONVERSATION_MAX_FIELD_ATTEMPTS", "3"))

    # When /intent/resolve returns more than one candidate service, the top
    # candidate is accepted automatically (skipping disambiguation) only if
    # its match_confidence leads the runner-up by at least this much;
    # otherwise the conversation asks the citizen to pick.
    conversation_disambiguation_confidence_gap: float = _env_float("CONVERSATION_DISAMBIGUATION_CONFIDENCE_GAP", 0.34)


settings = Settings()
