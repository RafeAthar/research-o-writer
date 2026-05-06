"""Auth scoping is the single safety boundary in Phase 1.

The harness here intentionally hits ``/me`` because it is the only authenticated
endpoint with no DB or external-service dependency. If 401 enforcement breaks
there, every other authenticated route is broken the same way.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_me_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_bad_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/me", headers={"X-Auth-Token": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_accepts_valid_token():
    settings = get_settings()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/me", headers={"X-Auth-Token": settings.app_auth_token})
    assert r.status_code == 200
    assert r.json() == {"user_id": settings.app_default_user_id}
