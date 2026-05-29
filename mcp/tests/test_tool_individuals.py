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
    await client.aclose()
