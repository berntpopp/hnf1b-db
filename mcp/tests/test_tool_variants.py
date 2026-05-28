"""Tests for the hnf1b_search_variants and hnf1b_get_variant tool registration."""
from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools.variants import register

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Shared test data (mirrors test_variants.py shapes)
# ---------------------------------------------------------------------------

VARIANT_1 = {
    "simple_id": "var-1",
    "variant_id": "HNF1B:c.494G>A",
    "label": "c.494G>A (p.Arg165Gln)",
    "gene_symbol": "HNF1B",
    "structural_type": "SNV",
    "pathogenicity": "PATHOGENIC",
    "phenopacket_count": 5,
    "hg38": "17:36107165:G:A",
    "transcript": "NM_000458.3",
    "protein": "p.Arg165Gln",
    "molecular_consequence": "missense",
}

ALL_VARIANTS_RESPONSE = {
    "data": [VARIANT_1],
    "meta": {"total": 1},
}

CARRIER_RESPONSE = [
    {"phenopacket_id": "pp-001"},
    {"phenopacket_id": "pp-002"},
]


# ---------------------------------------------------------------------------
# Registration / annotation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_variants_registers_with_readonly_hint():
    """hnf1b_search_variants must expose readOnlyHint=True, openWorldHint=False."""
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_search_variants")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_get_variant_registers_with_readonly_hint():
    """hnf1b_get_variant must expose readOnlyHint=True, openWorldHint=False."""
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_variant")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


# ---------------------------------------------------------------------------
# hnf1b_search_variants — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_happy_path():
    """hnf1b_search_variants returns data_class=CURATED, meta, and variants."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_search_variants", {})
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    variants = sc["variants"]
    assert len(variants) == 1

    v = variants[0]
    assert v["variant_id"] == "HNF1B:c.494G>A"
    assert v["classification"] == "PATHOGENIC"
    assert v["consequence"] == "missense"
    assert v["carrier_count"] == 5
    assert v["uri"] == "hnf1b://variant/HNF1B:c.494G>A"

    assert sc["total"] == 1
    assert sc["page"] == 1
    assert sc["page_size"] == 25


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_with_filters():
    """hnf1b_search_variants forwards filters to the service."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_search_variants",
        {
            "query": "kidney",
            "classification": "PATHOGENIC",
            "consequence": "missense",
            "domain": "POU Homeodomain",
            "page": 2,
            "page_size": 10,
        },
    )
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert sc["variants"] == []

    call = route.calls[0]
    sent_params = dict(call.request.url.params)
    assert sent_params["query"] == "kidney"
    assert sent_params["classification"] == "PATHOGENIC"
    assert sent_params["consequence"] == "missense"
    assert sent_params["domain"] == "POU Homeodomain"
    assert sent_params["page[number]"] == "2"
    assert sent_params["page[size]"] == "10"


# ---------------------------------------------------------------------------
# hnf1b_get_variant — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_happy_path():
    """hnf1b_get_variant returns data_class=CURATED, meta, and carriers list."""
    respx.get(f"{BASE}/phenopackets/by-variant/var-1").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_variant", {"variant_id": "var-1"})
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    assert sc["variant_id"] == "var-1"
    assert sc["carriers"] == ["pp-001", "pp-002"]
    assert sc["carrier_count"] == 2
    assert sc["uri"] == "hnf1b://variant/var-1"
    assert "note" in sc
