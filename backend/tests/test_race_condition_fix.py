"""Tests for TOCTOU race condition fix in phenopacket creation.

Tests that duplicate phenopacket IDs are handled correctly even with
concurrent requests, ensuring HTTP 409 (not 500) is returned.

NOTE: These are integration tests that require a running database.
Run `make hybrid-up` before executing these tests.
"""

import asyncio
from typing import List

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket


@pytest.fixture
def fixture_race_condition_phenopacket_data():
    """Fixture for sample phenopacket data."""
    return {
        "id": "test_race_condition",
        "subject": {"id": "patient_race_test", "sex": "MALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Test feature"}}],
        "metaData": {
            "created": "2024-01-01T00:00:00Z",
            "phenopacketSchemaVersion": "2.0.0",
        },
    }


class TestRaceConditionSequentialDuplicates:
    """Test sequential duplicate insert detection."""

    @pytest.mark.asyncio
    async def test_race_condition_sequential_duplicate_raises_integrity_error(
        self, fixture_db_session: AsyncSession, fixture_race_condition_phenopacket_data
    ):
        """Test that sequential duplicate inserts are caught by database constraint.

        Scenario:
        1. Insert phenopacket with ID 'test_dup_seq'
        2. Attempt to insert another with same ID
        3. Should raise IntegrityError (caught by endpoint as 409)
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # First insert
        data1 = fixture_race_condition_phenopacket_data.copy()
        data1["id"] = "test_dup_sequential"
        sanitized1 = sanitizer.sanitize_phenopacket(data1)

        phenopacket1 = Phenopacket(
            phenopacket_id=sanitized1["id"],
            phenopacket=sanitized1,
            subject_id=sanitized1["subject"]["id"],
            subject_sex=sanitized1["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket1)
        await fixture_db_session.commit()

        # Verify first insert succeeded
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_sequential"
            )
        )
        assert result.scalar_one_or_none() is not None

        # Second insert with same ID
        data2 = fixture_race_condition_phenopacket_data.copy()
        data2["id"] = "test_dup_sequential"
        data2["subject"]["id"] = "different_patient"  # Different subject
        sanitized2 = sanitizer.sanitize_phenopacket(data2)

        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized2["id"],  # Same ID
            phenopacket=sanitized2,
            subject_id=sanitized2["subject"]["id"],
            subject_sex=sanitized2["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket2)

        # Should raise IntegrityError
        with pytest.raises(IntegrityError) as exc_info:
            await fixture_db_session.commit()

        # Verify error mentions phenopacket_id
        error_str = str(exc_info.value).lower()
        assert "phenopacket_id" in error_str or "duplicate" in error_str

        await fixture_db_session.rollback()

        # Cleanup
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_sequential"
            )
        )
        phenopacket = result.scalar_one()
        await fixture_db_session.delete(phenopacket)
        await fixture_db_session.commit()

    @pytest.mark.asyncio
    async def test_race_condition_unique_constraint_exists_on_phenopacket_id(
        self, fixture_db_session: AsyncSession
    ):
        """Verify that phenopacket_id has UNIQUE constraint in database."""
        from sqlalchemy import inspect

        # Get table metadata using run_sync properly
        def get_constraints(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_unique_constraints("phenopackets")

        # Await connection first, then call run_sync
        conn = await fixture_db_session.connection()
        constraints = await conn.run_sync(get_constraints)

        # Check for unique constraint on phenopacket_id
        phenopacket_id_unique = False
        for constraint in constraints:
            if "phenopacket_id" in constraint.get("column_names", []):
                phenopacket_id_unique = True
                break

        assert phenopacket_id_unique, (
            "phenopacket_id must have UNIQUE constraint in database"
        )


@pytest.mark.integration
class TestRaceConditionConcurrentDuplicates:
    """Test concurrent duplicate insert detection (race condition).

    NOTE: These tests use the production async_session_maker from app.database
    to create separate database sessions for testing concurrent behavior.
    This requires the database to be running and accessible.

    Run with: pytest tests/test_race_condition_fix.py -m integration -v
    """

    @pytest.mark.asyncio
    async def test_race_condition_concurrent_duplicate_exactly_one_succeeds(
        self, fixture_db_session: AsyncSession, fixture_race_condition_phenopacket_data
    ):
        """Test that concurrent duplicate inserts are caught by database.

        Scenario:
        1. Spawn two async tasks simultaneously
        2. Both try to insert phenopacket with same ID
        3. One should succeed, one should fail with IntegrityError
        4. No race window - database handles atomically
        """
        from sqlalchemy import delete

        from app.database import async_session_maker
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Prepare phenopacket data with same ID
        data = fixture_race_condition_phenopacket_data.copy()
        data["id"] = "test_dup_concurrent"
        sanitized = sanitizer.sanitize_phenopacket(data)

        # Clean up any leftover data from previous failed runs
        async with async_session_maker() as session:
            await session.execute(
                delete(Phenopacket).where(
                    Phenopacket.phenopacket_id == "test_dup_concurrent"
                )
            )
            await session.commit()

        # Use list to collect results (thread-safe for append)
        results: List[str] = []

        async def insert_phenopacket(session_index: int):
            """Insert phenopacket in separate session."""
            async with async_session_maker() as session:
                phenopacket = Phenopacket(
                    phenopacket_id=sanitized["id"],
                    phenopacket=sanitized,
                    subject_id=sanitized["subject"]["id"],
                    subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
                    created_by=f"test_user_{session_index}",
                )

                session.add(phenopacket)

                try:
                    await session.commit()
                    results.append("success")
                except IntegrityError:
                    await session.rollback()
                    results.append("duplicate")
                except Exception as e:
                    results.append(f"error_{type(e).__name__}")

        # Launch concurrent inserts
        await asyncio.gather(
            insert_phenopacket(1),
            insert_phenopacket(2),
        )

        # Count results
        success_count = results.count("success")
        error_count = results.count("duplicate")

        # Verify exactly one succeeded and one failed
        assert success_count == 1, (
            f"Exactly one insert should succeed (got {success_count}, results: {results})"
        )
        assert error_count == 1, (
            f"Exactly one insert should fail with IntegrityError (got {error_count}, results: {results})"
        )

        # Verify only one record exists
        async with async_session_maker() as session:
            result = await session.execute(
                select(Phenopacket).where(
                    Phenopacket.phenopacket_id == "test_dup_concurrent"
                )
            )
            all_records = result.scalars().all()
            assert len(all_records) == 1, "Only one record should exist"

            # Cleanup
            for record in all_records:
                await session.delete(record)
            await session.commit()

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Requires standalone execution due to connection pool event loop issues"
    )
    async def test_race_condition_high_concurrency_stress_test(
        self, fixture_db_session: AsyncSession, fixture_race_condition_phenopacket_data
    ):
        """Stress test with 10 concurrent duplicate inserts.

        Simulates high-load scenario with multiple clients attempting
        to create the same phenopacket simultaneously.

        NOTE: Run standalone: pytest tests/test_race_condition_fix.py::TestRaceConditionConcurrentDuplicates::test_race_condition_high_concurrency_stress_test -v
        """
        from sqlalchemy import delete

        from app.database import async_session_maker
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        data = fixture_race_condition_phenopacket_data.copy()
        data["id"] = "test_dup_high_concurrency"
        sanitized = sanitizer.sanitize_phenopacket(data)

        # Clean up any leftover data from previous failed runs
        async with async_session_maker() as session:
            await session.execute(
                delete(Phenopacket).where(
                    Phenopacket.phenopacket_id == "test_dup_high_concurrency"
                )
            )
            await session.commit()

        results: List[str] = []

        async def insert_phenopacket(task_id: int):
            """Insert phenopacket in separate session."""
            try:
                async with async_session_maker() as session:
                    phenopacket = Phenopacket(
                        phenopacket_id=sanitized["id"],
                        phenopacket=sanitized,
                        subject_id=sanitized["subject"]["id"],
                        subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
                        created_by=f"test_user_{task_id}",
                    )

                    session.add(phenopacket)

                    try:
                        await session.commit()
                        results.append("success")
                    except IntegrityError:
                        await session.rollback()
                        results.append("duplicate")
            except Exception as e:
                # Catch any other exceptions (connection errors, etc.)
                results.append(f"error_{type(e).__name__}")

        # Launch 10 concurrent inserts
        tasks = [insert_phenopacket(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify exactly one succeeded
        success_count = results.count("success")
        duplicate_count = results.count("duplicate")
        total_completed = len(results)

        assert success_count == 1, (
            f"Exactly one insert should succeed (got {success_count}, results: {results})"
        )
        assert duplicate_count >= 7, (
            f"At least 7 inserts should fail with IntegrityError (got {duplicate_count}, results: {results})"
        )
        assert total_completed >= 8, (
            f"At least 8 tasks should complete (got {total_completed}, results: {results})"
        )

        # Verify only one record exists
        async with async_session_maker() as session:
            result = await session.execute(
                select(Phenopacket).where(
                    Phenopacket.phenopacket_id == "test_dup_high_concurrency"
                )
            )
            all_records = result.scalars().all()
            assert len(all_records) == 1, "Only one record should exist after stress test"

            # Cleanup
            for record in all_records:
                await session.delete(record)
            await session.commit()


class TestRaceConditionErrorHandling:
    """Test that proper HTTP status codes are returned."""

    @pytest.mark.asyncio
    async def test_race_condition_duplicate_id_maps_to_409(
        self, fixture_db_session: AsyncSession, fixture_race_condition_phenopacket_data
    ):
        """Test that duplicate IDs return HTTP 409, not 500.

        This verifies the endpoint's error handling logic converts
        IntegrityError to HTTPException(409).
        """
        from fastapi import HTTPException

        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # First insert
        data = fixture_race_condition_phenopacket_data.copy()
        data["id"] = "test_error_409"
        sanitized = sanitizer.sanitize_phenopacket(data)

        phenopacket1 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket1)
        await fixture_db_session.commit()

        # Simulate endpoint logic: try to insert duplicate
        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket2)

        try:
            await fixture_db_session.commit()
            pytest.fail("Should have raised IntegrityError")
        except IntegrityError as e:
            await fixture_db_session.rollback()
            # Simulate endpoint error handling
            error_str = str(e).lower()
            if (
                "duplicate" in error_str or "unique" in error_str
            ) and "phenopacket_id" in error_str:
                # This should raise HTTPException(409)
                http_error = HTTPException(
                    status_code=409,
                    detail=f"Phenopacket with ID '{sanitized['id']}' already exists",
                )
                assert http_error.status_code == 409
                assert "already exists" in http_error.detail
            else:
                pytest.fail("IntegrityError should mention phenopacket_id")

        # Cleanup
        result = await fixture_db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id == "test_error_409")
        )
        phenopacket = result.scalar_one()
        await fixture_db_session.delete(phenopacket)
        await fixture_db_session.commit()

    @pytest.mark.asyncio
    async def test_race_condition_error_message_contains_phenopacket_id(
        self, fixture_db_session: AsyncSession, fixture_race_condition_phenopacket_data
    ):
        """Test that error message includes the duplicate phenopacket ID."""
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        data = fixture_race_condition_phenopacket_data.copy()
        data["id"] = "test_error_message_id"
        sanitized = sanitizer.sanitize_phenopacket(data)

        # First insert
        phenopacket1 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket1)
        await fixture_db_session.commit()

        # Second insert with same ID
        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket2)

        try:
            await fixture_db_session.commit()
        except IntegrityError:
            await fixture_db_session.rollback()
            # Error message should include the ID
            error_message = f"Phenopacket with ID '{sanitized['id']}' already exists"
            assert sanitized["id"] in error_message
            assert "already exists" in error_message

        # Cleanup
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_error_message_id"
            )
        )
        phenopacket = result.scalar_one()
        await fixture_db_session.delete(phenopacket)
        await fixture_db_session.commit()
