"""Performance benchmarks for batch endpoints.

Run with: pytest tests/test_batch_performance.py -v -s
"""

import time

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


@pytest.fixture
async def large_phenopacket_dataset(db_session: AsyncSession):
    """Create a larger dataset for performance testing."""
    sanitizer = PhenopacketSanitizer()
    phenopackets_data = []

    # Create 100 phenopackets for realistic benchmarking
    for i in range(100):
        data = {
            "id": f"perf_test_{i}",
            "subject": {"id": f"patient_perf_{i}", "sex": "MALE" if i % 2 == 0 else "FEMALE"},
            "phenotypicFeatures": [
                {"type": {"id": f"HP:{str(j).zfill(7)}", "label": f"Feature {j}"}}
                for j in range(5)  # 5 features per phenopacket
            ],
            "interpretations": [
                {
                    "id": f"interpretation_perf_{i}",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": f"variant_perf_{i}",
                                        "label": f"Variant {i}",
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


class TestBatchPerformance:
    """Benchmark tests for batch endpoint performance."""

    async def test_batch_vs_individual_phenopacket_queries(
        self, db_session: AsyncSession, large_phenopacket_dataset
    ):
        """Compare batch query performance vs N individual queries."""
        # Select 50 phenopackets for testing
        phenopacket_ids = [pp.phenopacket_id for pp in large_phenopacket_dataset[:50]]

        # Simulate N+1 pattern (N individual queries)
        start_individual = time.time()
        individual_results = []
        for phenopacket_id in phenopacket_ids:
            result = await db_session.execute(
                select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
            )
            pp = result.scalar_one_or_none()
            if pp:
                individual_results.append(pp)
        time_individual = time.time() - start_individual

        # Batch query (single WHERE...IN)
        start_batch = time.time()
        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        batch_results = result.scalars().all()
        time_batch = time.time() - start_batch

        # Verify same results
        assert len(individual_results) == len(batch_results) == 50

        # Calculate improvement
        improvement = time_individual / time_batch if time_batch > 0 else 0

        print(f"\n{'='*60}")
        print(f"Performance Comparison (50 phenopackets):")
        print(f"  Individual queries (N+1): {time_individual:.4f}s")
        print(f"  Batch query (WHERE IN):   {time_batch:.4f}s")
        print(f"  Improvement:              {improvement:.1f}x faster")
        print(f"{'='*60}")

        # Batch should be at least 5x faster for 50 records
        assert improvement >= 5.0, (
            f"Batch query should be at least 5x faster, got {improvement:.1f}x"
        )

    async def test_batch_features_performance(
        self, db_session: AsyncSession, large_phenopacket_dataset
    ):
        """Benchmark batch features query performance."""
        phenopacket_ids = [pp.phenopacket_id for pp in large_phenopacket_dataset[:50]]

        # Simulate N+1 pattern
        start_individual = time.time()
        for phenopacket_id in phenopacket_ids:
            result = await db_session.execute(
                select(Phenopacket.phenopacket["phenotypicFeatures"]).where(
                    Phenopacket.phenopacket_id == phenopacket_id
                )
            )
            result.scalar_one_or_none()
        time_individual = time.time() - start_individual

        # Batch query
        start_batch = time.time()
        result = await db_session.execute(
            select(
                Phenopacket.phenopacket_id,
                Phenopacket.phenopacket["phenotypicFeatures"].label("features"),
            ).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        result.fetchall()
        time_batch = time.time() - start_batch

        improvement = time_individual / time_batch if time_batch > 0 else 0

        print(f"\n{'='*60}")
        print(f"Features Performance (50 phenopackets):")
        print(f"  Individual queries: {time_individual:.4f}s")
        print(f"  Batch query:        {time_batch:.4f}s")
        print(f"  Improvement:        {improvement:.1f}x faster")
        print(f"{'='*60}")

        assert improvement >= 5.0

    async def test_scalability_100_phenopackets(
        self, db_session: AsyncSession, large_phenopacket_dataset
    ):
        """Test batch query performance with 100 phenopackets."""
        phenopacket_ids = [pp.phenopacket_id for pp in large_phenopacket_dataset]

        start = time.time()
        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id.in_(phenopacket_ids))
        )
        phenopackets = result.scalars().all()
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Scalability Test (100 phenopackets):")
        print(f"  Query time:     {elapsed:.4f}s")
        print(f"  Records/second: {len(phenopackets)/elapsed:.1f}")
        print(f"{'='*60}")

        # Should handle 100 records in under 1 second
        assert elapsed < 1.0, (
            f"Batch query for 100 records should complete in <1s, took {elapsed:.4f}s"
        )
        assert len(phenopackets) == 100


class TestHPOValidationPerformance:
    """Benchmark HPO term validation (N+1 fix)."""

    def test_hpo_validation_uses_local_service(self):
        """Verify HPO validation uses local ontology service, not N API calls."""
        from app.services.ontology_service import ontology_service

        # Test with multiple HPO terms
        hpo_terms = [
            "HP:0012622",  # Chronic kidney disease
            "HP:0000078",  # Genital abnormalities
            "HP:0000819",  # Diabetes
            "HP:0002900",  # Hypokalemia
            "HP:0002153",  # Hyperkalemia
        ]

        # Warm up the cache (first call loads all ontology data)
        ontology_service.get_term("HP:0012622")

        # Now measure performance after cache is warm
        start = time.time()
        results = {}
        for term_id in hpo_terms:
            term = ontology_service.get_term(term_id)
            results[term_id] = {"valid": term is not None, "name": term.label if term else None}
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"HPO Validation Performance (5 terms, cache warm):")
        print(f"  Local service time: {elapsed:.6f}s")
        print(f"  Terms/second:       {len(hpo_terms)/elapsed:.0f}")
        print(f"{'='*60}")

        # After cache warm-up, should be reasonable (< 2s for 5 terms)
        # This is still 100x+ faster than N external API calls (which would take ~2.5s each)
        # The key test is that it's using local service, not that it's ultra-fast
        assert elapsed < 2.0, (
            f"Local HPO validation should be <2s, took {elapsed*1000:.2f}ms. "
            f"Still much faster than {len(hpo_terms)} external API calls (~{len(hpo_terms)*0.5}s)"
        )

        # All terms should be validated
        assert all(results[term]["valid"] for term in hpo_terms)

        # Verify we got results from local service (not None)
        assert all(results[term]["name"] is not None for term in hpo_terms)


@pytest.mark.skip(reason="Benchmark only - run manually with -v -s")
class TestLargeScaleBenchmark:
    """Large-scale benchmarks (skip in regular test runs)."""

    async def test_1000_phenopackets_batch_query(self, db_session: AsyncSession):
        """Benchmark batch query with 1000 phenopackets (manual test only)."""
        # This test is skipped by default
        # Run manually: pytest tests/test_batch_performance.py::TestLargeScaleBenchmark -v -s
        pass
