# ✅ COMPLETED: Migration Script Fix
## Correct Database Schema + Import with Proper Attribution

**Original Date**: 2025-11-16
**Status**: ✅ **COMPLETED** (2025-11-16)
**Completion Commits**:
- `a7f9c44` - feat(migration): add revision field and reviewer attribution for curation system
- `dd957e3` - feat(migration): enable audit trail creation for initial import
- `b3b5265` - fix(db): fix audit migration to add missing columns without conflicts

---

## ✅ What Was Accomplished

### Database Schema Changes
- ✅ Added `revision` column (Integer, default=1) for optimistic locking
- ✅ Added `deleted_at` and `deleted_by` columns for soft delete
- ✅ Created `phenopacket_audit` table with all required columns
- ✅ Added `change_patch`, `change_summary`, and `change_reason` fields

### Import Script Fixes
- ✅ Integrated ReviewerMapper for proper curator attribution
- ✅ Set initial `revision=1` for all imported phenopackets
- ✅ Created initial audit trail entries for imported data
- ✅ Mapped Google Sheets reviewers to database users

### Model Updates
- ✅ Updated Pydantic models with `revision` field
- ✅ Added `PhenopacketAudit` model with all audit trail fields
- ✅ Implemented soft delete fields in `Phenopacket` model
- ✅ Made `revision` field optional for flexibility

### Verification
- ✅ All 864 phenopackets imported successfully
- ✅ Proper attribution via ReviewerMapper working
- ✅ Initial audit entries created for all imports
- ✅ Optimistic locking functional in UPDATE operations

---

## Original Implementation Plan

Below is the original plan that was executed:

---
# Migration Script Fix: Implementation Plan
## Correct Database Schema + Import with Proper Attribution

**Date**: 2025-11-16
**Status**: ✅ READY FOR IMPLEMENTATION
**Complexity**: Medium
**Estimated Duration**: 4-6 hours

---

## Executive Summary

This plan fixes the migration script BEFORE deploying the curation system, ensuring all imported data has:
- ✅ Correct `revision` field (Integer) for optimistic locking
- ✅ Proper curator attribution via ReviewerMapper
- ✅ Initial audit trail entries
- ✅ Clean database regeneration (no backfill needed)

**Approach**: Fix the source, regenerate cleanly (alpha advantage)

---

## Table of Contents

1. [Database Schema Changes](#1-database-schema-changes)
2. [Import Script Fixes](#2-import-script-fixes)
3. [Model Updates](#3-model-updates)
4. [Testing Strategy](#4-testing-strategy)
5. [Regeneration Steps](#5-regeneration-steps)
6. [Verification Checklist](#6-verification-checklist)

---

## 1. Database Schema Changes

### Task 1.1: Add Revision Column Migration

**File**: `backend/alembic/versions/002_add_revision_column.py`

**Action**: CREATE NEW FILE

```python
"""Add revision column for optimistic locking

Revision ID: 002_add_revision
Revises: 2e28b299e3b6
Create Date: 2025-11-16

Changes:
- Add revision column (Integer, default 1) to phenopackets table
- This is the revision counter for optimistic locking
- Keep 'version' as String for GA4GH schema version
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_revision'
down_revision: Union[str, Sequence[str], None] = '2e28b299e3b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add revision column for optimistic locking
    op.add_column(
        'phenopackets',
        sa.Column(
            'revision',
            sa.Integer,
            nullable=False,
            server_default='1',
            comment='Revision counter for optimistic locking'
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('phenopackets', 'revision')
```

**Why This Approach**:
- ✅ Keeps `version` as String (GA4GH schema version "2.0")
- ✅ Adds `revision` as Integer (concurrency control)
- ✅ No confusion between schema version and revision counter
- ✅ server_default='1' handles NULL safely

---

### Task 1.2: Run Migration After Soft Delete

**Execution Order**:
```bash
cd backend

# First: Soft delete migration (already exists or will be created)
uv run alembic upgrade head  # Gets to latest

# Then: Add revision column
uv run alembic upgrade head  # Runs 002_add_revision
```

**Verify**:
```bash
psql $DATABASE_URL -c "\d phenopackets"
# Should show:
# - deleted_at (timestamp, nullable)
# - deleted_by (varchar, nullable)
# - revision (integer, not null, default 1)
```

---

## 2. Import Script Fixes

### Task 2.1: Update PhenopacketStorage to Use ReviewerMapper

**File**: `backend/migration/database/storage.py`

**Action**: MODIFY EXISTING FILE

**Current Issues**:
1. ❌ Hardcoded `created_by = "direct_sheets_migration"`
2. ❌ No `revision` field in INSERT
3. ❌ No audit trail creation

**Find** (entire `store_phenopackets` method, lines 41-94):
```python
async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]) -> int:
    """Store phenopackets in the database.

    Args:
        phenopackets: List of phenopacket dictionaries

    Returns:
        Number of successfully stored phenopackets
    """
    async with self.session_maker() as session:
        stored_count = 0

        for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
            try:
                # Extract subject_id and subject_sex from phenopacket
                subject_id = phenopacket.get("subject", {}).get("id")
                subject_sex = phenopacket.get("subject", {}).get("sex")

                # Insert phenopacket with extracted subject data
                query = text("""
                    INSERT INTO phenopackets
                    (id, phenopacket_id, version, phenopacket, subject_id, subject_sex, created_by, schema_version)
                    VALUES (gen_random_uuid(), :phenopacket_id, :version, :phenopacket, :subject_id, :subject_sex, :created_by, :schema_version)
                    ON CONFLICT (phenopacket_id) DO UPDATE
                    SET phenopacket = EXCLUDED.phenopacket,
                        subject_id = EXCLUDED.subject_id,
                        subject_sex = EXCLUDED.subject_sex,
                        updated_at = CURRENT_TIMESTAMP
                """)

                await session.execute(
                    query,
                    {
                        "phenopacket_id": phenopacket["id"],
                        "version": "2.0",
                        "phenopacket": json.dumps(phenopacket),
                        "subject_id": subject_id,
                        "subject_sex": subject_sex,
                        "created_by": "direct_sheets_migration",
                        "schema_version": "2.0.0",
                    },
                )

                stored_count += 1

            except Exception as e:
                logger.error(
                    f"Error storing phenopacket {phenopacket.get('id')}: {e}"
                )
                continue

        await session.commit()
        logger.info(f"Successfully stored {stored_count} phenopackets")
        return stored_count
```

**Replace with**:
```python
async def store_phenopackets(
    self,
    phenopackets: List[Dict[str, Any]],
    reviewer_mapper=None,
    create_audit: bool = False,
) -> int:
    """Store phenopackets in the database with proper attribution.

    Args:
        phenopackets: List of phenopacket dictionaries
        reviewer_mapper: ReviewerMapper instance for curator attribution
        create_audit: Whether to create audit trail entries (default: False for backward compat)

    Returns:
        Number of successfully stored phenopackets
    """
    async with self.session_maker() as session:
        stored_count = 0

        for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
            try:
                # Extract subject_id and subject_sex from phenopacket
                subject_id = phenopacket.get("subject", {}).get("id")
                subject_sex = phenopacket.get("subject", {}).get("sex")

                # Get curator attribution from phenopacket metadata
                created_by = "data_migration_system"  # Default fallback
                if reviewer_mapper and "_migration_metadata" in phenopacket:
                    reviewer_email = phenopacket["_migration_metadata"].get("reviewer_email")
                    if reviewer_email:
                        created_by = reviewer_mapper.generate_username(reviewer_email)
                        logger.debug(
                            f"Mapped reviewer {reviewer_email} → {created_by} "
                            f"for phenopacket {phenopacket['id']}"
                        )

                # Remove migration metadata before storing
                phenopacket_clean = {k: v for k, v in phenopacket.items() if k != "_migration_metadata"}

                # Insert phenopacket with proper attribution and revision
                query = text("""
                    INSERT INTO phenopackets
                    (id, phenopacket_id, version, phenopacket, subject_id, subject_sex,
                     created_by, schema_version, revision)
                    VALUES (gen_random_uuid(), :phenopacket_id, :version, :phenopacket,
                            :subject_id, :subject_sex, :created_by, :schema_version, :revision)
                    ON CONFLICT (phenopacket_id) DO UPDATE
                    SET phenopacket = EXCLUDED.phenopacket,
                        subject_id = EXCLUDED.subject_id,
                        subject_sex = EXCLUDED.subject_sex,
                        updated_by = 'data_reimport',
                        revision = EXCLUDED.revision,
                        updated_at = CURRENT_TIMESTAMP
                """)

                await session.execute(
                    query,
                    {
                        "phenopacket_id": phenopacket["id"],
                        "version": "2.0",
                        "phenopacket": json.dumps(phenopacket_clean),
                        "subject_id": subject_id,
                        "subject_sex": subject_sex,
                        "created_by": created_by,
                        "schema_version": "2.0.0",
                        "revision": 1,  # All imports start at revision 1
                    },
                )

                # Create audit entry if requested
                if create_audit:
                    audit_query = text("""
                        INSERT INTO phenopacket_audit
                        (id, phenopacket_id, action, old_value, new_value,
                         changed_by, change_reason, change_summary)
                        VALUES (gen_random_uuid(), :phenopacket_id, :action, :old_value,
                                :new_value, :changed_by, :change_reason, :change_summary)
                    """)

                    # Generate change summary
                    phenotype_count = len(phenopacket_clean.get("phenotypicFeatures", []))
                    variant_count = len(phenopacket_clean.get("interpretations", []))
                    change_summary = (
                        f"Initial import: {phenotype_count} phenotype(s), "
                        f"{variant_count} variant(s)"
                    )

                    await session.execute(
                        audit_query,
                        {
                            "phenopacket_id": phenopacket["id"],
                            "action": "CREATE",
                            "old_value": None,
                            "new_value": json.dumps(phenopacket_clean),
                            "changed_by": created_by,
                            "change_reason": "Initial import from Google Sheets",
                            "change_summary": change_summary,
                        },
                    )

                stored_count += 1

            except Exception as e:
                logger.error(
                    f"Error storing phenopacket {phenopacket.get('id')}: {e}"
                )
                logger.exception(e)  # Full traceback for debugging
                continue

        await session.commit()
        logger.info(f"Successfully stored {stored_count} phenopackets")
        return stored_count
```

**Key Changes**:
1. ✅ Added `reviewer_mapper` parameter
2. ✅ Extract `reviewer_email` from `_migration_metadata`
3. ✅ Use `reviewer_mapper.generate_username()` for `created_by`
4. ✅ Added `revision=1` to INSERT
5. ✅ Added `create_audit` flag for audit trail generation
6. ✅ Clean phenopacket before storing (remove `_migration_metadata`)
7. ✅ Better error logging with full traceback

---

### Task 2.2: Update PhenopacketBuilder to Attach Reviewer Email

**File**: `backend/migration/phenopackets/builder_simple.py`

**Action**: MODIFY EXISTING FILE

**Find** the method that builds phenopackets from rows (likely `build_phenopacket` or similar).

**Need to locate exact method** - let me check:

```python
# Assuming the builder creates phenopacket dictionaries
# We need to attach _migration_metadata with reviewer_email
```

**Add after phenopacket is built**:
```python
# In build_phenopacket method, after constructing phenopacket dict:

# Attach migration metadata for attribution
# This will be used by storage layer, then removed before DB insert
reviewer_email = row.get("ReviewBy") or row.get("review_by")  # Try both casings
if reviewer_email:
    phenopacket["_migration_metadata"] = {
        "reviewer_email": reviewer_email,
        "sheet_row_number": row.name if hasattr(row, 'name') else None,
        "import_date": datetime.utcnow().isoformat(),
    }
```

**Why `_migration_metadata`**:
- Prefixed with `_` to indicate internal/temporary
- Not part of GA4GH schema
- Stripped before DB storage
- Allows reviewer email to flow through pipeline

---

### Task 2.3: Update Main Migration Script

**File**: `backend/migration/direct_sheets_to_phenopackets.py`

**Action**: MODIFY EXISTING FILE

**Find** the section where phenopackets are stored (likely in `run()` or `migrate()` method):

**Current** (approximately):
```python
# Store in database
stored_count = await self.storage.store_phenopackets(phenopackets)
```

**Change to**:
```python
# Store in database with reviewer attribution and audit trail
stored_count = await self.storage.store_phenopackets(
    phenopackets=phenopackets,
    reviewer_mapper=self.reviewer_mapper,  # Pass the mapper
    create_audit=True,  # Create audit entries for alpha import
)
```

**Ensure ReviewerMapper is loaded**:

**Find** (in `__init__` or `load_data` method):
```python
self.reviewer_mapper: Optional[ReviewerMapper] = None
```

**Verify it's initialized**:
```python
# Load reviewers (optional)
self.reviewers_df = self.sheets_loader.load_sheet("reviewers")
if self.reviewers_df is not None:
    self.reviewer_mapper = ReviewerMapper()
    self.reviewer_mapper.build_from_dataframe(self.reviewers_df)
    logger.info(f"Loaded {len(self.reviewer_mapper.data_map)} reviewers")
else:
    logger.warning("Reviewers sheet not found - using default attribution")
```

---

## 3. Model Updates

### Task 3.1: Update Phenopacket Model

**File**: `backend/app/phenopackets/models.py`

**Action**: MODIFY EXISTING FILE

**Find** (around line 32):
```python
version: Mapped[str] = mapped_column(String(10), default="2.0")
phenopacket: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
```

**Add after `version`**:
```python
version: Mapped[str] = mapped_column(
    String(10), default="2.0",
    comment="GA4GH Phenopackets schema version (e.g., '2.0', '2.1')"
)
phenopacket: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

# Optimistic locking
revision: Mapped[int] = mapped_column(
    Integer, default=1, nullable=False,
    comment="Revision counter for optimistic locking (increments on each update)"
)
```

**Update docstring** at top of `Phenopacket` class:
```python
class Phenopacket(Base):
    """Core phenopacket storage model.

    Fields:
        - version: GA4GH Phenopackets schema version (String, e.g., "2.0")
        - schema_version: Detailed schema version (String, e.g., "2.0.0")
        - revision: Optimistic locking counter (Integer, increments on update)
    """
```

---

### Task 3.2: Update Pydantic Response Models

**File**: `backend/app/phenopackets/models.py`

**Action**: MODIFY EXISTING FILE

**Find** `PhenopacketResponse` class (around line 344):
```python
class PhenopacketResponse(BaseModel):
    """Response model for phenopacket queries."""

    id: str
    phenopacket_id: str
    version: str
    phenopacket: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    schema_version: str
```

**Add `revision` field**:
```python
class PhenopacketResponse(BaseModel):
    """Response model for phenopacket queries."""

    id: str
    phenopacket_id: str
    version: str  # GA4GH schema version
    revision: int  # Optimistic locking counter
    phenopacket: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    schema_version: str
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True
```

**Why add `created_by` and `updated_by`**:
- Frontend needs to display "Created by john_doe"
- Useful for debugging and auditing
- Already in database, just expose in API

---

## 4. Testing Strategy

### Test 4.1: Unit Test for ReviewerMapper Attribution

**File**: `backend/tests/test_migration_reviewer_attribution.py`

**Action**: CREATE NEW FILE

```python
"""Tests for reviewer attribution in migration."""

import pytest
from migration.phenopackets.reviewer_mapper import ReviewerMapper
import pandas as pd


class TestReviewerAttribution:
    """Test reviewer email to username mapping."""

    def test_generate_username_from_email(self):
        """Verify email → username conversion."""
        mapper = ReviewerMapper()

        # Test standard email
        assert mapper.generate_username("john.doe@example.com") == "john_doe"

        # Test uppercase
        assert mapper.generate_username("Jane.Smith@Example.COM") == "jane_smith"

        # Test no domain
        assert mapper.generate_username("admin") == "admin"

        # Test dots replaced with underscores
        assert mapper.generate_username("mary.jane.watson@marvel.com") == "mary_jane_watson"

    def test_reviewer_data_lookup(self):
        """Test loading reviewer data from dataframe."""
        # Create mock reviewer data
        reviewers_data = pd.DataFrame({
            "email": ["john.doe@example.com", "jane.smith@example.com"],
            "user_name": ["john_doe", "jane_smith"],
            "first_name": ["John", "Jane"],
            "family_name": ["Doe", "Smith"],
            "orcid": ["0000-0001-1234-5678", "0000-0002-9876-5432"],
            "user_role": ["Reviewer", "Administrator"],
        })

        mapper = ReviewerMapper()
        mapper.build_from_dataframe(reviewers_data)

        # Test lookup
        john_data = mapper.get_reviewer_data("john.doe@example.com")
        assert john_data is not None
        assert john_data["email"] == "john.doe@example.com"
        assert john_data["first_name"] == "John"

        # Test case-insensitive lookup
        jane_data = mapper.get_reviewer_data("JANE.SMITH@EXAMPLE.COM")
        assert jane_data is not None
        assert jane_data["first_name"] == "Jane"

    def test_role_mapping(self):
        """Test Google Sheets role → app role mapping."""
        reviewers_data = pd.DataFrame({
            "email": ["admin@example.com", "curator@example.com"],
            "user_role": ["Administrator", "Reviewer"],
        })

        mapper = ReviewerMapper()
        mapper.build_from_dataframe(reviewers_data)

        # Administrator → admin
        assert mapper.get_role("admin@example.com") == "admin"

        # Reviewer → curator
        assert mapper.get_role("curator@example.com") == "curator"

        # Unknown → curator (default)
        assert mapper.get_role("unknown@example.com") == "curator"
```

---

### Test 4.2: Integration Test for Storage

**File**: `backend/tests/test_migration_storage_attribution.py`

**Action**: CREATE NEW FILE

```python
"""Integration tests for phenopacket storage with attribution."""

import pytest
from migration.database.storage import PhenopacketStorage
from migration.phenopackets.reviewer_mapper import ReviewerMapper
import pandas as pd


@pytest.mark.asyncio
async def test_store_with_reviewer_attribution(test_db_url):
    """Test storing phenopackets with reviewer attribution."""

    # Create mock reviewer mapper
    reviewers_data = pd.DataFrame({
        "email": ["curator@hnf1b.org"],
        "user_name": ["curator"],
    })

    reviewer_mapper = ReviewerMapper()
    reviewer_mapper.build_from_dataframe(reviewers_data)

    # Create test phenopacket with migration metadata
    phenopacket = {
        "id": "test-phenopacket-001",
        "subject": {"id": "patient-001", "sex": "MALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000107", "label": "Renal cyst"}, "excluded": False}
        ],
        "interpretations": [],
        "metaData": {
            "created": "2024-01-01T00:00:00Z",
            "createdBy": "Test",
            "resources": [],
        },
        "_migration_metadata": {
            "reviewer_email": "curator@hnf1b.org",
        },
    }

    # Store with attribution
    storage = PhenopacketStorage(test_db_url)
    count = await storage.store_phenopackets(
        phenopackets=[phenopacket],
        reviewer_mapper=reviewer_mapper,
        create_audit=True,
    )

    assert count == 1

    # Verify in database
    async with storage.async_session() as session:
        from sqlalchemy import text

        # Check phenopacket
        result = await session.execute(
            text("SELECT created_by, revision FROM phenopackets WHERE phenopacket_id = :id"),
            {"id": "test-phenopacket-001"},
        )
        row = result.fetchone()

        assert row is not None
        assert row.created_by == "curator"  # Mapped from email
        assert row.revision == 1

        # Check audit entry
        audit_result = await session.execute(
            text("SELECT changed_by, action FROM phenopacket_audit WHERE phenopacket_id = :id"),
            {"id": "test-phenopacket-001"},
        )
        audit_row = audit_result.fetchone()

        assert audit_row is not None
        assert audit_row.changed_by == "curator"
        assert audit_row.action == "CREATE"

    await storage.close()


@pytest.mark.asyncio
async def test_store_without_reviewer_uses_default(test_db_url):
    """Test that phenopackets without reviewer get default attribution."""

    phenopacket = {
        "id": "test-phenopacket-002",
        "subject": {"id": "patient-002", "sex": "FEMALE"},
        "phenotypicFeatures": [],
        "interpretations": [],
        "metaData": {"created": "2024-01-01T00:00:00Z", "createdBy": "Test", "resources": []},
        # No _migration_metadata
    }

    storage = PhenopacketStorage(test_db_url)
    count = await storage.store_phenopackets(
        phenopackets=[phenopacket],
        reviewer_mapper=None,  # No mapper
        create_audit=False,
    )

    assert count == 1

    # Verify default attribution
    async with storage.async_session() as session:
        from sqlalchemy import text

        result = await session.execute(
            text("SELECT created_by FROM phenopackets WHERE phenopacket_id = :id"),
            {"id": "test-phenopacket-002"},
        )
        row = result.fetchone()

        assert row is not None
        assert row.created_by == "data_migration_system"  # Default fallback

    await storage.close()
```

---

### Test 4.3: End-to-End Migration Test

**File**: `backend/tests/test_migration_e2e.py`

**Action**: CREATE NEW FILE

```python
"""End-to-end test for complete migration pipeline."""

import pytest
from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_migration_with_attribution(test_db_url, tmp_path):
    """Test complete migration flow with reviewer attribution.

    This test uses the test data mode (20 phenopackets).
    """

    # Initialize migration
    migrator = DirectSheetsToPhenopackets(target_db_url=test_db_url)

    # Load data (will load test subset)
    await migrator.load_data()

    # Build phenopackets
    phenopackets = migrator.build_phenopackets()

    assert len(phenopackets) > 0, "No phenopackets built"

    # Verify _migration_metadata exists
    phenopackets_with_metadata = [
        p for p in phenopackets if "_migration_metadata" in p
    ]

    # At least some should have metadata if reviewers sheet exists
    if migrator.reviewer_mapper:
        assert len(phenopackets_with_metadata) > 0, "No phenopackets have reviewer metadata"

    # Store with attribution
    stored_count = await migrator.storage.store_phenopackets(
        phenopackets=phenopackets,
        reviewer_mapper=migrator.reviewer_mapper,
        create_audit=True,
    )

    assert stored_count == len(phenopackets)

    # Verify in database
    async with migrator.storage.async_session() as session:
        from sqlalchemy import text, func

        # Count phenopackets
        result = await session.execute(
            text("SELECT COUNT(*) FROM phenopackets")
        )
        count = result.scalar()
        assert count == stored_count

        # Check that NOT all have default attribution
        result = await session.execute(
            text("SELECT COUNT(*) FROM phenopackets WHERE created_by != 'data_migration_system'")
        )
        attributed_count = result.scalar()

        if migrator.reviewer_mapper:
            assert attributed_count > 0, "All phenopackets have default attribution - reviewer mapping failed"

        # Check all have revision=1
        result = await session.execute(
            text("SELECT COUNT(*) FROM phenopackets WHERE revision = 1")
        )
        revision_count = result.scalar()
        assert revision_count == stored_count, "Not all phenopackets have revision=1"

        # Check audit entries created
        result = await session.execute(
            text("SELECT COUNT(*) FROM phenopacket_audit WHERE action = 'CREATE'")
        )
        audit_count = result.scalar()
        assert audit_count == stored_count, "Audit entries not created for all phenopackets"

    await migrator.close()
```

---

## 5. Regeneration Steps

### Step 5.1: Backup Current Database (Optional)

```bash
# Optional: Save current database state
pg_dump $DATABASE_URL > backup_before_migration_fix.sql
```

### Step 5.2: Drop and Recreate Database

```bash
cd /mnt/c/development/hnf1b-db

# Drop all tables
make db-reset

# OR manual:
# psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Step 5.3: Run ALL Migrations

```bash
cd backend

# Run all migrations including the new ones
uv run alembic upgrade head

# Verify
uv run alembic current
# Should show: 002_add_revision (head)
```

### Step 5.4: Create Admin User

```bash
make db-create-admin
# OR
cd backend
uv run python scripts/create_admin.py
```

### Step 5.5: Run Fixed Import Script

```bash
# Test import (20 phenopackets)
make phenopackets-migrate-test

# Verify results
psql $DATABASE_URL -c "SELECT phenopacket_id, created_by, revision FROM phenopackets LIMIT 5;"

# If test looks good, run full import (864 phenopackets)
make phenopackets-migrate
```

---

## 6. Verification Checklist

### 6.1: Database Schema Verification

```bash
# Check columns exist
psql $DATABASE_URL -c "\d phenopackets" | grep -E "revision|deleted_at|deleted_by"

# Expected output:
# revision         | integer           | not null | 1
# deleted_at       | timestamp with time zone |  |
# deleted_by       | character varying(100)   |  |
```

### 6.2: Data Verification

```bash
# Check revision values
psql $DATABASE_URL -c "SELECT COUNT(*), MIN(revision), MAX(revision) FROM phenopackets;"
# Expected: count=864 (or 20 for test), min=1, max=1

# Check created_by distribution
psql $DATABASE_URL -c "SELECT created_by, COUNT(*) FROM phenopackets GROUP BY created_by ORDER BY COUNT(*) DESC;"
# Expected: Multiple usernames, NOT just "direct_sheets_migration"

# Check audit trail
psql $DATABASE_URL -c "SELECT COUNT(*) FROM phenopacket_audit WHERE action='CREATE';"
# Expected: count = number of phenopackets

# Sample audit entry
psql $DATABASE_URL -c "SELECT phenopacket_id, changed_by, change_summary FROM phenopacket_audit LIMIT 3;"
```

### 6.3: Application Verification

```bash
# Start backend
cd backend
uv run uvicorn app.main:app --reload

# In another terminal, test API
curl http://localhost:8000/api/v2/phenopackets/ | jq '.[0] | {phenopacket_id, revision, created_by}'

# Expected output:
# {
#   "phenopacket_id": "HNF1B-001",
#   "revision": 1,
#   "created_by": "actual_curator_username"
# }
```

### 6.4: Audit Trail Verification

```bash
# Get audit history for a phenopacket
curl http://localhost:8000/api/v2/phenopackets/HNF1B-001/audit | jq

# Expected: At least one CREATE entry with proper attribution
```

---

## 7. Linting and Code Quality

### Lint All Changes

```bash
# Backend
cd backend
make check  # Runs: ruff, mypy, pytest

# Expected: All pass

# If ruff errors:
make format  # Auto-fix formatting
make lint    # Verify

# If mypy errors:
# Add type hints or use # type: ignore with comment
```

### Run Full Test Suite

```bash
cd backend

# Unit tests
uv run pytest tests/test_migration_reviewer_attribution.py -v

# Integration tests
uv run pytest tests/test_migration_storage_attribution.py -v

# E2E test (uses real Google Sheets - may need credentials)
uv run pytest tests/test_migration_e2e.py -v -m integration

# All tests
uv run pytest -v
```

---

## 8. Common Issues & Solutions

### Issue 1: "No module named 'app'"

**Solution**:
```bash
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
# OR use uv run which sets it automatically
```

### Issue 2: ReviewerMapper not finding data

**Cause**: Reviewers sheet not loaded

**Solution**:
```python
# In direct_sheets_to_phenopackets.py, verify:
self.reviewers_df = self.sheets_loader.load_sheet("reviewers")
if self.reviewers_df is not None:
    logger.info(f"Loaded {len(self.reviewers_df)} reviewers")
else:
    logger.error("REVIEWERS SHEET NOT FOUND!")  # Add this
```

### Issue 3: _migration_metadata not being attached

**Cause**: PhenopacketBuilder not updated

**Solution**: Ensure builder attaches metadata with reviewer_email

### Issue 4: Audit entries using wrong timezone

**Cause**: DateTime without timezone

**Solution**: Already handled - `changed_at` column has `timezone=True`

---

## Summary of Changes

| File | Action | Lines Changed | Purpose |
|------|--------|---------------|---------|
| `alembic/versions/002_add_revision.py` | CREATE | ~40 | Add revision column |
| `app/phenopackets/models.py` | MODIFY | +10 | Add revision field to model |
| `migration/database/storage.py` | MODIFY | ~80 | Use ReviewerMapper, add revision, create audit |
| `migration/phenopackets/builder_simple.py` | MODIFY | +10 | Attach _migration_metadata |
| `migration/direct_sheets_to_phenopackets.py` | MODIFY | +3 | Pass reviewer_mapper to storage |
| `tests/test_migration_reviewer_attribution.py` | CREATE | ~60 | Unit tests |
| `tests/test_migration_storage_attribution.py` | CREATE | ~100 | Integration tests |
| `tests/test_migration_e2e.py` | CREATE | ~80 | E2E test |

**Total**: 3 new files, 4 modified files, ~383 lines

---

## Timeline

| Task | Duration | Dependencies |
|------|----------|--------------|
| Database migration | 30 min | None |
| Storage.py updates | 1 hour | Migration complete |
| Builder updates | 30 min | None |
| Model updates | 30 min | Migration complete |
| Testing | 1.5 hours | All code complete |
| DB regeneration | 30 min | All complete |
| Verification | 30 min | Import complete |

**Total**: ~5 hours

---

## Success Criteria

✅ All phenopackets have `revision=1`
✅ All phenopackets have proper `created_by` (not all "direct_sheets_migration")
✅ All phenopackets have CREATE audit entry
✅ All tests pass (unit, integration, E2E)
✅ Linting passes (ruff, mypy)
✅ Can query `/api/v2/phenopackets/{id}` and see `revision` field
✅ Can query `/api/v2/phenopackets/{id}/audit` and see CREATE entry

---

**READY FOR IMPLEMENTATION** ✅

After completing this plan, the database will be correctly structured and populated for the curation system implementation.
