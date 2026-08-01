from fastapi.testclient import TestClient

from ai_guidance_engine.app import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_endpoint_returns_fields() -> None:
    payload = {
        "applicant_id": "123",
        "documents": [
            {"type": "aadhaar", "text": "Applicant Name: Ramesh Patil"},
            {"type": "income_certificate", "text": "Pension Type: Old Age"},
        ],
    }
    response = client.post("/api/v1/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["provider"] == "Gemini"
    assert isinstance(data["fields"], list)
    assert data["fields"]
