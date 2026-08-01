from ai_guidance_engine.services.confidence_service import ConfidenceService


def test_none_value_scores_zero_and_low() -> None:
    confidence, level = ConfidenceService().score(None, "some reason", "aadhaar")
    assert confidence == 0.0
    assert level == "Low"


def test_empty_string_value_scores_zero_and_low() -> None:
    confidence, level = ConfidenceService().score("   ", "some reason", "aadhaar")
    assert confidence == 0.0
    assert level == "Low"


def test_clear_value_with_source_and_reason_is_high_confidence() -> None:
    confidence, level = ConfidenceService().score("Ramesh Patil", "Clearly printed on the document", "aadhaar")
    assert confidence == ConfidenceService.HIGH_CONFIDENCE
    assert level == "High"


def test_hedged_reason_lowers_confidence_even_with_a_value() -> None:
    confidence, level = ConfidenceService().score(
        "Ramesh Patil", "Text was blurred and hard to read, best guess", "aadhaar"
    )
    assert level == "Low"
    assert confidence < ConfidenceService.MEDIUM_CONFIDENCE


def test_hedged_reason_without_source_is_lower_than_hedged_with_source() -> None:
    with_source, _ = ConfidenceService().score("Ramesh Patil", "illegible in parts", "aadhaar")
    without_source, _ = ConfidenceService().score("Ramesh Patil", "illegible in parts", "")
    assert without_source < with_source


def test_value_without_reason_or_source_is_medium_not_high() -> None:
    confidence, level = ConfidenceService().score("Ramesh Patil", "", "")
    assert level == "Medium"
    assert confidence < ConfidenceService.HIGH_CONFIDENCE


def test_build_field_wires_score_into_extracted_field() -> None:
    field = ConfidenceService().build_field("Applicant Name", "Ramesh Patil", "aadhaar", "Clearly printed")
    assert field.field == "Applicant Name"
    assert field.value == "Ramesh Patil"
    assert field.confidence == ConfidenceService.HIGH_CONFIDENCE
    assert field.confidence_level == "High"
