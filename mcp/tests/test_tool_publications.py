"""Tests for the hnf1b_get_publications tool registration and behaviour."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.tools.publications import register

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixture data — mirrors test_publications.py so mock JSON is consistent
# ---------------------------------------------------------------------------

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
}

_BY_PUB_RESPONSE = [
    {"phenopacket_id": "PP001", "phenopacket": {}},
    {"phenopacket_id": "PP002", "phenopacket": {}},
    {"phenopacket_id": "PP003", "phenopacket": {}},
]


# ---------------------------------------------------------------------------
# Helper: build a registered MCP + ApiClient pair
# ---------------------------------------------------------------------------


def _make_mcp_and_client() -> tuple[FastMCP, ApiClient]:  # type: ignore[type-arg]
    """Return a FastMCP instance with the tool registered and an ApiClient."""
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    client = ApiClient(base_url=BASE)
    register(mcp, client)
    return mcp, client


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registers_with_readonly_hint() -> None:
    """Tool is registered with readOnlyHint=True and openWorldHint=False."""
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_get_publications")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is False


# ---------------------------------------------------------------------------
# List path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_list_path_structured_content_data_class() -> None:
    """List path: data_class is CURATED."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == DataClass.CURATED


@pytest.mark.asyncio
@respx.mock
async def test_list_path_has_meta() -> None:
    """List path: response includes a meta block."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    sc = r.structured_content
    assert "meta" in sc


@pytest.mark.asyncio
@respx.mock
async def test_list_path_publications_list_present() -> None:
    """List path: publications list is present with expected length."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    sc = r.structured_content
    assert "publications" in sc
    assert len(sc["publications"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_list_path_publication_has_recommended_citation() -> None:
    """List path: each publication record has a recommended_citation."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    sc = r.structured_content
    pub = next(p for p in sc["publications"] if p["pmid"] == "PMID:1001")
    assert "recommended_citation" in pub
    assert "Smith J, Jones B" in pub["recommended_citation"]
    assert "2022" in pub["recommended_citation"]


@pytest.mark.asyncio
@respx.mock
async def test_list_path_total_from_meta() -> None:
    """List path: total comes from API meta, not list length."""
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    sc = r.structured_content
    assert sc["total"] == 42


@pytest.mark.asyncio
@respx.mock
async def test_list_path_year_filter_forwarded() -> None:
    """List path: year filter is forwarded as filter[year]."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    await mcp.call_tool("hnf1b_get_publications", {"year": 2022})
    await client.aclose()

    url_str = str(route.calls.last.request.url)
    assert "2022" in url_str
    assert "year" in url_str


@pytest.mark.asyncio
@respx.mock
async def test_list_path_has_doi_filter_forwarded() -> None:
    """List path: has_doi filter is forwarded when specified."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    await mcp.call_tool("hnf1b_get_publications", {"has_doi": True})
    await client.aclose()

    url_str = str(route.calls.last.request.url)
    assert "has_doi" in url_str


@pytest.mark.asyncio
@respx.mock
async def test_list_path_no_filter_when_none() -> None:
    """List path: None year/has_doi do not appear as filter params."""
    route = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    await mcp.call_tool("hnf1b_get_publications", {})
    await client.aclose()

    url_str = str(route.calls.last.request.url)
    assert "filter%5Byear%5D" not in url_str
    assert "filter[year]" not in url_str
    assert "filter%5Bhas_doi%5D" not in url_str
    assert "filter[has_doi]" not in url_str


# ---------------------------------------------------------------------------
# Reverse-lookup path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_reverse_lookup_path_citing_individuals() -> None:
    """Reverse-lookup path: citing_individuals list is returned."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {"citing_pmid": "123"})
    await client.aclose()

    sc = r.structured_content
    assert "citing_individuals" in sc
    assert sc["citing_individuals"] == ["PP001", "PP002", "PP003"]


@pytest.mark.asyncio
@respx.mock
async def test_reverse_lookup_path_data_class() -> None:
    """Reverse-lookup path: data_class is CURATED."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {"citing_pmid": "123"})
    await client.aclose()

    sc = r.structured_content
    assert sc["data_class"] == DataClass.CURATED


@pytest.mark.asyncio
@respx.mock
async def test_reverse_lookup_path_total() -> None:
    """Reverse-lookup path: total equals length of citing_individuals."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {"citing_pmid": "123"})
    await client.aclose()

    sc = r.structured_content
    assert sc["total"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_reverse_lookup_path_never_calls_list_endpoint() -> None:
    """Reverse-lookup path: the /publications/ list endpoint is NOT called."""
    route_list = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    await mcp.call_tool("hnf1b_get_publications", {"citing_pmid": "123"})
    await client.aclose()

    assert route_list.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_reverse_lookup_pmid_prefix_stripped() -> None:
    """Reverse-lookup path: PMID: prefix in citing_pmid is stripped."""
    respx.get(f"{BASE}/phenopackets/by-publication/123").mock(
        return_value=httpx.Response(200, json=_BY_PUB_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publications", {"citing_pmid": "PMID:123"})
    await client.aclose()

    sc = r.structured_content
    # The pmid field echoes the original input, but the API was called without prefix
    assert "citing_individuals" in sc
    assert sc["total"] == 3
