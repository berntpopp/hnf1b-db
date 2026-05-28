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
    result = await get_statistics(
        c, metric="survival", comparison="variant_type"
    )
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
