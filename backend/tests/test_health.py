"""M1 smoke tests: app boots and liveness endpoint responds."""

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.main import create_app


@pytest.mark.asyncio
async def test_health_ok():
    app = create_app()
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "TraceGuard AI"


@pytest.mark.asyncio
async def test_root_metadata():
    app = create_app()
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["tagline"] == "Connect. Analyze. Uncover."
