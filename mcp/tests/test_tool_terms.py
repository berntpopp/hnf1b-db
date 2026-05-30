"""Tests for hnf1b_mcp.tools.terms — the hnf1b_resolve_terms MCP tool."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools.terms import register

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixture data — mirrors services/terms.py response shapes
# ---------------------------------------------------------------------------

_HPO_AUTOCOMPLETE_RESP = {
    "data": [
        {
            "hpo_id": "HP:0000083",
            "label": "Renal insufficiency",
            "category": "Renal",
            "description": "Reduced ability of the kidney to filter waste.",
            "synonyms": ["Kidney failure"],
        },
        {
            "hpo_id": "HP:0000107",
            "label": "Renal cysts",
            "category": "Renal",
            "description": "Fluid-filled sacs in the kidney.",
            "synonyms": [],
        },
    ]
}

_SEX_VOCAB_RESP = {
    "data": [
        {"id": "MALE", "label": "Male", "description": "Biological male"},
        {"id": "FEMALE", "label": "Female", "description": "Biological female"},
        {"id": "UNKNOWN_SEX", "label": "Unknown", "description": "Sex not recorded"},
    ]
}

_HPO_AUTOCOMPLETE_RESP_SCORED = {
    "data": [
        {
            "hpo_id": "HP:0000107",
            "label": "Renal cyst",
            "description": "Fluid-filled sacs in the kidney.",
            "similarity_score": 0.9,
            "phenopacket_count": 42,
        },
    ]
}


# ---------------------------------------------------------------------------
# Registration / annotation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registered_readonly() -> None:
    """Tool must be registered with readOnlyHint=True."""
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_resolve_terms")
    assert tool.annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_registered_not_open_world() -> None:
    """Tool must be registered with openWorldHint=False."""
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, None)
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "hnf1b_resolve_terms")
    assert tool.annotations.openWorldHint is False


# ---------------------------------------------------------------------------
# HPO path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_hpo_data_class() -> None:
    """structured_content must carry data_class == external_reference_identifier."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "renal"})
    sc = r.structured_content
    assert sc["data_class"] == "external_reference_identifier"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_hpo_meta_present() -> None:
    """structured_content must contain a meta block."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "renal"})
    sc = r.structured_content
    assert "meta" in sc
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_hpo_matches_list() -> None:
    """Matches must be a list of dicts with id and label."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "renal"})
    sc = r.structured_content
    matches = sc["matches"]
    assert isinstance(matches, list)
    assert len(matches) == 2
    for m in matches:
        assert "id" in m
        assert "label" in m
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_hpo_match_id_value() -> None:
    """HPO match id must be mapped from hpo_id."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "renal"})
    sc = r.structured_content
    assert sc["matches"][0]["id"] == "HP:0000083"
    assert sc["matches"][0]["label"] == "Renal insufficiency"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("mode", ["minimal", "compact", "standard", "full"])
async def test_hpo_score_survives_response_mode(mode: str) -> None:
    """The HPO relevance score forwards through the tool in every response mode."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP_SCORED)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool(
        "hnf1b_resolve_terms", {"text": "renal cyst", "response_mode": mode}
    )
    sc = r.structured_content
    assert sc["matches"][0]["id"] == "HP:0000107"
    assert sc["matches"][0]["score"] == 0.9
    await c.aclose()


# ---------------------------------------------------------------------------
# Controlled-vocabulary path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_sex_vocab_data_class() -> None:
    """Sex vocabulary path must also carry data_class == external_reference_identifier."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "", "vocabulary": "sex"})
    sc = r.structured_content
    assert sc["data_class"] == "external_reference_identifier"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_sex_vocab_matches_list() -> None:
    """Sex vocabulary must return all items when text is empty."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "", "vocabulary": "sex"})
    sc = r.structured_content
    matches = sc["matches"]
    assert isinstance(matches, list)
    assert len(matches) == 3
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_sex_vocab_match_fields() -> None:
    """Each sex vocabulary match must have id and label."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "", "vocabulary": "sex"})
    sc = r.structured_content
    first = sc["matches"][0]
    assert first["id"] == "MALE"
    assert first["label"] == "Male"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_sex_vocab_meta_present() -> None:
    """Sex vocabulary path must also include meta block."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    mcp: FastMCP = FastMCP("test")  # type: ignore[type-arg]
    register(mcp, c)
    r = await mcp.call_tool("hnf1b_resolve_terms", {"text": "", "vocabulary": "sex"})
    sc = r.structured_content
    assert "meta" in sc
    await c.aclose()
