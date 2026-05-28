"""Tests for services/individuals.py — get_individual and get_individuals."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.individuals import get_individual, get_individuals

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Realistic fixture data
# ---------------------------------------------------------------------------

_PHENOPACKET_X: dict = {
    "id": "pp-X",
    "phenopacket_id": "X",
    "version": 1,
    "revision": 0,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "schema_version": "2.0",
    "phenopacket": {
        "id": "X",
        "subject": {
            "id": "X",
            "sex": "MALE",
            "timeAtLastEncounter": {"age": {"iso8601duration": "P30Y"}},
        },
        "phenotypicFeatures": [
            {
                "type": {"id": "HP:0000083", "label": "Renal insufficiency"},
                "excluded": False,
            },
            {"type": {"id": "HP:0000107", "label": "Renal cysts"}, "excluded": False},
        ],
        "measurements": [
            {
                "assay": {"id": "LOINC:2160-0", "label": "Creatinine"},
                "value": {
                    "quantity": {
                        "value": 1.2,
                        "unit": {"id": "UCUM:mg/dL", "label": "mg/dL"},
                    }
                },
            }
        ],
        "diseases": [
            {
                "term": {"id": "OMIM:137920", "label": "HNF1B-related disease"},
                "onset": {
                    "ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}
                },
            }
        ],
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
                                    "vcfRecord": {
                                        "chrom": "17",
                                        "pos": "36099020",
                                        "ref": "C",
                                        "alt": "T",
                                    },
                                    "expressions": [
                                        {
                                            "syntax": "hgvs.c",
                                            "value": "NM_000458.4:c.544C>T",
                                        }
                                    ],
                                    "allelicState": {
                                        "id": "GENO:0000135",
                                        "label": "heterozygous",
                                    },
                                }
                            },
                        }
                    ]
                },
            }
        ],
        "medicalActions": [],
        "metaData": {
            "created": "2024-01-01T00:00:00Z",
            "createdBy": "curator",
            "externalReferences": [
                {"id": "PMID:12345678", "description": "Source publication"},
                {"id": "PMID:87654321", "description": "Second publication"},
                {"id": "OMIM:137920", "description": "Disease entry (no PMID)"},
            ],
        },
    },
}

_PHENOPACKET_A: dict = {
    "id": "pp-A",
    "phenopacket_id": "A",
    "version": 1,
    "revision": 0,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "schema_version": "2.0",
    "phenopacket": {
        "id": "A",
        "subject": {"id": "A", "sex": "FEMALE"},
        "phenotypicFeatures": [],
        "measurements": [],
        "diseases": [],
        "interpretations": [],
        "medicalActions": [],
        "metaData": {"externalReferences": [{"id": "PMID:11111111"}]},
    },
}

_PHENOPACKET_B: dict = {
    "id": "pp-B",
    "phenopacket_id": "B",
    "version": 1,
    "revision": 0,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "schema_version": "2.0",
    "phenopacket": {
        "id": "B",
        "subject": {"id": "B", "sex": "MALE"},
        "phenotypicFeatures": [],
        "measurements": [],
        "diseases": [],
        "interpretations": [],
        "medicalActions": [],
        "metaData": {"externalReferences": [{"id": "PMID:22222222"}]},
    },
}

# Real batch-endpoint shape: bare list of {phenopacket_id, phenopacket} objects.
_BATCH_ITEM_A: dict = {
    "phenopacket_id": "A",
    "phenopacket": _PHENOPACKET_A["phenopacket"],
}
_BATCH_ITEM_B: dict = {
    "phenopacket_id": "B",
    "phenopacket": _PHENOPACKET_B["phenopacket"],
}

# Real list-endpoint item shape: raw phenopacket with top-level "id" (no phenopacket_id).
_LIST_ITEM_A: dict = {
    "id": "A",
    "subject": {"id": "A", "sex": "FEMALE"},
    "phenotypicFeatures": [],
    "measurements": [],
    "diseases": [],
    "interpretations": [],
    "medicalActions": [],
    "metaData": {"externalReferences": [{"id": "PMID:11111111"}]},
}
_LIST_ITEM_B: dict = {
    "id": "B",
    "subject": {"id": "B", "sex": "MALE"},
    "phenotypicFeatures": [],
    "measurements": [],
    "diseases": [],
    "interpretations": [],
    "medicalActions": [],
    "metaData": {"externalReferences": [{"id": "PMID:22222222"}]},
}


# ---------------------------------------------------------------------------
# get_individual tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_shaped_fields_present():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X")
    await c.aclose()

    assert result["phenopacket_id"] == "X"
    assert result["uri"] == "hnf1b://individual/X"
    assert result["subject"]["sex"] == "MALE"
    assert len(result["phenotypic_features"]) == 2
    assert result["phenotypic_features"][0]["id"] == "HP:0000083"
    assert len(result["diseases"]) == 1
    assert len(result["measurements"]) == 1
    assert len(result["variants"]) == 1
    assert result["variants"][0]["gene"] == "HNF1B"
    assert result["variants"][0]["hgvs"] == "NM_000458.4:c.544C>T"


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_uri_correct():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X")
    await c.aclose()

    assert result["uri"] == "hnf1b://individual/X"


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_publication_has_recommended_citation():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X")
    await c.aclose()

    # Only PMID references should be included (not OMIM:137920)
    assert len(result["publications"]) == 2
    pub = result["publications"][0]
    assert "recommended_citation" in pub
    assert "date_confidence" in pub
    assert pub["pmid"] in ("12345678", "87654321")


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_variants_false_omits_key():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", include_variants=False)
    await c.aclose()

    assert "variants" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_phenotypes_false_omits_key():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", include_phenotypes=False)
    await c.aclose()

    assert "phenotypic_features" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_measurements_false_omits_key():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", include_measurements=False)
    await c.aclose()

    assert "measurements" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_publications_false_omits_key():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", include_publications=False)
    await c.aclose()

    assert "publications" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_not_found_raises():
    respx.get(f"{BASE}/phenopackets/MISSING").mock(return_value=httpx.Response(404))
    c = ApiClient(base_url=BASE)
    from hnf1b_mcp.services.errors import McpToolError

    with pytest.raises(McpToolError) as exc_info:
        await get_individual(c, "MISSING")
    await c.aclose()
    assert exc_info.value.code == "not_found"


# ---------------------------------------------------------------------------
# get_individuals tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_by_ids_uses_batch():
    # Batch endpoint returns a BARE LIST (not a {results:[...]} envelope)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_A, _BATCH_ITEM_B])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "B"])
    await c.aclose()

    assert result["total"] == 2
    assert len(result["individuals"]) == 2
    ids = {ind["phenopacket_id"] for ind in result["individuals"]}
    assert ids == {"A", "B"}


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_by_ids_uri_present():
    # Batch endpoint returns a BARE LIST (not a {results:[...]} envelope)
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_A, _BATCH_ITEM_B])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "B"])
    await c.aclose()

    for ind in result["individuals"]:
        pid = ind["phenopacket_id"]
        assert ind["uri"] == f"hnf1b://individual/{pid}"


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_list_endpoint():
    # Real API shape: data items have top-level "id"; meta uses page.totalRecords
    list_resp = {
        "data": [_LIST_ITEM_A, _LIST_ITEM_B],
        "meta": {
            "page": {
                "currentPage": 1,
                "pageSize": 10,
                "totalPages": 1,
                "totalRecords": 2,
            }
        },
        "links": {},
    }
    respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json=list_resp)
    )
    # Each individual fetched separately when expand=True
    respx.get(f"{BASE}/phenopackets/A").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_A)
    )
    respx.get(f"{BASE}/phenopackets/B").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_B)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, page_size=10, expand=True)
    await c.aclose()

    assert result["total"] == 2
    assert result["page_size"] == 10
    assert len(result["individuals"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_list_stub_no_expand():
    # Without expand=True the service returns minimal stubs; ids must be non-empty
    list_resp = {
        "data": [_LIST_ITEM_A, _LIST_ITEM_B],
        "meta": {
            "page": {
                "currentPage": 1,
                "pageSize": 25,
                "totalPages": 1,
                "totalRecords": 2,
            }
        },
        "links": {},
    }
    respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json=list_resp)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, page_size=25)
    await c.aclose()

    assert result["total"] == 2
    for ind in result["individuals"]:
        assert ind["phenopacket_id"] != ""
        assert ind["uri"] == f"hnf1b://individual/{ind['phenopacket_id']}"


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_filters_passed():
    list_resp = {
        "data": [_LIST_ITEM_A],
        "meta": {
            "page": {
                "currentPage": 1,
                "pageSize": 5,
                "totalPages": 1,
                "totalRecords": 1,
            }
        },
        "links": {},
    }
    route = respx.get(f"{BASE}/phenopackets/").mock(
        return_value=httpx.Response(200, json=list_resp)
    )
    respx.get(f"{BASE}/phenopackets/A").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_A)
    )
    c = ApiClient(base_url=BASE)
    await get_individuals(c, filters={"sex": "FEMALE"}, page_size=5)
    await c.aclose()

    # The request should include filter[sex] in params
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_dedupe_publications():
    # Both phenopackets share PMID:11111111; batch returns a BARE LIST
    inner_b_shared: dict = {
        **_PHENOPACKET_B["phenopacket"],
        "metaData": {"externalReferences": [{"id": "PMID:11111111"}]},
    }
    batch_item_b_shared: dict = {"phenopacket_id": "B", "phenopacket": inner_b_shared}

    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_A, batch_item_b_shared])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "B"], dedupe_publications=True)
    await c.aclose()

    assert "publications" in result
    assert len(result["publications"]) == 1
    assert result["publications"][0]["pmid"] == "11111111"
    for ind in result["individuals"]:
        assert "publication_refs" in ind
        assert "publications" not in ind
