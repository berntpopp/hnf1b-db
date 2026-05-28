"""Tests for hnf1b_mcp.services.search."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.search import search

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixture data — a mix of pp_, var_, pub_, gene_ prefixed IDs
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE = {
    "results": [
        {
            "id": "pp_001",
            "label": "Individual 001",
            "type": "individual",
            "subtype": "phenopacket",
            "extra_info": None,
            "score": 0.95,
        },
        {
            "id": "var_HNF1B:c.494G>A",
            "label": "c.494G>A (p.Arg165Gln)",
            "type": "variant",
            "subtype": "SNV",
            "extra_info": "PATHOGENIC",
            "score": 0.88,
        },
        {
            "id": "pub_12345678",
            "label": "Smith et al. 2020",
            "type": "publication",
            "subtype": None,
            "extra_info": None,
            "score": 0.75,
        },
        {
            "id": "gene_HNF1B",
            "label": "HNF1B",
            "type": "gene",
            "subtype": None,
            "extra_info": None,
            "score": 0.70,
        },
    ]
}

_EMPTY_RESPONSE: dict = {"results": []}


# ---------------------------------------------------------------------------
# URI derivation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_uri_individual_prefix():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    individual_hits = [h for h in result["hits"] if h["type"] == "individual"]
    assert len(individual_hits) == 1
    assert individual_hits[0]["uri"] == "hnf1b://individual/001"
    assert individual_hits[0]["id"] == "pp_001"


@pytest.mark.asyncio
@respx.mock
async def test_search_uri_variant_prefix():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    variant_hits = [h for h in result["hits"] if h["type"] == "variant"]
    assert len(variant_hits) == 1
    assert variant_hits[0]["uri"] == "hnf1b://variant/HNF1B:c.494G>A"
    assert variant_hits[0]["id"] == "var_HNF1B:c.494G>A"


@pytest.mark.asyncio
@respx.mock
async def test_search_uri_publication_prefix():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    pub_hits = [h for h in result["hits"] if h["type"] == "publication"]
    assert len(pub_hits) == 1
    assert pub_hits[0]["uri"] == "hnf1b://publication/PMID:12345678"
    assert pub_hits[0]["id"] == "pub_12345678"


@pytest.mark.asyncio
@respx.mock
async def test_search_uri_gene_prefix():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B", types=("gene",))
    await c.aclose()

    gene_hits = [h for h in result["hits"] if h["type"] == "gene"]
    assert len(gene_hits) == 1
    assert gene_hits[0]["uri"] == "hnf1b://gene/HNF1B"
    assert gene_hits[0]["id"] == "gene_HNF1B"


# ---------------------------------------------------------------------------
# Type filtering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_filter_variant_only():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B", types=("variant",))
    await c.aclose()

    assert len(result["hits"]) == 1
    assert result["hits"][0]["type"] == "variant"
    # counts should only include requested types
    assert "variant" in result["counts"]
    assert result["counts"]["variant"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_search_filter_individual_and_publication():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B", types=("individual", "publication"))
    await c.aclose()

    types_in_hits = {h["type"] for h in result["hits"]}
    assert types_in_hits == {"individual", "publication"}
    assert result["counts"]["individual"] == 1
    assert result["counts"]["publication"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_search_default_types_excludes_gene():
    """Default types=(individual, variant, publication) excludes gene hits."""
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    types_in_hits = {h["type"] for h in result["hits"]}
    assert "gene" not in types_in_hits
    assert "gene" not in result["counts"]


# ---------------------------------------------------------------------------
# Counts and structure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_counts_per_type():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(
        c,
        query="HNF1B",
        types=("individual", "variant", "publication", "gene"),
    )
    await c.aclose()

    assert result["counts"]["individual"] == 1
    assert result["counts"]["variant"] == 1
    assert result["counts"]["publication"] == 1
    assert result["counts"]["gene"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_search_result_structure():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    assert "query" in result
    assert result["query"] == "HNF1B"
    assert "hits" in result
    assert "counts" in result
    assert "guidance" in result
    assert isinstance(result["hits"], list)
    assert isinstance(result["counts"], dict)
    assert isinstance(result["guidance"], str)


@pytest.mark.asyncio
@respx.mock
async def test_search_hit_fields():
    """Each hit contains type, id, label, uri."""
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_SEARCH_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="HNF1B")
    await c.aclose()

    for hit in result["hits"]:
        assert "type" in hit
        assert "id" in hit
        assert "label" in hit
        assert "uri" in hit


# ---------------------------------------------------------------------------
# Empty results test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_empty_results():
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_EMPTY_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="nonexistent_xyz_query_123")
    await c.aclose()

    assert result["hits"] == []
    assert result["counts"] == {}
    assert result["query"] == "nonexistent_xyz_query_123"


# ---------------------------------------------------------------------------
# Query param forwarding tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_passes_query_and_page_size():
    route = respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_EMPTY_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    await search(c, query="kidney", limit=15)
    await c.aclose()

    call = route.calls[0]
    params = dict(call.request.url.params)
    assert params["q"] == "kidney"
    assert params["page_size"] == "15"


@pytest.mark.asyncio
@respx.mock
async def test_search_single_type_passes_type_param():
    """When types has a single entry, the type param is sent to the backend."""
    route = respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=_EMPTY_RESPONSE)
    )
    c = ApiClient(base_url=BASE)
    await search(c, query="HNF1B", types=("variant",))
    await c.aclose()

    call = route.calls[0]
    params = dict(call.request.url.params)
    assert "type" in params


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_empty_query_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search(c, query="")
    await c.aclose()

    assert exc_info.value.code == "invalid_input"
    assert exc_info.value.details.get("argument") == "query"


@pytest.mark.asyncio
async def test_search_blank_query_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search(c, query="   ")
    await c.aclose()

    assert exc_info.value.code == "invalid_input"


@pytest.mark.asyncio
async def test_search_invalid_type_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search(c, query="HNF1B", types=("bogus_type",))
    await c.aclose()

    assert exc_info.value.code == "invalid_input"
    assert exc_info.value.details.get("argument") == "types"


@pytest.mark.asyncio
async def test_search_invalid_limit_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await search(c, query="HNF1B", limit=0)
    await c.aclose()

    assert exc_info.value.code == "invalid_input"
    assert exc_info.value.details.get("argument") == "limit"


# ---------------------------------------------------------------------------
# JSON:API envelope support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_jsonapi_data_envelope():
    """Backend may wrap results in {data: [...]} JSON:API style."""
    jsonapi_response = {
        "data": [
            {
                "id": "pp_999",
                "label": "Individual 999",
                "type": "individual",
                "subtype": None,
                "extra_info": None,
                "score": 0.9,
            }
        ]
    }
    respx.get(f"{BASE}/search/global").mock(
        return_value=httpx.Response(200, json=jsonapi_response)
    )
    c = ApiClient(base_url=BASE)
    result = await search(c, query="test", types=("individual",))
    await c.aclose()

    assert len(result["hits"]) == 1
    assert result["hits"][0]["uri"] == "hnf1b://individual/999"


def test_pub_uri_not_double_prefixed():
    from hnf1b_mcp.services.search import _derive_uri

    # id already carrying PMID: must not become PMID:PMID:
    assert _derive_uri("pub_PMID:30666461") == (
        "publication",
        "hnf1b://publication/PMID:30666461",
    )
    # bare numeric id still gets a single PMID: prefix
    assert _derive_uri("pub_30666461") == (
        "publication",
        "hnf1b://publication/PMID:30666461",
    )
