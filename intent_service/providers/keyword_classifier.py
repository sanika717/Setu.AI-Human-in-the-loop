import json
import re
import unicodedata
from pathlib import Path

from .base_classifier import BaseIntentClassifier, IntentScore

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_PATH = _DATA_DIR / "intents.json"

# Phase C3: one taxonomy file per supported language, mirroring the ISO
# 639-1 codes providers/language_detector.py can return (and that
# official_service_registry/data/services.json's `supported_languages`
# already uses). "en" keeps pointing at the original Phase C1 file rather
# than a duplicate - there is exactly one English taxonomy.
LANGUAGE_TAXONOMY_FILES: dict[str, Path] = {
    "en": _DATA_PATH,
    "hi": _DATA_DIR / "intents_hi.json",
    "mr": _DATA_DIR / "intents_mr.json",
    "bn": _DATA_DIR / "intents_bn.json",
    "ta": _DATA_DIR / "intents_ta.json",
    "te": _DATA_DIR / "intents_te.json",
}

# Loaded lazily and cached per language - each file is small and immutable
# for the process lifetime, so re-parsing it on every request would be pure
# waste (same reasoning Phase C1/C2 relied on by loading the English file
# once at classifier construction time).
_TAXONOMY_CACHE: dict[str, list[dict]] = {}


def _load_taxonomy(path: Path = _DATA_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["intents"]


def load_taxonomy(path: Path = _DATA_PATH) -> list[dict]:
    """Public wrapper around `_load_taxonomy`, used outside this module by
    Phase C2's `services/intent_category_map.py` to read each intent's
    `service_category_hint` without duplicating the JSON-loading logic.

    Deliberately still defaults to the English taxonomy: every localized
    taxonomy file declares the exact same `intent_id` -> `service_category_hint`
    mapping as data/intents.json (see each file's `_comment`), so building
    the category map from any one of them - English included - is
    sufficient and there's no need to re-derive it per language.
    """

    return _load_taxonomy(path)


def taxonomy_for_language(language: str) -> list[dict] | None:
    """Returns the keyword taxonomy for `language` (an ISO 639-1 code), or
    None if no taxonomy is registered for that language yet. Used by
    providers/factory.create_classifier_for_language to build a
    per-language KeywordIntentClassifier.
    """

    path = LANGUAGE_TAXONOMY_FILES.get(language)
    if path is None:
        return None
    if language not in _TAXONOMY_CACHE:
        _TAXONOMY_CACHE[language] = _load_taxonomy(path)
    return _TAXONOMY_CACHE[language]


def _normalize(text: str) -> str:
    # Lowercase and collapse anything that isn't a letter, a combining mark,
    # a digit, or whitespace into a single space, so punctuation never
    # breaks a phrase match (e.g. "pension?" or "pension," still matches
    # the "pension" keyword, and Hindi's danda "।" doesn't glue two words
    # together) while word boundaries between distinct words are preserved.
    #
    # This can't use regex's `\w` shorthand: `\w` matches only characters
    # str.isalnum() considers alphanumeric, which excludes Unicode
    # *combining marks* (category "Mn", e.g. Devanagari/Bengali/Tamil/
    # Telugu vowel signs and the anusvara). Stripping those would silently
    # corrupt every non-Latin keyword phrase Phase C3 added (e.g. Hindi
    # "पेंशन" would lose its "े"/"ं" matras and stop matching at all), so
    # this keeps every Unicode category starting with "L" (letter), "M"
    # (mark), or "N" (number) explicitly instead.
    lowered = text.lower()
    kept_chars = [
        char if (unicodedata.category(char)[0] in ("L", "M", "N") or char.isspace()) else " "
        for char in lowered
    ]
    return re.sub(r"\s+", " ", "".join(kept_chars)).strip()


class KeywordIntentClassifier(BaseIntentClassifier):
    """Scores text against a hand-authored keyword taxonomy (data/intents.json,
    or a language-specific data/intents_<code>.json - see LANGUAGE_TAXONOMY_FILES).

    Each intent's score is the sum of the weights of every keyword phrase
    found in the (normalized) input text, matched on word boundaries so
    "pan" doesn't match inside "expansion". This is intentionally simple
    and fully offline/deterministic - the right default for Phase C1 (no
    external API key or network call needed to classify a citizen's
    request), with the same interface an LLM-backed classifier can drop
    into later without any caller-side change.
    """

    def __init__(self, taxonomy: list[dict] | None = None) -> None:
        self.taxonomy = taxonomy if taxonomy is not None else _load_taxonomy()
        # Pre-compile one word-boundary regex per keyword phrase so scoring
        # a request doesn't re-parse the taxonomy's phrases every call.
        self._compiled: list[tuple[str, str, list[tuple[re.Pattern, float]]]] = []
        for intent in self.taxonomy:
            # Boundaries are anchored on whitespace/string-edges rather than
            # regex's built-in `\b`. `\b` is defined via `\w` transitions,
            # and `\w` excludes Unicode combining marks (category "Mn") -
            # e.g. Hindi "केवाईसी" ends in the vowel sign "ी", so `\b` right
            # after it would silently fail to match. Since `_normalize`
            # already collapses every separator down to a single space,
            # "preceded by start-of-string-or-space, followed by
            # end-of-string-or-space" is an exact, script-agnostic
            # substitute that has no such gap.
            patterns = [
                (
                    re.compile(rf"(?:^|(?<=\s)){re.escape(kw['phrase'].lower())}(?:$|(?=\s))"),
                    float(kw["weight"]),
                )
                for kw in intent.get("keywords", [])
            ]
            self._compiled.append((intent["intent_id"], intent["label"], patterns))

    async def score_intents(self, text: str) -> list[IntentScore]:
        normalized = _normalize(text)
        scores: list[IntentScore] = []
        for intent_id, label, patterns in self._compiled:
            raw_score = sum(weight for pattern, weight in patterns if pattern.search(normalized))
            if raw_score > 0:
                scores.append(IntentScore(intent_id=intent_id, label=label, raw_score=raw_score))
        return scores
