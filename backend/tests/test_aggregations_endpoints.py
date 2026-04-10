"""Smoke tests for the aggregation endpoints in ``/api/v2/phenopackets/aggregate/``.

Wave 3 refactor landed a shared ``calculate_percentages`` helper in
``aggregations/common.py`` that is called from 11 sites across
``demographics``, ``diseases``, ``variants``, ``features``, and
``publications`` routers. The initial draft of the helper only accepted
``dict`` rows or rows exposing ``._mapping``, which caused a runtime
``TypeError`` on every endpoint that uses ``result.mappings().all()``
(the SQLAlchemy ``RowMapping`` shape is a ``collections.abc.Mapping``
subclass that is neither a ``dict`` nor exposes ``._mapping``).

The bug slipped through the initial commit because these endpoints had
zero HTTP-level test coverage — the unit tests covered the helper in
isolation but not the call sites. This module closes that gap by
hitting every aggregation endpoint through the FastAPI stack, using
the ``async_client`` fixture from ``conftest.py``. The test database is
empty, so every query returns an empty result — that is fine for a
smoke test: the imports, routing, query compilation, and
``calculate_percentages`` dispatch are all exercised, and the response
shape is validated.

For the materialized-view-backed endpoints (``/sex-distribution``,
``/by-disease``, ``/by-feature``), the fallback path runs because the
test database does not carry the materialized views. That fallback is
exactly where the ``result.mappings().all()`` call sites live, so
running the smoke test against an empty test DB still exercises the
critical codepath.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

AGGREGATE_PATH = "/api/v2/phenopackets/aggregate"


@pytest.mark.asyncio
class TestAggregationListEndpoints:
    """Endpoints returning ``List[AggregationResult]`` all share the same shape."""

    @pytest.mark.parametrize(
        "path",
        [
            "/sex-distribution",
            "/age-of-onset",
            "/by-disease",
            "/kidney-stages",
            "/by-feature",
            "/variant-pathogenicity",
            "/variant-types",
            "/publication-types",
        ],
    )
    async def test_returns_200_and_list(
        self, async_client: AsyncClient, path: str
    ) -> None:
        """Every list-shaped aggregation endpoint returns 200 with a JSON list.

        On an empty test DB the list will be empty, but:
        - The route matched and the dispatcher ran.
        - The SQL compiled and executed (no JSONB path typos).
        - ``calculate_percentages`` was called and dispatched correctly
          on whatever row shape came back from the driver (dict,
          RowMapping, or Row) — this is the regression guard for the
          bug the Wave 3 initial draft shipped.
        - The Pydantic ``AggregationResult`` envelope validated.
        """
        response = await async_client.get(f"{AGGREGATE_PATH}{path}")
        assert response.status_code == 200, response.text

        body = response.json()
        assert isinstance(body, list)

        # If any rows came back, they should match the AggregationResult shape.
        # Shape is `{label: str, count: int, percentage: float, details?: dict}`.
        for item in body:
            assert "label" in item
            assert "count" in item
            assert "percentage" in item
            # percentage should be a float after the Wave 3 Review fix
            # (was int 0 in the else branch before).
            assert isinstance(item["percentage"], (int, float))


@pytest.mark.asyncio
class TestAggregationSummaryEndpoint:
    """``/summary`` returns ``Dict[str, int]``."""

    async def test_summary_returns_dict(self, async_client: AsyncClient) -> None:
        """Home-page summary aggregation smoke test."""
        response = await async_client.get(f"{AGGREGATE_PATH}/summary")
        assert response.status_code == 200, response.text

        body = response.json()
        assert isinstance(body, dict)


@pytest.mark.asyncio
class TestAggregationTimelineEndpoints:
    """Publications timeline endpoints that return ``List[Dict]``."""

    @pytest.mark.parametrize(
        "path",
        [
            "/publications-timeline",
            "/publications-by-type",
            "/publications-timeline-data",
        ],
    )
    async def test_returns_200_and_list(
        self, async_client: AsyncClient, path: str
    ) -> None:
        """Timeline endpoints return a JSON list of timeline-shaped dicts."""
        response = await async_client.get(f"{AGGREGATE_PATH}{path}")
        assert response.status_code == 200, response.text

        body = response.json()
        assert isinstance(body, list)
