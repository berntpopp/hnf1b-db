"""Tests for hnf1b_mcp.services.terms – resolve_terms."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.terms import resolve_terms

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Fixture data
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


# ---------------------------------------------------------------------------
# HPO autocomplete tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_returns_matches() -> None:
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="renal", vocabulary="hpo", limit=10)
    await c.aclose()

    assert result["query"] == "renal"
    assert result["vocabulary"] == "hpo"
    matches = result["matches"]
    assert len(matches) == 2


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_maps_hpo_id_to_id() -> None:
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="renal", vocabulary="hpo")
    await c.aclose()

    first = result["matches"][0]
    assert first["id"] == "HP:0000083"
    assert first["label"] == "Renal insufficiency"
    assert "description" in first


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_second_item_id() -> None:
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="renal")
    await c.aclose()

    second = result["matches"][1]
    assert second["id"] == "HP:0000107"
    assert second["label"] == "Renal cysts"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_passes_limit_param() -> None:
    route = respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    await resolve_terms(c, text="renal", limit=5)
    await c.aclose()

    assert route.called
    req_url = str(route.calls[0].request.url)
    assert "limit=5" in req_url


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_passes_q_param() -> None:
    route = respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    await resolve_terms(c, text="kidney")
    await c.aclose()

    req_url = str(route.calls[0].request.url)
    assert "q=kidney" in req_url


# ---------------------------------------------------------------------------
# Controlled vocabulary tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_sex_vocab_returns_matches() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex")
    await c.aclose()

    assert result["vocabulary"] == "sex"
    matches = result["matches"]
    assert len(matches) == 3


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_sex_vocab_maps_id_label_description() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex")
    await c.aclose()

    first = result["matches"][0]
    assert first["id"] == "MALE"
    assert first["label"] == "Male"
    assert first["description"] == "Biological male"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_vocab_respects_limit() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex", limit=2)
    await c.aclose()

    assert len(result["matches"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_vocab_filters_by_text() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="male", vocabulary="sex")
    await c.aclose()

    # "MALE" and "Female" both contain "male" (case-insensitive)
    ids = {m["id"] for m in result["matches"]}
    assert "MALE" in ids
    assert "FEMALE" in ids


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_vocab_no_text_returns_all_capped() -> None:
    """Empty text returns all entries capped at limit."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex", limit=10)
    await c.aclose()

    assert len(result["matches"]) == 3


# ---------------------------------------------------------------------------
# Tests for other controlled vocabularies being accepted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_interpretation_status_accepted() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/interpretation-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"id": "CAUSATIVE", "label": "Causative", "description": ""}]
            },
        )
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="interpretation-status")
    await c.aclose()

    assert result["vocabulary"] == "interpretation-status"
    assert len(result["matches"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_allelic_state_accepted() -> None:
    respx.get(f"{BASE}/ontology/vocabularies/allelic-state").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "GENO:0000135", "label": "heterozygous"}]}
        )
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="allelic-state")
    await c.aclose()

    assert result["vocabulary"] == "allelic-state"
    # description key present even if missing from API (defaults to empty string)
    assert "description" in result["matches"][0]


# ---------------------------------------------------------------------------
# Invalid vocabulary test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_terms_unknown_vocabulary_raises_invalid_input() -> None:
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await resolve_terms(c, text="hello", vocabulary="bogus")
    await c.aclose()

    err = exc_info.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "vocabulary"
    assert "choices" in err.details
    assert "hpo" in err.details["choices"]
