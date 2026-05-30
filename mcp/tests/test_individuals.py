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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", response_mode="full")
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", response_mode="full")
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(
        c, "X", include_measurements=False, response_mode="full"
    )
    await c.aclose()

    assert "measurements" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_include_publications_false_omits_key():
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(
        c, "X", include_publications=False, response_mode="full"
    )
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
    # Batch requests echo coverage so missing ids are never silently dropped.
    assert result["requested"] == 2
    assert result["not_found"] == []


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_applies_sex_filter():
    """The sex filter is HONORED on an explicit ids batch and echoed in _meta."""
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_A, _BATCH_ITEM_B])
    )
    c = ApiClient(base_url=BASE)
    # A is FEMALE, B is MALE — filtering to MALE must drop A.
    result = await get_individuals(c, ids=["A", "B"], filters={"sex": "MALE"})
    await c.aclose()

    assert {i["phenopacket_id"] for i in result["individuals"]} == {"B"}
    assert result["total"] == 1
    # not_found stays existence-based, not "filtered out".
    assert result["not_found"] == []
    assert result["_meta"]["applied_filters"] == {"sex": "MALE"}


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_sex_filter_no_match():
    """A batch filtered to a sex none of the records have returns total 0."""
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_B])  # B is MALE
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["B"], filters={"sex": "FEMALE"})
    await c.aclose()

    assert result["individuals"] == []
    assert result["total"] == 0
    assert result["_meta"]["applied_filters"] == {"sex": "FEMALE"}


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_reports_not_found():
    """A requested id the batch endpoint does not return appears in not_found."""
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[_BATCH_ITEM_A])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "DOES-NOT-EXIST"])
    await c.aclose()

    assert result["requested"] == 2
    assert result["not_found"] == ["DOES-NOT-EXIST"]
    assert {i["phenopacket_id"] for i in result["individuals"]} == {"A"}


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_response_mode_trims():
    """minimal/compact return strictly smaller field sets than full (H3)."""
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    minimal = await get_individual(c, "X", response_mode="minimal")
    compact = await get_individual(c, "X", response_mode="compact")
    full = await get_individual(c, "X", response_mode="full")
    await c.aclose()

    assert set(minimal) == {"phenopacket_id", "subject", "uri"}
    # compact carries phenotypes/variants but drops the heavy measurements +
    # the redundant publications block.
    assert "phenotypic_features" in compact
    assert "variants" in compact
    assert "measurements" not in compact
    assert "publications" not in compact
    # full keeps everything.
    assert "measurements" in full
    assert "publications" in full
    assert len(set(full)) > len(set(compact)) > len(set(minimal))


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


# ---------------------------------------------------------------------------
# Field projection, excluded-feature split, citation enrichment, batch budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_fields_projection() -> None:
    """fields=["variants"] returns only variants (+ always-kept id/uri)."""
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", response_mode="full", fields=["variants"])
    await c.aclose()

    assert set(result) == {"phenopacket_id", "uri", "variants"}
    assert result["variants"][0]["gene"] == "HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_splits_observed_and_excluded_features() -> None:
    """phenotypic_features = observed only; excluded_features + counts separate."""
    pp = {
        "phenopacket_id": "Y",
        "phenopacket": {
            "subject": {"id": "Y", "sex": "FEMALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000107", "label": "Renal cysts"}},
                {
                    "type": {"id": "HP:0000822", "label": "Hypertension"},
                    "excluded": True,
                },
            ],
        },
    }
    respx.get(f"{BASE}/phenopackets/Y").mock(return_value=httpx.Response(200, json=pp))
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "Y", response_mode="full")
    await c.aclose()

    assert [f["id"] for f in result["phenotypic_features"]] == ["HP:0000107"]
    assert [f["id"] for f in result["excluded_features"]] == ["HP:0000822"]
    assert result["feature_counts"] == {"observed": 1, "excluded": 1}


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_compact_surfaces_excluded_features() -> None:
    """Compact must show WHICH features were excluded, not just the count (was hidden)."""
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "Y", response_mode="compact")
    await c.aclose()

    # Observed feature behavior unchanged.
    assert [f["id"] for f in result["phenotypic_features"]] == ["HP:0000107"]
    # The excluded (confirmed-negative) feature is now visible by label/id.
    assert [f["id"] for f in result["excluded_features"]] == ["HP:0000819"]
    # Counts always present.
    assert result["feature_counts"] == {"observed": 1, "excluded": 1}


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_standard_surfaces_excluded_features() -> None:
    """Standard likewise surfaces the excluded list and feature_counts."""
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "Y", response_mode="standard")
    await c.aclose()

    assert [f["id"] for f in result["excluded_features"]] == ["HP:0000819"]
    assert result["feature_counts"] == {"observed": 1, "excluded": 1}


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_long_excluded_list_is_bounded() -> None:
    """A long excluded list is sampled in compact with an _meta signal; counts intact."""
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "Z", response_mode="compact")
    await c.aclose()

    # Bounded sample (10) but the count stays the true total (25).
    assert len(result["excluded_features"]) == 10
    assert result["feature_counts"] == {"observed": 1, "excluded": 25}
    # The truncation signal is attached for the wrapper to surface in meta.
    signal = result["_meta"]
    assert signal["excluded_features_total"] == 25
    assert signal["excluded_features_returned"] == 10
    assert signal["excluded_features_truncated"] is True
    assert "excluded_features_note" in signal


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_fields_projection_keeps_meta_signal() -> None:
    """fields=["excluded_features"] must not strip the internal _meta channel.

    Regression: _select_fields kept only ``set(fields) | _ALWAYS_KEEP``; without
    ``_meta`` in that keep-set an explicit field projection silently discarded
    the truncation signal, so run_tool had nothing to hoist into meta — a silent
    truncation. ``_meta`` is an internal control channel and must survive.
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(
        c, "Z", response_mode="compact", fields=["excluded_features"]
    )
    await c.aclose()

    # Projection kept the requested field (sampled to 10) + always-kept id/uri.
    assert len(result["excluded_features"]) == 10
    assert set(result) >= {"phenopacket_id", "uri", "excluded_features"}
    # The internal _meta channel survived projection for run_tool to hoist.
    signal = result["_meta"]
    assert signal["excluded_features_total"] == 25
    assert signal["excluded_features_returned"] == 10
    assert signal["excluded_features_truncated"] is True
    assert "excluded_features_note" in signal


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_fields_projection_no_spurious_meta() -> None:
    """A short (<=10) excluded list under fields= emits NO _meta (no false signal)."""
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(
        c, "Y", response_mode="compact", fields=["excluded_features"]
    )
    await c.aclose()

    assert [f["id"] for f in result["excluded_features"]] == ["HP:0000819"]
    # No truncation occurred, so no internal channel is attached.
    assert "_meta" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_full_keeps_entire_excluded_list() -> None:
    """Full keeps the complete excluded list (no sampling) and emits no signal."""
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
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {}})
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "Z", response_mode="full")
    await c.aclose()

    assert len(result["excluded_features"]) == 25
    assert result["feature_counts"] == {"observed": 1, "excluded": 25}
    assert "_meta" not in result


@pytest.mark.asyncio
@respx.mock
async def test_get_individual_enriches_embedded_citation() -> None:
    """Embedded PMID refs inherit the verified citation from the publication cache."""
    respx.get(f"{BASE}/phenopackets/X").mock(
        return_value=httpx.Response(200, json=_PHENOPACKET_X)
    )
    respx.get(f"{BASE}/publications/").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "pmid": "PMID:12345678",
                        "title": "HNF1B paper",
                        "authors": "Doe J",
                        "journal": "Kidney Int",
                        "year": 2021,
                    }
                ],
                "meta": {},
            },
        )
    )
    c = ApiClient(base_url=BASE)
    result = await get_individual(c, "X", response_mode="full")
    await c.aclose()

    pub = next(p for p in result["publications"] if p["pmid"] == "12345678")
    assert pub["date_confidence"] == "verified"
    assert "2021" in pub["recommended_citation"]


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_budget_enforced() -> None:
    """A minimal batch is trimmed to the mode char budget (not overflowed)."""
    # 80 records, each carrying a chunky subject so the raw batch far exceeds the
    # 4 000-char minimal budget.
    big = [
        {
            "phenopacket_id": f"pp-{i}",
            "phenopacket": {
                "subject": {"id": f"pp-{i}", "sex": "UNKNOWN_SEX", "pad": "x" * 80}
            },
        }
        for i in range(80)
    ]
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=big)
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(
        c, ids=[f"pp-{i}" for i in range(80)], response_mode="minimal"
    )
    await c.aclose()

    # Trimmed to fit the budget → fewer than 80 returned, with a drop signal.
    assert len(result["individuals"]) < 80
    assert result["_dropped"]["dropped_records"] > 0


# ---------------------------------------------------------------------------
# B4: batch results follow the caller's requested id order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_preserves_request_order():
    """The batch endpoint's own order is normalized to the requested ids order."""
    item_a = {"phenopacket_id": "A", "phenopacket": _PHENOPACKET_A["phenopacket"]}
    item_b = {"phenopacket_id": "B", "phenopacket": _PHENOPACKET_B["phenopacket"]}
    item_c = {"phenopacket_id": "C", "phenopacket": _PHENOPACKET_A["phenopacket"]}
    # Backend returns a DIFFERENT order than requested.
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[item_c, item_a, item_b])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "B", "C"])
    await c.aclose()
    assert [i["phenopacket_id"] for i in result["individuals"]] == ["A", "B", "C"]


@pytest.mark.asyncio
@respx.mock
async def test_get_individuals_batch_order_with_not_found():
    item_a = {"phenopacket_id": "A", "phenopacket": _PHENOPACKET_A["phenopacket"]}
    item_b = {"phenopacket_id": "B", "phenopacket": _PHENOPACKET_B["phenopacket"]}
    # MISSING is requested but not returned; A/B come back reversed.
    respx.get(f"{BASE}/phenopackets/batch").mock(
        return_value=httpx.Response(200, json=[item_b, item_a])
    )
    c = ApiClient(base_url=BASE)
    result = await get_individuals(c, ids=["A", "MISSING", "B"])
    await c.aclose()
    assert [i["phenopacket_id"] for i in result["individuals"]] == ["A", "B"]
    assert result["not_found"] == ["MISSING"]
