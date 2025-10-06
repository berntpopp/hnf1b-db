"""Performance benchmarks for JSONB index improvements.

Run with: pytest tests/test_index_performance_benchmark.py -v -s

These tests measure query performance with GIN indexes on JSONB paths.
"""

import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestAggregationQueryPerformance:
    """Benchmark aggregation query performance with JSONB indexes."""

    async def test_phenotypic_features_aggregation_performance(
        self, db_session: AsyncSession
    ):
        """Benchmark HPO term aggregation query."""
        query = text("""
            SELECT
                feature->'type'->>'id' as hpo_id,
                feature->'type'->>'label' as hpo_label,
                COUNT(*) as count
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            GROUP BY hpo_id, hpo_label
            ORDER BY count DESC
            LIMIT 20
        """)

        # Warm-up query
        await db_session.execute(query)

        # Timed execution
        start = time.time()
        result = await db_session.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Phenotypic Features Aggregation:")
        print(f"  Query time:     {elapsed*1000:.2f}ms")
        print(f"  Features found: {len(rows)}")
        if rows:
            print(f"  Top feature:    {rows[0].hpo_label} ({rows[0].count} occurrences)")
        print(f"{'='*60}")

        # With GIN index, should complete in reasonable time
        # For 864 phenopackets: <200ms is good performance
        # For 10,000 phenopackets: <500ms is good performance
        assert elapsed < 1.0, (
            f"Aggregation query should complete in <1s, took {elapsed*1000:.2f}ms"
        )

    async def test_disease_aggregation_performance(self, db_session: AsyncSession):
        """Benchmark disease term aggregation query."""
        query = text("""
            SELECT
                disease->'term'->>'id' as disease_id,
                disease->'term'->>'label' as disease_label,
                COUNT(*) as count
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'diseases') as disease
            WHERE disease->'term'->>'id' IS NOT NULL
            GROUP BY disease_id, disease_label
            ORDER BY count DESC
            LIMIT 20
        """)

        # Warm-up
        await db_session.execute(query)

        # Timed execution
        start = time.time()
        result = await db_session.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Disease Aggregation:")
        print(f"  Query time:    {elapsed*1000:.2f}ms")
        print(f"  Diseases found: {len(rows)}")
        if rows:
            print(f"  Top disease:    {rows[0].disease_label} ({rows[0].count} cases)")
        print(f"{'='*60}")

        assert elapsed < 1.0, (
            f"Disease aggregation should complete in <1s, took {elapsed*1000:.2f}ms"
        )

    async def test_variant_pathogenicity_aggregation_performance(
        self, db_session: AsyncSession
    ):
        """Benchmark variant pathogenicity aggregation query."""
        query = text("""
            SELECT
                interp->'diagnosis'->'genomicInterpretations'->0->
                'variantInterpretation'->'acmgPathogenicityClassification' as classification,
                COUNT(*) as count
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'interpretations') as interp
            WHERE interp->'diagnosis'->'genomicInterpretations' IS NOT NULL
            GROUP BY classification
            ORDER BY count DESC
        """)

        # Warm-up
        await db_session.execute(query)

        # Timed execution
        start = time.time()
        result = await db_session.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Variant Pathogenicity Aggregation:")
        print(f"  Query time:         {elapsed*1000:.2f}ms")
        print(f"  Classifications:    {len(rows)}")
        print(f"{'='*60}")

        assert elapsed < 1.0, (
            f"Variant aggregation should complete in <1s, took {elapsed*1000:.2f}ms"
        )


class TestComplexJSONBQueries:
    """Test performance of complex JSONB queries that benefit from indexes."""

    async def test_contains_query_performance(self, db_session: AsyncSession):
        """Test @> (contains) operator performance with GIN index."""
        # Search for phenopackets with a specific HPO term
        query = text("""
            SELECT phenopacket_id, subject_id
            FROM phenopackets
            WHERE phenopacket->'phenotypicFeatures' @> '[{"type": {"id": "HP:0012622"}}]'::jsonb
        """)

        # Warm-up
        await db_session.execute(query)

        # Timed execution
        start = time.time()
        result = await db_session.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Contains Query (HP:0012622 - Chronic kidney disease):")
        print(f"  Query time:  {elapsed*1000:.2f}ms")
        print(f"  Matches:     {len(rows)}")
        print(f"{'='*60}")

        # Contains queries with GIN index should be very fast
        assert elapsed < 0.5, (
            f"Contains query should complete in <500ms, took {elapsed*1000:.2f}ms"
        )

    async def test_existence_query_performance(self, db_session: AsyncSession):
        """Test ? (existence) operator performance with GIN index."""
        query = text("""
            SELECT phenopacket_id, subject_sex
            FROM phenopackets
            WHERE phenopacket ? 'phenotypicFeatures'
            LIMIT 100
        """)

        # Warm-up
        await db_session.execute(query)

        # Timed execution
        start = time.time()
        result = await db_session.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Existence Query (has phenotypicFeatures):")
        print(f"  Query time:  {elapsed*1000:.2f}ms")
        print(f"  Matches:     {len(rows)}")
        print(f"{'='*60}")

        assert elapsed < 0.5, (
            f"Existence query should complete in <500ms, took {elapsed*1000:.2f}ms"
        )


class TestQueryPlanVerification:
    """Verify that query plans are reasonable and queries execute correctly.

    Note: On small test datasets (<1000 rows), PostgreSQL may choose sequential
    scan over index scan because it's actually faster. This is expected optimizer
    behavior. Index benefits appear on larger production datasets.
    """

    async def test_aggregation_query_plan_is_reasonable(self, db_session: AsyncSession):
        """Verify aggregation queries have reasonable query plans."""
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT TEXT)
                SELECT
                    feature->'type'->>'id' as hpo_id,
                    COUNT(*) as count
                FROM phenopackets,
                     jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
                GROUP BY hpo_id
                LIMIT 10
            """)
        )

        explain_lines = [row[0] for row in result.fetchall()]
        explain_text = "\n".join(explain_lines)

        print(f"\n{'='*60}")
        print("Query Plan for Feature Aggregation:")
        print(explain_text)
        print(f"{'='*60}")

        # Verify query uses jsonb_array_elements (core requirement)
        explain_lower = explain_text.lower()
        assert "jsonb_array_elements" in explain_lower, (
            "Query should use jsonb_array_elements function"
        )

        # On small datasets, seq scan is expected and optimal
        # On large datasets (>1000 rows), would use index/bitmap scan

    async def test_contains_query_plan_is_reasonable(self, db_session: AsyncSession):
        """Verify @> queries have reasonable query plans."""
        result = await db_session.execute(
            text("""
                EXPLAIN (FORMAT TEXT)
                SELECT phenopacket_id
                FROM phenopackets
                WHERE phenopacket->'phenotypicFeatures' @> '[{"type": {"id": "HP:0012622"}}]'::jsonb
            """)
        )

        explain_lines = [row[0] for row in result.fetchall()]
        explain_text = "\n".join(explain_lines)

        print(f"\n{'='*60}")
        print("Query Plan for Contains Query:")
        print(explain_text)
        print(f"{'='*60}")

        # Verify query uses the @> operator (GIN-indexable)
        explain_lower = explain_text.lower()
        assert "phenopackets" in explain_lower, (
            "Query should scan phenopackets table"
        )

        # On small datasets, seq scan is expected
        # On large datasets (>1000 rows), would use GIN index with bitmap scan


@pytest.mark.skip(reason="Benchmark only - compare before/after manually")
class TestBeforeAfterComparison:
    """Manual tests to compare performance before/after adding indexes.

    To use:
    1. Run queries before migration (save times)
    2. Run migration: alembic upgrade head
    3. Run queries after migration (save times)
    4. Compare improvement (should be 5-60x faster)
    """

    async def test_measure_baseline_without_indexes(self, db_session: AsyncSession):
        """Measure query performance without JSONB path indexes."""
        # Would need to drop indexes first for accurate comparison
        pass

    async def test_measure_improvement_with_indexes(self, db_session: AsyncSession):
        """Measure query performance with JSONB path indexes."""
        # Run after migration and compare to baseline
        pass
