import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError

BASE = "http://api.test/api/v2"


@pytest.mark.asyncio
@respx.mock
async def test_get_allowed_returns_json():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json={"id": "X"})
    )
    c = ApiClient(base_url=BASE)
    assert (await c.get("/phenopackets/X"))["id"] == "X"
    await c.aclose()


@pytest.mark.asyncio
async def test_get_blocks_non_allowlisted():
    c = ApiClient(base_url=BASE)
    with pytest.raises(PermissionError):
        await c.get("/admin/sync")
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_404_maps_to_not_found():
    respx.get(f"{BASE}/phenopackets/missing").mock(return_value=httpx.Response(404))
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await c.get("/phenopackets/missing")
    assert ei.value.code == "not_found"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_cache_hit_skips_second_call():
    route = respx.get(f"{BASE}/phenopackets/aggregate/summary").mock(
        return_value=httpx.Response(200, json={"total_phenopackets": 1})
    )
    c = ApiClient(base_url=BASE, cache_ttl=60)
    await c.get("/phenopackets/aggregate/summary")
    await c.get("/phenopackets/aggregate/summary")
    assert route.call_count == 1
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_422_names_offending_field_and_value():
    """A FastAPI 422 body is parsed into an actionable invalid_input envelope."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["query", "variant_type"],
                        "msg": "value is not a valid enumeration member",
                        "input": "missense",
                    }
                ]
            },
        )
    )
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await c.get("/phenopackets/aggregate/all-variants")
    err = ei.value
    assert err.code == "invalid_input"
    # The offending field name and bad value must be surfaced.
    assert err.details["field"] == "variant_type"
    assert "missense" in err.message
    assert "variant_type" in err.message
    # variant_type maps to a known contract enum → allowed values attached.
    assert "SNV" in err.details["allowed"]
    assert err.details["hint"]
    # Raw upstream detail is preserved for the model to reason over.
    assert err.details["upstream_detail"][0]["loc"] == ["query", "variant_type"]
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_422_unknown_field_still_actionable():
    """A 422 for a field with no contract enum still names the field."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["query", "page"], "msg": "must be >= 1", "input": 0}
                ]
            },
        )
    )
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await c.get("/phenopackets/aggregate/all-variants")
    err = ei.value
    assert err.code == "invalid_input"
    assert err.details["field"] == "page"
    # No contract enum for 'page' → no 'allowed', but still a hint.
    assert "allowed" not in err.details
    assert err.details["hint"]
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_422_unparseable_body_falls_back():
    """A non-standard 422 body still produces an actionable envelope."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(422, text="gateway said no")
    )
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await c.get("/phenopackets/aggregate/all-variants")
    err = ei.value
    assert err.code == "invalid_input"
    assert err.details["field"] == "unknown"
    assert err.details["hint"]
    await c.aclose()
