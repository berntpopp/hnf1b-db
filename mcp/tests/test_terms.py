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

# The REAL backend HPO autocomplete (SELECT … similarity(label, q) AS
# similarity_score …) returns a pg_trgm trigram relevance score per row,
# 0–1, higher = better. The MCP must forward it verbatim onto a ``score`` key
# so a client can rank strong vs. weak HPO matches.
_HPO_AUTOCOMPLETE_RESP_SCORED = {
    "data": [
        {
            "hpo_id": "HP:0000107",
            "label": "Renal cyst",
            "description": "Fluid-filled sacs in the kidney.",
            "similarity_score": 0.9,
            "phenopacket_count": 42,
        },
        {
            "hpo_id": "HP:0000083",
            "label": "Renal insufficiency",
            "description": "Reduced ability of the kidney to filter waste.",
            "similarity_score": 0.25,
            "phenopacket_count": 7,
        },
    ]
}

# The REAL backend sex vocabulary is ``value``-keyed (no ``id`` column), with a
# Title-cased ``label``. The mapper must fall back to ``value`` for the id so
# the returned id is the "MALE"/"FEMALE" token the get_individuals(sex=…) filter
# expects — not an empty string.
_SEX_VOCAB_RESP_VALUE_KEYED = {
    "data": [
        {"value": "MALE", "label": "Male", "description": "Biological male"},
        {"value": "FEMALE", "label": "Female", "description": "Biological female"},
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
# HPO relevance score forwarding — the backend computes a per-hit trigram
# ``similarity_score`` (0–1, higher = better). The MCP must forward it verbatim
# onto a ``score`` key so a client can rank strong vs. weak HPO matches.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_forwards_similarity_score() -> None:
    """Each HPO hit's backend ``similarity_score`` forwards verbatim as ``score``."""
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP_SCORED)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="renal cyst", vocabulary="hpo")
    await c.aclose()

    matches = result["matches"]
    assert matches[0]["id"] == "HP:0000107"
    assert matches[0]["score"] == 0.9
    assert matches[1]["id"] == "HP:0000083"
    assert matches[1]["score"] == 0.25


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_hpo_without_score_omits_key() -> None:
    """An HPO hit lacking ``similarity_score`` shapes cleanly with NO ``score``.

    The forward must be guarded so a missing score never crashes and never
    fabricates a misleading value (e.g. a 0 that looks like a real weak match).
    """
    respx.get(f"{BASE}/ontology/hpo/autocomplete").mock(
        return_value=httpx.Response(200, json=_HPO_AUTOCOMPLETE_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="renal", vocabulary="hpo")
    await c.aclose()

    assert len(result["matches"]) == 2
    for match in result["matches"]:
        assert "score" not in match


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
async def test_resolve_terms_sex_value_keyed_id_falls_back_to_value() -> None:
    """Real backend sex rows are value-keyed; id must be the token, not ''."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP_VALUE_KEYED)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex")
    await c.aclose()

    ids = [m["id"] for m in result["matches"]]
    assert ids == ["MALE", "FEMALE"]  # usable directly as get_individuals(sex=…)
    assert result["matches"][0]["label"] == "Male"


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


@pytest.mark.asyncio
async def test_resolve_terms_rejects_nonpositive_limit() -> None:
    """A limit below 1 returns an actionable invalid_input error (no I/O)."""
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc_info:
        await resolve_terms(c, text="renal", vocabulary="hpo", limit=0)
    await c.aclose()
    err = exc_info.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "limit"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_terms_vocab_cap_emits_truncation_signal() -> None:
    """A controlled-vocab list capped by limit surfaces total_matches/returned."""
    respx.get(f"{BASE}/ontology/vocabularies/sex").mock(
        return_value=httpx.Response(200, json=_SEX_VOCAB_RESP)
    )
    c = ApiClient(base_url=BASE)
    result = await resolve_terms(c, text="", vocabulary="sex", limit=2)
    await c.aclose()
    assert len(result["matches"]) == 2
    assert result["_meta"]["total_matches"] == 3
    assert result["_meta"]["returned"] == 2
