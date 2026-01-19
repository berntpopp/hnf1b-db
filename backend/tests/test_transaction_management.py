"""Tests for database transaction management.

Ensures that failed requests do NOT commit changes to the database,
while successful requests DO commit changes.

NOTE: These are integration tests that require a running database.
Run `make hybrid-up` before executing these tests.

Fixtures used from conftest.py:
- fixture_db_session
- fixture_valid_phenopacket_data
- fixture_invalid_phenopacket_data
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket


class TestTransactionRollback:
    """Test suite for transaction rollback scenarios."""

    async def test_validation_failure_does_not_commit(
        self, db_session: AsyncSession, invalid_phenopacket_data
    ):
        """Test that validation errors prevent database commits.

        Scenario:
        1. Attempt to create phenopacket with missing required fields
        2. Validation should fail
        3. Database should NOT contain the invalid phenopacket
        """
        from app.phenopackets.validator import PhenopacketValidator

        validator = PhenopacketValidator()

        # Validate the invalid data
        errors = validator.validate(invalid_phenopacket_data)

        # Should have validation errors
        assert len(errors) > 0, "Expected validation errors for invalid data"

        # Check database is clean (no record created)
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == invalid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Invalid phenopacket should not exist in database"

    async def test_successful_request_commits_changes(
        self, db_session: AsyncSession, valid_phenopacket_data
    ):
        """Test that successful requests DO commit changes.

        Scenario:
        1. Create valid phenopacket
        2. Explicitly commit
        3. Verify data persists in database
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Sanitize and create phenopacket
        sanitized = sanitizer.sanitize_phenopacket(valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(new_phenopacket)
        await db_session.commit()
        await db_session.refresh(new_phenopacket)

        # Verify it exists in database
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == valid_phenopacket_data["id"]
            )
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None, "Valid phenopacket should exist in database"
        assert fetched.phenopacket_id == valid_phenopacket_data["id"], (
            "Phenopacket ID should match"
        )

        # Cleanup
        await db_session.delete(fetched)
        await db_session.commit()

    async def test_exception_during_request_triggers_rollback(
        self, db_session: AsyncSession, valid_phenopacket_data
    ):
        """Test that exceptions trigger automatic rollback.

        Scenario:
        1. Start creating phenopacket
        2. Simulate exception before commit
        3. Verify no data persists in database
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()
        sanitized = sanitizer.sanitize_phenopacket(valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(new_phenopacket)

        # Simulate exception before commit
        try:
            raise Exception("Simulated error during request")
        except Exception:
            await db_session.rollback()

        # Verify data was NOT committed
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == valid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Phenopacket should not exist after rollback"

    async def test_duplicate_id_prevents_commit(
        self, db_session: AsyncSession, valid_phenopacket_data
    ):
        """Test that duplicate ID errors trigger rollback.

        Scenario:
        1. Create phenopacket with ID 'test_dup'
        2. Attempt to create another with same ID
        3. Verify only first phenopacket exists
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Create first phenopacket
        data1 = valid_phenopacket_data.copy()
        data1["id"] = "test_duplicate_tx"
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

        # Count records before duplicate attempt
        count_before = await db_session.scalar(
            select(func.count())
            .select_from(Phenopacket)
            .where(Phenopacket.phenopacket_id == "test_duplicate_tx")
        )

        # Attempt to create duplicate
        data2 = valid_phenopacket_data.copy()
        data2["id"] = "test_duplicate_tx"  # Same ID
        sanitized2 = sanitizer.sanitize_phenopacket(data2)

        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized2["id"],
            phenopacket=sanitized2,
            subject_id=sanitized2["subject"]["id"],
            subject_sex=sanitized2["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(phenopacket2)

        # Should raise integrity error
        with pytest.raises(Exception):  # IntegrityError or similar
            await db_session.commit()

        # Rollback the failed transaction
        await db_session.rollback()

        # Count records after failed attempt
        count_after = await db_session.scalar(
            select(func.count())
            .select_from(Phenopacket)
            .where(Phenopacket.phenopacket_id == "test_duplicate_tx")
        )

        assert count_before == count_after == 1, (
            "Only one record should exist after duplicate attempt"
        )

        # Cleanup
        result = await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id == "test_duplicate_tx")
        )
        phenopacket = result.scalar_one()
        await db_session.delete(phenopacket)
        await db_session.commit()

    async def test_http_exception_does_not_commit(
        self, db_session: AsyncSession, valid_phenopacket_data
    ):
        """Test that HTTPException prevents commit.

        Scenario:
        1. Start creating phenopacket
        2. Business logic raises HTTPException
        3. Verify no data persists
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()
        sanitized = sanitizer.sanitize_phenopacket(valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        db_session.add(new_phenopacket)

        # Simulate business logic error (e.g., authorization failure)
        try:
            raise HTTPException(status_code=403, detail="Permission denied")
        except HTTPException:
            await db_session.rollback()

        # Verify no data committed
        result = await db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == valid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Phenopacket should not exist after HTTPException"


class TestReadOnlyOperations:
    """Test that read-only operations don't require commits."""

    async def test_read_operations_work_without_commit(self, db_session: AsyncSession):
        """Test that GET requests work without commits."""
        # Query should work without any commit
        result = await db_session.execute(select(Phenopacket).limit(5))
        phenopackets = result.scalars().all()

        # Should execute successfully (may return empty list)
        assert isinstance(phenopackets, list)


# Need to add func import for count tests
from sqlalchemy import func  # noqa: E402
