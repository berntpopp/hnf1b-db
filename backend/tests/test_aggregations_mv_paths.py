"""Tests for the materialized-view fast paths in the aggregation endpoints.

The ``/sex-distribution``, ``/by-disease``, ``/by-feature`` endpoints
(and indirectly others) each have two code paths:

1. **MV fast path** — used when the startup-cached
   ``mv_cache.is_available(view_name)`` reports the materialized view
   exists. A single ``SELECT ... FROM mv_*_aggregation`` query returns
   the pre-aggregated rows.
2. **Fallback path** — live JSONB query computing the aggregation on
   the fly.

The CI test database is empty and has no materialized views, so the
endpoint-level smoke tests in ``test_aggregations_endpoints.py``
always hit the fallback. That leaves the MV fast-path branches
uncovered — Codecov flagged these on PR #231.

This module mocks ``check_materialized_view_exists`` to return True
and the ``AsyncSession.execute`` call to return a canned RowMapping
sequence, driving the MV branches. It uses the FastAPI TestClient to
exercise the real route wiring, not just the raw function.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class _FakeRowMapping(Mapping):
    """Mimic SQLAlchemy ``RowMapping`` returned by ``result.mappings().all()``.

    A real RowMapping is a ``collections.abc.Mapping`` subclass that is
    neither a ``dict`` nor exposes ``._mapping``. Modelling this shape
    is load-bearing because ``calculate_percentages`` dispatches on it.
    """

    def __init__(self, **fields: Any) -> None:
        self._fields: Dict[str, Any] = dict(fields)

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]

    def __iter__(self):
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)


def _mock_db_execute_returning_mappings(
    mv_rows: List[_FakeRowMapping],
) -> MagicMock:
    """Build an execute() side_effect that returns mv_rows via .mappings().all().

    SQLAlchemy's ``Result`` exposes ``.mappings()`` returning an object
    whose ``.all()`` method returns a sequence of RowMapping. We model
    that two-step chain so the endpoint code can call it unchanged.
    """
    result = MagicMock()
    mappings = MagicMock()
    mappings.all.return_value = mv_rows
    result.mappings.return_value = mappings
    # Some endpoints also call .fetchall() on the same result when they
    # follow a different path — return an empty list so nothing crashes
    # if both code paths are exercised.
    result.fetchall.return_value = []
    return result


@pytest.fixture()
def mv_client() -> TestClient:
    """Synchronous TestClient for MV-path tests.

    Kept local to this module so it doesn't collide with the
    ``async_client`` conftest fixture or the sync ``client`` fixture in
    ``test_phenopackets_crud.py``. The MV tests monkey-patch the
    aggregation module's DB access, so we don't need a real database
    or session override.
    """
    return TestClient(app)


# --------------------------------------------------------------------------
# /sex-distribution — demographics.py MV fast path
# --------------------------------------------------------------------------


class TestSexDistributionMvPath:
    """The MV fast path at demographics.py returns rows from
    ``mv_sex_distribution`` and runs them through ``calculate_percentages``.
    """

    def test_mv_hit_returns_aggregated_rows_with_percentages(
        self, mv_client: TestClient
    ) -> None:
        """When the MV is available, the endpoint returns rows whose
        percentages sum to 100%.
        """
        mv_rows = [
            _FakeRowMapping(sex="MALE", count=360, percentage=41.6),
            _FakeRowMapping(sex="FEMALE", count=345, percentage=39.7),
            _FakeRowMapping(sex="UNKNOWN_SEX", count=159, percentage=18.7),
        ]

        with patch(
            "app.phenopackets.routers.aggregations.demographics"
            ".check_materialized_view_exists",
            new=AsyncMock(return_value=True),
        ):
            # Patch the AsyncSession.execute path for this module so the
            # MV SELECT returns our canned rows.
            with patch(
                "app.phenopackets.routers.aggregations.demographics.text"
            ) as mock_text:
                # text() is called to compile the SQL — give it back a
                # sentinel value; the mock session will use side_effect
                # to produce the result.
                mock_text.side_effect = lambda sql: sql
                # Wire the session via dependency override.
                from app.database import get_db

                async def _override_get_db():
                    session = AsyncMock()
                    session.execute = AsyncMock(
                        return_value=_mock_db_execute_returning_mappings(mv_rows)
                    )
                    yield session

                app.dependency_overrides[get_db] = _override_get_db
                try:
                    response = mv_client.get(
                        "/api/v2/phenopackets/aggregate/sex-distribution"
                    )
                finally:
                    app.dependency_overrides.clear()

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 3
        # Calculate percentages were computed from the MV's raw count field
        # (the MV also has a `percentage` column, but the helper re-derives
        # it from count / total).
        total = sum(r["count"] for r in body)
        assert total == 864
        # Percentages sum to ~100%
        assert abs(sum(r["percentage"] for r in body) - 100.0) < 0.01


# --------------------------------------------------------------------------
# /by-disease — diseases.py MV fast path
# --------------------------------------------------------------------------


class TestByDiseaseMvPath:
    """The MV fast path at diseases.py returns rows from
    ``mv_disease_aggregation`` and runs them through ``calculate_percentages``.
    """

    def test_mv_hit_returns_aggregated_rows_with_percentages(
        self, mv_client: TestClient
    ) -> None:
        """MV-available path returns rows whose percentages sum to 100."""
        mv_rows = [
            _FakeRowMapping(
                disease_id="MONDO:0005147",
                label="MODY5",
                count=450,
                percentage=52.0,
            ),
            _FakeRowMapping(
                disease_id="MONDO:0014556",
                label="RCAD syndrome",
                count=415,
                percentage=48.0,
            ),
        ]

        with patch(
            "app.phenopackets.routers.aggregations.diseases"
            ".check_materialized_view_exists",
            new=AsyncMock(return_value=True),
        ):
            from app.database import get_db

            async def _override_get_db():
                session = AsyncMock()
                session.execute = AsyncMock(
                    return_value=_mock_db_execute_returning_mappings(mv_rows)
                )
                yield session

            app.dependency_overrides[get_db] = _override_get_db
            try:
                response = mv_client.get(
                    "/api/v2/phenopackets/aggregate/by-disease"
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 2
        total = sum(r["count"] for r in body)
        assert total == 865
        assert abs(sum(r["percentage"] for r in body) - 100.0) < 0.01
        # details.disease_id is preserved from the MV row
        assert body[0]["details"]["disease_id"] == "MONDO:0005147"


# --------------------------------------------------------------------------
# /by-feature — features.py MV fast path (uses count_key="present_count")
# --------------------------------------------------------------------------


class TestByFeatureMvPath:
    """The MV fast path at features.py uses ``count_key='present_count'``
    and carries additional fields through to ``details``.
    """

    def test_mv_hit_returns_aggregated_rows_with_percentages(
        self, mv_client: TestClient
    ) -> None:
        """MV-available path uses present_count as the percentage
        denominator-source and preserves absent_count / not_reported_count
        in the details envelope.
        """
        mv_rows = [
            _FakeRowMapping(
                hpo_id="HP:0000107",
                label="Renal cyst",
                present_count=600,
                absent_count=10,
                not_reported_count=254,
                total_phenopackets=864,
            ),
            _FakeRowMapping(
                hpo_id="HP:0012625",
                label="Stage 3 CKD",
                present_count=400,
                absent_count=5,
                not_reported_count=459,
                total_phenopackets=864,
            ),
        ]

        with patch(
            "app.phenopackets.routers.aggregations.features"
            ".check_materialized_view_exists",
            new=AsyncMock(return_value=True),
        ):
            from app.database import get_db

            async def _override_get_db():
                session = AsyncMock()
                session.execute = AsyncMock(
                    return_value=_mock_db_execute_returning_mappings(mv_rows)
                )
                yield session

            app.dependency_overrides[get_db] = _override_get_db
            try:
                response = mv_client.get(
                    "/api/v2/phenopackets/aggregate/by-feature"
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 2
        # `count` in the response comes from `present_count`
        assert body[0]["count"] == 600
        assert body[1]["count"] == 400
        # Percentages sum to 100 (total_present_count = 600 + 400 = 1000)
        assert abs(sum(r["percentage"] for r in body) - 100.0) < 0.01
        # The first row should be 60% of the total present_count
        assert abs(body[0]["percentage"] - 60.0) < 0.01
        # details.absent_count / not_reported_count are preserved
        assert body[0]["details"]["absent_count"] == 10
        assert body[0]["details"]["not_reported_count"] == 254
