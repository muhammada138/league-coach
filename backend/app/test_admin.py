import pytest
from httpx import AsyncClient, ASGITransport

from .main import app

@pytest.mark.asyncio
async def test_admin_routes_without_auth(mocker):
    # Mock ADMIN_API_KEY for testing
    mocker.patch("app.routes.api.ADMIN_API_KEY", "test-secret-key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test missing header
        response = await client.get("/admin/data-summary")
        assert response.status_code == 403
        assert response.json()["detail"] == "Could not validate credentials"

        # Test wrong header
        response = await client.get("/admin/data-summary", headers={"X-Admin-Token": "wrong-key"})
        assert response.status_code == 403

@pytest.mark.asyncio
async def test_admin_routes_with_auth(mocker):
    # Mock db to return mock data
    mocker.patch("app.routes.api.db.get_ingestion_status", return_value={"mock": "data"})
    mocker.patch("app.routes.api.ADMIN_API_KEY", "test-secret-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/data-summary", headers={"X-Admin-Token": "test-secret-key"})
        assert response.status_code == 200
        assert "meta" in response.json()
