import os
import sys

from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.app import app  # noqa: E402

client = TestClient(app)

# One real, natural sentence per supported language, each clearly a
# pension_application per that language's data/intents_<code>.json.
_PENSION_TEXT_BY_LANGUAGE = {
    "hi": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है",
    "mr": "मला निवृत्तीवेतनासाठी अर्ज करायचा आहे",
    "bn": "আমি পেনশনের জন্য আবেদন করতে চাই",
    "ta": "எனக்கு பென்சனுக்கு விண்ணப்பிக்க வேண்டும்",
    "te": "నాకు పింఛను కోసం దరఖాస్తు చేయాలి",
}

_LANGUAGE_NAMES = {"hi": "Hindi", "mr": "Marathi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu"}


def test_classify_auto_detects_english_by_default() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I want to apply for old age pension"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert data["language_name"] == "English"
    assert data["language_source"] == "detected"
    assert data["language_supported"] is True
    assert data["detected_intent"] == "pension_application"


def test_classify_auto_detects_and_classifies_every_supported_language() -> None:
    for language, text in _PENSION_TEXT_BY_LANGUAGE.items():
        response = client.post("/api/v1/intent/classify", json={"text": text})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["language"] == language, f"expected {language}, got {data['language']} for text {text!r}"
        assert data["language_name"] == _LANGUAGE_NAMES[language]
        assert data["language_source"] == "detected"
        assert data["language_supported"] is True
        assert data["detected_intent"] == "pension_application", data


def test_classify_detects_hindi_banking_kyc_intent() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "मुझे अपना केवाईसी अपडेट करना है"},
    )
    data = response.json()
    assert data["language"] == "hi"
    assert data["detected_intent"] == "banking_kyc"


def test_classify_detects_marathi_vs_hindi_via_markers() -> None:
    # Both are Devanagari script; only the Marathi marker words in the
    # actual sentence (not the taxonomy) should tip this to "mr".
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "माझे केवायसी अद्ययावत करा"},
    )
    data = response.json()
    assert data["language"] == "mr"
    assert data["detected_intent"] == "banking_kyc"


def test_classify_declared_language_overrides_autodetection() -> None:
    # Text is ambiguous/English-looking, but the caller explicitly declares
    # Hindi - a nonsensical combination for a real citizen, but the point is
    # that `language` on the request must be treated as authoritative.
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "old age pension", "language": "hi"},
    )
    data = response.json()
    assert data["language"] == "hi"
    assert data["language_source"] == "declared"
    assert data["language_detection_confidence"] == 1.0
    # The Hindi taxonomy has no "old age pension" (English) phrase, so this
    # correctly reports unclassified rather than silently falling back to
    # the English taxonomy.
    assert data["detected_intent"] == "unclassified"


def test_classify_declared_language_matches_when_text_agrees() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है", "language": "hi"},
    )
    data = response.json()
    assert data["language"] == "hi"
    assert data["language_source"] == "declared"
    assert data["detected_intent"] == "pension_application"


def test_classify_reports_unsupported_for_unrecognized_declared_language_code() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "Je veux demander une pension", "language": "fr"},
    )
    assert response.status_code == 200  # never crashes - Phase A independence requirement
    data = response.json()
    assert data["language"] == "fr"
    assert data["language_supported"] is False
    assert data["detected_intent"] == "unclassified"
    assert data["confidence"] == 0.0


def test_classify_declared_language_code_is_case_and_whitespace_insensitive() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है", "language": " HI "},
    )
    data = response.json()
    assert data["language"] == "hi"
    assert data["detected_intent"] == "pension_application"


def test_classify_reports_low_confidence_alternates_across_languages_consistently() -> None:
    # Sanity check that the confidence/level machinery (shared across all
    # languages via the same IntentService.classify code path) still holds
    # for a non-English request with multiple plausible intents.
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "पेंशन के लिए आवेदन और आधार अपडेट"},  # pension + aadhaar update, mixed
    )
    data = response.json()
    assert data["language"] == "hi"
    assert data["confidence_level"] in ("High", "Medium", "Low")
    assert 0.0 <= data["confidence"] <= 1.0
    for alt in data["alternate_intents"]:
        assert 0.0 <= alt["confidence"] <= 1.0
