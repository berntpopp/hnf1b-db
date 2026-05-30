"""Tests for hnf1b_mcp.services.compare — cross-variant phenotype comparison.

Covers the reshaped contract: shared variant-id resolution + unmatched signal
(B2/Rec3), alias-keyed tuple cells (Rec1), observed_rate / annotation_completeness
(Rec2), response_mode char budget (NEW-1), and exploratory Fisher stats (Rec4).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.compare import compare_phenotypes
from hnf1b_mcp.services.errors import McpToolError

BASE = "http://api.test/api/v2"


def _carrier(pp_id: str, features: list[tuple[str, str, bool]]) -> dict:
    return {
        "phenopacket_id": pp_id,
        "phenopacket": {
            "phenotypicFeatures": [
                {"type": {"id": hid, "label": lbl}, "excluded": exc}
                for hid, lbl, exc in features
            ]
        },
    }


def _mock_all_variants(variants: list[tuple[str, str]]) -> None:
    """Mock the all-variants aggregate endpoint with ``(variant_id, simple_id)`` rows."""
    respx.get(f"{BASE}/phenopackets/aggregate/all-variants").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"variant_id": vid, "simple_id": sid, "label": f"label {sid}"}
                    for vid, sid in variants
                ],
                "meta": {"page": {"totalRecords": len(variants)}},
            },
        )
    )


# ---------------------------------------------------------------------------
# Happy path — alias-keyed tuple cells (Rec1) + rates (Rec2).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_compare_tabulates_with_alias_tuple_cells():
    _mock_all_variants([("ga4gh:VA.A", "Var1"), ("ga4gh:VA.B", "Var2")])
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(
            200,
            json=[
                _carrier("p1", [("HP:1", "Renal cysts", False)]),
                _carrier("p2", [("HP:1", "Renal cysts", False), ("HP:2", "DM", True)]),
            ],
        )
    )
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.B").mock(
        return_value=httpx.Response(200, json=[_carrier("p3", [("HP:2", "DM", False)])])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A", "ga4gh:VA.B"], top_n=10)
    await c.aclose()

    # Groups carry alias + canonical id + simple_id + n.
    by_alias = {g["alias"]: g for g in result["groups"]}
    assert by_alias["g0"]["variant_id"] == "ga4gh:VA.A"
    assert by_alias["g0"]["simple_id"] == "Var1"
    assert by_alias["g0"]["n"] == 2
    assert by_alias["g1"]["n"] == 1
    assert result["group_aliases"] == {"g0": "ga4gh:VA.A", "g1": "ga4gh:VA.B"}
    assert result["unmatched_variant_ids"] == []

    feats = {f["hpo_id"]: f for f in result["features"]}
    # by_group keyed by ALIAS; cell = [observed, excluded, unknown, rate].
    # HP:1 observed in 2/2 of g0 (rate 1.0), unknown in g1 (rate None).
    assert feats["HP:1"]["by_group"]["g0"] == [2, 0, 0, 1.0]
    assert feats["HP:1"]["by_group"]["g1"] == [0, 0, 1, None]
    # HP:2 excluded once in g0 (rate 0.0), observed once in g1 (rate 1.0).
    assert feats["HP:2"]["by_group"]["g0"] == [0, 1, 1, 0.0]
    assert feats["HP:2"]["by_group"]["g1"] == [1, 0, 0, 1.0]
    # Ranked by total observed (HP:1 total 2 > HP:2 total 1).
    assert result["features"][0]["hpo_id"] == "HP:1"
    assert result["total_distinct_features"] == 2
    assert result["has_more"] is False
    assert "by_group_format" in result["_meta"]


# ---------------------------------------------------------------------------
# B2 / Rec3 — unmatched vs real-zero-carrier; simple_id acceptance.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_compare_unknown_variant_id_reported_as_unmatched():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", [("HP:1", "F", False)])])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A", "ga4gh:VA.TYPO"], top_n=10)
    await c.aclose()

    assert result["unmatched_variant_ids"] == ["ga4gh:VA.TYPO"]
    assert [g["variant_id"] for g in result["groups"]] == ["ga4gh:VA.A"]


@pytest.mark.asyncio
@respx.mock
async def test_compare_real_variant_zero_carriers_not_unmatched():
    """A real variant with no phenotyped carriers stays in groups with n:0."""
    _mock_all_variants([("ga4gh:VA.A", "Var1"), ("ga4gh:VA.EMPTY", "Var9")])
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", [("HP:1", "F", False)])])
    )
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.EMPTY").mock(
        return_value=httpx.Response(200, json=[])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A", "ga4gh:VA.EMPTY"], top_n=10)
    await c.aclose()

    assert result["unmatched_variant_ids"] == []
    n_by_id = {g["variant_id"]: g["n"] for g in result["groups"]}
    assert n_by_id == {"ga4gh:VA.A": 1, "ga4gh:VA.EMPTY": 0}


@pytest.mark.asyncio
@respx.mock
async def test_compare_accepts_simple_id_resolves_to_canonical():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    route = respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", [("HP:1", "F", False)])])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["Var1"], top_n=10)
    await c.aclose()

    # The by-variant fetch used the CANONICAL id, not the friendly simple_id.
    assert route.called
    assert result["groups"][0]["variant_id"] == "ga4gh:VA.A"
    assert result["groups"][0]["n"] == 1
    assert result["unmatched_variant_ids"] == []


@pytest.mark.asyncio
@respx.mock
async def test_compare_all_unmatched_returns_empty_no_raise():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["nope1", "nope2"], top_n=10)
    await c.aclose()
    assert result["groups"] == []
    assert result["features"] == []
    assert result["unmatched_variant_ids"] == ["nope1", "nope2"]


@pytest.mark.asyncio
@respx.mock
async def test_compare_dedupes_same_variant_supplied_twice():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", [("HP:1", "F", False)])])
    )
    c = ApiClient(base_url=BASE)
    # canonical id AND its simple_id name the same variant -> one group.
    result = await compare_phenotypes(c, ["ga4gh:VA.A", "Var1"], top_n=10)
    await c.aclose()
    assert len(result["groups"]) == 1


# ---------------------------------------------------------------------------
# Rec2 — observed_rate_among_recorded + annotation_completeness.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_compare_annotation_completeness_reflects_assessment_depth():
    _mock_all_variants([("ga4gh:VA.DENSE", "Var1"), ("ga4gh:VA.SPARSE", "Var2")])
    # Dense group: both carriers assess both features. Sparse: one carrier, one feature.
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.DENSE").mock(
        return_value=httpx.Response(
            200,
            json=[
                _carrier("p1", [("HP:1", "F1", False), ("HP:2", "F2", True)]),
                _carrier("p2", [("HP:1", "F1", False), ("HP:2", "F2", False)]),
            ],
        )
    )
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.SPARSE").mock(
        return_value=httpx.Response(200, json=[_carrier("p3", [("HP:1", "F1", False)])])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(
        c, ["ga4gh:VA.DENSE", "ga4gh:VA.SPARSE"], top_n=10
    )
    await c.aclose()

    comp = {g["alias"]: g["annotation_completeness"] for g in result["groups"]}
    # g0 assessed both features in both carriers => 1.0; g1 assessed 1 of 2 => 0.5.
    assert comp["g0"] == 1.0
    assert comp["g1"] == 0.5


# ---------------------------------------------------------------------------
# NEW-1 — response_mode threads through and bounds the payload.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_compare_response_mode_enforces_char_budget():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    many = [(f"HP:{i:07d}", f"Feature {i}", False) for i in range(120)]
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", many)])
    )
    c = ApiClient(base_url=BASE)
    minimal = await compare_phenotypes(
        c, ["ga4gh:VA.A"], top_n=100, response_mode="minimal"
    )
    full = await compare_phenotypes(c, ["ga4gh:VA.A"], top_n=100, response_mode="full")
    await c.aclose()

    import json

    assert len(json.dumps(minimal)) <= 4000
    assert minimal["_dropped"]["dropped_records"] > 0
    assert minimal["has_more"] is True
    assert minimal["returned_features"] == len(minimal["features"])
    # keep_min=1: never empty when matches exist.
    assert len(minimal["features"]) >= 1
    # A wider mode returns strictly more features than the trimmed minimal one.
    assert len(full["features"]) > len(minimal["features"])


# ---------------------------------------------------------------------------
# Rec4 — exploratory Fisher stats (two groups only).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_compare_include_stats_two_groups():
    _mock_all_variants([("ga4gh:VA.A", "Var1"), ("ga4gh:VA.B", "Var2")])
    # HP:1 strongly enriched in g0 (5/5 present) vs g1 (0/5, all excluded).
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(
            200, json=[_carrier(f"a{i}", [("HP:1", "F", False)]) for i in range(5)]
        )
    )
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.B").mock(
        return_value=httpx.Response(
            200, json=[_carrier(f"b{i}", [("HP:1", "F", True)]) for i in range(5)]
        )
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(
        c, ["ga4gh:VA.A", "ga4gh:VA.B"], top_n=10, include_stats=True
    )
    await c.aclose()

    hp1 = next(f for f in result["features"] if f["hpo_id"] == "HP:1")
    assert "stats" in hp1
    assert hp1["stats"]["fisher_p"] is not None
    assert hp1["stats"]["fisher_p"] < 0.05  # 5/5 vs 0/5 is significant
    assert hp1["stats"]["effect_direction"] == "higher_in_g0"
    assert "stats_note" in result["_meta"]


@pytest.mark.asyncio
@respx.mock
async def test_compare_include_stats_requires_exactly_two_groups():
    _mock_all_variants([("ga4gh:VA.A", "Var1")])
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(200, json=[_carrier("p1", [("HP:1", "F", False)])])
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A"], include_stats=True)
    await c.aclose()
    # Single group -> no per-feature stats, but a note explains why.
    assert "stats" not in result["features"][0]
    assert "require exactly" in result["_meta"]["stats_note"]


# ---------------------------------------------------------------------------
# Input validation (unchanged).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_phenotypes_rejects_empty():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc:
        await compare_phenotypes(c, [])
    await c.aclose()
    assert exc.value.code == "invalid_input"


@pytest.mark.asyncio
async def test_compare_phenotypes_rejects_too_many():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc:
        await compare_phenotypes(c, [f"v{i}" for i in range(11)])
    await c.aclose()
    assert exc.value.code == "invalid_input"


@pytest.mark.asyncio
async def test_compare_phenotypes_rejects_bad_top_n():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError):
        await compare_phenotypes(c, ["v1"], top_n=0)
    await c.aclose()
