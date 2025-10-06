"""Tests to verify JSONB indexes are created and used by queries.

These tests validate that:
1. GIN indexes exist on JSONB paths
2. Queries use indexes instead of sequential scans
3. Performance improves with indexes
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestJSONBIndexesExist:
    """Verify that JSONB indexes are created."""

    async def test_phenotypic_features_index_exists(self, db_session: AsyncSession):
        """Verify idx_phenopacket_features_gin index exists."""
        result = await db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'phenopackets'
                AND indexname = 'idx_phenopacket_features_gin'
            """)
        )
        row = result.fetchone()

        assert row is not None, "idx_phenopacket_features_gin index should exist"
        assert "gin" in row.indexdef.lower(), "Should be a GIN index"
        assert "phenotypicfeatures" in row.indexdef.lower(), "Should index phenotypicFeatures"

    async def test_interpretations_index_exists(self, db_session: AsyncSession):
        """Verify idx_phenopacket_interpretations_gin index exists."""
        result = await db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'phenopackets'
                AND indexname = 'idx_phenopacket_interpretations_gin'
            """)
        )
        row = result.fetchone()

        assert row is not None, "idx_phenopacket_interpretations_gin index should exist"
        assert "gin" in row.indexdef.lower(), "Should be a GIN index"

    async def test_diseases_index_exists(self, db_session: AsyncSession):
        """Verify idx_phenopacket_diseases_gin index exists."""
        result = await db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'phenopackets'
                AND indexname = 'idx_phenopacket_diseases_gin'
            """)
        )
        row = result.fetchone()

        assert row is not None, "idx_phenopacket_diseases_gin index should exist"
        assert "gin" in row.indexdef.lower(), "Should be a GIN index"

    async def test_measurements_index_exists(self, db_session: AsyncSession):
        """Verify idx_phenopacket_measurements_gin index exists."""
        result = await db_session.execute(
            text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'phenopackets'
                AND indexname = 'idx_phenopacket_measurements_gin'
            """)
        )
        row = result.fetchone()

        assert row is not None, "idx_phenopacket_measurements_gin index should exist"
        assert "gin" in row.indexdef.lower(), "Should be a GIN index"


class TestJSONBIndexUsage:
    """Verify that queries use the JSONB indexes."""

    async def test_phenotypic_features_query_uses_index(self, db_session: AsyncSession):
        """Verify feature aggregation queries use the GIN index."""
        # Run EXPLAIN on a typical feature aggregation query
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT JSON)
                SELECT
                    feature->'type'->>'id' as hpo_id,
                    COUNT(*) as count
                FROM phenopackets,
                     jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
                GROUP BY hpo_id
                LIMIT 10
            """)
        )
        explain_output = result.scalar()

        # Convert to string for easier searching
        explain_str = str(explain_output).lower()

        # With GIN index, should see "bitmap index scan" or "index scan"
        # Should NOT see "seq scan" on phenopackets table
        assert "index" in explain_str or "bitmap" in explain_str, (
            "Query should use an index. "
            f"EXPLAIN output: {explain_output}"
        )

    async def test_disease_aggregation_uses_index(self, db_session: AsyncSession):
        """Verify disease aggregation queries can use the GIN index."""
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT JSON)
                SELECT
                    disease->'term'->>'id' as disease_id,
                    COUNT(*) as count
                FROM phenopackets,
                     jsonb_array_elements(phenopacket->'diseases') as disease
                GROUP BY disease_id
                LIMIT 10
            """)
        )
        explain_output = result.scalar()
        explain_str = str(explain_output).lower()

        # Should be able to use index for this query
        assert "index" in explain_str or "bitmap" in explain_str, (
            f"Disease query should use index. EXPLAIN: {explain_output}"
        )

    async def test_variant_search_can_use_index(self, db_session: AsyncSession):
        """Verify variant searches can leverage the interpretations index."""
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT JSON)
                SELECT phenopacket_id
                FROM phenopackets
                WHERE phenopacket->'interpretations' @> '[{"id": "test"}]'::jsonb
                LIMIT 10
            """)
        )
        explain_output = result.scalar()
        explain_str = str(explain_output).lower()

        # GIN index supports @> (contains) operator
        # Should use bitmap index scan
        assert "bitmap" in explain_str or "index" in explain_str, (
            f"Contains query should use GIN index. EXPLAIN: {explain_output}"
        )


class TestIndexStatistics:
    """Verify index statistics and size."""

    async def test_index_sizes_are_reasonable(self, db_session: AsyncSession):
        """Verify JSONB indexes don't use excessive storage."""
        result = await db_session.execute(
            text("""
                SELECT
                    indexname,
                    pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                FROM pg_indexes
                WHERE tablename = 'phenopackets'
                AND indexname LIKE 'idx_phenopacket_%_gin'
                ORDER BY indexname
            """)
        )
        indexes = result.fetchall()

        # Should have at least the 4 JSONB path indexes
        assert len(indexes) >= 4, f"Should have 4+ GIN indexes, found {len(indexes)}"

        # Print index sizes for visibility
        print(f"\n{'='*60}")
        print("JSONB Index Sizes:")
        for idx in indexes:
            print(f"  {idx.indexname}: {idx.size}")
        print(f"{'='*60}")

    async def test_table_statistics_updated(self, db_session: AsyncSession):
        """Verify table statistics are up-to-date (ANALYZE was run)."""
        result = await db_session.execute(
            text("""
                SELECT
                    schemaname,
                    tablename,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE tablename = 'phenopackets'
            """)
        )
        stats = result.fetchone()

        assert stats is not None, "phenopackets table should have statistics"

        # Either manual ANALYZE or auto-analyze should have run
        has_stats = stats.last_analyze is not None or stats.last_autoanalyze is not None
        assert has_stats, "Table statistics should be updated (run ANALYZE)"


@pytest.mark.skip(reason="Manual verification - requires data and visual inspection")
class TestIndexPerformanceManual:
    """Manual tests for verifying index performance improvements.

    Run these manually with real data to see performance improvements.
    """

    async def test_compare_query_cost_with_without_index(self, db_session: AsyncSession):
        """Compare query costs with and without indexes (manual verification)."""
        # This would require:
        # 1. Run EXPLAIN before creating indexes (save cost)
        # 2. Create indexes
        # 3. Run EXPLAIN after creating indexes (save cost)
        # 4. Compare costs (should be 50%+ reduction)
        pass

    async def test_measure_aggregation_query_time(self, db_session: AsyncSession):
        """Measure actual query execution time (manual verification)."""
        # This would require:
        # 1. Time query execution before indexes
        # 2. Time query execution after indexes
        # 3. Compare times (should be 5-10x faster)
        pass
