import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError

BASE = "http://api.test/api/v2"


@pytest.mark.asyncio
@respx.mock
async def test_get_allowed_returns_json():
    respx.get(f"{BASE}/phenopackets/X").mock(return_value=httpx.Response(200, json={"id": "X"}))
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
        return_value=httpx.Response(200, json={"total_phenopackets": 1}))
    c = ApiClient(base_url=BASE, cache_ttl=60)
    await c.get("/phenopackets/aggregate/summary")
    await c.get("/phenopackets/aggregate/summary")
    assert route.call_count == 1
    await c.aclose()
