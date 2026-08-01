import os
import sys

import pytest
from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from risk_engine.api.dependencies import get_risk_assessment_service  # noqa: E402
from risk_engine.app import app  # noqa: E402
from risk_engine.services.registry_client import RegistryClient  # noqa: E402
from risk_engine.services.risk_assessment_service import RiskAssessmentService  # noqa: E402
from risk_engine.utils.exceptions import RegistryUnavailableError  # noqa: E402

client = TestClient(app)


class FakeRegistryClient(RegistryClient):
    """Test double so risk-assessment tests never need a live registry
    process. Returns whatever `fixed_response` was constructed with, or
    raises RegistryUnavailableError if `unavailable=True`.
    """

    def __init__(self, fixed_response: dict | None, unavailable: bool = False):
        self.fixed_response = fixed_response
        self.unavailable = unavailable

    async def redirect_info(self, service_id: str):
        if self.unavailable:
            raise RegistryUnavailableError("registry unreachable (test double)")
        return self.fixed_response


def _override_with(fake_client: FakeRegistryClient):
    app.dependency_overrides[get_risk_assessment_service] = lambda: RiskAssessmentService(
        registry_client=fake_client
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_redirect_check_passes_for_whitelisted_https_url() -> None:
    _override_with(
        FakeRegistryClient(
            {
                "service_id": "nsap_old_age_pension",
                "service_name": "NSAP Old Age Pension",
                "official_url": "https://nsap.gov.in",
                "allowed_domains": ["nsap.gov.in"],
            }
        )
    )
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={"service_id": "nsap_old_age_pension", "target_url": "https://nsap.gov.in/apply"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["https_verified"] is True
    assert data["domain_whitelist_verified"] is True
    assert data["risk_level"] == "none"
    assert data["should_pause_guidance"] is False
    assert data["findings"] == []


def test_redirect_check_flags_non_https() -> None:
    _override_with(
        FakeRegistryClient(
            {
                "service_id": "nsap_old_age_pension",
                "service_name": "NSAP Old Age Pension",
                "official_url": "https://nsap.gov.in",
                "allowed_domains": ["nsap.gov.in"],
            }
        )
    )
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={"service_id": "nsap_old_age_pension", "target_url": "http://nsap.gov.in/apply"},
    )
    data = response.json()
    assert data["https_verified"] is False
    assert data["should_pause_guidance"] is True
    assert any(f["code"] == "INSECURE_SCHEME" for f in data["findings"])


def test_redirect_check_flags_domain_off_whitelist() -> None:
    _override_with(
        FakeRegistryClient(
            {
                "service_id": "nsap_old_age_pension",
                "service_name": "NSAP Old Age Pension",
                "official_url": "https://nsap.gov.in",
                "allowed_domains": ["nsap.gov.in"],
            }
        )
    )
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={"service_id": "nsap_old_age_pension", "target_url": "https://nsap-gov-in.example.com/apply"},
    )
    data = response.json()
    assert data["domain_whitelist_verified"] is False
    assert data["risk_level"] == "high"
    assert data["should_pause_guidance"] is True
    assert any(f["code"] == "DOMAIN_NOT_WHITELISTED" for f in data["findings"])


def test_redirect_check_flags_suspicious_redirect_hop() -> None:
    _override_with(
        FakeRegistryClient(
            {
                "service_id": "sbi_kyc_update",
                "service_name": "SBI KYC Update",
                "official_url": "https://sbi.co.in",
                "allowed_domains": ["sbi.co.in", "onlinesbi.sbi"],
            }
        )
    )
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={
            "service_id": "sbi_kyc_update",
            "target_url": "https://onlinesbi.sbi/kyc",
            "redirect_chain": ["https://sbi.co.in/start", "https://phishing-lookalike.example"],
        },
    )
    data = response.json()
    assert data["domain_whitelist_verified"] is True  # final target is fine
    assert data["should_pause_guidance"] is True  # but a hop wasn't
    assert any(f["code"] == "SUSPICIOUS_REDIRECT_HOP" for f in data["findings"])


def test_redirect_check_degrades_gracefully_when_registry_unreachable() -> None:
    _override_with(FakeRegistryClient(fixed_response=None, unavailable=True))
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={"service_id": "nsap_old_age_pension", "target_url": "https://nsap.gov.in/apply"},
    )
    assert response.status_code == 200  # never crashes - Phase A independence requirement
    data = response.json()
    assert data["domain_whitelist_verified"] is None
    assert data["risk_level"] == "unknown"
    assert any(f["code"] == "REGISTRY_UNAVAILABLE" for f in data["findings"])


def test_redirect_check_flags_unknown_service() -> None:
    _override_with(FakeRegistryClient(fixed_response=None, unavailable=False))
    response = client.post(
        "/api/v1/risk/redirect-check",
        json={"service_id": "not_a_real_service", "target_url": "https://example.gov.in/apply"},
    )
    data = response.json()
    assert data["domain_whitelist_verified"] is False
    assert data["should_pause_guidance"] is True
    assert any(f["code"] == "UNKNOWN_SERVICE" for f in data["findings"])


@pytest.mark.parametrize(
    "page_text,expected",
    [
        ("Enter the OTP sent to your mobile number", ["otp"]),
        ("Please enter your net banking Password", ["password"]),
        ("Enter your 4-digit ATM PIN to continue", ["pin"]),
        ("Enter the CVV printed on the back of your card", ["cvv"]),
        ("Enter your full name and date of birth", []),
    ],
)
def test_content_scan_detects_sensitive_field_labels(page_text: str, expected: list[str]) -> None:
    response = client.post("/api/v1/risk/content-scan", json={"page_text": page_text})
    assert response.status_code == 200
    data = response.json()
    assert data["sensitive_fields_detected"] == expected
    assert data["should_pause_guidance"] == bool(expected)
