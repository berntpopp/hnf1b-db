"""Tests for the hnf1b_get_statistics tool — Task 2g."""
from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.tools.statistics import register

BASE = "http://api.test/api/v2"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registers_with_readonly_hint() -> None:
    """Tool must be registered with readOnlyHint=True and openWorldHint=False."""
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_statistics")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


# ---------------------------------------------------------------------------
# Happy path — summary metric
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_summary_happy_path() -> None:
    """Happy-path call for metric='summary' returns data_class DERIVED + meta."""
    respx.get(f"{BASE}/phenopackets/aggregate/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_phenopackets": 42,
                "with_variant": 35,
                "with_hpo": 40,
            },
        )
    )
    from hnf1b_mcp.client.api_client import ApiClient

    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_statistics", {"metric": "summary"})
    sc = r.structured_content

    assert sc["data_class"] == "curated_derived_analysis"
    assert "meta" in sc
    assert sc["metric"] == "summary"
    assert sc["result"]["total_phenopackets"] == 42

    await client.aclose()


# ---------------------------------------------------------------------------
# dry_run — no HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_returns_available_no_http() -> None:
    """dry_run=True must return available=True without making any HTTP request."""
    from hnf1b_mcp.client.api_client import ApiClient

    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    # No respx mock — any real HTTP would fail
    r = await mcp.call_tool(
        "hnf1b_get_statistics", {"metric": "summary", "dry_run": True}
    )
    sc = r.structured_content

    assert sc["available"] is True
    assert sc["metric"] == "summary"

    await client.aclose()


# ---------------------------------------------------------------------------
# Error path — survival without comparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_survival_without_comparison_is_error() -> None:
    """metric='survival' without comparison must produce an is_error envelope."""
    from hnf1b_mcp.client.api_client import ApiClient

    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_statistics", {"metric": "survival"})
    sc = r.structured_content

    assert sc["is_error"] is True
    assert sc["error"]["code"] == "invalid_input"

    await client.aclose()
