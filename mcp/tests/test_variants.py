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

# Real meta shape: meta.page.totalRecords / totalPages / currentPage.
ALL_VARIANTS_RESPONSE = {
    "data": [VARIANT_1, VARIANT_2],
    "meta": {
        "page": {
            "currentPage": 1,
            "pageSize": 25,
            "totalPages": 2,
            "totalRecords": 42,
        }
    },
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
    """search_variants returns correctly shaped variant dicts (standard mode)."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, response_mode="standard")
    await client.aclose()

    # total reflects meta.page.totalRecords, NOT 0
    assert result["total"] == 42
    assert result["total_pages"] == 2
    assert result["has_more"] is True
    assert result["page"] == 1
    assert result["page_size"] == 25
    variants = result["variants"]
    assert len(variants) == 2

    v1 = variants[0]
    assert v1["simple_id"] == "var-1"
    assert v1["variant_id"] == "HNF1B:c.494G>A"
    assert v1["label"] == "c.494G>A (p.Arg165Gln)"
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
async def test_search_variants_total_not_zero_when_rows_present():
    """Total must equal totalRecords (41 here), never 0 with rows present."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [VARIANT_1],
                "meta": {
                    "page": {
                        "currentPage": 1,
                        "pageSize": 2,
                        "totalPages": 21,
                        "totalRecords": 41,
                    }
                },
            },
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, classification="PATHOGENIC")
    await client.aclose()

    assert result["total"] == 41
    assert result["total"] != 0
    assert result["total_pages"] == 21
    assert result["has_more"] is True


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_compact_hoists_gene_symbol():
    """Compact mode drops per-row gene_symbol and hoists gene_symbol_all."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, response_mode="compact")
    await client.aclose()

    assert result["gene_symbol_all"] == "HNF1B"
    row = result["variants"][0]
    assert "gene_symbol" not in row
    assert "uri" not in row  # deterministic, dropped in compact
    # high-signal fields always present
    for key in (
        "variant_id",
        "label",
        "classification",
        "consequence",
        "carrier_count",
    ):
        assert key in row


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_passes_filters():
    """search_variants forwards valid enum filters to the API."""
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
    result = await search_variants(
        client,
        query="kidney",
        classification="PATHOGENIC",
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
    assert sent_params["domain"] == "POU Homeodomain"
    assert sent_params["page[number]"] == "2"
    assert sent_params["page[size]"] == "10"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_page_size_capped_at_500():
    """search_variants caps page_size at 500."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={"data": [], "meta": {"page": {"totalRecords": 0}}},
        )
    )
    client = ApiClient(base_url=BASE)
    await search_variants(client, page_size=9999)
    await client.aclose()

    call = route.calls[0]
    assert dict(call.request.url.params)["page[size]"] == "500"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_consequence_post_filter():
    """Consequence filter post-filters rows client-side (upstream bug)."""
    # Upstream ignores ?consequence= and returns mixed rows; the MCP must
    # filter so only matching rows are returned.
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [VARIANT_1, VARIANT_2],  # Missense + Frameshift
                "meta": {"page": {"totalRecords": 198}},
            },
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, consequence="Missense")
    await client.aclose()

    variants = result["variants"]
    assert len(variants) == 1
    assert variants[0]["consequence"] == "Missense"
    assert result["filtered_count"] == 1
    assert result["total"] == 1
    assert "consequence_filter_note" in result


# Missense variant template — cloned N times for pagination test.
def _make_missense(n: int) -> dict:
    return {
        "simple_id": f"var-m{n}",
        "variant_id": f"HNF1B:c.{n}G>A",
        "label": f"c.{n}G>A",
        "gene_symbol": "HNF1B",
        "structural_type": "SNV",
        "pathogenicity": "PATHOGENIC",
        "phenopacket_count": 1,
        "hg38": f"17:36{n:06d}:G:A",
        "transcript": "NM_000458.3",
        "protein": "p.Xaa",
        "molecular_consequence": "Missense",
    }


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_consequence_respects_pagination():
    """Consequence post-filter must honour the caller's page / page_size."""
    # 5 Missense rows returned by the API (upstream ignores ?consequence=)
    missense_rows = [_make_missense(i) for i in range(1, 6)]
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": missense_rows,
                "meta": {"page": {"totalRecords": 5, "totalPages": 1, "currentPage": 1}},
            },
        )
    )
    client = ApiClient(base_url=BASE)
    # Request page 1 with page_size=2 → should get first 2 of 5 matching rows.
    result = await search_variants(client, consequence="Missense", page=1, page_size=2)
    await client.aclose()

    assert result["total"] == 5
    assert result["filtered_count"] == 5
    assert result["page"] == 1
    assert result["page_size"] == 2
    assert len(result["variants"]) == 2
    assert result["total_pages"] == 3  # ceil(5/2)
    assert result["has_more"] is True
    assert "consequence_filter_note" in result

    # Request page 2 → next 2 rows.
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": missense_rows,
                "meta": {"page": {"totalRecords": 5, "totalPages": 1, "currentPage": 1}},
            },
        )
    )
    client2 = ApiClient(base_url=BASE)
    result2 = await search_variants(client2, consequence="Missense", page=2, page_size=2)
    await client2.aclose()

    assert result2["page"] == 2
    assert len(result2["variants"]) == 2
    assert result2["has_more"] is True  # page 2 < 3

    # Request page 3 → last 1 row.
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": missense_rows,
                "meta": {"page": {"totalRecords": 5, "totalPages": 1, "currentPage": 1}},
            },
        )
    )
    client3 = ApiClient(base_url=BASE)
    result3 = await search_variants(client3, consequence="Missense", page=3, page_size=2)
    await client3.aclose()

    assert result3["page"] == 3
    assert len(result3["variants"]) == 1
    assert result3["has_more"] is False


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
# get_variant – authoritative full record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_returns_full_record():
    """get_variant merges the full variant record with carrier IDs."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "HNF1B:c.494G>A")
    await client.aclose()

    assert result["variant_id"] == "HNF1B:c.494G>A"
    # authoritative interpretation fields present
    assert result["classification"] == "PATHOGENIC"
    assert result["consequence"] == "Missense"
    assert result["label"] == "c.494G>A (p.Arg165Gln)"
    assert result["structural_type"] == "SNV"
    assert result["hg38"] == "17:36107165:G:A"
    assert result["transcript"] == "NM_000458.3"
    assert result["protein"] == "p.Arg165Gln"
    assert result["gene_symbol"] == "HNF1B"
    # carriers merged in
    assert result["carriers"] == ["pp-001", "pp-002"]
    assert result["carrier_count"] == 2
    assert result["uri"] == "hnf1b://variant/HNF1B:c.494G>A"
    assert result["data_provenance"] == "curated HNF1B-db variant record"
    assert "note" in result


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_not_found_when_no_match():
    """get_variant raises not_found when no variant matches the id."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await get_variant(client, "HNF1B:c.999X>Y")
    await client.aclose()

    err = exc_info.value
    assert err.code == "not_found"
    assert err.details.get("field") == "variant_id"
