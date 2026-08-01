import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:

        response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_extract_endpoint_fallback(monkeypatch):
    async def fake_extract(self, text, schema):
        return {
            "extracted": {
                key: None for key in schema.keys()
            },
            "confidence": 0.0,
        }

    monkeypatch.setattr(
        "app.services.provider_client.OpenAIProvider.extract",
        fake_extract,
    )

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/api/v1/extract",
            json={
                "document_id": "doc1",
                "text": "Hello world",
                "schema": {
                    "name": "string",
                    "age": "integer",
                },
            },
        )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["document_id"] == "doc1"
    assert data["confidence"] == 0.0
    assert data["provider_name"] == "openai"

@pytest.mark.asyncio
async def test_portal_list_and_confirm():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        list_response = await client.get("/api/v1/portals")

        assert list_response.status_code == status.HTTP_200_OK
        portals = list_response.json()
        assert isinstance(portals, list)
        assert len(portals) >= 1
        portal = portals[0]
        assert "id" in portal
        assert "url" in portal

        confirm_response = await client.post(
            "/api/v1/portals/confirm",
            json={
                "portal_id": portal["id"],
                "permission_given": True,
                "user_note": "Test confirmation",
            },
        )

        assert confirm_response.status_code == status.HTTP_200_OK
        confirm_data = confirm_response.json()
        assert confirm_data["portal_id"] == portal["id"]
        assert confirm_data["redirect_url"] == portal["url"]
        assert "Permission granted" in confirm_data["message"]


@pytest.mark.asyncio
async def test_document_upload_and_hash():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/documents",
            json={
                "title": "Test document",
                "source": "unit-test",
                "content": "This is a secure upload test.",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Test document"
        assert data["source"] == "unit-test"
        assert "content_hash" in data
        assert data["id"] > 0
