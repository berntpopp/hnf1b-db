"""Tests for hnf1b_mcp.services.compare — cross-variant phenotype comparison."""

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


@pytest.mark.asyncio
@respx.mock
async def test_compare_phenotypes_tabulates_by_group():
    """observed/excluded/unknown are tabulated per variant group."""
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
        return_value=httpx.Response(
            200,
            json=[_carrier("p3", [("HP:2", "DM", False)])],
        )
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A", "ga4gh:VA.B"], top_n=10)
    await c.aclose()

    groups = {g["variant_id"]: g["n"] for g in result["groups"]}
    assert groups == {"ga4gh:VA.A": 2, "ga4gh:VA.B": 1}

    feats = {f["hpo_id"]: f for f in result["features"]}
    # HP:1 observed in 2/2 of group A, absent (unknown) in group B.
    hp1 = feats["HP:1"]["by_group"]
    assert hp1["ga4gh:VA.A"] == {"observed": 2, "excluded": 0, "unknown": 0}
    assert hp1["ga4gh:VA.B"] == {"observed": 0, "excluded": 0, "unknown": 1}
    # HP:2: excluded once in A (1 unknown), observed once in B.
    hp2 = feats["HP:2"]["by_group"]
    assert hp2["ga4gh:VA.A"] == {"observed": 0, "excluded": 1, "unknown": 1}
    assert hp2["ga4gh:VA.B"] == {"observed": 1, "excluded": 0, "unknown": 0}
    # ranked by total observed (HP:1 total 2 > HP:2 total 1)
    assert result["features"][0]["hpo_id"] == "HP:1"
    # full result set fit within top_n=10, so nothing is hidden.
    assert result["total_distinct_features"] == 2
    assert result["returned_features"] == 2
    assert result["top_n"] == 10
    assert result["has_more"] is False


@pytest.mark.asyncio
@respx.mock
async def test_compare_phenotypes_truncation_is_transparent():
    """top_n smaller than the distinct-feature count exposes has_more, not a silent cut."""
    respx.get(f"{BASE}/phenopackets/by-variant/ga4gh:VA.A").mock(
        return_value=httpx.Response(
            200,
            json=[
                _carrier("p1", [("HP:1", "F1", False), ("HP:2", "F2", False)]),
            ],
        )
    )
    c = ApiClient(base_url=BASE)
    result = await compare_phenotypes(c, ["ga4gh:VA.A"], top_n=1)
    await c.aclose()

    assert result["total_distinct_features"] == 2
    assert result["returned_features"] == 1
    assert result["top_n"] == 1
    assert result["has_more"] is True
    assert len(result["features"]) == 1


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
