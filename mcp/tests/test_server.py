import httpx
import pytest

from hnf1b_mcp.config import Settings
from hnf1b_mcp.server import (
    SERVER_INSTRUCTIONS,
    build_app,
    build_http_app,
    is_origin_allowed,
)
from hnf1b_mcp.services.resources import load_resource


def test_instructions_have_safety():
    s = SERVER_INSTRUCTIONS.lower()
    assert "not instructions" in s
    assert "research" in s


def test_instructions_capabilities_is_advisory_not_mandatory():
    """Step 1 must frame get_capabilities as advisory, not a mandatory cold load.

    The server ships a `capabilities_version` content hash (warm-skip) and every
    tool advertises its filterable-field enums, so a client can build valid calls
    without a mandatory full capabilities fetch. Lock that the primer says so.
    """
    s = SERVER_INSTRUCTIONS.lower()
    # Advisory framing: recommended/optional, not "call first" prescriptively.
    assert "recommended" in s
    assert "optional" in s
    assert "call `hnf1b_get_capabilities` first" not in s
    # The warm-skip affordance must be surfaced, alongside the per-tool enums.
    assert "capabilities_version" in s
    assert "descriptor_chars" in s
    assert "filterable_fields" in s


@pytest.mark.asyncio
async def test_app_exposes_tools_and_resources():
    mcp = build_app()
    names = {t.name for t in await mcp.list_tools()}
    assert "hnf1b_get_capabilities" in names
    resources = await mcp.list_resources()
    assert any("schema/overview" in str(r.uri) for r in resources)


@pytest.mark.asyncio
async def test_tool_guide_has_section_for_each_registered_tool():
    mcp = build_app()
    names = {t.name for t in await mcp.list_tools()}
    guide = load_resource("hnf1b://schema/tool-guide")
    missing = sorted(name for name in names if f"### `{name}`" not in guide)
    assert missing == []


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


def test_origin_helper_strict():
    allowed = ["https://claude.ai"]
    assert is_origin_allowed(None, allowed, require_origin=True) is False
    assert is_origin_allowed("https://claude.ai", allowed, require_origin=True) is True


@pytest.mark.asyncio
async def test_health_strict_origin_validation():
    settings = Settings(allowed_origins=["https://claude.ai"], require_origin=True)
    app = build_http_app(settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        # No Origin with require_origin=True -> 403.
        r = await ac.get("/health")
        assert r.status_code == 403
        # Allowed Origin -> 200.
        r = await ac.get("/health", headers={"Origin": "https://claude.ai"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_bearer_token_auth():
    settings = Settings(api_key="secret-token-123")
    app = build_http_app(settings=settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:
            # /health is open without auth
            r = await ac.get("/health")
            assert r.status_code == 200

            # Protected endpoint without auth -> 401
            r = await ac.post("/")
            assert r.status_code == 401
            assert r.json()["error"]["code"] == "unauthorized"

            # Wrong token -> 401
            r = await ac.post("/", headers={"Authorization": "Bearer wrong-token"})
            assert r.status_code == 401
            assert r.json()["error"]["code"] == "unauthorized"

            # Correct token -> authorized (passes middleware)
            r = await ac.post("/", headers={"Authorization": "Bearer secret-token-123"})
            assert r.status_code != 401
