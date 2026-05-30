"""Tests for the individuals tool registration and behavior."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools.individuals import register

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Realistic fixture data (mirrors test_individuals.py)
# ---------------------------------------------------------------------------

_PHENOPACKET_X: dict = {
    "id": "pp-X",
    "phenopacket_id": "X",
    "phenopacket": {
        "id": "X",
        "subject": {"id": "X", "sex": "MALE"},
        "phenotypicFeatures": [
            {
                "type": {"id": "HP:0000083", "label": "Renal insufficiency"},
                "excluded": False,
            },
        ],
        "measurements": [],
        "diseases": [{"term": {"id": "OMIM:137920", "label": "HNF1B-related disease"}}],
        "interpretations": [
            {
                "id": "interp-1",
                "progressStatus": "SOLVED",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": "X",
                            "interpretationStatus": "CAUSATIVE",
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "id": "var-1",
                                    "geneContext": {
                                        "geneId": "HGNC:11630",
                                        "symbol": "HNF1B",
                                    },
                                    "expressions": [
                                        {
                                            "syntax": "hgvs.c",
                                            "value": "NM_000458.4:c.544C>T",
                                        }
                                    ],
                                }
                            },
                        }
                    ]
                },
            }
        ],
        "metaData": {
            "externalReferences": [
                {"id": "PMID:12345678", "description": "Source publication"},
            ],
        },
    },
}

_PHENOPACKET_A: dict = {
    "id": "pp-A",
    "phenopacket_id": "A",
    "phenopacket": {
        "id": "A",
        "subject": {"id": "A", "sex": "FEMALE"},
        "phenotypicFeatures": [],
        "measurements": [],
        "diseases": [],
        "interpretations": [],
        "metaData": {"externalReferences": [{"id": "PMID:11111111"}]},
    },
}

_PHENOPACKET_B: dict = {
    "id": "pp-B",
    "phenopacket_id": "B",
    "phenopacket": {
        "id": "B",
        "subject": {"id": "B", "sex": "MALE"},
        "phenotypicFeatures": [],
        "measurements": [],
        "diseases": [],
        "interpretations": [],
        "metaData": {"externalReferences": [{"id": "PMID:22222222"}]},
    },
}

_PHENOPACKET_C: dict = {
    "id": "pp-C",
    "phenopacket_id": "C",
    "phenopacket": {
        "id": "C",
        "subject": {"id": "C", "sex": "MALE"},
        "phenotypicFeatures": [],
        "measurements": [],
        "diseases": [],
        "interpretations": [],
        "metaData": {"externalReferences": []},
    },
}

# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registers_all_three_tools():
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "hnf1b_get_individual" in names
    assert "hnf1b_get_individuals" in names
    assert "hnf1b_find_individuals_by_phenotype" in names


@pytest.mark.asyncio
async def test_get_individual_has_readonly_hint():
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_individual")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_get_individuals_has_readonly_hint():
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_individuals")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_find_individuals_by_phenotype_has_readonly_hint():
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_find_individuals_by_phenotype")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


# ---------------------------------------------------------------------------
# hnf1b_get_individual happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_happy_path():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "X"})
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    assert sc["phenopacket_id"] == "X"
    await client.aclose()


@pytest.mark.asyncio
async def test_find_by_phenotype_rejects_malformed_hpo_id():
    """A non-HPO-ID string returns invalid_input, not a misleading total:0."""
    mcp = FastMCP("test")
    register(mcp, ApiClient(base_url=BASE))

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype", {"hpo_ids": ["renal cyst"]}
    )
    sc = r.structured_content
    assert sc["is_error"] is True
    assert sc["error"]["code"] == "invalid_input"
    assert sc["error"]["field"] == "hpo_ids"
    # The hint must route the agent to the resolver, not leave it guessing.
    assert "resolve" in sc["error"]["hint"].lower()


@pytest.mark.asyncio
async def test_find_by_phenotype_accepts_valid_hpo_id_shape():
    """A well-formed HP:####### id passes validation (reaches the search call)."""
    mcp = FastMCP("test")
    with respx.mock:
        respx.get(f"{BASE}/phenopackets/search").mock(
            return_value=httpx.Response(
                200, json={"data": [], "meta": {"page": {"hasNextPage": False}}}
            )
        )
        register(mcp, ApiClient(base_url=BASE))
        r = await mcp.call_tool(
            "hnf1b_find_individuals_by_phenotype", {"hpo_ids": ["HP:0000107"]}
        )
    sc = r.structured_content
    # Valid shape, no matches -> a real empty cohort (total 0), NOT invalid_input.
    assert sc.get("is_error") is not True
    assert sc["total"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_subject_and_uri():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "X"})
    sc = r.structured_content

    assert sc["uri"] == "hnf1b://individual/X"
    assert sc["subject"]["sex"] == "MALE"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_phenotypic_features_present():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "X"})
    sc = r.structured_content

    assert len(sc["phenotypic_features"]) == 1
    assert sc["phenotypic_features"][0]["id"] == "HP:0000083"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_compact_marks_excluded_features():
    """Compact response shows excluded (confirmed-negative) features, not just a count."""
    pp = {
        "phenopacket_id": "Y",
        "phenopacket": {
            "subject": {"id": "Y", "sex": "FEMALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000107", "label": "Renal cysts"}},
                {
                    "type": {"id": "HP:0000819", "label": "Diabetes mellitus"},
                    "excluded": True,
                },
            ],
        },
    }
    respx.get(f"{BASE}/phenopackets/Y").mock(return_value=httpx.Response(200, json=pp))
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "Y"})
    sc = r.structured_content

    assert [f["id"] for f in sc["phenotypic_features"]] == ["HP:0000107"]
    assert [f["id"] for f in sc["excluded_features"]] == ["HP:0000819"]
    assert sc["feature_counts"] == {"observed": 1, "excluded": 1}
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_long_excluded_list_signal_in_meta():
    """A long excluded list surfaces a truncation signal in the tool meta block."""
    excluded = [
        {"type": {"id": f"HP:{i:07d}", "label": f"Excluded {i}"}, "excluded": True}
        for i in range(25)
    ]
    pp = {
        "phenopacket_id": "Z",
        "phenopacket": {
            "subject": {"id": "Z", "sex": "MALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000107", "label": "Renal cysts"}},
                *excluded,
            ],
        },
    }
    respx.get(f"{BASE}/phenopackets/Z").mock(return_value=httpx.Response(200, json=pp))
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "Z"})
    sc = r.structured_content

    assert len(sc["excluded_features"]) == 10
    assert sc["feature_counts"] == {"observed": 1, "excluded": 25}
    # The signal is hoisted into the meta block by run_tool, not left as _meta.
    assert "_meta" not in sc
    assert sc["meta"]["excluded_features_total"] == 25
    assert sc["meta"]["excluded_features_truncated"] is True
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_fields_projection_preserves_truncation_signal():
    """fields=["excluded_features"] must NOT silently strip the truncation signal.

    Regression: _select_fields kept only ``set(fields) | _ALWAYS_KEEP``, which
    did not include the internal ``_meta`` control channel. So an explicit
    ``fields=["excluded_features"]`` on a record with a long (>10) excluded list
    sampled the list to 10 but discarded the truncation signal before run_tool
    could hoist it — a silent truncation. The signal must survive into meta.
    """
    excluded = [
        {"type": {"id": f"HP:{i:07d}", "label": f"Excluded {i}"}, "excluded": True}
        for i in range(25)
    ]
    pp = {
        "phenopacket_id": "Z",
        "phenopacket": {
            "subject": {"id": "Z", "sex": "MALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000107", "label": "Renal cysts"}},
                *excluded,
            ],
        },
    }
    respx.get(f"{BASE}/phenopackets/Z").mock(return_value=httpx.Response(200, json=pp))
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_get_individual",
        {
            "phenopacket_id": "Z",
            "response_mode": "compact",
            "fields": ["excluded_features"],
        },
    )
    sc = r.structured_content

    # The requested field is sampled to 10 (the bound still applies)...
    assert len(sc["excluded_features"]) == 10
    # ...and the projection kept it (plus the always-kept id/uri).
    assert set(sc) >= {"phenopacket_id", "uri", "excluded_features"}
    # The internal channel is hoisted, never leaked as a data field.
    assert "_meta" not in sc
    # The truncation signal SURVIVES the explicit fields projection.
    assert sc["meta"]["excluded_features_total"] == 25
    assert sc["meta"]["excluded_features_returned"] == 10
    assert sc["meta"]["excluded_features_truncated"] is True
    assert "excluded_features_note" in sc["meta"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_variants_false():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_get_individual",
        {"phenopacket_id": "X", "include_variants": False},
    )
    sc = r.structured_content

    assert "variants" not in sc
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_not_found_returns_error_envelope():
    respx.get(f"{BASE}/phenopackets/MISSING").mock(return_value=httpx.Response(404))
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individual", {"phenopacket_id": "MISSING"})
    sc = r.structured_content

    assert sc.get("is_error") is True
    assert sc["error"]["code"] == "not_found"
    assert sc["error"]["field"] == "phenopacket_id"
    assert "MISSING" in sc["error"]["message"]
    await client.aclose()


# ---------------------------------------------------------------------------
# hnf1b_get_individuals happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_by_ids_batch():
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200, json={"results": [_PHENOPACKET_A, _PHENOPACKET_B]}
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individuals", {"ids": ["A", "B"]})
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    assert sc["total"] == 2
    assert len(sc["individuals"]) == 2
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_sex_filter_passed():
    list_resp = {
        "data": [{"attributes": {"phenopacket_id": "A"}}],
        "meta": {"total": 1},
    }
    route = respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json=list_resp)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individuals", {"sex": "FEMALE", "page_size": 10})
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert route.called
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_no_filters_passes_none():
    list_resp = {
        "data": [],
        "meta": {"total": 0},
    }
    respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json=list_resp)
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool("hnf1b_get_individuals", {})
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert sc["total"] == 0
    await client.aclose()


# ---------------------------------------------------------------------------
# hnf1b_find_individuals_by_phenotype
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_find_individuals_by_phenotype_happy_path():
    search_resp = {
        "data": [
            {"id": "A", "type": "phenopacket"},
            {"id": "B", "type": "phenopacket"},
        ]
    }
    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json=search_resp)
    )
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200, json={"results": [_PHENOPACKET_A, _PHENOPACKET_B]}
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083"]},
    )
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert "meta" in sc
    assert sc["total"] == 2
    assert len(sc["individuals"]) == 2
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_individuals_by_phenotype_dedupes_ids():
    # Two HPO terms both return the same individual A; A should appear once.
    search_resp_1 = {"data": [{"id": "A"}, {"id": "B"}]}
    search_resp_2 = {"data": [{"id": "A"}, {"id": "C"}]}
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=search_resp_1)
        return httpx.Response(200, json=search_resp_2)

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _PHENOPACKET_A,
                    _PHENOPACKET_B,
                    {
                        "id": "pp-C",
                        "phenopacket_id": "C",
                        "phenopacket": {
                            "id": "C",
                            "subject": {"id": "C", "sex": "MALE"},
                            "phenotypicFeatures": [],
                            "measurements": [],
                            "diseases": [],
                            "interpretations": [],
                            "metaData": {"externalReferences": []},
                        },
                    },
                ],
            },
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"]},
    )
    sc = r.structured_content

    # Unique IDs: A, B, C — total 3
    assert sc["total"] == 3
    ids = {ind["phenopacket_id"] for ind in sc["individuals"]}
    assert ids == {"A", "B", "C"}
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_individuals_by_phenotype_empty_search_result():
    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    # When no IDs are found, get_individuals is called without ids (discovery)
    respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:9999999"]},
    )
    sc = r.structured_content

    assert sc["data_class"] == "curated_hnf1b_evidence"
    assert sc["total"] == 0
    # A well-formed-yet-unmatched HPO id must be flagged, not silently dropped.
    assert sc["unmatched_hpo_ids"] == ["HP:9999999"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_reports_partial_unmatched():
    # HP:0000107 (first call) matches A; HP:9999999 (second call) does not.
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"data": [{"id": "A"}]})
        return httpx.Response(200, json={"data": []})

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json={"results": [_PHENOPACKET_A]})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000107", "HP:9999999"]},
    )
    sc = r.structured_content

    assert sc["total"] >= 1
    assert sc["unmatched_hpo_ids"] == ["HP:9999999"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_all_matched_reports_empty_unmatched():
    """The key is ALWAYS present; a fully-matched query reports an empty list."""
    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "A"}]})
    )
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json={"results": [_PHENOPACKET_A]})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083"]},
    )
    sc = r.structured_content

    assert sc["total"] >= 1
    assert sc["unmatched_hpo_ids"] == []
    await client.aclose()


# ---------------------------------------------------------------------------
# match_mode: "any" (union) vs "all" (intersection)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_match_mode_any_is_union():
    # term A matches {A, B, C}; term B matches {B, C, D}; UNION = {A,B,C,D}.
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200, json={"data": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}
            )
        return httpx.Response(
            200, json={"data": [{"id": "B"}, {"id": "C"}, {"id": "D"}]}
        )

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _PHENOPACKET_A,
                    _PHENOPACKET_B,
                    _PHENOPACKET_C,
                    {
                        "id": "pp-D",
                        "phenopacket_id": "D",
                        "phenopacket": {
                            "id": "D",
                            "subject": {"id": "D", "sex": "MALE"},
                            "phenotypicFeatures": [],
                            "measurements": [],
                            "diseases": [],
                            "interpretations": [],
                            "metaData": {"externalReferences": []},
                        },
                    },
                ]
            },
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"], "match_mode": "any"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "any"
    assert sc["total"] == 4
    ids = {ind["phenopacket_id"] for ind in sc["individuals"]}
    assert ids == {"A", "B", "C", "D"}
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_match_mode_all_is_intersection():
    # term A matches {1,2,3} == {A,B,C}; term B matches {2,3,4} == {B,C,D};
    # INTERSECTION = {B, C}. Order must follow first-seen input order.
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200, json={"data": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}
            )
        return httpx.Response(
            200, json={"data": [{"id": "B"}, {"id": "C"}, {"id": "D"}]}
        )

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200, json={"results": [_PHENOPACKET_B, _PHENOPACKET_C]}
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    assert sc["total"] == 2
    ids = {ind["phenopacket_id"] for ind in sc["individuals"]}
    assert ids == {"B", "C"}
    # A (only in term A) and D (only in term B) must be excluded.
    assert "A" not in ids
    assert "D" not in ids
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_match_mode_all_one_unmatched_term_empty():
    # term A matches {A}; term B (HP:9999999) matches nothing.
    # Under "all" the intersection MUST be empty and the term flagged unmatched.
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"data": [{"id": "A"}]})
        return httpx.Response(200, json={"data": []})

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000107", "HP:9999999"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    assert sc["total"] == 0
    assert sc["individuals"] == []
    assert sc["unmatched_hpo_ids"] == ["HP:9999999"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_single_term_any_equals_all():
    # With a single term, "any" and "all" must yield identical cohorts.
    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "A"}, {"id": "B"}]})
    )
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(
            200, json={"results": [_PHENOPACKET_A, _PHENOPACKET_B]}
        )
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r_all = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083"], "match_mode": "all"},
    )
    sc_all = r_all.structured_content
    assert sc_all["match_mode"] == "all"
    assert sc_all["total"] == 2
    assert {i["phenopacket_id"] for i in sc_all["individuals"]} == {"A", "B"}
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_all_intra_term_dupes_dont_satisfy_intersection():
    # term A returns A TWICE (duplicate within its own pages) and nothing else;
    # term B returns only B. Naive per-occurrence counting would count A twice
    # and falsely satisfy a 2-term intersection. Correct intersection = {} .
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"data": [{"id": "A"}, {"id": "A"}]})
        return httpx.Response(200, json={"data": [{"id": "B"}]})

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    # A appeared twice under ONE term but is absent from term B; B appeared under
    # ONE term only. Intersection across BOTH terms is empty.
    assert sc["total"] == 0
    assert sc["individuals"] == []
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_all_repeated_input_term_keeps_match():
    # A caller repeats the SAME term: ["HP:0000107", "HP:0000107"]. There is one
    # DISTINCT term, so the intersection threshold is 1 and any individual that
    # carries it must be kept. A naive per-occurrence count would increment the
    # term to 2 (> the distinct threshold of 1) and WRONGLY drop the true match.
    call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"data": [{"id": "A"}]})

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json={"results": [_PHENOPACKET_A]})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000107", "HP:0000107"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    # One distinct term matched {A}; the cohort must be {A}, NOT empty.
    assert sc["total"] == 1
    assert {i["phenopacket_id"] for i in sc["individuals"]} == {"A"}
    assert sc["unmatched_hpo_ids"] == []
    # The repeated term must be enumerated exactly once (no redundant backend
    # fetch for the duplicate input term).
    assert call_count == 1
    await client.aclose()


# ---------------------------------------------------------------------------
# Page-cap caveat: capping must surface total_is_capped + the under-inclusive
# "all"-mode warning on BOTH the populated AND the empty return paths.
# ---------------------------------------------------------------------------


def _full_page_always_next(page: int, end_cursor: str = "next") -> dict:
    """A search page that is always full and always reports hasNextPage.

    Returning *page* full ids with ``hasNextPage: true`` on every call drives
    ``_collect_matches`` to its ``_MAX_PAGES`` cap deterministically.
    """
    return {
        "data": [{"id": f"id-{i:04d}"} for i in range(page)],
        "meta": {"page": {"hasNextPage": True, "endCursor": end_cursor}},
    }


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_all_capped_nonempty_surfaces_caveat():
    """Capped + NON-empty "all" intersection → total_is_capped + caveat present.

    Both terms always return the SAME full page of ids (id-0000..id-0099) and
    always report hasNextPage, so every term hits the page cap (capped=True)
    yet the intersection across the two terms is non-empty.
    """
    from hnf1b_mcp.tools import individuals as individuals_mod

    page = individuals_mod._PAGE
    results = [
        {
            "id": f"pp-id-{i:04d}",
            "phenopacket_id": f"id-{i:04d}",
            "phenopacket": {
                "id": f"id-{i:04d}",
                "subject": {"id": f"id-{i:04d}", "sex": "MALE"},
                "phenotypicFeatures": [],
                "measurements": [],
                "diseases": [],
                "interpretations": [],
                "metaData": {"externalReferences": []},
            },
        }
        for i in range(page)
    ]

    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json=_full_page_always_next(page))
    )
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json={"results": results})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    # Both terms enumerate the same ids -> intersection is non-empty.
    assert sc["total"] > 0
    # _meta is hoisted into meta by run_tool; the capped signal must be present.
    assert sc["meta"]["total_is_capped"] is True
    assert "under-inclusive" in sc["meta"]["note"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_all_capped_empty_still_surfaces_caveat():
    """Finding-1 regression guard: capping-induced EMPTY "all" cohort.

    The two terms return DISJOINT full pages and both always report
    hasNextPage, so each term hits the page cap (capped=True) and the
    intersection is empty. The empty-cohort return path MUST still carry
    total_is_capped + the under-inclusive caveat — otherwise a capping-induced
    empty reads as a confident "0 individuals carry all these terms".
    """
    from hnf1b_mcp.tools import individuals as individuals_mod

    page = individuals_mod._PAGE

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        # Disjoint per-term id namespaces keyed off the queried HPO term, so the
        # two terms never share an id and the per-id count never reaches the
        # distinct-term threshold of 2 (intersection stays empty). hasNextPage is
        # always true, so each term hits the page cap (capped=True).
        term = request.url.params.get("hpo_id", "")
        data = [{"id": f"{term}-{i:04d}"} for i in range(page)]
        return httpx.Response(
            200,
            json={
                "data": data,
                "meta": {"page": {"hasNextPage": True, "endCursor": "next"}},
            },
        )

    respx.get(f"{BASE}/phenopackets/search").mock(side_effect=search_side_effect)
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083", "HP:0000107"], "match_mode": "all"},
    )
    sc = r.structured_content

    assert sc["match_mode"] == "all"
    # Disjoint per-term sets -> intersection empty.
    assert sc["total"] == 0
    assert sc["individuals"] == []
    # The empty path must STILL flag the capping + under-inclusive caveat.
    assert sc["meta"]["total_is_capped"] is True
    assert "under-inclusive" in sc["meta"]["note"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_match_mode_defaults_to_any():
    # No match_mode supplied → default "any"; returned field echoes "any".
    respx.get(f"{BASE}/phenopackets/search").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "A"}]})
    )
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json={"results": [_PHENOPACKET_A]})
    )
    client = ApiClient(base_url=BASE)
    mcp = FastMCP("test")
    register(mcp, client)

    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000083"]},
    )
    sc = r.structured_content
    assert sc["match_mode"] == "any"
    await client.aclose()
