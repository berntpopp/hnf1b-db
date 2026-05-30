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
    "molecular_consequence": "Missense",
}

# Real meta shape: meta.page.totalRecords / totalPages / currentPage.
ALL_VARIANTS_RESPONSE = {
    "data": [VARIANT_1],
    "meta": {
        "page": {
            "currentPage": 1,
            "pageSize": 25,
            "totalPages": 1,
            "totalRecords": 1,
        }
    },
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
    assert v["consequence"] == "Missense"
    assert v["carrier_count"] == 5

    # total resolved from meta.page.totalRecords, not 0
    assert sc["total"] == 1
    assert sc["page"] == 1
    assert sc["page_size"] == 25
    # compact (default) hoists invariant gene_symbol
    assert sc["gene_symbol_all"] == "HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_with_filters():
    """hnf1b_search_variants forwards filters to the service."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [],
                "meta": {
                    "page": {
                        "currentPage": 2,
                        "pageSize": 10,
                        "totalPages": 0,
                        "totalRecords": 0,
                    }
                },
            },
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_search_variants",
        {
            "query": "kidney",
            "classification": "PATHOGENIC",
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
    assert sent_params["domain"] == "POU Homeodomain"
    assert sent_params["page[number]"] == "2"
    assert sent_params["page[size]"] == "10"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_typed_sort_echoes_applied_sort():
    """A typed VariantSort value is honored and echoed back as applied_sort."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_search_variants", {"sort": "-carrier_count"})
    await client.aclose()

    # Wire: the public token is translated to the backend ORDER BY token.
    sent_params = dict(route.calls[0].request.url.params)
    assert sent_params["sort"] == "-individualCount"

    # Echo: the caller's public vocabulary confirms what the server did.
    sc = r.structured_content
    assert sc["meta"]["applied_sort"] == "-carrier_count"
    assert sc["meta"]["ignored_params"] == []


# ---------------------------------------------------------------------------
# hnf1b_get_variant — authoritative full record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_happy_path():
    """hnf1b_get_variant returns the authoritative full record + carriers."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    # full mode == keep-all, so the data_provenance/note prose is present.
    r = await mcp.call_tool(
        "hnf1b_get_variant",
        {"variant_id": "HNF1B:c.494G>A", "response_mode": "full"},
    )
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    assert sc["variant_id"] == "HNF1B:c.494G>A"
    assert sc["classification"] == "PATHOGENIC"
    assert sc["consequence"] == "Missense"
    assert sc["label"] == "c.494G>A (p.Arg165Gln)"
    assert sc["carriers"] == ["pp-001", "pp-002"]
    assert sc["carrier_count"] == 2
    assert sc["uri"] == "hnf1b://variant/HNF1B:c.494G>A"
    assert sc["data_provenance"] == "curated HNF1B-db variant record"
    assert "note" in sc
    # The wrapped meta states what carrier_count counts, so "most common" is
    # never ambiguous (distinct carrier individuals, not reports/publications).
    assert sc["meta"]["carrier_count_basis"] == "distinct_carrier_individuals"
    assert "publication" in sc["meta"]["carrier_count_note"].lower()


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_meta_documents_carrier_count_basis():
    """The wrapped search_variants meta documents the carrier_count basis."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_search_variants", {})
    await client.aclose()

    sc = r.structured_content
    assert sc["meta"]["carrier_count_basis"] == "distinct_carrier_individuals"
    assert "publication" in sc["meta"]["carrier_count_note"].lower()
