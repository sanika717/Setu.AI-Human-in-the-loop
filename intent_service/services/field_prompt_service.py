import json
import re
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_FIELD_PROMPTS_PATH = _DATA_DIR / "field_prompts.json"
_MESSAGES_PATH = _DATA_DIR / "conversation_messages.json"
_LEXICON_PATH = _DATA_DIR / "answer_lexicon.json"

_FALLBACK_LANGUAGE = "en"

_field_prompts_cache: dict[str, dict[str, str]] | None = None
_messages_cache: dict[str, dict[str, str]] | None = None
_lexicon_cache: dict[str, dict[str, list[str]]] | None = None


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _field_prompts() -> dict[str, dict[str, str]]:
    global _field_prompts_cache
    if _field_prompts_cache is None:
        _field_prompts_cache = _load_json(_FIELD_PROMPTS_PATH)["prompts"]
    return _field_prompts_cache


def _messages() -> dict[str, dict[str, str]]:
    global _messages_cache
    if _messages_cache is None:
        _messages_cache = _load_json(_MESSAGES_PATH)["messages"]
    return _messages_cache


def _lexicon() -> dict[str, dict[str, list[str]]]:
    global _lexicon_cache
    if _lexicon_cache is None:
        raw = _load_json(_LEXICON_PATH)
        _lexicon_cache = {"affirmative": raw["affirmative"], "negative": raw["negative"]}
    return _lexicon_cache


def _humanize(field_name: str) -> str:
    """Generic fallback label for a field with no entry in field_prompts.json,
    e.g. `has_active_policy` -> `active policy`. Never raises and never
    needs updating when a new registry field appears - that's the point.
    """

    words = [w for w in re.split(r"[_\s]+", field_name.strip()) if w]
    words = [w for w in words if w.lower() not in ("has", "is", "applicant")]
    return " ".join(words) if words else field_name


def get_field_prompt(field_name: str, language: str, field_type: str) -> str:
    """Returns the question to ask for `field_name`. Prefers an authored
    translation from data/field_prompts.json for `language`, then that
    field's English entry, then a fully generic template built from the
    field name and its inferred type (boolean/numeric/string) - so any
    field a new service introduces in official_service_registry works in a
    conversation immediately, with a better-worded question only if/when
    someone adds one to the data file.
    """

    entry = _field_prompts().get(field_name, {})
    if language in entry:
        return entry[language]
    if _FALLBACK_LANGUAGE in entry:
        return entry[_FALLBACK_LANGUAGE]

    label = _humanize(field_name)
    if field_type == "boolean":
        return f"Regarding {label} - is that true for you? (yes/no)"
    if field_type == "numeric":
        return f"What is your {label}? (please answer with a number)"
    return f"Could you provide your {label}?"


def get_message(key: str, language: str, **placeholders: Any) -> str:
    """Returns a system-authored (non-service-specific) conversation message,
    localized if available, English otherwise, with `{placeholder}` values
    substituted in.
    """

    entry = _messages().get(key, {})
    template = entry.get(language) or entry.get(_FALLBACK_LANGUAGE) or key
    try:
        return template.format(**placeholders)
    except (KeyError, IndexError):  # pragma: no cover - defensive, malformed placeholder
        return template


def affirmative_words(language: str) -> set[str]:
    lex = _lexicon()["affirmative"]
    words = set(lex.get(_FALLBACK_LANGUAGE, []))
    words |= set(lex.get(language, []))
    return {w.lower() for w in words}


def negative_words(language: str) -> set[str]:
    lex = _lexicon()["negative"]
    words = set(lex.get(_FALLBACK_LANGUAGE, []))
    words |= set(lex.get(language, []))
    return {w.lower() for w in words}
