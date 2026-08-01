import re

from pydantic import BaseModel, Field

# Unicode script blocks for the languages official_service_registry already
# declares support for (see services.json's `supported_languages` values),
# plus English/Latin as the default. Each language is identified by its
# ISO 639-1 code. Scripts are checked by counting codepoints that fall in
# each block - the block with the most hits wins. This is a real,
# deterministic, fully offline technique (no model, no network call), the
# same "no external dependency for the default path" principle Phase C1's
# keyword classifier already follows.
_SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "devanagari": (0x0900, 0x097F),  # Hindi, Marathi (disambiguated below)
    "bengali": (0x0980, 0x09FF),
    "tamil": (0x0B80, 0x0BFF),
    "telugu": (0x0C00, 0x0C7F),
}

_SCRIPT_TO_LANGUAGE: dict[str, str] = {
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
}

# ISO 639-1 code -> display name, for every language this module can ever
# return, plus every language a caller may legally *declare* on a request
# (see IntentClassifyRequest.language). Kept here rather than duplicated in
# intent_service.py so there is exactly one source of truth for "which
# languages does Sahaay.AI know the name of".
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
}

# Devanagari is shared by Hindi and Marathi, so script alone can't tell them
# apart. These are common Marathi function words/verb forms that either
# don't occur in Hindi or occur far less often than their Hindi
# equivalents (e.g. Marathi "आहे"/"आहेत" for "is"/"are" vs Hindi "है"/"हैं";
# Marathi possessive suffixes "चा"/"ची"/"चे" vs Hindi "का"/"की"/"के"). Any
# hit tips the classification to Marathi; otherwise Devanagari text
# defaults to Hindi, the more widely used of the two on this platform.
_MARATHI_MARKERS = re.compile(r"(आहे|आहेत|माझे|माझा|तुमचे|कशी|कसे|यांचे|\bचा\b|\bची\b|\bचे\b)")

_LATIN_RE = re.compile(r"[A-Za-z]")


class LanguageDetectionResult(BaseModel):
    language: str = Field(..., description="ISO 639-1 code, e.g. 'en', 'hi'")
    language_name: str
    script: str = Field(
        ..., description="'latin', 'devanagari', 'bengali', 'tamil', 'telugu', or 'declared'"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Share of script-classifiable characters that matched the winning script"
    )


def _script_char_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {script: 0 for script in _SCRIPT_RANGES}
    for char in text:
        codepoint = ord(char)
        for script, (start, end) in _SCRIPT_RANGES.items():
            if start <= codepoint <= end:
                counts[script] += 1
                break
    return counts


def detect_language(text: str) -> LanguageDetectionResult:
    """Detects the dominant script in `text` and maps it to a language.

    Falls back to English/Latin whenever no non-Latin script block has any
    hits at all (including empty or punctuation-only input) - the safe
    default given this platform's primary audience and existing English
    taxonomy. Devanagari text is further disambiguated into Hindi vs
    Marathi via `_MARATHI_MARKERS`; every other supported script maps to
    exactly one language so no further disambiguation is needed.
    """

    script_counts = _script_char_counts(text)
    latin_count = len(_LATIN_RE.findall(text))
    total_classifiable = sum(script_counts.values()) + latin_count

    if total_classifiable == 0:
        return LanguageDetectionResult(language="en", language_name="English", script="latin", confidence=0.0)

    winning_script, winning_count = max(script_counts.items(), key=lambda item: item[1])

    if winning_count == 0 or latin_count >= winning_count:
        confidence = latin_count / total_classifiable
        return LanguageDetectionResult(
            language="en", language_name="English", script="latin", confidence=round(confidence, 4)
        )

    confidence = round(winning_count / total_classifiable, 4)

    if winning_script == "devanagari":
        if _MARATHI_MARKERS.search(text):
            return LanguageDetectionResult(
                language="mr", language_name="Marathi", script="devanagari", confidence=confidence
            )
        return LanguageDetectionResult(
            language="hi", language_name="Hindi", script="devanagari", confidence=confidence
        )

    language = _SCRIPT_TO_LANGUAGE[winning_script]
    return LanguageDetectionResult(
        language=language, language_name=LANGUAGE_NAMES[language], script=winning_script, confidence=confidence
    )
