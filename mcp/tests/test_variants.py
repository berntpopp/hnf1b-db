"""Tests for hnf1b_mcp.services.variants."""

from __future__ import annotations

from typing import get_args

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.variants import (
    CARRIER_COUNT_BASIS,
    CARRIER_COUNT_NOTE,
    VARIANT_SORT_FIELDS,
    VariantSort,
    get_variant,
    search_variants,
)

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
async def test_search_variants_echoes_applied_filters_and_server_mode():
    """Active filters are echoed in _meta with filter_mode == 'server'.

    An agent can then programmatically confirm which predicates were honored and
    that they were applied server-side against an honest cross-page total — the
    machine-readable replacement for parsing a prose filter note.
    """
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 88}}}
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(
        client,
        consequence="Missense",
        classification="PATHOGENIC",
    )
    await client.aclose()

    assert result["_meta"]["filter_mode"] == "server"
    assert result["_meta"]["applied_filters"] == {
        "consequence": "Missense",
        "classification": "PATHOGENIC",
    }


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_no_filter_omits_filter_meta():
    """An unfiltered browse emits neither applied_filters nor filter_mode."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 0}}}
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client)
    await client.aclose()

    # No filters/sort -> _meta carries only the carrier_count basis,
    # never applied_filters/filter_mode.
    meta = result.get("_meta", {})
    assert "applied_filters" not in meta
    assert "filter_mode" not in meta


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_translates_and_echoes_sort():
    """Sort is translated to the backend token but echoed in the PUBLIC token."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 0}}}
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, sort="-carrier_count")
    await client.aclose()

    sent_params = dict(route.calls[0].request.url.params)
    # Wire: carrier_count -> individualCount (the token the backend honors).
    assert sent_params["sort"] == "-individualCount"
    # Echo: the caller's public vocabulary, never the internal column name.
    assert result["_meta"]["applied_sort"] == "-carrier_count"
    assert result["_meta"]["ignored_params"] == []


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_sort_alias_echoes_public_token():
    """A backend-token alias is accepted but echoed normalized to public form."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 0}}}
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, sort="-individualCount")
    await client.aclose()

    sent_params = dict(route.calls[0].request.url.params)
    assert sent_params["sort"] == "-individualCount"
    # Even when the caller used the internal alias, the echo is the public token.
    assert result["_meta"]["applied_sort"] == "-carrier_count"


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_unsortable_field_disclosed_not_silent():
    """A non-sortable field is NOT forwarded and is disclosed in meta."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 0}}}
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, sort="label")
    await client.aclose()

    sent_params = dict(route.calls[0].request.url.params)
    assert "sort" not in sent_params  # not silently sent as an ignored key
    assert result["_meta"]["applied_sort"] is None
    assert result["_meta"]["ignored_params"] == ["sort"]
    assert "sort_note" in result["_meta"]


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
async def test_search_variants_consequence_filtered_server_side():
    """Consequence is forwarded to the server, whose filtered data/total is trusted."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [VARIANT_1],  # server already filtered to Missense
                "meta": {
                    "page": {"totalRecords": 1, "totalPages": 1, "currentPage": 1}
                },
            },
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, consequence="Missense")
    await client.aclose()

    # consequence is forwarded for server-side filtering (no client shim).
    assert dict(route.calls[0].request.url.params)["consequence"] == "Missense"
    variants = result["variants"]
    assert len(variants) == 1
    assert variants[0]["consequence"] == "Missense"
    assert result["total"] == 1
    assert result["filtered_count"] == 1  # == server-side filtered total


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
async def test_search_variants_consequence_pagination_trusts_server():
    """Pagination is server-driven: MCP forwards page params and trusts totals."""
    # Server returns the requested page (2 of 5 filtered rows) with honest meta.
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [_make_missense(1), _make_missense(2)],
                "meta": {
                    "page": {"totalRecords": 5, "totalPages": 3, "currentPage": 1}
                },
            },
        )
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client, consequence="Missense", page=1, page_size=2)
    await client.aclose()

    sent = dict(route.calls[0].request.url.params)
    assert sent["page[number]"] == "1"
    assert sent["page[size]"] == "2"
    assert sent["consequence"] == "Missense"
    assert result["total"] == 5
    assert result["filtered_count"] == 5
    assert result["page"] == 1
    assert result["page_size"] == 2
    assert len(result["variants"]) == 2  # the server's page, trusted as-is
    assert result["total_pages"] == 3
    assert result["has_more"] is True


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
    # full mode == keep-all, so the complete authoritative record (including the
    # genomic-coordinate block + provenance prose) is returned.
    result = await get_variant(client, "HNF1B:c.494G>A", response_mode="full")
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
async def test_get_variant_by_simple_id_resolves_carriers_via_canonical_id():
    """A simple_id lookup must fetch carriers under the CANONICAL variant_id.

    Regression: the carrier endpoint was previously called with the raw caller
    input, so a simple_id ("var-1") hit /by-variant/var-1 (-> 200 []), leaving
    carriers empty while carrier_count fell back to the aggregate count. Only the
    canonical route is mocked here, so any call to /by-variant/var-1 would raise.
    """
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "var-1")  # friendly simple_id
    await client.aclose()

    assert result["variant_id"] == "HNF1B:c.494G>A"
    assert result["simple_id"] == "var-1"
    # Carriers resolved (not the empty/fallback path) and count agrees.
    assert result["carriers"] == ["pp-001", "pp-002"]
    assert result["carrier_count"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_trims_carriers_to_budget_in_minimal_mode():
    """A high-carrier variant must respect the minimal char budget.

    carrier_count stays the true total; the carriers LIST is trimmed with a
    machine-readable truncation signal so the omission is never silent.
    """
    many = [{"phenopacket_id": f"phenopacket-{i}"} for i in range(400)]
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=many)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "HNF1B:c.494G>A", response_mode="minimal")
    await client.aclose()

    assert result["carrier_count"] == 400  # true total preserved
    assert len(result["carriers"]) < 400  # list trimmed to fit the budget
    assert result["_meta"]["carriers_truncated"] is True
    assert result["_meta"]["carrier_count"] == 400
    assert result["_dropped"]["dropped_records"] > 0


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_full_mode_keeps_all_carriers():
    """Full mode (48 KB budget) keeps the entire carriers list untrimmed."""
    many = [{"phenopacket_id": f"phenopacket-{i}"} for i in range(400)]
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=many)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "HNF1B:c.494G>A", response_mode="full")
    await client.aclose()

    assert len(result["carriers"]) == 400
    assert "_dropped" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_minimal_has_fewer_fields_than_full():
    """The scalar field set forms a STRICT ladder minimal ⊊ compact ⊊ standard ⊊ full.

    response_mode previously only trimmed the carriers LIST, so a low-carrier
    variant returned an identical field set for every mode. The per-mode scalar
    projection must make each tier a genuinely smaller subset of the next; the
    strict-subset chain is the load-bearing regression guard against re-collapse
    (the "response_mode is inert" bug this task fixes). minimal keeps identity +
    interpretation; the coordinate block (hg38/transcript/protein) lands in
    standard; the provenance prose (data_provenance/note) is full-only.
    """
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    minimal = set(await get_variant(c, "HNF1B:c.494G>A", response_mode="minimal"))
    compact = set(await get_variant(c, "HNF1B:c.494G>A", response_mode="compact"))
    standard = set(await get_variant(c, "HNF1B:c.494G>A", response_mode="standard"))
    full = set(await get_variant(c, "HNF1B:c.494G>A", response_mode="full"))
    await c.aclose()

    # Strict ladder: each tier is a proper subset of the next.
    assert minimal < compact < standard < full
    assert {"variant_id", "label", "classification", "carrier_count"} <= minimal
    # The genomic-coordinate block lands in standard, not compact.
    assert {"hg38", "transcript", "protein"} <= standard
    assert "hg38" not in compact
    # Provenance prose is full-only.
    assert "data_provenance" not in standard and "note" not in standard
    assert "data_provenance" in full and "note" in full


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


# ---------------------------------------------------------------------------
# VariantSort enum drift guard
# ---------------------------------------------------------------------------


def test_variant_sort_enum_matches_sort_fields() -> None:
    """The VariantSort Literal must stay in lockstep with VARIANT_SORT_FIELDS.

    Every member is one of the canonical sort fields, optionally ``-``-prefixed
    for descending. Stripping the prefix must yield EXACTLY the keys of
    VARIANT_SORT_FIELDS — so editing one without the other fails fast here
    rather than silently shipping a sort vocabulary the tool cannot honor.
    """
    members = set(get_args(VariantSort))
    # Each public field appears in both directions: bare (asc) and '-' (desc).
    expected: set[str] = set()
    for field in VARIANT_SORT_FIELDS:
        expected.add(field)
        expected.add(f"-{field}")
    assert members == expected
    # The set of fields stripped of '-' equals the sort-field keys exactly.
    stripped = {m[1:] if m.startswith("-") else m for m in members}
    assert stripped == set(VARIANT_SORT_FIELDS)
    # No invented keys (e.g. 'position') leaked in.
    assert "position" not in stripped


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_accepts_variant_sort_member() -> None:
    """A typed VariantSort member is honored and echoed as applied_sort."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200, json={"data": [], "meta": {"page": {"totalRecords": 0}}}
        )
    )
    client = ApiClient(base_url=BASE)
    sort_value: VariantSort = "-carrier_count"
    result = await search_variants(client, sort=sort_value)
    await client.aclose()

    sent_params = dict(route.calls[0].request.url.params)
    assert sent_params["sort"] == "-individualCount"
    assert result["_meta"]["applied_sort"] == "-carrier_count"
    assert result["_meta"]["ignored_params"] == []


# ---------------------------------------------------------------------------
# carrier_count basis descriptor (self-documenting "common" ambiguity)
# ---------------------------------------------------------------------------


def test_carrier_count_basis_constants() -> None:
    """The shared basis string + note are defined once and are unambiguous.

    They must state that carrier_count counts DISTINCT CARRIER INDIVIDUALS
    (phenopackets), NOT reports/observations and NOT publications — so an
    evaluator never has to guess what "most common variant" means.
    """
    assert CARRIER_COUNT_BASIS == "distinct_carrier_individuals"
    note = CARRIER_COUNT_NOTE.lower()
    assert "distinct" in note
    assert "individual" in note or "phenopacket" in note
    assert "report" in note
    assert "publication" in note


@pytest.mark.asyncio
@respx.mock
async def test_search_variants_meta_carries_carrier_count_basis() -> None:
    """search_variants meta states what carrier_count counts, even unfiltered."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await search_variants(client)
    await client.aclose()

    meta = result["_meta"]
    assert meta["carrier_count_basis"] == "distinct_carrier_individuals"
    assert meta["carrier_count_note"] == CARRIER_COUNT_NOTE


@pytest.mark.asyncio
@respx.mock
async def test_get_variant_meta_carries_carrier_count_basis() -> None:
    """get_variant meta states what carrier_count counts (distinct individuals)."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(200, json=ALL_VARIANTS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-variant/HNF1B:c.494G>A").mock(
        return_value=httpx.Response(200, json=CARRIER_RESPONSE)
    )
    client = ApiClient(base_url=BASE)
    result = await get_variant(client, "HNF1B:c.494G>A", response_mode="full")
    await client.aclose()

    meta = result["_meta"]
    assert meta["carrier_count_basis"] == "distinct_carrier_individuals"
    assert meta["carrier_count_note"] == CARRIER_COUNT_NOTE
