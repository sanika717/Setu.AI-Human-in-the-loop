import re
from typing import Any, Literal

from . import field_prompt_service

FieldType = Literal["boolean", "numeric", "string"]

# Devanagari (Hindi/Marathi), Bengali, Tamil, and Telugu digit blocks, mapped
# to ASCII 0-9, so a citizen answering "६०" or "৬০" for their age works the
# same as "60". This is Unicode digit-block knowledge, the same category of
# fact providers/language_detector.py's _SCRIPT_RANGES already encodes, not
# a business rule - no service/eligibility logic depends on it.
_DIGIT_BLOCKS: dict[str, str] = {
    "\u0966": "0", "\u0967": "1", "\u0968": "2", "\u0969": "3", "\u096a": "4",
    "\u096b": "5", "\u096c": "6", "\u096d": "7", "\u096e": "8", "\u096f": "9",  # Devanagari
    "\u09e6": "0", "\u09e7": "1", "\u09e8": "2", "\u09e9": "3", "\u09ea": "4",
    "\u09eb": "5", "\u09ec": "6", "\u09ed": "7", "\u09ee": "8", "\u09ef": "9",  # Bengali
    "\u0be6": "0", "\u0be7": "1", "\u0be8": "2", "\u0be9": "3", "\u0bea": "4",
    "\u0beb": "5", "\u0bec": "6", "\u0bed": "7", "\u0bee": "8", "\u0bef": "9",  # Tamil
    "\u0c66": "0", "\u0c67": "1", "\u0c68": "2", "\u0c69": "3", "\u0c6a": "4",
    "\u0c6b": "5", "\u0c6c": "6", "\u0c6d": "7", "\u0c6e": "8", "\u0c6f": "9",  # Telugu
}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def infer_field_type(rule: dict[str, Any]) -> FieldType:
    """Infers the expected answer shape for an eligibility rule's `field`
    purely from that rule's `operator`/`value` - the same data
    official_service_registry already stores, so a new service never needs
    a matching code change here.
    """

    operator = rule.get("operator")
    value = rule.get("value")

    if operator in ("gte", "lte", "gt", "lt"):
        return "numeric"
    if operator in ("eq", "ne") and isinstance(value, bool):
        return "boolean"
    if operator in ("eq", "ne") and isinstance(value, (int, float)):
        return "numeric"
    return "string"


def _normalize_digits(text: str) -> str:
    return "".join(_DIGIT_BLOCKS.get(char, char) for char in text)


def parse_number(text: str) -> float | int | None:
    match = _NUMBER_RE.search(_normalize_digits(text))
    if not match:
        return None
    raw = match.group()
    value = float(raw)
    return int(value) if value.is_integer() else value


def parse_boolean(text: str, language: str) -> bool | None:
    normalized = text.strip().lower()
    words = set(re.split(r"\s+", normalized))
    if words & field_prompt_service.affirmative_words(language):
        return True
    if words & field_prompt_service.negative_words(language):
        return False
    return None


def parse_answer(text: str, field_type: FieldType, language: str) -> tuple[bool, Any]:
    """Returns (parsed_successfully, value). On failure, value is None and
    the caller should re-ask rather than storing a garbage answer.
    """

    if field_type == "boolean":
        result = parse_boolean(text, language)
        return (result is not None, result)
    if field_type == "numeric":
        result = parse_number(text)
        return (result is not None, result)
    stripped = text.strip()
    return (bool(stripped), stripped or None)
