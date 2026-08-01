from fastapi.testclient import TestClient

from trust_governance_engine.app import app

client = TestClient(app)


def _create_application():
    payload = {
        "applicant_id": "APP-TEST-1",
        "service_id": "nsap_old_age_pension",
        "fields": [
            {
                "field": "full_name",
                "value": "Ramesh Kumar",
                "confidence": 0.94,
                "confidence_level": "high",
                "source_document": "aadhaar",
                "reason": "Exact match",
            },
            {
                "field": "bank_account_number",
                "value": "0091234567890",
                "confidence": 0.62,
                "confidence_level": "medium",
                "source_document": "bank_passbook",
                "reason": "Partially obscured",
            },
            {
                "field": "nominee_name",
                "value": None,
                "confidence": 0.2,
                "confidence_level": "low",
                "source_document": "pension_form",
                "reason": "Blank in source",
                "required": False,
            },
        ],
    }
    response = client.post("/api/v1/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_application_starts_in_draft() -> None:
    data = _create_application()
    assert data["status"] == "draft"
    assert len(data["fields"]) == 3
    assert all(f["decision_status"] == "pending" for f in data["fields"])


def test_duplicate_field_names_rejected() -> None:
    payload = {
        "applicant_id": "APP-DUPE",
        "fields": [
            {
                "field": "full_name",
                "value": "A",
                "confidence": 0.9,
                "confidence_level": "high",
                "source_document": "aadhaar",
                "reason": "x",
            },
            {
                "field": "full_name",
                "value": "B",
                "confidence": 0.9,
                "confidence_level": "high",
                "source_document": "aadhaar",
                "reason": "y",
            },
        ],
    }
    response = client.post("/api/v1/applications", json=payload)
    assert response.status_code == 422


def test_full_review_and_submission_flow() -> None:
    application = _create_application()
    app_id = application["application_id"]

    # Reject the optional field — should not block submission.
    response = client.post(
        f"/api/v1/applications/{app_id}/fields/nominee_name/reject",
        json={"actor": "caseworker:asha", "reason": "No nominee on file"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "under_review"

    # Edit the low-confidence field.
    response = client.post(
        f"/api/v1/applications/{app_id}/fields/bank_account_number/edit",
        json={
            "actor": "caseworker:asha",
            "new_value": "00912345678901",
            "reason": "Corrected trailing digit after manual review",
        },
    )
    assert response.status_code == 200, response.text
    edited_field = next(f for f in response.json()["fields"] if f["field"] == "bank_account_number")
    assert edited_field["is_edited"] is True
    assert edited_field["decision_status"] == "approved"

    # Approve the remaining field -> application should be ready for submission.
    response = client.post(
        f"/api/v1/applications/{app_id}/fields/full_name/approve",
        json={"actor": "caseworker:asha"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready_for_submission"

    # Submission should still be blocked until OTP is verified.
    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is False
    assert any("OTP" in reason for reason in response.json()["blocking_reasons"])

    # Request + verify OTP (dev mode exposes the code so the flow can be tested).
    response = client.post(f"/api/v1/applications/{app_id}/otp/request", json={"destination": "+911234567890"})
    assert response.status_code == 200, response.text
    otp_code = response.json()["otp_code"]
    assert otp_code is not None

    # Wrong code first -> should fail with attempts remaining.
    response = client.post(f"/api/v1/applications/{app_id}/otp/verify", json={"code": "000000"})
    assert response.status_code == 401

    response = client.post(f"/api/v1/applications/{app_id}/otp/verify", json={"code": otp_code})
    assert response.status_code == 200, response.text
    assert response.json()["otp_verified"] is True

    # Now submission validation should pass.
    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is True

    response = client.post(f"/api/v1/applications/{app_id}/submit", json={"actor": "caseworker:asha"})
    assert response.status_code == 200, response.text
    submission = response.json()
    assert "full_name" in submission["field_snapshot"]
    assert "nominee_name" not in submission["field_snapshot"]  # rejected optional field excluded

    # Application is now locked.
    response = client.post(
        f"/api/v1/applications/{app_id}/fields/full_name/approve",
        json={"actor": "caseworker:asha"},
    )
    assert response.status_code == 409

    # Audit log should be non-empty and internally consistent.
    response = client.get(f"/api/v1/applications/{app_id}/audit-log")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) >= 6
    actions = [entry["action"] for entry in entries]
    assert "application_created" in actions
    assert "application_submitted" in actions

    response = client.get(f"/api/v1/applications/{app_id}/audit-log/verify")
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_required_field_rejection_blocks_submission() -> None:
    application = _create_application()
    app_id = application["application_id"]

    client.post(
        f"/api/v1/applications/{app_id}/fields/nominee_name/reject",
        json={"actor": "caseworker:asha", "reason": "No nominee"},
    )
    client.post(
        f"/api/v1/applications/{app_id}/fields/full_name/approve",
        json={"actor": "caseworker:asha"},
    )
    # Reject a REQUIRED field this time.
    response = client.post(
        f"/api/v1/applications/{app_id}/fields/bank_account_number/reject",
        json={"actor": "caseworker:asha", "reason": "Illegible"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validation_failed"

    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.json()["can_submit"] is False
    assert any("required field" in reason for reason in response.json()["blocking_reasons"])


def test_reports_are_generated_in_all_formats() -> None:
    application = _create_application()
    app_id = application["application_id"]

    for fmt, content_type_prefix in [("json", "application/json"), ("csv", "text/csv"), ("pdf", "application/pdf")]:
        response = client.get(f"/api/v1/applications/{app_id}/report", params={"format": fmt})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(content_type_prefix)
        assert len(response.content) > 0


def test_unknown_application_returns_404() -> None:
    response = client.get("/api/v1/applications/does-not-exist")
    assert response.status_code == 404


def test_create_application_accepts_legacy_pension_type_alias() -> None:
    """Backward compatibility: callers still sending the old 'pension_type'
    field (pre-Phase B) must keep working unmodified."""
    payload = {
        "applicant_id": "APP-LEGACY-1",
        "pension_type": "nsap_old_age_pension",
        "fields": [
            {
                "field": "full_name",
                "value": "Legacy Caller",
                "confidence": 0.9,
                "confidence_level": "high",
                "source_document": "aadhaar",
                "reason": "Exact match",
            }
        ],
    }
    response = client.post("/api/v1/applications", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["service_id"] == "nsap_old_age_pension"


def _make_ready_for_submission_application() -> str:
    """Creates an application, resolves every field, and verifies OTP —
    i.e. gets it to the point where the only thing submission blocking on
    is exactly what the test wants to exercise.
    """

    application = _create_application()
    app_id = application["application_id"]

    client.post(
        f"/api/v1/applications/{app_id}/fields/nominee_name/reject",
        json={"actor": "caseworker:asha", "reason": "No nominee on file"},
    )
    client.post(
        f"/api/v1/applications/{app_id}/fields/bank_account_number/edit",
        json={"actor": "caseworker:asha", "new_value": "00912345678901", "reason": "Corrected digit"},
    )
    client.post(
        f"/api/v1/applications/{app_id}/fields/full_name/approve",
        json={"actor": "caseworker:asha"},
    )
    otp_response = client.post(f"/api/v1/applications/{app_id}/otp/request", json={"destination": "+911234567890"})
    otp_code = otp_response.json()["otp_code"]
    client.post(f"/api/v1/applications/{app_id}/otp/verify", json={"code": otp_code})
    return app_id


def test_trusted_delegate_blocks_submission_until_approved() -> None:
    app_id = _make_ready_for_submission_application()

    # OTP is verified and every field is resolved — submission should be
    # allowed at this point, before any delegate is registered.
    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is True

    # Registering a required Trusted Delegate should now gate submission,
    # even though nothing else about the application changed.
    response = client.post(
        f"/api/v1/applications/{app_id}/delegate",
        json={
            "delegate_name": "Sunita Devi",
            "relationship_to_applicant": "daughter",
            "contact": "+919876543210",
            "approval_required": True,
            "consent_given_by": "applicant:APP-TEST-1",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["approved"] is False

    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is False
    assert any("Trusted Delegate" in reason for reason in response.json()["blocking_reasons"])

    response = client.post(f"/api/v1/applications/{app_id}/submit", json={"actor": "caseworker:asha"})
    assert response.status_code == 409

    # Once the delegate approves, submission unblocks.
    response = client.post(
        f"/api/v1/applications/{app_id}/delegate/approve", json={"actor": "Sunita Devi"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["approved"] is True

    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is True

    response = client.post(f"/api/v1/applications/{app_id}/submit", json={"actor": "caseworker:asha"})
    assert response.status_code == 200, response.text


def test_trusted_delegate_with_approval_not_required_does_not_block() -> None:
    app_id = _make_ready_for_submission_application()

    response = client.post(
        f"/api/v1/applications/{app_id}/delegate",
        json={
            "delegate_name": "Ravi Shah",
            "relationship_to_applicant": "NGO volunteer",
            "contact": "ravi@example-ngo.org",
            "approval_required": False,
            "consent_given_by": "applicant:APP-TEST-1",
        },
    )
    assert response.status_code == 201, response.text

    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is True


def test_trusted_delegate_events_record_notification_channel() -> None:
    # Registering, approving, then revoking a delegate should each fire the
    # (default: log-only) DelegateNotificationProvider and record the
    # channel used on the corresponding audit entry - the same pattern OTP
    # delivery already uses.
    app_id = _make_ready_for_submission_application()

    client.post(
        f"/api/v1/applications/{app_id}/delegate",
        json={
            "delegate_name": "Sunita Devi",
            "relationship_to_applicant": "daughter",
            "contact": "+919876543210",
            "approval_required": True,
            "consent_given_by": "applicant:APP-TEST-1",
        },
    )
    client.post(f"/api/v1/applications/{app_id}/delegate/approve", json={"actor": "Sunita Devi"})
    client.post(f"/api/v1/applications/{app_id}/delegate/revoke", json={"actor": "caseworker:asha"})

    response = client.get(f"/api/v1/applications/{app_id}/audit-log")
    assert response.status_code == 200
    entries = response.json()

    delegate_actions = {"trusted_delegate_registered", "trusted_delegate_approved", "trusted_delegate_revoked"}
    delegate_entries = [entry for entry in entries if entry["action"] in delegate_actions]
    assert len(delegate_entries) == 3
    for entry in delegate_entries:
        assert entry["details"].get("notification_channel") == "log_only"


def test_trusted_delegate_revoke_and_not_found() -> None:
    app_id = _make_ready_for_submission_application()

    client.post(
        f"/api/v1/applications/{app_id}/delegate",
        json={
            "delegate_name": "Sunita Devi",
            "relationship_to_applicant": "daughter",
            "contact": "+919876543210",
            "approval_required": True,
            "consent_given_by": "applicant:APP-TEST-1",
        },
    )

    response = client.post(f"/api/v1/applications/{app_id}/delegate/revoke", json={"actor": "caseworker:asha"})
    assert response.status_code == 200, response.text
    assert response.json()["revoked_at"] is not None

    # No active delegate left — submission is no longer gated on one, and
    # GET .../delegate / a second revoke both report not-found.
    response = client.get(f"/api/v1/applications/{app_id}/submission/validate")
    assert response.status_code == 200
    assert response.json()["can_submit"] is True

    response = client.get(f"/api/v1/applications/{app_id}/delegate")
    assert response.status_code == 404

    response = client.post(f"/api/v1/applications/{app_id}/delegate/approve", json={"actor": "Sunita Devi"})
    assert response.status_code == 404
