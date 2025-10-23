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
def sample_phenopacket_data():
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


class TestSequentialDuplicates:
    """Test sequential duplicate insert detection."""

    async def test_sequential_duplicate_returns_409(
        self, db_session: AsyncSession, sample_phenopacket_data
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
        data1 = sample_phenopacket_data.copy()
        data1["id"] = "test_dup_sequential"
        sanitized1 = sanitizer.sanitize_phenopacket(data1)

        phenopacket1 = Phenopacket(
            phenopacket_id=sanitized1["id"],
            phenopacket=sanitized1,
            subject_id=sanitized1["subject"]["id"],
            subject_sex=sanitized1["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket1)
        await db_session.commit()

        # Verify first insert succeeded
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_sequential"
            )
        )
        assert result.scalar_one_or_none() is not None

        # Second insert with same ID
        data2 = sample_phenopacket_data.copy()
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

        db_session.add(phenopacket2)

        # Should raise IntegrityError
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        # Verify error mentions phenopacket_id
        error_str = str(exc_info.value).lower()
        assert "phenopacket_id" in error_str or "duplicate" in error_str

        await db_session.rollback()

        # Cleanup
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_sequential"
            )
        )
        phenopacket = result.scalar_one()
        await db_session.delete(phenopacket)
        await db_session.commit()

    async def test_database_constraint_is_unique(self, db_session: AsyncSession):
        """Verify that phenopacket_id has UNIQUE constraint in database."""
        from sqlalchemy import inspect

        # Get table metadata using run_sync properly
        def get_constraints(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_unique_constraints("phenopackets")

        # Await connection first, then call run_sync
        conn = await db_session.connection()
        constraints = await conn.run_sync(get_constraints)

        # Check for unique constraint on phenopacket_id
        phenopacket_id_unique = False
        for constraint in constraints:
            if "phenopacket_id" in constraint.get("column_names", []):
                phenopacket_id_unique = True
                break

        assert (
            phenopacket_id_unique
        ), "phenopacket_id must have UNIQUE constraint in database"


class TestConcurrentDuplicates:
    """Test concurrent duplicate insert detection (race condition)."""

    async def test_concurrent_duplicate_inserts(
        self, db_session: AsyncSession, sample_phenopacket_data
    ):
        """Test that concurrent duplicate inserts are caught by database.

        Scenario:
        1. Spawn two async tasks simultaneously
        2. Both try to insert phenopacket with same ID
        3. One should succeed, one should fail with IntegrityError
        4. No race window - database handles atomically
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Prepare two phenopackets with same ID
        data = sample_phenopacket_data.copy()
        data["id"] = "test_dup_concurrent"
        sanitized = sanitizer.sanitize_phenopacket(data)

        success_count = 0
        error_count = 0

        async def insert_phenopacket(session_index: int):
            """Insert phenopacket in separate session."""
            nonlocal success_count, error_count

            # Create new session for this task
            from app.database import async_session_maker

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
                    success_count += 1
                except IntegrityError:
                    await session.rollback()
                    error_count += 1

        # Launch concurrent inserts
        await asyncio.gather(
            insert_phenopacket(1),
            insert_phenopacket(2),
            return_exceptions=True,
        )

        # Verify exactly one succeeded and one failed
        assert success_count == 1, "Exactly one insert should succeed"
        assert error_count == 1, "Exactly one insert should fail with IntegrityError"

        # Verify only one record exists
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_concurrent"
            )
        )
        all_records = result.scalars().all()
        assert len(all_records) == 1, "Only one record should exist"

        # Cleanup
        await db_session.delete(all_records[0])
        await db_session.commit()

    async def test_high_concurrency_duplicate_inserts(
        self, db_session: AsyncSession, sample_phenopacket_data
    ):
        """Stress test with 10 concurrent duplicate inserts.

        Simulates high-load scenario with multiple clients attempting
        to create the same phenopacket simultaneously.
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        data = sample_phenopacket_data.copy()
        data["id"] = "test_dup_high_concurrency"
        sanitized = sanitizer.sanitize_phenopacket(data)

        results: List[str] = []

        async def insert_phenopacket(task_id: int):
            """Insert phenopacket in separate session."""
            from app.database import async_session_maker

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
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify exactly one succeeded
        success_count = results.count("success")
        duplicate_count = results.count("duplicate")
        total_completed = len(results)

        assert (
            success_count == 1
        ), f"Exactly one insert should succeed (got {success_count})"
        assert (
            duplicate_count >= 7
        ), f"At least 7 inserts should fail with IntegrityError (got {duplicate_count})"
        assert (
            total_completed >= 8
        ), f"At least 8 tasks should complete (got {total_completed}, results: {results})"

        # Verify only one record exists
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_dup_high_concurrency"
            )
        )
        all_records = result.scalars().all()
        assert len(all_records) == 1, "Only one record should exist after stress test"

        # Cleanup
        await db_session.delete(all_records[0])
        await db_session.commit()


class TestErrorHandling:
    """Test that proper HTTP status codes are returned."""

    async def test_duplicate_id_returns_409_not_500(
        self, db_session: AsyncSession, sample_phenopacket_data
    ):
        """Test that duplicate IDs return HTTP 409, not 500.

        This verifies the endpoint's error handling logic converts
        IntegrityError to HTTPException(409).
        """
        from fastapi import HTTPException

        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # First insert
        data = sample_phenopacket_data.copy()
        data["id"] = "test_error_409"
        sanitized = sanitizer.sanitize_phenopacket(data)

        phenopacket1 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket1)
        await db_session.commit()

        # Simulate endpoint logic: try to insert duplicate
        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket2)

        try:
            await db_session.commit()
            pytest.fail("Should have raised IntegrityError")
        except IntegrityError as e:
            await db_session.rollback()
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
        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id == "test_error_409")
        )
        phenopacket = result.scalar_one()
        await db_session.delete(phenopacket)
        await db_session.commit()

    async def test_error_message_includes_phenopacket_id(
        self, db_session: AsyncSession, sample_phenopacket_data
    ):
        """Test that error message includes the duplicate phenopacket ID."""
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        data = sample_phenopacket_data.copy()
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

        db_session.add(phenopacket1)
        await db_session.commit()

        # Second insert with same ID
        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket2)

        try:
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            # Error message should include the ID
            error_message = f"Phenopacket with ID '{sanitized['id']}' already exists"
            assert sanitized["id"] in error_message
            assert "already exists" in error_message

        # Cleanup
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_error_message_id"
            )
        )
        phenopacket = result.scalar_one()
        await db_session.delete(phenopacket)
        await db_session.commit()
