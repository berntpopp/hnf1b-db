"""Tests for hnf1b_mcp.tools.search — the hnf1b_search MCP tool."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools.search import register

BASE = "http://api.test/api/v2"

_HIT = {
    "id": "pp_HNF1B-1",
    "label": "Individual 1",
    "type": "individual",
    "score": 1.0,
}

_SEARCH_RESPONSE = {
    "results": [
        _HIT,
        {
            "id": "var_HNF1B:c.494G>A",
            "label": "c.494G>A",
            "type": "variant",
            "score": 0.9,
        },
        {
            "id": "pub_12345678",
            "label": "Smith et al. 2020",
            "type": "publication",
            "score": 0.8,
        },
    ]
}


@pytest.mark.asyncio
async def test_registered_readonly():
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_search")
    assert tool.annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_registered_not_open_world():
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_search")
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_hits():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "HNF1B"})
    sc = r.structured_content
    assert sc["data_class"] == "operational_metadata"
    assert "meta" in sc
    assert any(h["id"] == "pp_HNF1B-1" for h in sc["hits"])
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_hit_fields():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "HNF1B"})
    sc = r.structured_content
    for hit in sc["hits"]:
        assert "type" in hit
        assert "id" in hit
        assert "label" in hit
        assert "uri" in hit
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_types_filter():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "HNF1B", "types": ["variant"]})
    sc = r.structured_content
    assert all(h["type"] == "variant" for h in sc["hits"])
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_limit_forwarded():
    route = respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    await mcp.call_tool("hnf1b_search", {"query": "HNF1B", "limit": 5})
    call = route.calls[0]
    params = dict(call.request.url.params)
    assert params["page_size"] == "5"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_empty_results():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "nonexistent"})
    sc = r.structured_content
    assert sc["hits"] == []
    assert sc["counts"] == {}
    await c.aclose()


@pytest.mark.asyncio
async def test_search_invalid_query_returns_error_envelope():
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": ""})
    sc = r.structured_content
    assert sc.get("is_error") is True
    # Error code is nested under the "error" key in the envelope.
    assert sc["error"]["code"] == "invalid_input"
    await c.aclose()


@pytest.mark.asyncio
async def test_search_invalid_type_returns_error_envelope():
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "HNF1B", "types": ["bogus"]})
    sc = r.structured_content
    assert sc.get("is_error") is True
    # Error code is nested under the "error" key in the envelope.
    assert sc["error"]["code"] == "invalid_input"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_query_echoed_in_result():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "kidney disease"})
    sc = r.structured_content
    assert sc["query"] == "kidney disease"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("mode", ["compact", "standard"])
async def test_search_score_survives_response_mode(mode):
    """The relevance score forwards through the tool in every response mode."""
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool(
        "hnf1b_search", {"query": "HNF1B", "response_mode": mode}
    )
    sc = r.structured_content
    by_id = {h["id"]: h for h in sc["hits"]}
    assert by_id["pp_HNF1B-1"]["score"] == 1.0
    assert by_id["var_HNF1B:c.494G>A"]["score"] == 0.9
    assert by_id["pub_12345678"]["score"] == 0.8
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_search_guidance_present():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_search", {"query": "HNF1B"})
    sc = r.structured_content
    assert "guidance" in sc
    assert isinstance(sc["guidance"], str)
    await c.aclose()
