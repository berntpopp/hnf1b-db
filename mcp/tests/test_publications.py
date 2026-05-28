"""Tests for hnf1b_mcp.services.publications (TDD)."""
from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.publications import (
    get_publication_citing_individuals,
    list_publications,
)

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_PUB_WITH_YEAR = {
    "id": "PMID:1001",
    "type": "Publication",
    "attributes": {
        "pmid": "PMID:1001",
        "title": "HNF1B variants and kidney disease",
        "authors": "Smith J, Jones B",
        "journal": "Kidney Int",
        "year": 2022,
        "doi": "10.1016/j.kint.2022.01.001",
        "phenopacket_count": 5,
        "first_added": "2023-01-01",
    },
}

_PUB_WITHOUT_YEAR = {
    "id": "PMID:1002",
    "type": "Publication",
    "attributes": {
        "pmid": "PMID:1002",
        "title": "Early HNF1B study",
        "authors": "Brown K",
        "journal": "Nephrology",
        "year": None,
        "doi": None,
        "phenopacket_count": 2,
        "first_added": "2022-06-15",
    },
}

_PUBS_RESPONSE = {
    "data": [_PUB_WITH_YEAR, _PUB_WITHOUT_YEAR],
    "meta": {
        "total": 42,
        "page": 1,
        "page_size": 25,
    },
}

_BY_PUB_RESPONSE = {
    "data": [
        {"id": "PP001", "type": "Phenopacket", "attributes": {"phenopacket_id": "PP001"}},
        {"id": "PP002", "type": "Phenopacket", "attributes": {"phenopacket_id": "PP002"}},
        {"id": "PP003", "type": "Phenopacket", "attributes": {"phenopacket_id": "PP003"}},
    ],
    "meta": {"total": 3},
}


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
    result = await list_publications(c)
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
    result = await list_publications(c)
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
async def test_list_publications_item_fields():
    """Each publication carries the required flat fields."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await list_publications(c)
    await c.aclose()

    pub = result["publications"][0]
    for key in ("pmid", "recommended_citation", "date_confidence", "journal", "year",
                "phenopacket_count", "uri"):
        assert key in pub, f"missing key: {key}"


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
    assert b"page%5Bnumber%5D=2" in request.url.query or "page[number]=2" in str(request.url)
    assert b"page%5Bsize%5D=10" in request.url.query or "page[size]=10" in str(request.url)


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
    """Empty data list returns zero total."""
    respx.get(f"{BASE}/phenopackets/by-publication/999").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
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
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    c = ApiClient(base_url=BASE)
    await get_publication_citing_individuals(c, "456")
    await c.aclose()

    assert route.call_count == 1
