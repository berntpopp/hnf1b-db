"""MCP smoke tests using the FastMCP in-memory Client.

Exercises the full MCP protocol layer without a network call.
Run on demand with:
    uv run pytest tests/test_smoke.py -v -m smoke

Excluded from the default CI run via:
    uv run pytest -m "not smoke"
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from hnf1b_mcp.server import build_app

pytestmark = pytest.mark.smoke

_EXPECTED_TOOLS = {
    "hnf1b_get_capabilities",
    "hnf1b_search",
    "hnf1b_get_individual",
    "hnf1b_get_individuals",
    "hnf1b_find_individuals_by_phenotype",
    "hnf1b_search_variants",
    "hnf1b_get_variant",
    "hnf1b_get_gene_context",
    "hnf1b_get_publications",
    "hnf1b_get_publication_passages",
    "hnf1b_get_statistics",
    "hnf1b_resolve_terms",
    "hnf1b_compare_phenotypes",
}

_EXPECTED_RESOURCES = {
    "hnf1b://schema/overview",
    "hnf1b://schema/tool-guide",
}


@pytest.mark.asyncio
async def test_client_pings():
    """In-memory client connects and responds to ping."""
    async with Client(build_app()) as client:
        result = await client.ping()
    assert result is True


@pytest.mark.asyncio
async def test_list_tools_returns_all_hnf1b_tools():
    """list_tools exposes exactly the expected hnf1b_* tool set."""
    async with Client(build_app()) as client:
        tools = await client.list_tools()

    names = {t.name for t in tools}
    assert names == _EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_all_tools_have_read_only_hint():
    """Every tool carries readOnlyHint=True in its annotations."""
    async with Client(build_app()) as client:
        tools = await client.list_tools()

    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        assert tool.annotations.readOnlyHint is True, (
            f"{tool.name}.readOnlyHint is not True"
        )


@pytest.mark.asyncio
async def test_all_tools_have_display_title():
    """Every tool carries a non-empty human-readable title (2025 ToolAnnotations).

    The title is the spec-blessed display name a client shows instead of the raw
    ``hnf1b_*`` identifier; this guards against a new tool regressing the set.
    """
    async with Client(build_app()) as client:
        tools = await client.list_tools()

    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        title = tool.annotations.title
        assert title and title.strip(), f"{tool.name} has no display title"


@pytest.mark.asyncio
async def test_sample_tool_has_open_world_hint_false():
    """hnf1b_get_capabilities has openWorldHint=False (sample check)."""
    async with Client(build_app()) as client:
        tools = await client.list_tools()

    cap = next(t for t in tools if t.name == "hnf1b_get_capabilities")
    assert cap.annotations is not None
    assert cap.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_list_resources_returns_schema_resources():
    """list_resources exposes the two hnf1b://schema/* resources."""
    async with Client(build_app()) as client:
        resources = await client.list_resources()

    uris = {str(r.uri) for r in resources}
    assert uris == _EXPECTED_RESOURCES


@pytest.mark.asyncio
async def test_call_capabilities_returns_valid_payload():
    """hnf1b_get_capabilities returns a capabilities dict without network I/O."""
    async with Client(build_app()) as client:
        result = await client.call_tool("hnf1b_get_capabilities", {})

    assert not result.is_error
    # Both .structured_content and .data hold the same dict
    sc = result.structured_content
    assert sc is not None
    assert sc["data_class"] == "operational_metadata"
    assert "meta" in sc
    assert "tools" in sc
    assert len(sc["tools"]) == 13

    # .data is the convenience alias
    assert result.data is not None
    assert result.data["data_class"] == "operational_metadata"
