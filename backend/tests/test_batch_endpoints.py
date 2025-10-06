"""Tests for batch endpoints to prevent N+1 query problems."""

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


class QueryCounter:
    """Helper to count database queries executed."""

    def __init__(self):
        self.count = 0
        self.queries = []

    def reset(self):
        """Reset query counter."""
        self.count = 0
        self.queries = []


@pytest.fixture
def query_counter():
    """Fixture providing query counter."""
    return QueryCounter()


@pytest.fixture
async def sample_phenopackets(db_session: AsyncSession):
    """Create sample phenopackets for testing."""
    sanitizer = PhenopacketSanitizer()

    phenopackets_data = []
    for i in range(10):
        data = {
            "id": f"test_batch_{i}",
            "subject": {"id": f"patient_{i}", "sex": "MALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": f"Test feature {i}"}}
            ],
            "interpretations": [
                {
                    "id": f"interpretation_{i}",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": f"variant_{i}",
                                        "label": f"Test variant {i}",
                                    }
                                }
                            }
                        ]
                    },
                }
            ],
            "metaData": {
                "created": "2024-01-01T00:00:00Z",
                "phenopacketSchemaVersion": "2.0.0",
            },
        }

        sanitized = sanitizer.sanitize_phenopacket(data)

        phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket)
        phenopackets_data.append(phenopacket)

    await db_session.commit()

    yield phenopackets_data

    # Cleanup
    for pp in phenopackets_data:
        await db_session.delete(pp)
    await db_session.commit()


class TestBatchEndpointsQueryCount:
    """Test that batch endpoints use single queries instead of N+1."""

    async def test_batch_phenopackets_uses_single_query(
        self, db_session: AsyncSession, sample_phenopackets, query_counter
    ):
        """Verify batch phenopacket endpoint uses 1 query, not N queries."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:5]]

        # Setup query counter
        def count_query(conn, cursor, statement, parameters, context, executemany):
            query_counter.count += 1
            query_counter.queries.append(statement)

        # Attach listener
        engine = db_session.get_bind()
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)

        try:
            # Execute batch query
            query_counter.reset()
            result = await db_session.execute(
                select(Phenopacket).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
            )
            phenopackets = result.scalars().all()

            # Verify results
            assert len(phenopackets) == 5

            # Verify query count: should be exactly 1 query
            assert query_counter.count == 1, (
                f"Expected 1 query, got {query_counter.count}. "
                f"Batch endpoint should use WHERE...IN, not N separate queries."
            )

        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    async def test_batch_features_uses_single_query(
        self, db_session: AsyncSession, sample_phenopackets, query_counter
    ):
        """Verify batch features endpoint uses 1 query, not N queries."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:5]]

        # Setup query counter
        def count_query(conn, cursor, statement, parameters, context, executemany):
            query_counter.count += 1

        engine = db_session.get_bind()
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)

        try:
            # Execute batch features query
            query_counter.reset()
            result = await db_session.execute(
                select(
                    Phenopacket.phenopacket_id,
                    Phenopacket.phenopacket["phenotypicFeatures"].label("features"),
                ).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
            )
            rows = result.fetchall()

            # Verify results
            assert len(rows) == 5

            # Verify query count: should be exactly 1 query
            assert query_counter.count == 1, (
                f"Expected 1 query, got {query_counter.count}. "
                f"Features batch endpoint should use single SELECT."
            )

        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    async def test_batch_variants_uses_single_query(
        self, db_session: AsyncSession, sample_phenopackets, query_counter
    ):
        """Verify batch variants endpoint uses 1 query, not N queries."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:5]]

        # Setup query counter
        def count_query(conn, cursor, statement, parameters, context, executemany):
            query_counter.count += 1

        engine = db_session.get_bind()
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)

        try:
            # Execute batch variants query
            query_counter.reset()
            result = await db_session.execute(
                select(
                    Phenopacket.phenopacket_id,
                    Phenopacket.phenopacket["interpretations"].label("interpretations"),
                ).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
            )
            rows = result.fetchall()

            # Verify results
            assert len(rows) == 5

            # Verify query count: should be exactly 1 query
            assert query_counter.count == 1, (
                f"Expected 1 query, got {query_counter.count}. "
                f"Variants batch endpoint should use single SELECT."
            )

        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)


class TestBatchEndpointsFunctionality:
    """Test that batch endpoints return correct data."""

    async def test_batch_phenopackets_returns_all_requested(
        self, db_session: AsyncSession, sample_phenopackets
    ):
        """Verify batch endpoint returns all requested phenopackets."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:3]]

        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        phenopackets = result.scalars().all()

        assert len(phenopackets) == 3
        returned_ids = {pp.phenopacket_id for pp in phenopackets}
        assert returned_ids == set(phenopacket_ids)

    async def test_batch_features_includes_features(
        self, db_session: AsyncSession, sample_phenopackets
    ):
        """Verify batch features endpoint includes phenotypic features."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:3]]

        result = await db_session.execute(
            select(
                Phenopacket.phenopacket_id,
                Phenopacket.phenopacket["phenotypicFeatures"].label("features"),
            ).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        rows = result.fetchall()

        assert len(rows) == 3
        for row in rows:
            assert row.phenopacket_id in phenopacket_ids
            assert row.features is not None
            assert len(row.features) > 0

    async def test_batch_variants_includes_interpretations(
        self, db_session: AsyncSession, sample_phenopackets
    ):
        """Verify batch variants endpoint includes interpretations."""
        phenopacket_ids = [pp.phenopacket_id for pp in sample_phenopackets[:3]]

        result = await db_session.execute(
            select(
                Phenopacket.phenopacket_id,
                Phenopacket.phenopacket["interpretations"].label("interpretations"),
            ).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        rows = result.fetchall()

        assert len(rows) == 3
        for row in rows:
            assert row.phenopacket_id in phenopacket_ids
            assert row.interpretations is not None
            assert len(row.interpretations) > 0

    async def test_batch_endpoints_handle_empty_input(self, db_session: AsyncSession):
        """Verify batch endpoints handle empty input gracefully."""
        # Empty list should return empty results
        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id.in_([]))
        )
        phenopackets = result.scalars().all()
        assert len(phenopackets) == 0

    async def test_batch_endpoints_handle_nonexistent_ids(
        self, db_session: AsyncSession
    ):
        """Verify batch endpoints handle non-existent IDs gracefully."""
        fake_ids = ["nonexistent_1", "nonexistent_2", "nonexistent_3"]

        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id.in_(fake_ids))
        )
        phenopackets = result.scalars().all()

        # Should return empty list, not error
        assert len(phenopackets) == 0
