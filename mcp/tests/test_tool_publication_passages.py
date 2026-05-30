"""Tests for the hnf1b_get_publication_passages tool registration and behaviour."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.tools.publication_passages import register

BASE = "http://api.test/api/v2"

# Citation map source (GET /publications/) — must contain the passage's PMID so
# the recommended_citation resolves for the shaped passage.
_PUBS_RESPONSE = {
    "data": [
        {
            "pmid": "PMID:1001",
            "title": "HNF1B variants and kidney disease",
            "authors": "Smith J, Jones B",
            "journal": "Kidney Int",
            "year": 2022,
            "doi": "10.1016/j.kint.2022.01.001",
            "phenopacket_count": 5,
            "coverage": "full_text",
            "has_full_text": True,
        }
    ],
    "meta": {"page": {"totalRecords": 1, "currentPage": 1, "pageSize": 1000}},
}

_PASSAGES_RESPONSE = {
    "passages": [
        {
            "passage_id": "PMID:1001:results:0",
            "pmid": "PMID:1001",
            "section": "results",
            "seq": 4,
            "score": 0.0325,
            "source": "pubtator_full_bioc",
            "char_count": 60,
            "token_count": 9,
            "text": None,
            "snippet": "renal <b>cysts</b> and diabetes were frequent",
            "lexical_rank": 1,
            "dense_rank": 2,
        }
    ],
    "meta": {
        "query": "cystic kidney",
        "mode": "brief",
        "rerank_used": "rrf",
        "total": 1,
        "lexical_candidate_count": 3,
        "dense_candidate_count": 4,
        "embedding_dim": 384,
        "embeddings_available": True,
        "truncated": False,
        "notes": [],
    },
}

# A backend response where hybrid silently degraded to lexical (the common live
# state): the dense leg could not run, so embeddings_available is False.
_PASSAGES_RESPONSE_LEXICAL = {
    "passages": _PASSAGES_RESPONSE["passages"],
    "meta": {
        **_PASSAGES_RESPONSE["meta"],
        "rerank_used": "lexical",
        "dense_candidate_count": 0,
        "embedding_dim": None,
        "embeddings_available": False,
        "notes": ["dense disabled: no embedding provider available"],
    },
}


def _make_mcp_and_client() -> tuple[FastMCP, ApiClient]:  # type: ignore[type-arg]
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    client = ApiClient(base_url=BASE)
    register(mcp, client)
    return mcp, client


def _mock_both() -> None:
    respx.get(f"{BASE}/publications/passages").mock(
        return_value=httpx.Response(200, json=_PASSAGES_RESPONSE)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )


@pytest.mark.asyncio
async def test_registers_with_readonly_hint() -> None:
    """Tool is registered with readOnlyHint=True and openWorldHint=False."""
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_get_publication_passages")
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
@respx.mock
async def test_data_class_is_curated() -> None:
    _mock_both()
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "cystic kidney"}
    )
    await client.aclose()
    assert r.structured_content["data_class"] == DataClass.CURATED


@pytest.mark.asyncio
@respx.mock
async def test_passage_has_citation_and_snippet() -> None:
    _mock_both()
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "cystic kidney"}
    )
    await client.aclose()
    sc = r.structured_content
    assert sc["passages"]
    p = sc["passages"][0]
    assert p["passage_id"] == "PMID:1001:results:0"
    assert "Smith J, Jones B" in p["recommended_citation"]
    assert "2022" in p["recommended_citation"]
    assert "cysts" in p["snippet"]


@pytest.mark.asyncio
@respx.mock
async def test_score_present_in_compact_seq_source_only_in_full() -> None:
    _mock_both()
    mcp, client = _make_mcp_and_client()

    compact = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "renal cysts"}
    )
    p0 = compact.structured_content["passages"][0]
    assert "score" in p0  # caller can now judge relevance in the default mode
    assert "seq" not in p0 and "source" not in p0  # still trimmed in compact

    full = await mcp.call_tool(
        "hnf1b_get_publication_passages",
        {"query": "renal cysts", "response_mode": "full"},
    )
    pf = full.structured_content["passages"][0]
    assert "score" in pf and "seq" in pf and "source" in pf
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_meta_surfaces_retrieval_diagnostics() -> None:
    _mock_both()
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "cystic kidney"}
    )
    await client.aclose()
    meta = r.structured_content["meta"]
    assert meta["rerank_used"] == "rrf"
    assert meta["lexical_candidate_count"] == 3
    assert meta["dense_candidate_count"] == 4
    assert meta["embedding_dim"] == 384
    # The dense leg ran here, so the explicit availability flag is surfaced True.
    assert meta["embeddings_available"] is True


@pytest.mark.asyncio
@respx.mock
async def test_meta_surfaces_embeddings_available_false_in_compact_and_standard() -> (
    None
):
    """When hybrid silently degrades to lexical, meta.embeddings_available=False.

    The flag must travel in every response mode so an MCP client can tell that
    "hybrid" actually ran lexical-only (no embedding stack in the deployment).
    """
    respx.get(f"{BASE}/publications/passages").mock(
        return_value=httpx.Response(200, json=_PASSAGES_RESPONSE_LEXICAL)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()

    compact = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "cystic kidney"}
    )
    assert compact.structured_content["meta"]["embeddings_available"] is False

    standard = await mcp.call_tool(
        "hnf1b_get_publication_passages",
        {"query": "cystic kidney", "response_mode": "standard"},
    )
    assert standard.structured_content["meta"]["embeddings_available"] is False
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_params_forwarded() -> None:
    route = respx.get(f"{BASE}/publications/passages").mock(
        return_value=httpx.Response(200, json=_PASSAGES_RESPONSE)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    await mcp.call_tool(
        "hnf1b_get_publication_passages",
        {
            "query": "cystic kidney",
            "pmids": ["PMID:1001", "30791938"],
            "sections": ["results", "abstract"],
            "rerank": "lexical",
            "mode": "full",
            "limit": 5,
        },
    )
    await client.aclose()
    url = str(route.calls.last.request.url)
    assert "cystic+kidney" in url or "cystic%20kidney" in url
    assert "rerank=lexical" in url
    assert "mode=full" in url
    # PMID: prefix is stripped before forwarding.
    assert "1001" in url and "30791938" in url
    assert "results" in url


@pytest.mark.asyncio
@respx.mock
async def test_invalid_mode_rejected_by_schema_enum() -> None:
    """B7: ``mode`` is a Literal, so a typo is rejected at the schema boundary.

    The PassageMode enum makes FastMCP reject an out-of-set value during input
    validation (naming the allowed values), instead of forwarding it to the
    service guard — the whole point of promoting the param to an enum.
    """
    import pydantic_core

    _mock_both()
    mcp, client = _make_mcp_and_client()
    with pytest.raises(pydantic_core.ValidationError) as excinfo:
        await mcp.call_tool(
            "hnf1b_get_publication_passages", {"query": "x", "mode": "bogus"}
        )
    await client.aclose()
    # The validation error advertises the allowed values so a caller self-corrects.
    assert "brief" in str(excinfo.value)


@pytest.mark.asyncio
@respx.mock
async def test_invalid_mode_service_guard_still_returns_envelope() -> None:
    """Defense-in-depth: the runtime guard still yields the invalid_input envelope.

    A client that does not validate against the schema (or a direct service
    call) is still protected by the service-level check — Literal is a ``str``
    subtype, so the two compose.
    """
    from hnf1b_mcp.services import publication_passages as passages_service
    from hnf1b_mcp.services.errors import McpToolError

    _mock_both()
    mcp, client = _make_mcp_and_client()
    with pytest.raises(McpToolError) as excinfo:
        await passages_service.get_publication_passages(client, query="x", mode="bogus")
    await client.aclose()
    assert excinfo.value.code == "invalid_input"


@pytest.mark.asyncio
@respx.mock
async def test_no_citation_call_when_no_passages() -> None:
    """When the endpoint returns no passages, the citation map is not fetched."""
    respx.get(f"{BASE}/publications/passages").mock(
        return_value=httpx.Response(200, json={"passages": [], "meta": {}})
    )
    route_list = respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json=_PUBS_RESPONSE)
    )
    mcp, client = _make_mcp_and_client()
    r = await mcp.call_tool("hnf1b_get_publication_passages", {"query": "nomatch"})
    await client.aclose()
    assert r.structured_content["passages"] == []
    assert route_list.call_count == 0
