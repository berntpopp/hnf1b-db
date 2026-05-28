"""Tests for services/statistics.py — Task 1f."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.statistics import get_statistics

BASE = "http://api.test/api/v2"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_metric_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await get_statistics(c, metric="nonexistent_metric")
    await c.aclose()
    assert ei.value.code == "invalid_input"
    assert ei.value.details.get("argument") == "metric"
    # choices should list all valid metrics
    choices = ei.value.details.get("choices", [])
    assert isinstance(choices, list)
    assert "summary" in choices


@pytest.mark.asyncio
async def test_survival_without_comparison_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await get_statistics(c, metric="survival")
    await c.aclose()
    assert ei.value.code == "invalid_input"
    assert ei.value.details.get("argument") == "comparison"


@pytest.mark.asyncio
async def test_survival_with_invalid_comparison_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as ei:
        await get_statistics(c, metric="survival", comparison="bad_value")
    await c.aclose()
    assert ei.value.code == "invalid_input"
    assert ei.value.details.get("argument") == "comparison"


# ---------------------------------------------------------------------------
# Happy path — summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_summary_happy_path():
    respx.get(f"{BASE}/phenopackets/aggregate/summary").mock(
        return_value=httpx.Response(200, json={"total_phenopackets": 42, "data": []})
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(c, metric="summary")
    await c.aclose()

    assert result["metric"] == "summary"
    assert "result" in result
    assert result["result"]["total_phenopackets"] == 42


# ---------------------------------------------------------------------------
# dry_run — no HTTP call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_returns_available_no_http():
    """dry_run must return available=True without making any HTTP requests."""
    # No mocking at all — if an HTTP call happens it will fail
    c = ApiClient(base_url=BASE)
    result = await get_statistics(c, metric="summary", dry_run=True)
    await c.aclose()

    assert result["available"] is True
    assert result["metric"] == "summary"
    assert "estimated" in result


@pytest.mark.asyncio
async def test_dry_run_survival_with_valid_comparison():
    """dry_run for survival still validates comparison before returning early."""
    c = ApiClient(base_url=BASE)
    result = await get_statistics(
        c, metric="survival", dry_run=True, comparison="variant_type"
    )
    await c.aclose()
    assert result["available"] is True


# ---------------------------------------------------------------------------
# Budget trim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_budget_trim_drops_records():
    """Budget trim drops records.

    When a metric returns a large list and max_response_chars is small,
    _dropped must be set with dropped_records > 0.
    """
    big_list = [{"id": i, "label": f"item_{i}" * 5} for i in range(200)]
    respx.get(f"{BASE}/phenopackets/aggregate/by-feature").mock(
        return_value=httpx.Response(200, json={"features": big_list})
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(
        c,
        metric="by_feature",
        max_response_chars=300,
    )
    await c.aclose()

    assert "_dropped" in result
    assert result["_dropped"]["dropped_records"] > 0


# ---------------------------------------------------------------------------
# survival happy path (with comparison param)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_survival_happy_path():
    respx.get(f"{BASE}/phenopackets/aggregate/survival-data").mock(
        return_value=httpx.Response(
            200,
            json={"groups": [{"group": "del", "data": []}]},
        )
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(c, metric="survival", comparison="variant_type")
    await c.aclose()

    assert result["metric"] == "survival"
    assert "result" in result
    assert "groups" in result["result"]


# ---------------------------------------------------------------------------
# Ensure every non-survival metric hits the right path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_publications_timeline_metric():
    respx.get(f"{BASE}/phenopackets/aggregate/publications-timeline").mock(
        return_value=httpx.Response(200, json={"timeline": []})
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(c, metric="publications_timeline")
    await c.aclose()
    assert result["metric"] == "publications_timeline"


# ---------------------------------------------------------------------------
# M8: variant-metric unit labeling, percentage rounding, count_mode, survival
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_variant_types_labels_instance_unit_and_rounds_percentage():
    """variant_types is labeled as per-carrier instances; % noise is rounded."""
    respx.get(f"{BASE}/phenopackets/aggregate/variant-types").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"label": "Copy Number Loss", "count": 389,
                 "percentage": 45.023148148148145, "details": None},
                {"label": "SNV", "count": 302,
                 "percentage": 34.9537037037037, "details": None},
            ],
        )
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(c, "variant_types", response_mode="full")
    await c.aclose()

    assert result["unit"] == "variant_instances_per_carrier"
    assert "distinct" in result["unit_note"]
    rows = result["result"]["raw"]
    assert rows[0]["percentage"] == 45.02  # rounded, no float tail
    assert rows[1]["percentage"] == 34.95


@pytest.mark.asyncio
@respx.mock
async def test_variant_types_unique_count_mode_forwarded_and_labeled():
    """count_mode=unique is forwarded and the unit flips to distinct_variants."""
    route = respx.get(f"{BASE}/phenopackets/aggregate/variant-types").mock(
        return_value=httpx.Response(200, json=[])
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(
        c, "variant_types", count_mode="unique", response_mode="full"
    )
    await c.aclose()

    assert dict(route.calls[0].request.url.params)["count_mode"] == "unique"
    assert result["unit"] == "distinct_variants"


@pytest.mark.asyncio
async def test_invalid_count_mode_raises():
    c = ApiClient(base_url=BASE)
    with pytest.raises(McpToolError) as exc:
        await get_statistics(c, "variant_types", count_mode="bogus")
    await c.aclose()
    assert exc.value.code == "invalid_input"
    assert exc.value.details.get("argument") == "count_mode"


@pytest.mark.asyncio
@respx.mock
async def test_survival_budget_preserves_all_arms_by_downsampling():
    """Over budget, survival down-samples curves but keeps every arm."""
    long_curve = [
        {"time": i / 10, "survival_probability": 1.0 - i / 1000,
         "ci_lower": 0.9, "ci_upper": 1.0, "at_risk": 200 - i,
         "events": 1, "censored": 0}
        for i in range(400)
    ]
    payload = {
        "comparison_type": "pathogenicity",
        "endpoint": "renal",
        "groups": [
            {"name": "P/LP", "n": 255, "events": 109,
             "survival_data": list(long_curve)},
            {"name": "VUS", "n": 80, "events": 20,
             "survival_data": list(long_curve)},
        ],
        "statistical_tests": {"logrank_p": 0.01},
    }
    respx.get(f"{BASE}/phenopackets/aggregate/survival-data").mock(
        return_value=httpx.Response(200, json=payload)
    )
    c = ApiClient(base_url=BASE)
    result = await get_statistics(
        c, "survival", comparison="pathogenicity", response_mode="minimal"
    )
    await c.aclose()

    groups = result["result"]["groups"]
    # Both arms survive; statistical_tests still present.
    assert {g["name"] for g in groups} == {"P/LP", "VUS"}
    assert "statistical_tests" in result["result"]
    # Curves were down-sampled (fewer points than the original 400).
    assert all(len(g["survival_data"]) < 400 for g in groups)
    # The service signals truncation via _dropped (run_tool turns it into
    # meta.truncated + meta.dropped_summary at the tool boundary).
    assert "arms_preserved" in result["_dropped"]
    assert result["_dropped"]["arms_preserved"] == 2
