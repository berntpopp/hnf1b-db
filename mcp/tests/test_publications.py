"""Tests for hnf1b_mcp.services.publications (TDD)."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.publications import (
    get_publication_citing_individuals,
    list_publications,
)

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# FLAT item shape matching the real API (no JSON:API attributes nesting)
_PUB_WITH_YEAR = {
    "pmid": "PMID:1001",
    "title": "HNF1B variants and kidney disease",
    "authors": "Smith J, Jones B",
    "journal": "Kidney Int",
    "year": 2022,
    "doi": "10.1016/j.kint.2022.01.001",
    "phenopacket_count": 5,
    "first_added": "2023-01-01",
}

_PUB_WITHOUT_YEAR = {
    "pmid": "PMID:1002",
    "title": "Early HNF1B study",
    "authors": "Brown K",
    "journal": "Nephrology",
    "year": None,
    "doi": None,
    "phenopacket_count": 2,
    "first_added": "2022-06-15",
}

# Real meta shape: meta.page.{totalRecords, currentPage, pageSize, totalPages}
_PUBS_RESPONSE = {
    "data": [_PUB_WITH_YEAR, _PUB_WITHOUT_YEAR],
    "meta": {
        "page": {
            "totalRecords": 42,
            "currentPage": 1,
            "pageSize": 25,
            "totalPages": 2,
        }
    },
    "links": {},
}

# Real by-publication shape: a BARE JSON list of {phenopacket_id, phenopacket}
_BY_PUB_RESPONSE = [
    {"phenopacket_id": "PP001", "phenopacket": {}},
    {"phenopacket_id": "PP002", "phenopacket": {}},
    {"phenopacket_id": "PP003", "phenopacket": {}},
]


# ---------------------------------------------------------------------------
# list_publications tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_returns_structured_result():
    """list_publications returns expected keys and correct count."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c)
    await c.aclose()

    assert "publications" in result
    assert result["total"] == 42
    assert result["page"] == 1
    assert result["page_size"] == 25
    assert len(result["publications"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_verified_citation():
    """Publication with year produces verified date_confidence."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, response_mode="full")
    await c.aclose()

    pub = next(p for p in result["publications"] if p["pmid"] == "PMID:1001")
    assert pub["date_confidence"] == "verified"
    assert "Smith J, Jones B" in pub["recommended_citation"]
    assert "2022" in pub["recommended_citation"]
    assert "10.1016/j.kint.2022.01.001" in pub["recommended_citation"]


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_unverified_citation():
    """Publication without year produces unverified date_confidence."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, response_mode="full")
    await c.aclose()

    pub = next(p for p in result["publications"] if p["pmid"] == "PMID:1002")
    assert pub["date_confidence"] == "unverified"
    assert "publication date unverified" in pub["recommended_citation"]


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_uri_shape():
    """Each publication has a uri shaped 'hnf1b://publication/PMID:{bare_id}'."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c)
    await c.aclose()

    pub = result["publications"][0]
    assert "uri" in pub
    # Must NOT double the PMID: prefix
    assert pub["uri"].startswith("hnf1b://publication/PMID:")
    bare = pub["uri"].replace("hnf1b://publication/PMID:", "")
    assert "PMID:" not in bare  # no double prefix


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_item_fields_full_mode():
    """In full mode each publication carries every structured field."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, response_mode="full")
    await c.aclose()

    pub = result["publications"][0]
    for key in (
        "pmid",
        "recommended_citation",
        "date_confidence",
        "journal",
        "year",
        "phenopacket_count",
        "uri",
    ):
        assert key in pub, f"missing key: {key}"


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_compact_trims_redundant_citation_fields():
    """Compact omits journal/year/date_confidence (already in the citation)."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, response_mode="compact")
    await c.aclose()

    pub = result["publications"][0]
    assert set(pub) == {"pmid", "recommended_citation", "phenopacket_count", "uri"}
    # default ordering is surfaced, never undocumented.
    assert result["applied_sort"] == "-phenopacket_count"


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_forwards_sort_and_defaults():
    """Sort is forwarded; default is -phenopacket_count and is echoed."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    default_result = await list_publications(c)
    await list_publications(c, sort="year")
    await c.aclose()

    assert default_result["applied_sort"] == "-phenopacket_count"
    assert "sort=-phenopacket_count" in str(route.calls[0].request.url)
    assert "sort=year" in str(route.calls[1].request.url)


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_passes_page_params():
    """Page and page_size are forwarded as JSON:API params."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    await list_publications(c, page=2, page_size=10)
    await c.aclose()

    assert route.called
    request = route.calls.last.request
    assert b"page%5Bnumber%5D=2" in request.url.query or "page[number]=2" in str(
        request.url
    )
    assert b"page%5Bsize%5D=10" in request.url.query or "page[size]=10" in str(
        request.url
    )


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_clamps_page_size():
    """page_size is clamped to 1000."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    await list_publications(c, page_size=9999)
    await c.aclose()

    request = route.calls.last.request
    url_str = str(request.url)
    # 9999 must NOT appear; 1000 must appear
    assert "9999" not in url_str
    assert "1000" in url_str


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_passes_q_and_filters():
    """Q and filters dict are forwarded as query parameters."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    await list_publications(
        c,
        q="HNF1B",
        filters={"year_gte": "2015", "has_doi": "true"},
    )
    await c.aclose()

    url_str = str(route.calls.last.request.url)
    assert "q=HNF1B" in url_str or "q=HNF1B" in str(route.calls.last.request.url)
    assert "2015" in url_str
    assert "has_doi" in url_str


# ---------------------------------------------------------------------------
# Defensive test: the service must NEVER call /publications/{pmid}/metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_never_calls_metadata_endpoint():
    """Defensive: no call to /publications/{pmid}/metadata is made or needed."""
    route_list = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    # NOTE: we deliberately do NOT register a mock for /publications/.*/metadata.
    # If the code attempted such a call, respx would raise an error (unmatched
    # request), making the test fail. This verifies the service stays allowlist-safe.
    c = ApiClient(base_url=BASE)
    await list_publications(c)
    await c.aclose()

    # Only the list endpoint was called
    assert route_list.call_count == 1


# ---------------------------------------------------------------------------
# get_publication_citing_individuals tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_publication_citing_individuals_returns_ids():
    """Returns correct phenopacket_ids and total count."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(c, "123")
    await c.aclose()

    assert result["pmid"] == "123"
    assert result["total"] == 3
    assert result["citing_individuals"] == ["PP001", "PP002", "PP003"]


@pytest.mark.asyncio
@respx.mock
async def test_get_publication_citing_individuals_empty():
    """Empty bare-list response returns zero total."""
    respx.get(f"{BASE}/phenopackets/by-publication/999").mock(
        return_value=httpx.Response(200, json=[])
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(c, "999")
    await c.aclose()

    assert result["total"] == 0
    assert result["citing_individuals"] == []


@pytest.mark.asyncio
@respx.mock
async def test_get_publication_citing_individuals_never_calls_metadata():
    """Defensive: reverse-lookup never calls /publications/.*/metadata."""
    route = respx.get(f"{BASE}/phenopackets/by-publication/456").mock(
        return_value=httpx.Response(200, json=[])
    )
    c = ApiClient(base_url=BASE)
    await get_publication_citing_individuals(c, "456")
    await c.aclose()

    assert route.call_count == 1


# ---------------------------------------------------------------------------
# citing_individuals summarization (default sample + opt-in full list)
# ---------------------------------------------------------------------------

# A foundational publication cited by many individuals — the uncapped-id-list
# defect this fix closes (the most-cited HNF1B paper is cited by ~75 individuals).
_MANY_CITING = [{"phenopacket_id": f"PP{i:03d}", "phenopacket": {}} for i in range(75)]


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("mode", ["compact", "standard"])
async def test_citing_individuals_summarized_by_default(mode: str):
    """DEFAULT: >10 citing individuals are sampled to <=10 with a meta signal.

    Core regression: the citing_pmid reverse lookup previously shipped ~75
    citing_individuals ids uncapped in compact/standard. The default now caps the
    LIST to the shared sample size and flags it in meta — total stays the true
    citing count.
    """
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_MANY_CITING)
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(c, "123", response_mode=mode)
    await c.aclose()

    assert result["total"] == 75  # true count preserved
    assert len(result["citing_individuals"]) == 10  # capped to the sample size
    meta = result["_meta"]
    assert meta["citing_individuals_truncated"] is True
    assert meta["citing_individuals_total"] == 75
    assert meta["citing_individuals_returned"] == 10
    note = meta["citing_individuals_note"]
    assert "include_citing_individuals" in note
    assert "hnf1b_find_individuals_by_phenotype" in note
    # No budget trim happened on the sample — the opt-in path owns _dropped.
    assert "_dropped" not in result


@pytest.mark.asyncio
@respx.mock
async def test_citing_individuals_full_via_opt_in():
    """include_citing_individuals=True returns the FULL list (budget permitting)."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_MANY_CITING)
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(
        c, "123", response_mode="full", include_citing_individuals=True
    )
    await c.aclose()

    assert result["total"] == 75
    assert len(result["citing_individuals"]) == 75  # full set returned
    # Full set fit the budget: no summarize-default signal and no budget trim.
    assert "_meta" not in result or "citing_individuals_truncated" not in result.get(
        "_meta", {}
    )
    assert "_dropped" not in result


@pytest.mark.asyncio
@respx.mock
async def test_citing_individuals_full_opt_in_budget_bounded():
    """include_citing_individuals=True is still bounded by the mode char budget."""
    huge = [
        {"phenopacket_id": f"phenopacket-{i:05d}", "phenopacket": {}}
        for i in range(4000)
    ]
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=huge)
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(
        c, "123", response_mode="minimal", include_citing_individuals=True
    )
    await c.aclose()

    assert result["total"] == 4000  # true count preserved
    assert len(result["citing_individuals"]) < 4000  # trimmed to fit budget
    assert result["_dropped"]["dropped_records"] > 0
    assert result["_meta"]["citing_individuals_truncated"] is True
    assert result["_meta"]["citing_individuals_total"] == 4000


@pytest.mark.asyncio
@respx.mock
async def test_citing_individuals_small_set_not_flagged():
    """<=10 citing individuals: all returned, no truncation signal."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)  # 3 items
    )
    c = ApiClient(base_url=BASE)
    result = await get_publication_citing_individuals(c, "123")
    await c.aclose()

    assert result["citing_individuals"] == ["PP001", "PP002", "PP003"]
    assert result["total"] == 3
    assert "_meta" not in result
    assert "_dropped" not in result


# ---------------------------------------------------------------------------
# Full-text coverage flags + abstract (mode-gated)
# ---------------------------------------------------------------------------

_PUB_WITH_COVERAGE = {
    "pmid": "PMID:2001",
    "title": "HNF1B full-text study",
    "authors": "Doe A",
    "journal": "J Nephrol",
    "year": 2021,
    "doi": "10.1/x",
    "phenopacket_count": 9,
    "coverage": "full_text",
    "abstract": "A long abstract about cystic kidney disease and HNF1B carriers.",
}
_COVERAGE_RESPONSE = {
    "data": [_PUB_WITH_COVERAGE],
    "meta": {"page": {"totalRecords": 1, "currentPage": 1, "pageSize": 25}},
}


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_exposes_coverage_flags_every_mode():
    """coverage/has_full_text ride along in every mode; abstract only standard+."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_COVERAGE_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    compact = (await list_publications(c, response_mode="compact"))["publications"][0]
    full = (await list_publications(c, response_mode="full"))["publications"][0]
    await c.aclose()

    # Tiny high-signal flags present in compact.
    assert compact["coverage"] == "full_text"
    assert compact["has_full_text"] is True
    assert "abstract" not in compact  # large field withheld in compact
    # The full abstract appears in the verbose tier.
    assert full["coverage"] == "full_text"
    assert "cystic kidney disease" in full["abstract"]


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_invalid_sort_raises_invalid_input():
    """An unknown sort field returns an actionable invalid_input error."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc:
        await list_publications(c, sort="bogus_field")
    await c.aclose()
    assert exc.value.code == "invalid_input"
    assert exc.value.details.get("argument") == "sort"


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_descending_sort_validates_bare_field():
    """A '-'-prefixed valid field passes validation and is forwarded."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, sort="-year")
    await c.aclose()
    assert result["applied_sort"] == "-year"
    assert dict(route.calls[0].request.url.params)["sort"] == "-year"


@pytest.mark.asyncio
@respx.mock
async def test_list_publications_enforces_char_budget():
    """A large page in minimal mode is trimmed to the budget with a signal."""
    big = [
        {
            "pmid": f"PMID:{i}",
            "title": "T",
            "authors": "A B",
            "journal": "J",
            "year": 2020,
            "doi": f"10.1/{i}",
            "phenopacket_count": 1,
        }
        for i in range(300)
    ]
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": big,
                "meta": {
                    "page": {"totalRecords": 300, "currentPage": 1, "pageSize": 300}
                },
            },
        )
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c, response_mode="minimal")
    await c.aclose()
    assert result["total"] == 300  # true count preserved
    assert len(result["publications"]) < 300  # trimmed to fit 4 KB
    assert result["_dropped"]["dropped_records"] > 0
