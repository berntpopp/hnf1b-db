import httpx
import pytest

from hnf1b_mcp.config import Settings
from hnf1b_mcp.server import (
    SERVER_INSTRUCTIONS,
    build_app,
    build_http_app,
    is_origin_allowed,
)


def test_instructions_have_safety():
    s = SERVER_INSTRUCTIONS.lower()
    assert "not instructions" in s
    assert "research" in s


@pytest.mark.asyncio
async def test_app_exposes_tools_and_resources():
    mcp = build_app()
    names = {t.name for t in await mcp.list_tools()}
    assert "hnf1b_get_capabilities" in names
    resources = await mcp.list_resources()
    assert any("schema/overview" in str(r.uri) for r in resources)


def test_origin_helper():
    allowed = ["https://claude.ai", "https://claude.com"]
    # No Origin header -> allowed (non-browser client).
    assert is_origin_allowed(None, allowed) is True
    # Allowed origin -> allowed.
    assert is_origin_allowed("https://claude.ai", allowed) is True
    # Disallowed origin -> rejected.
    assert is_origin_allowed("https://evil.example", allowed) is False


@pytest.mark.asyncio
async def test_health_origin_validation():
    settings = Settings(allowed_origins=["https://claude.ai"])
    app = build_http_app(settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        # No Origin -> 200.
        r = await ac.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        # Allowed Origin -> 200.
        r = await ac.get("/health", headers={"Origin": "https://claude.ai"})
        assert r.status_code == 200
        # Disallowed Origin -> 403.
        r = await ac.get("/health", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
