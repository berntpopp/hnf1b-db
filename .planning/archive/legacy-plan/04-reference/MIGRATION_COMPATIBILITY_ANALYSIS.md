# Migration Script Compatibility Analysis
## Curation System vs. Google Sheets Import

**Analysis Date**: 2025-11-16
**Analyst**: Senior Backend Engineer & Data Migration Specialist
**Scope**: Compatibility between existing Google Sheets migration and new curation system
**Status**: ⚠️ **CRITICAL INCOMPATIBILITIES FOUND**

---

## Executive Summary

The existing Google Sheets import script has **4 critical incompatibilities** and **3 moderate issues** that must be resolved before deploying the curation system.

### Critical Issues (Blocking)
1. 🔴 **Version field type mismatch** - String vs Integer (breaks optimistic locking)
2. 🔴 **Reviewer data not mapped to created_by** (audit attribution lost)
3. 🔴 **No initial audit trail** for imported phenopackets
4. 🔴 **Raw SQL bypasses ORM** (won't set new columns)

### Moderate Issues
5. 🟡 **Generic created_by value** ("direct_sheets_migration")
6. 🟡 **updated_by never set** in migration
7. 🟡 **Schema version confusion** (field name collision)

---

## Detailed Analysis

### 1. Version Field Type Mismatch 🔴 CRITICAL

**Current State** (`backend/app/phenopackets/models.py:32`):
```python
version: Mapped[str] = mapped_column(String(10), default="2.0")
```

**Migration Script** (`backend/migration/database/storage.py:75`):
```python
"version": "2.0",  # String value
```

**Implementation Plan Assumption**:
```python
# Assumes INTEGER for optimistic locking
version: Mapped[int] = mapped_column(Integer, default=1)
existing.version += 1  # Increment on update
```

**Impact**:
- ❌ **Optimistic locking completely broken**
- ❌ Cannot increment string "2.0" → "3.0" doesn't make sense
- ❌ `expected_version` comparison will fail
- ❌ All 864 imported phenopackets have version="2.0" (string)

**Root Cause**:
The `version` field was originally meant to store the **GA4GH Phenopackets schema version** (e.g., "2.0", "2.0.1"), NOT a revision counter for optimistic locking.

**There's a separate field** `schema_version` that also stores "2.0.0".

**Evidence**:
```python
# Line 32: version for GA4GH schema version
version: Mapped[str] = mapped_column(String(10), default="2.0")

# Line 53: schema_version also for GA4GH version
schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")
```

**Resolution Required**:
1. **Add NEW column** `revision` (Integer) for optimistic locking
2. **Keep** `version` as String for GA4GH schema version
3. **Update implementation plan** to use `revision` instead of `version`
4. **Backfill** all existing phenopackets with `revision=1`

---

### 2. Reviewer Data Not Mapped to created_by 🔴 CRITICAL

**What Exists**:
The migration has a complete `ReviewerMapper` class that loads reviewer data from Google Sheets:

**File**: `backend/migration/phenopackets/reviewer_mapper.py`

**Capabilities**:
```python
class ReviewerMapper:
    def get_reviewer_data(email: str) -> Dict[str, Any]:
        """Returns: {email, user_name, first_name, family_name, orcid, user_role}"""

    def generate_username(email: str) -> str:
        """Converts email to username (e.g., john.doe@example.com → john_doe)"""

    def get_full_name(email: str) -> str:
        """Returns: "John Doe" """

    def get_role(email: str) -> str:
        """Maps: Administrator → admin, Reviewer → curator"""
```

**What's Actually Stored**:

**File**: `backend/migration/database/storage.py:79`
```python
"created_by": "direct_sheets_migration",  # Hardcoded, ignores reviewer data!
```

**Impact**:
- ❌ **Reviewer attribution lost** for all 864 imported phenopackets
- ❌ Cannot determine who originally curated each case
- ❌ Authorization checks will fail (curator can't edit their own records)
- ❌ Audit trail shows "direct_sheets_migration" instead of actual curator

**What Should Happen**:
```python
# In migration script - get reviewer email from row
reviewer_email = row.get("ReviewBy")  # From Google Sheets Individuals sheet
reviewer_username = reviewer_mapper.generate_username(reviewer_email)

# Store actual curator username
"created_by": reviewer_username or "data_migration_system",
```

**Evidence from Google Sheets**:
The Individuals sheet has a `ReviewBy` column containing reviewer emails.

**Resolution Required**:
1. **Update migration script** to use ReviewerMapper
2. **Map ReviewBy email → created_by username**
3. **Re-import data** with proper attribution
4. **OR create migration script** to update existing records

---

### 3. No Initial Audit Trail 🔴 CRITICAL

**Current State**:
When 864 phenopackets are imported, **zero audit entries** are created.

**File**: `backend/migration/database/storage.py:60-83`
```python
# Only inserts into phenopackets table
query = text("""
    INSERT INTO phenopackets
    (id, phenopacket_id, version, phenopacket, subject_id, subject_sex, created_by, schema_version)
    VALUES (...)
    ON CONFLICT (phenopacket_id) DO UPDATE
    SET phenopacket = EXCLUDED.phenopacket, ...
""")

# NO audit entry created!
```

**Impact**:
- ❌ No record of initial data import in audit log
- ❌ Cannot track provenance of migrated data
- ❌ Audit timeline incomplete (first entry would be an UPDATE, not CREATE)
- ❌ Compliance issue (no proof of when data was loaded)

**What Should Happen**:
```python
# After each phenopacket insert
await create_audit_entry(
    db=db,
    phenopacket_id=phenopacket["id"],
    action=AuditAction.CREATE,
    old_value=None,
    new_value=phenopacket,
    changed_by="data_migration_system",
    change_reason=f"Initial import from Google Sheets (ReviewBy: {reviewer_email})"
)
```

**Resolution Required**:
1. **Update migration script** to create CREATE audit entries
2. **OR run backfill script** to create audit entries for existing data
3. **Include metadata**: Original ReviewBy email, import date, sheet row number

---

### 4. Raw SQL Bypasses ORM 🔴 CRITICAL

**Current State**:
Migration uses raw SQL text() instead of SQLAlchemy ORM.

**File**: `backend/migration/database/storage.py:60`
```python
query = text("""
    INSERT INTO phenopackets
    (id, phenopacket_id, version, phenopacket, subject_id, subject_sex, created_by, schema_version)
    VALUES (...)
""")
```

**Problem**:
New columns added by curation system migration are **NOT included** in the INSERT:
- `deleted_at` → Will be NULL (✅ correct for non-deleted)
- `deleted_by` → Will be NULL (✅ correct)
- `revision` → Will be NULL (❌ **BREAKS OPTIMISTIC LOCKING**)

**Impact**:
- ❌ Imported phenopackets will have `revision=NULL`
- ❌ First update will fail: `existing.revision += 1` raises TypeError
- ❌ Must manually set default value in migration

**Resolution Required**:

**Option A: Update raw SQL**
```python
query = text("""
    INSERT INTO phenopackets
    (id, phenopacket_id, version, phenopacket, subject_id, subject_sex,
     created_by, schema_version, revision)  -- Add revision
    VALUES (:id, :phenopacket_id, :version, :phenopacket, :subject_id, :subject_sex,
            :created_by, :schema_version, :revision)
    ON CONFLICT (phenopacket_id) DO UPDATE
    SET phenopacket = EXCLUDED.phenopacket,
        subject_id = EXCLUDED.subject_id,
        subject_sex = EXCLUDED.subject_sex,
        revision = EXCLUDED.revision,  -- Update revision too
        updated_at = CURRENT_TIMESTAMP
""")

# In execute parameters:
{
    ...
    "revision": 1,  # All imports start at revision 1
}
```

**Option B: Use ORM (RECOMMENDED)**
```python
from app.phenopackets.models import Phenopacket

async def store_phenopackets_orm(self, phenopackets: List[Dict]) -> int:
    async with self.session_maker() as session:
        for phenopacket in phenopackets:
            # Check if exists
            result = await session.execute(
                select(Phenopacket).where(
                    Phenopacket.phenopacket_id == phenopacket["id"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update
                existing.phenopacket = phenopacket
                existing.subject_id = phenopacket.get("subject", {}).get("id")
                existing.subject_sex = phenopacket.get("subject", {}).get("sex")
                # revision auto-increments in update endpoint
            else:
                # Create new
                new_phenopacket = Phenopacket(
                    phenopacket_id=phenopacket["id"],
                    version="2.0",
                    phenopacket=phenopacket,
                    subject_id=phenopacket.get("subject", {}).get("id"),
                    subject_sex=phenopacket.get("subject", {}).get("sex"),
                    created_by=get_reviewer_username(row),  # From ReviewerMapper
                    schema_version="2.0.0",
                    revision=1,  # Initial revision
                )
                session.add(new_phenopacket)

        await session.commit()
```

---

### 5. Generic created_by Value 🟡 MODERATE

**Current State**:
```python
"created_by": "direct_sheets_migration"
```

**Issue**:
All 864 phenopackets have the same `created_by` value, even though different reviewers curated them.

**Impact**:
- ⚠️ Cannot filter by curator
- ⚠️ Analytics on "who curated the most cases" impossible
- ⚠️ Authorization checks treat all as created by migration system

**Resolution**:
Use ReviewerMapper to set actual curator usernames (see Issue #2).

---

### 6. updated_by Never Set 🟡 MODERATE

**Current State**:
```python
# ON CONFLICT DO UPDATE doesn't set updated_by
SET phenopacket = EXCLUDED.phenopacket,
    subject_id = EXCLUDED.subject_id,
    subject_sex = EXCLUDED.subject_sex,
    updated_at = CURRENT_TIMESTAMP  -- Only timestamp, no user
```

**Issue**:
Re-running migration updates phenopackets but doesn't track WHO triggered the re-import.

**Impact**:
- ⚠️ Audit gap if migration is re-run
- ⚠️ Can't distinguish manual updates from re-imports

**Resolution**:
```python
SET phenopacket = EXCLUDED.phenopacket,
    subject_id = EXCLUDED.subject_id,
    subject_sex = EXCLUDED.subject_sex,
    updated_by = 'data_reimport_system',  -- Track re-import
    updated_at = CURRENT_TIMESTAMP
```

---

### 7. Schema Version Confusion 🟡 MODERATE

**Current State**:
Two fields that mean similar things:

```python
version: Mapped[str] = mapped_column(String(10), default="2.0")  # GA4GH schema version
schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")  # Also GA4GH version?
```

**Migration sets both**:
```python
"version": "2.0",
"schema_version": "2.0.0",
```

**Issue**:
- Redundant fields
- Confusing naming (version vs schema_version)
- Implementation plan overloads "version" with optimistic locking meaning

**Resolution**:
1. **Rename** `version` → `ga4gh_schema_version`
2. **Keep** `schema_version` for detailed version (2.0.0)
3. **Add** `revision` for optimistic locking
4. **OR**: Keep as-is, just add `revision` field

**Recommendation**: Add `revision` field, leave existing fields alone to avoid breaking changes.

---

## Compatibility Matrix

| Component | Current Migration | Curation Plan | Compatible? | Fix Required |
|-----------|------------------|---------------|-------------|--------------|
| **version field** | String "2.0" | Integer counter | ❌ NO | Add `revision` column |
| **created_by** | "direct_sheets_migration" | Actual username | ❌ NO | Use ReviewerMapper |
| **updated_by** | Not set | Username on update | ⚠️ PARTIAL | Set on re-import |
| **deleted_at** | Not in migration | NULL (default) | ✅ YES | Auto-handled |
| **deleted_by** | Not in migration | NULL (default) | ✅ YES | Auto-handled |
| **revision** | Not in migration | Integer, default 1 | ❌ NO | Add to INSERT |
| **Audit entries** | Not created | Required | ❌ NO | Create on import |
| **GA4GH structure** | Correct | Correct | ✅ YES | No change needed |
| **JSONB storage** | Correct | Correct | ✅ YES | No change needed |

---

## Required Changes

### A. Database Schema Changes

**File**: `backend/alembic/versions/002_add_revision_for_optimistic_locking.py`

**Action**: CREATE NEW MIGRATION

```python
"""Add revision column for optimistic locking

Revision ID: 002_add_revision
Revises: 001_soft_delete_audit
Create Date: 2025-11-16

This migration:
1. Adds 'revision' column for optimistic locking
2. Backfills existing phenopackets with revision=1
3. Keeps 'version' as GA4GH schema version (String)
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Add revision column
    op.add_column(
        'phenopackets',
        sa.Column('revision', sa.Integer, nullable=False, server_default='1')
    )

    # Backfill: All existing phenopackets start at revision 1
    op.execute('UPDATE phenopackets SET revision = 1 WHERE revision IS NULL')

    # Remove server_default (only needed for backfill)
    op.alter_column('phenopackets', 'revision', server_default=None)


def downgrade() -> None:
    op.drop_column('phenopackets', 'revision')
```

### B. Update Phenopacket Model

**File**: `backend/app/phenopackets/models.py`

**Action**: MODIFY

**Find** (around line 32):
```python
version: Mapped[str] = mapped_column(String(10), default="2.0")
```

**Add after**:
```python
revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
```

**Add docstring comment**:
```python
# Schema versioning
version: Mapped[str] = mapped_column(String(10), default="2.0")  # GA4GH Phenopackets schema version
schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")  # Detailed schema version

# Optimistic locking
revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Revision counter for concurrency control
```

### C. Update Migration Script

**File**: `backend/migration/database/storage.py`

**Action**: MODIFY

**Find** (line 41-94):
```python
async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]) -> int:
```

**Replace with**:
```python
async def store_phenopackets(
    self,
    phenopackets: List[Dict[str, Any]],
    reviewer_mapper=None  # Add reviewer mapper parameter
) -> int:
    """Store phenopackets in the database with proper attribution.

    Args:
        phenopackets: List of phenopacket dictionaries
        reviewer_mapper: ReviewerMapper instance for curator attribution

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

                # Get reviewer/curator attribution
                # phenopacket should have _metadata with original ReviewBy email
                reviewer_email = phenopacket.get("_metadata", {}).get("reviewer_email")
                if reviewer_email and reviewer_mapper:
                    created_by = reviewer_mapper.generate_username(reviewer_email)
                else:
                    created_by = "data_migration_system"

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
                        updated_by = 'data_reimport_system',
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
                        "created_by": created_by,  # Now uses actual reviewer
                        "schema_version": "2.0.0",
                        "revision": 1,  # All imports start at revision 1
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

### D. Update Implementation Plan

**File**: `plan/PHENOPACKET_CURATION_IMPLEMENTATION_GUIDE.md`

**Action**: GLOBAL FIND AND REPLACE

**Find**: `version` (when referring to optimistic locking)
**Replace**: `revision`

**Critical Updates**:

1. **Task 1.5: Update Pydantic Schemas**
```python
class PhenopacketUpdate(BaseModel):
    phenopacket: Dict[str, Any]
    updated_by: Optional[str] = None
    change_reason: Optional[str] = None
    expected_revision: int  # Changed from expected_version
```

2. **Task 2.1: Enhance UPDATE Endpoint**
```python
# Optimistic locking check
if existing.revision != phenopacket_data.expected_revision:  # Changed from version
    raise HTTPException(
        status_code=409,
        detail={
            "error": "Conflict",
            "message": (
                f"Phenopacket was modified by another user. "
                f"Expected revision {phenopacket_data.expected_revision}, "
                f"current revision {existing.revision}. "
                f"Please reload and try again."
            ),
            "current_revision": existing.revision,  # Changed from version
        }
    )

# ... after update ...
existing.revision += 1  # Increment revision counter
```

3. **Frontend API Calls**
```javascript
// Store revision when loading phenopacket
const phenopacket = await getPhenopacket(id);
const currentRevision = phenopacket.revision;  // Changed from version

// Send revision with update
await updatePhenopacket(id, {
  phenopacket: editedData,
  expected_revision: currentRevision,  // Changed from expected_version
  change_reason: reason
});
```

---

## Migration Backfill Script

To fix existing data, create this backfill script:

**File**: `backend/scripts/backfill_audit_and_attribution.py`

**Action**: CREATE NEW FILE

```python
#!/usr/bin/env python3
"""Backfill script to create audit entries and fix attribution for migrated data.

Run this ONCE after deploying the curation system to:
1. Create CREATE audit entries for all imported phenopackets
2. Update created_by to actual curator usernames (if possible)
3. Initialize revision=1 for all existing records

Usage:
    cd backend
    uv run python scripts/backfill_audit_and_attribution.py
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.phenopackets.models import Phenopacket, PhenopacketAudit
from app.utils.audit import AuditAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_audit_entries():
    """Create initial audit entries for all imported phenopackets."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        # Fetch all phenopackets without audit entries
        result = await session.execute(
            select(Phenopacket).where(
                Phenopacket.created_by == "direct_sheets_migration"
            )
        )
        phenopackets = result.scalars().all()

        logger.info(f"Found {len(phenopackets)} phenopackets from migration")

        for phenopacket in phenopackets:
            # Check if CREATE audit entry already exists
            audit_check = await session.execute(
                select(PhenopacketAudit).where(
                    PhenopacketAudit.phenopacket_id == phenopacket.phenopacket_id,
                    PhenopacketAudit.action == "CREATE"
                )
            )

            if audit_check.scalar_one_or_none():
                logger.debug(f"Audit entry already exists for {phenopacket.phenopacket_id}")
                continue

            # Create audit entry
            audit_entry = PhenopacketAudit(
                phenopacket_id=phenopacket.phenopacket_id,
                action=AuditAction.CREATE.value,
                old_value=None,
                new_value=phenopacket.phenopacket,
                changed_by="data_migration_system",
                changed_at=phenopacket.created_at,  # Use original creation time
                change_reason="Initial import from Google Sheets",
                change_patch=None,
                change_summary=f"Imported phenopacket with {len(phenopacket.phenopacket.get('phenotypicFeatures', []))} phenotypes"
            )

            session.add(audit_entry)

        await session.commit()
        logger.info(f"Created audit entries for {len(phenopackets)} phenopackets")

    await engine.dispose()


async def backfill_revision():
    """Set revision=1 for all existing phenopackets."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(
            update(Phenopacket).
            where(Phenopacket.revision == None).  # noqa: E711
            values(revision=1)
        )

        await session.commit()
        logger.info(f"Set revision=1 for {result.rowcount} phenopackets")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill_audit_entries())
    asyncio.run(backfill_revision())
    logger.info("Backfill complete!")
```

---

## Deployment Sequence

To ensure compatibility, follow this exact sequence:

### Step 1: Database Schema (Before Curation System)
```bash
cd backend

# Run migration to add deleted_at, deleted_by, change_patch, change_summary
uv run alembic upgrade head  # Runs 001_soft_delete_audit

# Run migration to add revision column
uv run alembic upgrade head  # Runs 002_add_revision
```

### Step 2: Update Migration Script
```bash
# Edit migration/database/storage.py
# Add revision=1 to INSERT statement
# Add reviewer_mapper parameter
```

### Step 3: Re-Import Data (Optional)
```bash
# If you want proper curator attribution
make phenopackets-migrate
```

### Step 4: Backfill (If Not Re-Importing)
```bash
# Create audit entries for existing data
uv run python scripts/backfill_audit_and_attribution.py
```

### Step 5: Deploy Curation System
```bash
# Deploy backend with updated endpoints
# Deploy frontend with Edit/Delete UI
```

### Step 6: Verify
```bash
# Check that revision is set
psql $DATABASE_URL -c "SELECT phenopacket_id, revision FROM phenopackets LIMIT 5;"

# Check audit entries exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM phenopacket_audit WHERE action='CREATE';"

# Test optimistic locking
# (Open same phenopacket in two tabs, edit both, save second → should get 409 Conflict)
```

---

## Testing Strategy

### Test 1: Imported Data Can Be Edited
```python
async def test_edit_imported_phenopacket(client, auth_headers):
    # Get an imported phenopacket
    response = await client.get("/api/v2/phenopackets/HNF1B-001")
    phenopacket = response.json()

    # Should have revision=1 from backfill
    assert phenopacket["revision"] == 1

    # Edit it
    phenopacket["phenopacket"]["subject"]["sex"] = "MALE"

    update_response = await client.put(
        "/api/v2/phenopackets/HNF1B-001",
        json={
            "phenopacket": phenopacket["phenopacket"],
            "expected_revision": 1,
            "change_reason": "Updated sex"
        }
    )

    # Should succeed
    assert update_response.status_code == 200
    assert update_response.json()["revision"] == 2
```

### Test 2: Audit History Includes Import
```python
async def test_imported_phenopacket_has_create_audit(client, auth_headers):
    response = await client.get("/api/v2/phenopackets/HNF1B-001/audit")
    audit_history = response.json()

    # Should have CREATE entry from backfill
    create_entry = [e for e in audit_history if e["action"] == "CREATE"]
    assert len(create_entry) == 1
    assert create_entry[0]["changed_by"] == "data_migration_system"
    assert "Initial import" in create_entry[0]["change_reason"]
```

### Test 3: Reviewer Attribution
```python
async def test_created_by_has_reviewer_username(db):
    # After re-import with ReviewerMapper
    result = await db.execute(
        select(Phenopacket).where(
            Phenopacket.created_by != "direct_sheets_migration"
        )
    )
    phenopackets = result.scalars().all()

    # Should have actual curator usernames
    assert len(phenopackets) > 0
    for pp in phenopackets:
        assert pp.created_by in ["john_doe", "jane_smith", "data_migration_system"]
        assert pp.created_by != "direct_sheets_migration"
```

---

## Recommendations

### Immediate Actions (Before Deploying Curation System)

1. ✅ **Add `revision` column** via migration 002
2. ✅ **Update migration script** to set revision=1
3. ✅ **Run backfill script** to create audit entries
4. ✅ **Update implementation plan** to use `revision` instead of `version`

### Future Improvements

1. **Re-import with reviewer attribution**
   - Update migration to use ReviewerMapper
   - Map ReviewBy email → created_by username
   - Run full re-import to get proper attribution

2. **Improve migration observability**
   - Add logging for each phenopacket stored
   - Track import metadata (date, source sheet row, reviewer email)

3. **Add migration validation**
   - Check that all phenopackets have revision >= 1
   - Verify audit CREATE entries exist
   - Validate created_by is not NULL

---

## Risk Assessment

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|------------|
| Optimistic locking breaks on imported data | HIGH | HIGH (100%) | Add `revision` column, backfill with 1 |
| Curator attribution lost | MEDIUM | HIGH (100%) | Use ReviewerMapper in migration OR backfill later |
| No audit trail for imports | LOW | HIGH (100%) | Run backfill script |
| Version field confusion | LOW | MEDIUM | Add clear comments, rename in future |
| Re-import overwrites updates | MEDIUM | LOW | Use ON CONFLICT properly, check revision |

---

## Conclusion

The existing migration script is **NOT compatible** with the curation system as currently designed. However, all issues are **fixable** with the changes outlined in this document.

**Critical Path**:
1. Add `revision` column (1 hour)
2. Update migration script (2 hours)
3. Run backfill script (30 minutes)
4. Update implementation plan (1 hour)

**Total effort**: ~4.5 hours

**After these changes**, the curation system will be **fully compatible** with imported data.

---

**Reviewed By**: _________________________
**Approved**: ☐ Yes ☐ No ☐ Needs Revision
**Date**: _________________________

---

**END OF COMPATIBILITY ANALYSIS**
