"""Tests for hnf1b_mcp.services.variants."""
from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.variants import get_variant, search_variants

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

VARIANT_1 = {
    "simple_id": "var-1",
    "variant_id": "HNF1B:c.494G>A",
    "label": "c.494G>A (p.Arg165Gln)",
    "gene_symbol": "HNF1B",
    "gene_id": "ENSG00000275410",
    "structural_type": "SNV",
    "pathogenicity": "PATHOGENIC",
    "phenopacket_count": 5,
    "hg38": "17:36107165:G:A",
    "transcript": "NM_000458.3",
    "protein": "p.Arg165Gln",
    "molecular_consequence": "Missense",
}

VARIANT_2 = {
    "simple_id": "var-2",
    "variant_id": "HNF1B:c.1A>T",
    "label": "c.1A>T (p.Met1Leu)",
    "gene_symbol": "HNF1B",
    "gene_id": "ENSG00000275410",
    "structural_type": "SNV",
    "pathogenicity": "LIKELY_PATHOGENIC",
    "phenopacket_count": 2,
    "hg38": "17:36000000:A:T",
    "transcript": "NM_000458.3",
    "protein": "p.Met1Leu",
    "molecular_consequence": "Frameshift",
}

ALL_VARIANTS_RESPONSE = {
    "data": [VARIANT_1, VARIANT_2],
    "meta": {"total": 42},
}

CARRIER_RESPONSE = [
    {"phenopacket_id": "pp-001", "some_other_field": "ignored"},
    {"phenopacket_id": "pp-002", "some_other_field": "also_ignored"},
]


# ---------------------------------------------------------------------------
# search_variants – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_shapes_items():
    """search_variants returns correctly shaped variant dicts."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client)
    await client.aclose()

    assert result["total"] == 42
    assert result["page"] == 1
    assert result["page_size"] == 25
    variants = result["variants"]
    assert len(variants) == 2

    v1 = variants[0]
    assert v1["simple_id"] == "var-1"
    assert v1["variant_id"] == "HNF1B:c.494G>A"
    assert v1["label"] == "c.494G>A (p.Arg165Gln)"
    assert v1["gene_symbol"] == "HNF1B"
    assert v1["structural_type"] == "SNV"
    # enum mapping: pathogenicity → classification
    assert v1["classification"] == "PATHOGENIC"
    # enum mapping: molecular_consequence → consequence
    assert v1["consequence"] == "Missense"
    assert v1["hg38"] == "17:36107165:G:A"
    assert v1["transcript"] == "NM_000458.3"
    assert v1["protein"] == "p.Arg165Gln"
    assert v1["carrier_count"] == 5
    assert v1["uri"] == "hnf1b://variant/HNF1B:c.494G>A"

    v2 = variants[1]
    assert v2["classification"] == "LIKELY_PATHOGENIC"
    assert v2["consequence"] == "Frameshift"
    assert v2["carrier_count"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_passes_filters():
    """search_variants forwards valid enum filters to the API."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(
        client,
        query="kidney",
        classification="PATHOGENIC",
        consequence="Missense",
        domain="POU Homeodomain",
        page=2,
        page_size=10,
    )
    await client.aclose()

    assert result["total"] == 0
    assert result["page"] == 2
    assert result["page_size"] == 10
    call = route.calls[0]
    sent_params = dict(call.request.url.params)
    assert sent_params["query"] == "kidney"
    assert sent_params["classification"] == "PATHOGENIC"
    assert sent_params["consequence"] == "Missense"
    assert sent_params["domain"] == "POU Homeodomain"
    assert sent_params["page[number]"] == "2"
    assert sent_params["page[size]"] == "10"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_page_size_capped_at_500():
    """search_variants caps page_size at 500."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    client = ApiClient(base_url=BASE)
    await search_variants(client, page_size=9999)
    await client.aclose()

    call = route.calls[0]
    assert dict(call.request.url.params)["page[size]"] == "500"


# ---------------------------------------------------------------------------
# search_variants – enum validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_classification_raises():
    """search_variants raises McpToolError for unknown classification."""
    client = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search_variants(client, classification="BOGUS")
    await client.aclose()

    err = exc_info.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "classification"
    assert "choices" in err.details


@pytest.mark.asyncio
async def test_invalid_consequence_raises():
    """search_variants raises McpToolError for unknown consequence."""
    client = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search_variants(client, consequence="UNKNOWN_CONS")
    await client.aclose()

    err = exc_info.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "consequence"


@pytest.mark.asyncio
async def test_invalid_domain_raises():
    """search_variants raises McpToolError for unknown domain."""
    client = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search_variants(client, domain="Bad Domain")
    await client.aclose()

    err = exc_info.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "domain"


# ---------------------------------------------------------------------------
# get_variant – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_returns_carriers():
    """get_variant extracts phenopacket_ids and returns carrier list."""
    respx.get(f"{BASE}/phenopackets/by-variant/var-1").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "var-1")
    await client.aclose()

    assert result["variant_id"] == "var-1"
    assert result["carriers"] == ["pp-001", "pp-002"]
    assert result["carrier_count"] == 2
    assert result["uri"] == "hnf1b://variant/var-1"
    assert "note" in result


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_empty_carriers():
    """get_variant handles an empty carrier list."""
    respx.get(f"{BASE}/phenopackets/by-variant/rare-var").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "rare-var")
    await client.aclose()

    assert result["carriers"] == []
    assert result["carrier_count"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_not_found_propagates():
    """get_variant propagates McpToolError not_found from ApiClient."""
    respx.get(f"{BASE}/phenopackets/by-variant/missing").mock(
        return_value=httpx.Response(404)
    )
    client = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await get_variant(client, "missing")
    await client.aclose()

    assert exc_info.value.code == "not_found"
