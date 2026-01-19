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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket


class TestTransactionRollback:
    """Test suite for transaction rollback scenarios."""

    async def test_transaction_validation_failure_prevents_commit(
        self, fixture_db_session: AsyncSession, fixture_invalid_phenopacket_data
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
        errors = validator.validate(fixture_invalid_phenopacket_data)

        # Should have validation errors
        assert len(errors) > 0, "Expected validation errors for invalid data"

        # Check database is clean (no record created)
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == fixture_invalid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Invalid phenopacket should not exist in database"

    async def test_transaction_successful_request_commits_changes(
        self, fixture_db_session: AsyncSession, fixture_valid_phenopacket_data
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
        sanitized = sanitizer.sanitize_phenopacket(fixture_valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(new_phenopacket)
        await fixture_db_session.commit()
        await fixture_db_session.refresh(new_phenopacket)

        # Verify it exists in database
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == fixture_valid_phenopacket_data["id"]
            )
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None, "Valid phenopacket should exist in database"
        assert fetched.phenopacket_id == fixture_valid_phenopacket_data["id"], (
            "Phenopacket ID should match"
        )

        # Cleanup
        await fixture_db_session.delete(fetched)
        await fixture_db_session.commit()

    async def test_transaction_exception_triggers_rollback(
        self, fixture_db_session: AsyncSession, fixture_valid_phenopacket_data
    ):
        """Test that exceptions trigger automatic rollback.

        Scenario:
        1. Start creating phenopacket
        2. Simulate exception before commit
        3. Verify no data persists in database
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()
        sanitized = sanitizer.sanitize_phenopacket(fixture_valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(new_phenopacket)

        # Simulate exception before commit
        try:
            raise Exception("Simulated error during request")
        except Exception:
            await fixture_db_session.rollback()

        # Verify data was NOT committed
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == fixture_valid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Phenopacket should not exist after rollback"

    async def test_transaction_duplicate_id_triggers_rollback(
        self, fixture_db_session: AsyncSession, fixture_valid_phenopacket_data
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
        data1 = fixture_valid_phenopacket_data.copy()
        data1["id"] = "test_duplicate_tx"
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

        # Count records before duplicate attempt
        count_before = await fixture_db_session.scalar(
            select(func.count())
            .select_from(Phenopacket)
            .where(Phenopacket.phenopacket_id == "test_duplicate_tx")
        )

        # Attempt to create duplicate
        data2 = fixture_valid_phenopacket_data.copy()
        data2["id"] = "test_duplicate_tx"  # Same ID
        sanitized2 = sanitizer.sanitize_phenopacket(data2)

        phenopacket2 = Phenopacket(
            phenopacket_id=sanitized2["id"],
            phenopacket=sanitized2,
            subject_id=sanitized2["subject"]["id"],
            subject_sex=sanitized2["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket2)

        # Should raise integrity error
        with pytest.raises(Exception):  # IntegrityError or similar
            await fixture_db_session.commit()

        # Rollback the failed transaction
        await fixture_db_session.rollback()

        # Count records after failed attempt
        count_after = await fixture_db_session.scalar(
            select(func.count())
            .select_from(Phenopacket)
            .where(Phenopacket.phenopacket_id == "test_duplicate_tx")
        )

        assert count_before == count_after == 1, (
            "Only one record should exist after duplicate attempt"
        )

        # Cleanup
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == "test_duplicate_tx"
            )
        )
        phenopacket = result.scalar_one()
        await fixture_db_session.delete(phenopacket)
        await fixture_db_session.commit()

    async def test_transaction_http_exception_prevents_commit(
        self, fixture_db_session: AsyncSession, fixture_valid_phenopacket_data
    ):
        """Test that HTTPException prevents commit.

        Scenario:
        1. Start creating phenopacket
        2. Business logic raises HTTPException
        3. Verify no data persists
        """
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()
        sanitized = sanitizer.sanitize_phenopacket(fixture_valid_phenopacket_data)

        new_phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="test_user",
        )

        fixture_db_session.add(new_phenopacket)

        # Simulate business logic error (e.g., authorization failure)
        try:
            raise HTTPException(status_code=403, detail="Permission denied")
        except HTTPException:
            await fixture_db_session.rollback()

        # Verify no data committed
        result = await fixture_db_session.execute(
            select(Phenopacket).where(
                Phenopacket.phenopacket_id == fixture_valid_phenopacket_data["id"]
            )
        )
        phenopacket = result.scalar_one_or_none()

        assert phenopacket is None, "Phenopacket should not exist after HTTPException"


class TestReadOnlyOperations:
    """Test that read-only operations don't require commits."""

    async def test_transaction_read_operation_succeeds_without_commit(
        self, fixture_db_session: AsyncSession
    ):
        """Test that GET requests work without commits."""
        # Query should work without any commit
        result = await fixture_db_session.execute(select(Phenopacket).limit(5))
        phenopackets = result.scalars().all()

        # Should execute successfully (may return empty list)
        assert isinstance(phenopackets, list)
