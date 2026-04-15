# HNF1B Database - Data Curation System Implementation Plan (Revised)

**Version:** 2.0 (Code Review Approved)
**Date:** November 14, 2025
**Milestone:** [Data entry (CRUD)](https://github.com/berntpopp/hnf1b-db/milestone/5)
**Reviewers:** Senior Full-Stack Developer & Code Maintainer

---

## Executive Summary

### Current Status: **85% Complete**

**Excellent News:** After code review, we discovered the infrastructure is **more complete** than initially assessed:

**What Already Exists:**
- ✅ Full CRUD API endpoints (Create, Read, Update, Delete)
- ✅ JWT authentication with RBAC (Admin, Curator, Viewer)
- ✅ **UUID foreign key for `reviewed_by` in schema** (no new fields needed!)
- ✅ User management with proper relationships
- ✅ Service layer architecture (`app/publications/service.py`)
- ✅ GA4GH Phenopackets v2 validation
- ✅ VEP variant annotation
- ✅ Only 12 well-organized migrations (not 20+)

**What's Actually Missing:**
- ⚠️ Reviewer data import using **existing** `reviewed_by` UUID FK
- ⚠️ Permission enforcement (1-line fix per endpoint)
- ⚠️ Frontend UI with composables + VeeValidate
- ⚠️ Publication submission workflow

**Key Architectural Decisions (Based on Code Review):**
1. **Use existing `reviewed_by: UUID` FK** - No schema changes needed
2. **Follow service layer pattern** - Like `app/publications/service.py`
3. **Create base `SheetMapper` class** - DRY principle
4. **Use Vue composables** - Not 600-line components
5. **Use VeeValidate** - Not manual validation
6. **Dependency injection** - For all services

**Estimated Total Effort:** 2 weeks (reduced from 3 weeks)

---

## Table of Contents

1. [Milestone 5 Issues Analysis](#milestone-5-issues-analysis)
2. [Architecture Overview](#architecture-overview)
3. [Phase 0: Data Discovery (CRITICAL)](#phase-0-data-discovery)
4. [Phase 1: Backend Implementation](#phase-1-backend-implementation)
5. [Phase 2: Frontend Implementation](#phase-2-frontend-implementation)
6. [Phase 3: Testing & Polish](#phase-3-testing--polish)
7. [Implementation Checklist](#implementation-checklist)
8. [Success Metrics](#success-metrics)

---

## Milestone 5 Issues Analysis

**Milestone:** Data entry (CRUD) - Due: November 14, 2025
**Status:** 3 open issues, 0 closed

### Issue #12: CRUD Operations for Logged In Users

**Status:** ✅ **Backend 95% Complete**

**What Exists:**
```python
# backend/app/phenopackets/routers/crud.py
@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),  # ← ANY authenticated user!
):
    # Full CRUD operations already implemented
```

**Quick Fix Needed (5 minutes per endpoint):**
```python
from app.auth import require_curator

# Change 3 lines:
current_user=Depends(require_curator),  # ← Only curator/admin
```

**Remaining Work:**
- Fix permission enforcement (15 min)
- Frontend UI components (Phase 2)

---

### Issue #101: Import Users from Google Sheets

**Status:** ❌ **Needs Redesign Based on Existing Schema**

**CRITICAL DISCOVERY:** The schema **already has** `reviewed_by: UUID` FK!

```python
# backend/app/schemas.py (EXISTING)
class ReportCreate(BaseSchema):
    reviewed_by: Optional[uuid.UUID] = None  # ← Already there!
    publication_ref: Optional[uuid.UUID] = None

class ReportResponse(ReportBase):
    reviewed_by: Optional[uuid.UUID] = None
    reviewer: Optional["UserResponse"] = None  # ← Relationship!
    publication: Optional["PublicationResponse"] = None
```

**Original Problem Statement:**
- Reviewers sheet (GID: 1321366018) configured but never loaded
- `ReviewBy` column exists in Individuals sheet
- Currently shows: `"updatedBy": "Publication: Smith2021"` ❌
- Should show: Actual reviewer from users table ✅

**Correct Approach:**
1. **Verify** ReviewBy column maps to Reviewers sheet (Phase 0)
2. **Import** reviewers as users (UUID primary keys)
3. **Link** via existing `reviewed_by` UUID FK
4. **No schema changes needed!**

---

### Issue #103: Fix Duplicate Protein Notation

**Status:** ⚠️ **Ready to Fix**

**Bug:** Variant labels show `"HNF1B:c.406C>T (p.Gln136Ter) (p.Gln136Ter)"`

**Root Cause:**
```python
# backend/migration/vrs/vrs_builder.py
# Line 342-344: First addition ✅
label = f"HNF1B:{c_dot}"
if p_dot:
    label += f" ({p_dot})"

# Line 394: Second addition ❌
variant_descriptor["label"] += f" ({p_dot})"  # DUPLICATE!
```

**Fix:**
```python
# Option 1: Remove line 394
# Option 2: Add conditional
if p_dot and f"({p_dot})" not in variant_descriptor["label"]:
    variant_descriptor["label"] += f" ({p_dot})"
```

**Testing:**
```bash
make db-reset
make phenopackets-migrate-test
curl http://localhost:8000/api/v2/phenopackets/aggregate/all-variants \
  | jq '.[].label'  # Should not have duplicates
```

---

## Architecture Overview

### Backend Architecture (Following Existing Patterns)

**Key Principle:** Follow `app/publications/service.py` pattern for **all** new features.

**Service Layer Pattern:**
```
Router (HTTP) → Service (Business Logic) → Database
     ↓                    ↓                     ↓
  FastAPI          Dependency Injection    SQLAlchemy
```

**Example (Existing Code):**
```python
# app/publications/service.py ✅ GOOD EXAMPLE
async def get_publication_metadata(
    pmid: str,
    db: AsyncSession,
    fetched_by: Optional[str] = "system"
) -> dict:
    """Service handles ALL business logic:
    1. Validate PMID (security)
    2. Check cache
    3. Fetch from API
    4. Store in cache
    """
```

**Anti-Pattern (DO NOT DO):**
```python
# ❌ Business logic in router
@router.post("/submit")
async def submit_publication(...):
    metadata = await fetch_pubmed(pmid)  # ← Should be in service!
    db.add(Publication(...))  # ← Should be in service!
```

**Correct Pattern:**
```python
# ✅ Router delegates to service
@router.post("/submit")
async def submit_publication(
    pmid: str,
    service: PublicationService = Depends(get_publication_service),
    current_user: User = Depends(require_curator),
):
    return await service.submit_for_review(pmid, current_user.id)
```

---

### Frontend Architecture (Vue 3 Composables)

**Key Principle:** Use **composables** for reusable logic, **VeeValidate** for validation.

**Composables Pattern:**
```javascript
// composables/usePhenopacketForm.js
export function usePhenopacketForm() {
  const phenopacket = ref({})
  const loading = ref(false)
  const error = ref(null)

  async function submit() {
    loading.value = true
    try {
      await createPhenopacket(phenopacket.value)
    } catch (e) {
      error.value = e
    } finally {
      loading.value = false
    }
  }

  return { phenopacket, loading, error, submit }
}

// Component uses composable
const { phenopacket, loading, submit } = usePhenopacketForm()
```

**VeeValidate Pattern:**
```javascript
// schemas/phenopacketSchema.js
import * as yup from 'yup'

export const phenopacketSchema = yup.object({
  subject: yup.object({
    id: yup.string().required('Subject ID is required')
  }),
  phenotypicFeatures: yup.array().min(1, 'At least one phenotype required')
})

// Component uses VeeValidate
import { useForm } from 'vee-validate'

const { errors, validate, handleSubmit } = useForm({
  validationSchema: phenopacketSchema
})
```

---

## Phase 0: Data Discovery (CRITICAL - DO NOT SKIP)

**Duration:** 0.5 days
**Priority:** **MUST DO FIRST**

### Why This Phase Exists

The code review revealed we're making **assumptions** about Google Sheets structure without verification. We must confirm:
1. What data exists in `ReviewBy` column?
2. How does it map to Reviewers sheet?
3. Does the join strategy work?

### Task 0.1: Create Data Discovery Script

**File:** `backend/scripts/verify_sheets_structure.py` (NEW)

```python
#!/usr/bin/env python3
"""Verify Google Sheets structure before implementing reviewer import.

This script validates assumptions about ReviewBy column and Reviewers sheet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from migration.data_sources.google_sheets import GoogleSheetsLoader

SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
GID_CONFIG = {
    "individuals": "0",
    "reviewers": "1321366018",
}


def main():
    print("=" * 80)
    print("Google Sheets Data Discovery")
    print("=" * 80)
    print()

    loader = GoogleSheetsLoader(SPREADSHEET_ID, GID_CONFIG)

    # Load sheets
    print("📥 Loading sheets...")
    individuals_df = loader.load_sheet("individuals")
    reviewers_df = loader.load_sheet("reviewers")

    if individuals_df is None:
        print("❌ Failed to load Individuals sheet")
        return

    if reviewers_df is None:
        print("❌ Failed to load Reviewers sheet")
        return

    print(f"✅ Individuals: {len(individuals_df)} rows")
    print(f"✅ Reviewers: {len(reviewers_df)} rows")
    print()

    # Analyze ReviewBy column
    print("=" * 80)
    print("ReviewBy Column Analysis")
    print("=" * 80)

    if "ReviewBy" not in individuals_df.columns:
        print("❌ ReviewBy column not found!")
        print(f"Available columns: {individuals_df.columns.tolist()}")
        return

    print(f"Total rows: {len(individuals_df)}")
    print(f"Non-null ReviewBy: {individuals_df['ReviewBy'].notna().sum()}")
    print(f"Null ReviewBy: {individuals_df['ReviewBy'].isna().sum()}")
    print()

    print("Top 10 ReviewBy values:")
    print(individuals_df["ReviewBy"].value_counts().head(10))
    print()

    print("Sample ReviewBy values:")
    print(individuals_df[["individual_id", "ReviewBy"]].head(10))
    print()

    # Analyze Reviewers sheet
    print("=" * 80)
    print("Reviewers Sheet Analysis")
    print("=" * 80)
    print(f"Columns: {reviewers_df.columns.tolist()}")
    print()
    print("Sample reviewers:")
    print(reviewers_df.head(10))
    print()

    # Check join feasibility
    print("=" * 80)
    print("Join Feasibility Check")
    print("=" * 80)

    # Try to identify key column in reviewers
    possible_keys = ["reviewer_id", "id", "email", "name", "username"]
    found_key = None

    for key in possible_keys:
        if key in reviewers_df.columns:
            found_key = key
            print(f"✅ Found potential key column: {key}")
            break

    if found_key is None:
        print("⚠️  No obvious key column found")
        print(f"Reviewers columns: {reviewers_df.columns.tolist()}")
    else:
        # Check if ReviewBy values exist in reviewers
        reviewer_values = set(reviewers_df[found_key].dropna().astype(str))
        reviewby_values = set(individuals_df["ReviewBy"].dropna().astype(str))

        matches = reviewby_values.intersection(reviewer_values)
        print(f"ReviewBy unique values: {len(reviewby_values)}")
        print(f"Reviewers {found_key} values: {len(reviewer_values)}")
        print(f"Matching values: {len(matches)}")
        print(f"Match rate: {len(matches) / len(reviewby_values) * 100:.1f}%")

        if len(matches) < len(reviewby_values) * 0.8:
            print("⚠️  Low match rate - review join strategy!")
            print(f"Unmatched ReviewBy values: {reviewby_values - matches}")

    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    if found_key and len(matches) / len(reviewby_values) >= 0.8:
        print(f"✅ Join strategy: ReviewBy → Reviewers.{found_key}")
        print(f"✅ Expected matches: {len(matches)}/{len(reviewby_values)}")
    else:
        print("⚠️  Manual review required:")
        print("   1. Check ReviewBy format")
        print("   2. Verify Reviewers key column")
        print("   3. Design custom mapping logic")

    print()


if __name__ == "__main__":
    main()
```

### Task 0.2: Run Discovery & Document Results

```bash
cd backend
python scripts/verify_sheets_structure.py > docs/sheets_structure_analysis.txt

# Review results:
cat docs/sheets_structure_analysis.txt

# Document findings in IMPLEMENTATION_LOG.md
```

### Task 0.3: Decision Point

**Based on discovery results, choose implementation strategy:**

**Strategy A: Direct Join (if >80% match)**
```python
# ReviewBy values directly match Reviewers.reviewer_id
reviewer_id = row.get("ReviewBy")
reviewer = reviewers_map[reviewer_id]
```

**Strategy B: Email-based Join (if ReviewBy contains emails)**
```python
# ReviewBy contains emails
reviewer_email = row.get("ReviewBy")
reviewer = reviewers_by_email[reviewer_email]
```

**Strategy C: Custom Mapping (if complex)**
```python
# Build custom mapping table
REVIEWBY_TO_REVIEWER_ID = {
    "JS": "reviewer_001",  # Manual mapping
    "Dr. Smith": "reviewer_001",
}
```

**DO NOT PROCEED to Phase 1 until this is resolved!**

---

## Phase 1: Backend Implementation

**Duration:** 5 days
**Prerequisites:** Phase 0 complete, join strategy confirmed

### Day 1: Quick Wins & Permission Fix

#### Task 1.1: Fix Issue #103 (Duplicate Protein Notation)

**File:** `backend/migration/vrs/vrs_builder.py` (MODIFY)

```python
# Line 394: Add conditional check
if p_dot and f"({p_dot})" not in variant_descriptor["label"]:
    variant_descriptor["label"] += f" ({p_dot})"
```

**Test:**
```bash
make db-reset
make phenopackets-migrate-test
curl http://localhost:8000/api/v2/phenopackets/aggregate/all-variants?limit=5 \
  | jq '.[].label'
# Verify no duplicate (p.Gln136Ter) (p.Gln136Ter)
```

#### Task 1.2: Enforce Curator Permissions (Issue #12)

**File:** `backend/app/phenopackets/routers/crud.py` (MODIFY)

```python
# Add import
from app.auth.dependencies import require_curator, require_admin

# Line 416: Create endpoint
@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),  # ← Changed!
):
    # Existing code...

# Line 469: Update endpoint
@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),  # ← Changed!
):
    # Existing code...

# Line 509: Delete endpoint (admin only?)
@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),  # ← Admin only for delete?
):
    # Existing code...
```

**Test:**
```bash
# Test as viewer (should fail)
curl -X POST http://localhost:8000/api/v2/phenopackets/ \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -d '{...}'
# Expected: 403 Forbidden

# Test as curator (should work)
curl -X POST http://localhost:8000/api/v2/phenopackets/ \
  -H "Authorization: Bearer $CURATOR_TOKEN" \
  -d '{...}'
# Expected: 201 Created
```

---

### Day 2-3: Base Mapper Class & Reviewer Integration

#### Task 2.1: Create Abstract Base Mapper (DRY)

**File:** `backend/migration/phenopackets/base_mapper.py` (NEW)

```python
"""Abstract base class for Google Sheets data mappers.

This module provides a reusable base class following the DRY principle.
All sheet mappers (Publication, Reviewer, etc.) should inherit from this.

Architecture:
- Abstract base class defines common interface
- Subclasses implement specific mapping logic
- Shared validation and error handling
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class SheetMapper(ABC):
    """Abstract base class for mapping Google Sheets data.

    Provides common functionality:
    - Empty DataFrame validation
    - Logging
    - Error handling
    - Consistent interface

    Subclasses must implement:
    - _build_map(): Specific mapping logic
    - _get_key_column(): Key column name for lookups
    """

    def __init__(self, df: Optional[pd.DataFrame] = None):
        """Initialize mapper with optional DataFrame.

        Args:
            df: DataFrame from Google Sheets
        """
        self.data_map: Dict[str, Any] = {}

        if df is not None and not df.empty:
            self._validate_columns(df)
            self._build_map(df)
            logger.info(
                f"{self.__class__.__name__} initialized with "
                f"{len(self.data_map)} entries"
            )
        else:
            logger.warning(f"{self.__class__.__name__} initialized with empty data")

    @abstractmethod
    def _build_map(self, df: pd.DataFrame) -> None:
        """Build internal mapping from DataFrame.

        Subclasses implement specific mapping logic.

        Args:
            df: Validated DataFrame
        """
        pass

    @abstractmethod
    def _get_required_columns(self) -> list[str]:
        """Return list of required column names.

        Returns:
            List of column names that must exist in DataFrame
        """
        pass

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Validate DataFrame has required columns.

        Args:
            df: DataFrame to validate

        Raises:
            ValueError: If required columns are missing
        """
        required = set(self._get_required_columns())
        actual = set(df.columns)
        missing = required - actual

        if missing:
            raise ValueError(
                f"{self.__class__.__name__}: Missing required columns: {missing}"
            )

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get mapped data by key.

        Args:
            key: Lookup key

        Returns:
            Mapped data dictionary or None if not found
        """
        return self.data_map.get(key)

    def get_all(self) -> list[Dict[str, Any]]:
        """Get all mapped data.

        Returns:
            List of all mapped data dictionaries
        """
        return list(self.data_map.values())

    def __len__(self) -> int:
        """Return number of mapped entries."""
        return len(self.data_map)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in map."""
        return key in self.data_map
```

#### Task 2.2: Refactor PublicationMapper to Use Base

**File:** `backend/migration/phenopackets/publication_mapper.py` (MODIFY)

```python
"""Publication reference mapping for phenopackets."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from .base_mapper import SheetMapper

logger = logging.getLogger(__name__)


class PublicationMapper(SheetMapper):
    """Maps publication IDs to external references.

    Now inherits from SheetMapper for DRY compliance.
    """

    def _get_required_columns(self) -> list[str]:
        """Required columns for publication mapping."""
        return ["publication_id", "publication_alias"]

    def _build_map(self, df: pd.DataFrame) -> None:
        """Build publication map from DataFrame.

        Maps both publication_id and publication_alias to same record.

        Args:
            df: Publications DataFrame
        """
        for _, pub_row in df.iterrows():
            pub_id = pub_row.get("publication_id")
            pub_alias = pub_row.get("publication_alias")

            # Map by both ID and alias
            if pub_id:
                self.data_map[str(pub_id)] = pub_row
            if pub_alias:
                self.data_map[str(pub_alias)] = pub_row

    def create_publication_reference(
        self, publication_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create an ExternalReference for a publication.

        Args:
            publication_id: Publication identifier

        Returns:
            ExternalReference dict with PMID/DOI or None
        """
        pub_data = self.get(publication_id)
        if not pub_data:
            return None

        # Build ExternalReference (existing logic preserved)
        reference = {
            "id": f"PMID:{pub_data.get('PMID')}" if pub_data.get('PMID') else None,
            "reference": pub_data.get('publication_id'),
            "description": pub_data.get('title', 'Unknown publication'),
        }

        return reference
```

#### Task 2.3: Create ReviewerMapper (Following Base Pattern)

**File:** `backend/migration/phenopackets/reviewer_mapper.py` (NEW)

```python
"""Reviewer mapping for phenopackets.

Maps reviewer identifiers from Google Sheets to user UUIDs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

import pandas as pd

from .base_mapper import SheetMapper

logger = logging.getLogger(__name__)


class ReviewerMapper(SheetMapper):
    """Maps reviewer identifiers to user information.

    This mapper handles the join between:
    - Individuals.ReviewBy column
    - Reviewers sheet data
    - users table (via username/email)

    The mapping strategy depends on Phase 0 data discovery results.
    """

    def __init__(
        self,
        reviewers_df: Optional[pd.DataFrame] = None,
        join_column: str = "reviewer_id"  # From Phase 0 discovery
    ):
        """Initialize reviewer mapper.

        Args:
            reviewers_df: Reviewers sheet DataFrame
            join_column: Column name to join on (from Phase 0 discovery)
        """
        self.join_column = join_column
        super().__init__(reviewers_df)

    def _get_required_columns(self) -> list[str]:
        """Required columns for reviewer mapping.

        Note: Actual columns depend on Phase 0 discovery.
        Adjust based on sheets_structure_analysis.txt results.
        """
        return [
            self.join_column,  # Key for joining (e.g., "reviewer_id")
            "full_name",       # Display name
            "email",           # For user account
        ]

    def _build_map(self, df: pd.DataFrame) -> None:
        """Build reviewer map from DataFrame.

        Maps reviewer identifier to user account information.

        Args:
            df: Reviewers DataFrame
        """
        for _, row in df.iterrows():
            reviewer_key = str(row.get(self.join_column, "")).strip()
            if not reviewer_key:
                continue

            self.data_map[reviewer_key] = {
                "reviewer_key": reviewer_key,
                "full_name": str(row.get("full_name", "")).strip(),
                "email": str(row.get("email", "")).strip(),
                "affiliation": str(row.get("affiliation", "")).strip() or None,
                "orcid": str(row.get("orcid", "")).strip() or None,
                # Will be populated after user creation:
                "user_id": None,  # UUID from users table
            }

    def set_user_id(self, reviewer_key: str, user_id: UUID) -> None:
        """Associate reviewer with created user UUID.

        Call this after creating user in database.

        Args:
            reviewer_key: Reviewer identifier
            user_id: UUID from users table
        """
        if reviewer_key in self.data_map:
            self.data_map[reviewer_key]["user_id"] = user_id

    def get_user_id(self, reviewer_key: str) -> Optional[UUID]:
        """Get user UUID for reviewer.

        Args:
            reviewer_key: Reviewer identifier (from ReviewBy column)

        Returns:
            User UUID or None if not found
        """
        reviewer = self.get(reviewer_key)
        return reviewer["user_id"] if reviewer else None

    def get_username(self, reviewer_key: str) -> Optional[str]:
        """Generate username from reviewer data.

        Strategy:
        1. Use email prefix (john.doe@uni.edu → john.doe)
        2. Fallback to lowercase full_name with underscores

        Args:
            reviewer_key: Reviewer identifier

        Returns:
            Generated username or None
        """
        reviewer = self.get(reviewer_key)
        if not reviewer:
            return None

        email = reviewer.get("email", "")
        if "@" in email:
            return email.split("@")[0].lower()

        full_name = reviewer.get("full_name", "")
        return full_name.lower().replace(" ", "_") if full_name else None
```

#### Task 2.4: User Import Service (Service Layer Pattern)

**File:** `backend/app/users/import_service.py` (NEW)

```python
"""User import service for creating curator accounts from Google Sheets.

Follows service layer architecture pattern from app/publications/service.py.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.models.user import User

logger = logging.getLogger(__name__)


class UserImportService:
    """Service for importing users from Google Sheets data.

    Business logic for:
    - Creating curator accounts
    - Handling duplicates
    - Generating default passwords
    """

    DEFAULT_PASSWORD = "ChangeMe123!"  # User must change on first login

    async def create_curator_from_reviewer(
        self,
        db: AsyncSession,
        username: str,
        email: str,
        full_name: str,
        orcid: Optional[str] = None,
    ) -> User:
        """Create or update curator user from reviewer data.

        Args:
            db: Database session
            username: Generated username
            email: Reviewer email
            full_name: Reviewer full name
            orcid: ORCID identifier (optional)

        Returns:
            User: Created or updated user

        Raises:
            ValueError: If username/email validation fails
        """
        # Validate inputs
        if not username or not email or not full_name:
            raise ValueError("Username, email, and full_name are required")

        # Check if user exists
        result = await db.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"User {username} already exists, updating...")
            # Update existing user
            existing_user.email = email
            existing_user.full_name = full_name
            existing_user.role = "curator"
            existing_user.is_active = True
            if orcid:
                # Assuming User model has orcid field (may need migration)
                existing_user.orcid = orcid

            await db.flush()
            return existing_user

        else:
            logger.info(f"Creating new curator user: {username}")
            # Create new user
            new_user = User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(self.DEFAULT_PASSWORD),
                role="curator",
                is_active=True,
            )

            db.add(new_user)
            await db.flush()  # Get user.id without commit
            logger.info(f"Created user {username} with ID {new_user.id}")
            return new_user

    async def import_all_reviewers(
        self,
        db: AsyncSession,
        reviewer_mapper: "ReviewerMapper",
    ) -> dict[str, UUID]:
        """Import all reviewers as curator users.

        Args:
            db: Database session
            reviewer_mapper: ReviewerMapper with loaded data

        Returns:
            dict: Mapping of reviewer_key → user_id (UUID)
        """
        user_map = {}
        created = 0
        updated = 0
        failed = 0

        for reviewer_key, reviewer_data in reviewer_mapper.data_map.items():
            try:
                username = reviewer_mapper.get_username(reviewer_key)
                if not username:
                    logger.warning(f"Could not generate username for {reviewer_key}")
                    failed += 1
                    continue

                user = await self.create_curator_from_reviewer(
                    db=db,
                    username=username,
                    email=reviewer_data["email"],
                    full_name=reviewer_data["full_name"],
                    orcid=reviewer_data.get("orcid"),
                )

                user_map[reviewer_key] = user.id
                reviewer_mapper.set_user_id(reviewer_key, user.id)

                if user.created_at == user.updated_at:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error(f"Failed to import reviewer {reviewer_key}: {e}")
                failed += 1

        await db.commit()

        logger.info(
            f"User import complete: {created} created, {updated} updated, {failed} failed"
        )

        return user_map
```

---

### Day 4: Migration Integration

#### Task 4.1: Update Migration Script to Load Reviewers

**File:** `backend/migration/direct_sheets_to_phenopackets.py` (MODIFY)

```python
# Add imports
from migration.phenopackets.reviewer_mapper import ReviewerMapper
from app.users.import_service import UserImportService

class DirectSheetsToPhenopackets:
    def __init__(self, target_db_url: str, ontology_mapper: Optional[OntologyMapper] = None):
        # Existing code...
        self.publication_mapper: Optional[PublicationMapper] = None
        self.reviewer_mapper: Optional[ReviewerMapper] = None  # ← ADD
        self.phenopacket_builder: Optional[PhenopacketBuilder] = None

        # Data storage
        self.individuals_df: Optional[pd.DataFrame] = None
        self.phenotypes_df: Optional[pd.DataFrame] = None
        self.publications_df: Optional[pd.DataFrame] = None
        self.reviewers_df: Optional[pd.DataFrame] = None  # ← ADD

    async def load_data(self) -> None:
        """Load all data from Google Sheets."""
        # Existing code for individuals, phenotypes, publications...

        # Load reviewers (ADD THIS BLOCK)
        self.reviewers_df = self.sheets_loader.load_sheet("reviewers")
        if self.reviewers_df is not None:
            # Use join_column from Phase 0 discovery
            join_column = "reviewer_id"  # ← Adjust based on Phase 0 results
            self.reviewer_mapper = ReviewerMapper(
                self.reviewers_df,
                join_column=join_column
            )
            logger.info(f"Loaded {len(self.reviewer_mapper)} reviewers")
        else:
            logger.warning("No reviewer data loaded")

        # Initialize phenopacket builder
        self.phenopacket_builder = PhenopacketBuilder(
            self.ontology_mapper,
            self.publication_mapper,
            self.reviewer_mapper  # ← ADD PARAMETER
        )

    async def import_reviewers_as_users(self) -> None:
        """Import reviewers as curator users in database.

        Creates/updates users table with curator accounts.
        """
        if not self.reviewer_mapper:
            logger.warning("No reviewer mapper - skipping user import")
            return

        logger.info("Importing reviewers as curator users...")

        async with self.storage.get_session() as db:
            service = UserImportService()
            user_map = await service.import_all_reviewers(db, self.reviewer_mapper)

            logger.info(f"Imported {len(user_map)} reviewers as users")

    async def migrate(self, test_mode: bool = False) -> None:
        """Execute migration.

        Args:
            test_mode: If True, limit to 20 individuals
        """
        await self.load_data()

        # NEW: Import reviewers as users FIRST
        await self.import_reviewers_as_users()

        # Existing migration code...
        # Build and store phenopackets
        # (now with reviewer attribution via UUID FK)
```

#### Task 4.2: Update PhenopacketBuilder to Use Reviewer UUIDs

**File:** `backend/migration/phenopackets/builder_simple.py` (MODIFY)

```python
class PhenopacketBuilder:
    def __init__(
        self,
        ontology_mapper: OntologyMapper,
        publication_mapper: Optional[PublicationMapper] = None,
        reviewer_mapper: Optional[ReviewerMapper] = None,  # ← ADD
    ):
        self.ontology_mapper = ontology_mapper
        self.publication_mapper = publication_mapper
        self.reviewer_mapper = reviewer_mapper  # ← STORE

    def _build_metadata(self, rows: pd.DataFrame) -> Dict[str, Any]:
        """Build metadata section with reviewer attribution.

        Uses existing reviewed_by UUID FK field in schema.
        """
        # Existing created/createdBy code...

        # Update history with REVIEWER UUID (not publication name!)
        if len(rows) > 1:
            updates = []
            for _, row in rows.iterrows():
                timestamp = self.age_parser.parse_review_date(row.get("ReviewDate"))
                if not timestamp:
                    continue

                # NEW: Get reviewer UUID from ReviewBy column
                reviewer_key = row.get("ReviewBy")
                reviewer_user_id = None

                if reviewer_key and self.reviewer_mapper:
                    reviewer_user_id = self.reviewer_mapper.get_user_id(reviewer_key)

                # Build update entry
                update_entry = {
                    "timestamp": timestamp,
                    "comment": f"Data from {row.get('Publication', 'Unknown source')}",
                }

                # Use reviewer UUID if available
                if reviewer_user_id:
                    # Store UUID in phenopacket metadata
                    # Will be used to populate reviewed_by FK in database
                    update_entry["reviewed_by_user_id"] = str(reviewer_user_id)
                    # Also include name for display (can join with users table)
                    reviewer_data = self.reviewer_mapper.get(reviewer_key)
                    if reviewer_data:
                        update_entry["updatedBy"] = reviewer_data["full_name"]
                else:
                    # Fallback to publication
                    update_entry["updatedBy"] = f"Publication: {row.get('Publication', 'Unknown')}"

                updates.append(update_entry)

            if updates:
                metadata["updates"] = updates

        return metadata
```

---

### Day 5: Publication Submission Service

#### Task 5.1: Create Publication Submission Service

**File:** `backend/app/publications/submission_service.py` (NEW)

```python
"""Publication submission service for curator workflow.

Handles submission, review, and approval of new publications.
Follows service layer pattern.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.publications.service import (
    get_publication_metadata,
    PubMedError,
    PubMedNotFoundError,
)

logger = logging.getLogger(__name__)


class PublicationStatus(str, Enum):
    """Publication submission status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationSubmissionService:
    """Service for handling publication submissions.

    Business logic:
    - Submit publication for review
    - Admin approval/rejection workflow
    - Status tracking
    """

    async def submit_for_review(
        self,
        pmid: str,
        db: AsyncSession,
        submitted_by_user_id: str,
    ) -> dict:
        """Submit a publication for curator review.

        Flow:
        1. Fetch metadata from PubMed (uses existing service)
        2. Create publication_metadata entry with status=pending
        3. Return submission details

        Args:
            pmid: PubMed ID (format: PMID:12345678 or 12345678)
            db: Database session
            submitted_by_user_id: UUID of submitting curator

        Returns:
            dict: Submission details with status

        Raises:
            ValueError: If publication already exists
            PubMedNotFoundError: If PMID not found
            PubMedError: If PubMed API fails
        """
        # Use existing PubMed service to fetch metadata
        # This handles validation, caching, rate limiting
        try:
            metadata = await get_publication_metadata(
                pmid=pmid,
                db=db,
                fetched_by=submitted_by_user_id,
            )
        except PubMedNotFoundError:
            raise ValueError(f"Publication {pmid} not found in PubMed")
        except PubMedError as e:
            raise ValueError(f"Failed to fetch publication: {e}")

        # Check if already submitted
        # (This would query publication_metadata table)
        # For now, get_publication_metadata handles caching

        # Update metadata status to pending
        # (Requires migration to add status column)
        metadata["status"] = PublicationStatus.PENDING.value
        metadata["submitted_by"] = submitted_by_user_id
        metadata["submitted_at"] = datetime.now(timezone.utc)

        logger.info(
            f"Publication {pmid} submitted for review by {submitted_by_user_id}"
        )

        return {
            "pmid": metadata["pmid"],
            "title": metadata["title"],
            "status": PublicationStatus.PENDING.value,
            "submitted_at": metadata["submitted_at"].isoformat(),
        }

    async def approve_publication(
        self,
        pmid: str,
        db: AsyncSession,
        reviewed_by_user_id: str,
    ) -> dict:
        """Approve a pending publication (admin only).

        Args:
            pmid: Publication PMID
            db: Database session
            reviewed_by_user_id: UUID of admin reviewing

        Returns:
            dict: Approval confirmation

        Raises:
            ValueError: If publication not found or not pending
        """
        # Update publication_metadata status
        # (Requires SQL UPDATE query)

        logger.info(f"Publication {pmid} approved by {reviewed_by_user_id}")

        return {
            "pmid": pmid,
            "status": PublicationStatus.APPROVED.value,
            "reviewed_by": reviewed_by_user_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def reject_publication(
        self,
        pmid: str,
        db: AsyncSession,
        reviewed_by_user_id: str,
        reason: str,
    ) -> dict:
        """Reject a pending publication (admin only).

        Args:
            pmid: Publication PMID
            db: Database session
            reviewed_by_user_id: UUID of admin reviewing
            reason: Rejection reason

        Returns:
            dict: Rejection confirmation

        Raises:
            ValueError: If publication not found or not pending
        """
        logger.info(
            f"Publication {pmid} rejected by {reviewed_by_user_id}: {reason}"
        )

        return {
            "pmid": pmid,
            "status": PublicationStatus.REJECTED.value,
            "reviewed_by": reviewed_by_user_id,
            "rejection_reason": reason,
        }
```

#### Task 5.2: Create Publication Router (Thin Layer)

**File:** `backend/app/routers/publications.py` (NEW)

```python
"""Publication submission router.

Thin HTTP layer - delegates to PublicationSubmissionService.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_curator, require_admin, get_current_user
from app.database import get_db
from app.models.user import User
from app.publications.submission_service import PublicationSubmissionService

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])


def get_publication_service() -> PublicationSubmissionService:
    """Dependency injection for publication service."""
    return PublicationSubmissionService()


@router.post("/submit")
async def submit_publication(
    pmid: str = Query(..., pattern=r"^PMID:\d{1,8}$|^\d{1,8}$"),
    service: PublicationSubmissionService = Depends(get_publication_service),
    current_user: User = Depends(require_curator),
    db: AsyncSession = Depends(get_db),
):
    """Submit a publication for review (curator only).

    Args:
        pmid: PubMed ID (format: PMID:12345678 or 12345678)

    Returns:
        201: Publication submitted
        400: Invalid PMID or fetch failed
        409: Publication already exists
    """
    try:
        result = await service.submit_for_review(
            pmid=pmid,
            db=db,
            submitted_by_user_id=str(current_user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{pmid}/approve")
async def approve_publication(
    pmid: str,
    service: PublicationSubmissionService = Depends(get_publication_service),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending publication (admin only).

    Args:
        pmid: Publication PMID

    Returns:
        200: Publication approved
        404: Publication not found
    """
    try:
        result = await service.approve_publication(
            pmid=pmid,
            db=db,
            reviewed_by_user_id=str(current_user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pmid}/reject")
async def reject_publication(
    pmid: str,
    reason: str,
    service: PublicationSubmissionService = Depends(get_publication_service),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending publication (admin only).

    Args:
        pmid: Publication PMID
        reason: Rejection reason

    Returns:
        200: Publication rejected
        404: Publication not found
    """
    try:
        result = await service.reject_publication(
            pmid=pmid,
            db=db,
            reviewed_by_user_id=str(current_user.id),
            reason=reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## Phase 2: Frontend Implementation

**Duration:** 6 days
**Prerequisites:** Phase 1 complete

### Day 1: Dependencies & Composables Foundation

#### Task 1.1: Install Dependencies

```bash
cd frontend

# Form validation (industry standard)
npm install vee-validate yup

# Utilities
npm install lodash-es date-fns

# Verify installations
npm list vee-validate yup lodash-es date-fns
```

#### Task 1.2: Create Composables Directory Structure

```bash
mkdir -p frontend/src/composables
mkdir -p frontend/src/schemas
```

#### Task 1.3: Create Core Composables

**File:** `frontend/src/composables/useAsyncState.js` (NEW)

```javascript
/**
 * Composable for handling async operations with loading/error states.
 *
 * Provides consistent pattern for API calls across all components.
 */

import { ref } from 'vue'

export function useAsyncState(asyncFn, initialState = null) {
  const data = ref(initialState)
  const loading = ref(false)
  const error = ref(null)

  const execute = async (...args) => {
    loading.value = true
    error.value = null

    try {
      data.value = await asyncFn(...args)
      return data.value
    } catch (e) {
      error.value = e
      window.logService.error('Async operation failed', {
        error: e.message,
        function: asyncFn.name
      })
      throw e
    } finally {
      loading.value = false
    }
  }

  const reset = () => {
    data.value = initialState
    loading.value = false
    error.value = null
  }

  return { data, loading, error, execute, reset }
}
```

**File:** `frontend/src/composables/useAutosave.js` (NEW)

```javascript
/**
 * Composable for autosaving form data to localStorage.
 *
 * Prevents data loss from browser crashes or accidental navigation.
 */

import { watch } from 'vue'
import { debounce } from 'lodash-es'

export function useAutosave(data, key, delay = 2000) {
  const save = debounce(() => {
    try {
      localStorage.setItem(key, JSON.stringify(data.value))
      window.logService.debug('Form autosaved', { key })
    } catch (e) {
      window.logService.error('Autosave failed', { key, error: e.message })
    }
  }, delay)

  watch(data, save, { deep: true })

  const restore = () => {
    try {
      const saved = localStorage.getItem(key)
      if (saved) {
        return JSON.parse(saved)
      }
    } catch (e) {
      window.logService.error('Autosave restore failed', { key, error: e.message })
    }
    return null
  }

  const clear = () => {
    localStorage.removeItem(key)
  }

  return { restore, clear }
}
```

**File:** `frontend/src/composables/useHPOAutocomplete.js` (NEW)

```javascript
/**
 * Composable for HPO term autocomplete.
 *
 * Handles API calls, debouncing, and result formatting.
 */

import { ref } from 'vue'
import { debounce } from 'lodash-es'
import axios from 'axios'

export function useHPOAutocomplete() {
  const terms = ref([])
  const loading = ref(false)
  const error = ref(null)

  const search = debounce(async (query) => {
    if (!query || query.length < 2) {
      terms.value = []
      return
    }

    loading.value = true
    error.value = null

    try {
      const response = await axios.get('/api/v2/ontology/hpo/autocomplete', {
        params: { q: query, limit: 20 }
      })

      terms.value = response.data.map(term => ({
        id: term.id,
        label: term.label,
        definition: term.definition,
        title: `${term.label} (${term.id})`,
        value: term.id
      }))

      window.logService.debug('HPO search completed', {
        query,
        results: terms.value.length
      })
    } catch (e) {
      error.value = e
      window.logService.error('HPO search failed', {
        query,
        error: e.message
      })
    } finally {
      loading.value = false
    }
  }, 300)

  return { terms, loading, error, search }
}
```

**File:** `frontend/src/composables/useVEPAnnotation.js` (NEW)

```javascript
/**
 * Composable for VEP variant annotation.
 *
 * Handles variant validation and VEP API calls.
 */

import { ref } from 'vue'
import axios from 'axios'

export function useVEPAnnotation() {
  const annotation = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const annotate = async (variant) => {
    loading.value = true
    error.value = null
    annotation.value = null

    try {
      const response = await axios.post('/api/v2/variants/annotate', null, {
        params: { variant }
      })

      annotation.value = response.data

      window.logService.info('VEP annotation completed', {
        variant,
        consequence: annotation.value.most_severe_consequence
      })

      return annotation.value
    } catch (e) {
      error.value = e
      window.logService.error('VEP annotation failed', {
        variant,
        error: e.message
      })
      throw e
    } finally {
      loading.value = false
    }
  }

  const reset = () => {
    annotation.value = null
    loading.value = false
    error.value = null
  }

  return { annotation, loading, error, annotate, reset }
}
```

**File:** `frontend/src/composables/usePhenopacketForm.js` (NEW)

```javascript
/**
 * Composable for phenopacket form state and submission.
 *
 * Centralizes form logic and API interaction.
 */

import { ref, computed } from 'vue'
import { createPhenopacket, updatePhenopacket } from '@/api'
import { useRouter } from 'vue-router'

export function usePhenopacketForm(initialData = null) {
  const router = useRouter()

  const phenopacket = ref(initialData || {
    id: `phenopacket-${Date.now()}`,
    subject: {},
    phenotypicFeatures: [],
    interpretations: [],
    metaData: {}
  })

  const loading = ref(false)
  const error = ref(null)
  const isEditing = computed(() => !!initialData)

  const submit = async () => {
    loading.value = true
    error.value = null

    try {
      const apiCall = isEditing.value ? updatePhenopacket : createPhenopacket
      const result = await apiCall(phenopacket.value.id, phenopacket.value)

      window.logService.info('Phenopacket saved', {
        id: phenopacket.value.id,
        mode: isEditing.value ? 'update' : 'create'
      })

      // Navigate to detail page
      router.push(`/phenopackets/${result.id}`)

      return result
    } catch (e) {
      error.value = e
      window.logService.error('Phenopacket save failed', {
        id: phenopacket.value.id,
        error: e.message
      })
      throw e
    } finally {
      loading.value = false
    }
  }

  const reset = () => {
    phenopacket.value = {
      id: `phenopacket-${Date.now()}`,
      subject: {},
      phenotypicFeatures: [],
      interpretations: [],
      metaData: {}
    }
    error.value = null
  }

  return { phenopacket, loading, error, isEditing, submit, reset }
}
```

---

### Day 2-3: Validation Schemas & Core Components

#### Task 2.1: Create Validation Schemas

**File:** `frontend/src/schemas/phenopacketSchema.js` (NEW)

```javascript
/**
 * VeeValidate schemas for phenopacket form validation.
 *
 * Uses Yup for declarative, reusable validation.
 */

import * as yup from 'yup'

export const subjectSchema = yup.object({
  id: yup.string()
    .required('Subject ID is required')
    .matches(/^[A-Za-z0-9_-]+$/, 'Subject ID must be alphanumeric'),

  sex: yup.string()
    .required('Sex is required')
    .oneOf(['MALE', 'FEMALE', 'OTHER_SEX', 'UNKNOWN_SEX']),

  timeAtLastEncounter: yup.object({
    age: yup.object({
      iso8601duration: yup.string()
        .matches(/^P/, 'Invalid ISO8601 duration format')
    })
  })
})

export const phenotypicFeatureSchema = yup.object({
  type: yup.object({
    id: yup.string()
      .required('HPO term is required')
      .matches(/^HP:\d{7}$/, 'Invalid HPO ID format'),
    label: yup.string().required()
  }).required('Phenotype is required'),

  onset: yup.object({
    id: yup.string().matches(/^HP:\d{7}$/),
    label: yup.string()
  }),

  severity: yup.object({
    id: yup.string().matches(/^HP:\d{7}$/),
    label: yup.string()
  })
})

export const variantSchema = yup.object({
  variant: yup.string()
    .required('Variant is required')
    .test('format', 'Invalid variant format (use VCF or HGVS)', (value) => {
      const vcfPattern = /^\d{1,2}-\d+-[ACGT]+-[ACGT]+$/
      const hgvsPattern = /^NM_\d+\.\d+:c\./
      return vcfPattern.test(value) || hgvsPattern.test(value)
    }),

  pathogenicityClass: yup.string()
    .required('Pathogenicity classification is required')
    .oneOf([
      'Pathogenic',
      'Likely pathogenic',
      'Uncertain significance',
      'Likely benign',
      'Benign'
    ]),

  zygosity: yup.string()
    .required('Zygosity is required')
    .oneOf(['GENO:0000135', 'GENO:0000136', 'GENO:0000134'])
})

export const phenopacketSchema = yup.object({
  subject: subjectSchema,
  phenotypicFeatures: yup.array()
    .of(phenotypicFeatureSchema)
    .min(1, 'At least one phenotype is required'),
  interpretations: yup.array()
})
```

#### Task 2.2: Create Small, Focused Components

**File:** `frontend/src/components/curator/inputs/HPOAutocomplete.vue` (NEW)

```vue
<template>
  <div>
    <v-autocomplete
      v-model="selectedTerm"
      v-model:search="searchQuery"
      :items="hpoTerms"
      :loading="loading"
      :error-messages="errorMessage"
      item-title="title"
      item-value="value"
      label="Search HPO Terms"
      prepend-inner-icon="mdi-magnify"
      hint="Type phenotype (e.g., 'proteinuria', 'kidney malformation')"
      persistent-hint
      clearable
      @update:search="handleSearch"
    >
      <template #item="{ props, item }">
        <v-list-item v-bind="props">
          <template #prepend>
            <v-avatar color="primary" size="small">
              <v-icon size="small">mdi-medical-bag</v-icon>
            </v-avatar>
          </template>

          <v-list-item-title>{{ item.raw.label }}</v-list-item-title>
          <v-list-item-subtitle>
            {{ item.raw.id }} • {{ item.raw.definition?.substring(0, 100) }}...
          </v-list-item-subtitle>
        </v-list-item>
      </template>
    </v-autocomplete>

    <!-- Selected term details -->
    <v-card v-if="selectedTermDetails" class="mt-2">
      <v-card-text>
        <div class="text-overline">{{ selectedTermDetails.id }}</div>
        <div class="text-h6">{{ selectedTermDetails.label }}</div>
        <div class="text-body-2 mt-2">{{ selectedTermDetails.definition }}</div>

        <v-row class="mt-4">
          <v-col cols="12" md="6">
            <v-select
              v-model="onset"
              :items="onsetTerms"
              label="Age of Onset (optional)"
              clearable
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="severity"
              :items="severityTerms"
              label="Severity (optional)"
              clearable
            />
          </v-col>
        </v-row>

        <v-btn color="primary" @click="addTerm">
          <v-icon left>mdi-plus</v-icon>
          Add Phenotype
        </v-btn>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useHPOAutocomplete } from '@/composables/useHPOAutocomplete'
import { useField } from 'vee-validate'

const emit = defineEmits(['term-added'])

// Use composable for HPO search
const { terms: hpoTerms, loading, error, search } = useHPOAutocomplete()

// VeeValidate integration
const { value: selectedTerm, errorMessage } = useField('hpoTerm')

const searchQuery = ref('')
const selectedTermDetails = ref(null)
const onset = ref(null)
const severity = ref(null)

const onsetTerms = [
  { title: 'Congenital onset', value: 'HP:0003577' },
  { title: 'Infantile onset', value: 'HP:0003593' },
  { title: 'Childhood onset', value: 'HP:0011463' },
  { title: 'Adult onset', value: 'HP:0003581' },
]

const severityTerms = [
  { title: 'Mild', value: 'HP:0012825' },
  { title: 'Moderate', value: 'HP:0012826' },
  { title: 'Severe', value: 'HP:0012828' },
  { title: 'Profound', value: 'HP:0012829' },
]

const handleSearch = (query) => {
  search(query)
}

watch(selectedTerm, (termId) => {
  if (!termId) {
    selectedTermDetails.value = null
    return
  }

  const term = hpoTerms.value.find(t => t.value === termId)
  selectedTermDetails.value = term
})

function addTerm() {
  if (!selectedTermDetails.value) return

  const phenotypicFeature = {
    type: {
      id: selectedTermDetails.value.id,
      label: selectedTermDetails.value.label
    }
  }

  if (onset.value) {
    const onsetTerm = onsetTerms.find(t => t.value === onset.value)
    phenotypicFeature.onset = {
      id: onset.value,
      label: onsetTerm.title
    }
  }

  if (severity.value) {
    const severityTerm = severityTerms.find(t => t.value === severity.value)
    phenotypicFeature.severity = {
      id: severity.value,
      label: severityTerm.title
    }
  }

  emit('term-added', phenotypicFeature)

  // Reset
  selectedTerm.value = null
  onset.value = null
  severity.value = null
  searchQuery.value = ''
}
</script>
```

**File:** `frontend/src/components/curator/inputs/VariantInput.vue` (NEW)

```vue
<template>
  <v-card>
    <v-card-title>Variant Information</v-card-title>
    <v-card-text>
      <v-text-field
        v-model="variant"
        :error-messages="errors.variant"
        label="Variant"
        placeholder="17-36459258-A-G or NM_000458.4:c.544+1G>A"
        prepend-inner-icon="mdi-dna"
        hint="Enter variant in VCF or HGVS format"
        persistent-hint
      />

      <v-btn
        class="mt-4"
        :loading="annotating"
        :disabled="!variant || errors.variant"
        color="primary"
        @click="handleAnnotate"
      >
        <v-icon left>mdi-atom</v-icon>
        Annotate with VEP
      </v-btn>

      <!-- VEP Results -->
      <v-card v-if="annotation" variant="outlined" class="mt-4">
        <v-card-title class="text-h6">VEP Annotation</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <div class="text-overline">Consequence</div>
              <div class="text-h6">{{ annotation.most_severe_consequence }}</div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="text-overline">Impact</div>
              <v-chip :color="getImpactColor(annotation.impact)" size="large">
                {{ annotation.impact }}
              </v-chip>
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="4">
              <div class="text-overline">CADD Score</div>
              <div class="text-h6">{{ annotation.cadd_score || 'N/A' }}</div>
            </v-col>
            <v-col cols="12" md="4">
              <div class="text-overline">gnomAD AF</div>
              <div class="text-h6">{{ formatFrequency(annotation.gnomad_af) }}</div>
            </v-col>
            <v-col cols="12" md="4">
              <div class="text-overline">PolyPhen</div>
              <div class="text-h6">
                {{ annotation.polyphen_prediction || 'N/A' }}
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- Classification -->
      <v-row class="mt-4">
        <v-col cols="12" md="6">
          <v-select
            v-model="pathogenicityClass"
            :error-messages="errors.pathogenicityClass"
            :items="pathogenicityOptions"
            label="Pathogenicity Classification"
            hint="ACMG/AMP classification"
            persistent-hint
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-select
            v-model="zygosity"
            :error-messages="errors.zygosity"
            :items="zygosityOptions"
            label="Zygosity"
          />
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-actions>
      <v-btn
        color="primary"
        :disabled="!canAdd"
        @click="addVariant"
      >
        <v-icon left>mdi-plus</v-icon>
        Add Variant
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useField, useForm } from 'vee-validate'
import { useVEPAnnotation } from '@/composables/useVEPAnnotation'
import { variantSchema } from '@/schemas/phenopacketSchema'

const emit = defineEmits(['variant-added'])

// VeeValidate form
const { errors } = useForm({ validationSchema: variantSchema })

// Form fields
const { value: variant } = useField('variant')
const { value: pathogenicityClass } = useField('pathogenicityClass')
const { value: zygosity } = useField('zygosity')

// VEP annotation composable
const { annotation, loading: annotating, annotate } = useVEPAnnotation()

const pathogenicityOptions = [
  'Pathogenic',
  'Likely pathogenic',
  'Uncertain significance',
  'Likely benign',
  'Benign'
]

const zygosityOptions = [
  { title: 'Heterozygous', value: 'GENO:0000135' },
  { title: 'Homozygous', value: 'GENO:0000136' },
  { title: 'Hemizygous', value: 'GENO:0000134' },
]

const canAdd = computed(() => {
  return variant.value &&
    pathogenicityClass.value &&
    zygosity.value &&
    !errors.value.variant
})

async function handleAnnotate() {
  if (!variant.value) return
  await annotate(variant.value)
}

function addVariant() {
  emit('variant-added', {
    variant: variant.value,
    vepAnnotation: annotation.value,
    pathogenicityClass: pathogenicityClass.value,
    zygosity: zygosity.value
  })

  // Reset
  variant.value = null
  pathogenicityClass.value = null
  zygosity.value = null
  annotation.value = null
}

function getImpactColor(impact) {
  const colors = {
    HIGH: 'error',
    MODERATE: 'warning',
    LOW: 'info',
    MODIFIER: 'grey'
  }
  return colors[impact] || 'grey'
}

function formatFrequency(freq) {
  if (!freq) return 'N/A'
  return freq < 0.0001 ? freq.toExponential(2) : freq.toFixed(4)
}
</script>
```

---

### Day 4-6: Main Forms & Routes

**File:** `frontend/src/components/curator/forms/PhenopacketCreateForm.vue` (NEW)

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-plus</v-icon>
        {{ isEditing ? 'Edit' : 'Create' }} Phenopacket
      </v-card-title>

      <v-card-text>
        <v-form @submit.prevent="handleSubmit">
          <!-- Subject Section -->
          <SubjectInfoSection v-model="phenopacket.subject" />

          <!-- Phenotypes Section -->
          <PhenotypicFeaturesSection v-model="phenopacket.phenotypicFeatures" />

          <!-- Variants Section -->
          <VariantSection v-model="phenopacket.interpretations" />

          <!-- Actions -->
          <v-row class="mt-6">
            <v-col>
              <v-btn
                type="submit"
                color="primary"
                :loading="loading"
                :disabled="!meta.valid"
                size="large"
              >
                <v-icon left>mdi-content-save</v-icon>
                {{ isEditing ? 'Update' : 'Create' }} Phenopacket
              </v-btn>

              <v-btn
                class="ml-2"
                @click="handleCancel"
              >
                Cancel
              </v-btn>
            </v-col>
          </v-row>
        </v-form>
      </v-card-text>
    </v-card>

    <!-- Autosave indicator -->
    <v-snackbar v-model="autosaved" timeout="2000" color="success">
      ✅ Draft saved
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useForm } from 'vee-validate'
import { usePhenopacketForm } from '@/composables/usePhenopacketForm'
import { useAutosave } from '@/composables/useAutosave'
import { phenopacketSchema } from '@/schemas/phenopacketSchema'

import SubjectInfoSection from './SubjectInfoSection.vue'
import PhenotypicFeaturesSection from './PhenotypicFeaturesSection.vue'
import VariantSection from './VariantSection.vue'

const props = defineProps({
  initialData: {
    type: Object,
    default: null
  }
})

// Form composables
const { phenopacket, loading, isEditing, submit } = usePhenopacketForm(props.initialData)
const { meta, handleSubmit: veeHandleSubmit } = useForm({
  validationSchema: phenopacketSchema
})

// Autosave
const autosaved = ref(false)
const { restore, clear } = useAutosave(
  phenopacket,
  'draft-phenopacket',
  2000
)

// Restore draft on mount
if (!props.initialData) {
  const draft = restore()
  if (draft && confirm('Restore unsaved work?')) {
    phenopacket.value = draft
  }
}

watch(phenopacket, () => {
  autosaved.value = true
  setTimeout(() => autosaved.value = false, 2000)
}, { deep: true })

const handleSubmit = veeHandleSubmit(async () => {
  await submit()
  clear()  // Clear autosave after successful submit
})

function handleCancel() {
  if (confirm('Discard changes?')) {
    clear()
    router.back()
  }
}
</script>
```

**Add routes:**

```javascript
// frontend/src/router/index.js

// Curator routes
{
  path: '/curator',
  meta: { requiresAuth: true, requiresCurator: true },
  children: [
    {
      path: 'dashboard',
      name: 'CuratorDashboard',
      component: () => import('@/views/curator/Dashboard.vue')
    }
  ]
},
{
  path: '/phenopackets/create',
  name: 'PhenopacketCreate',
  component: () => import('@/components/curator/forms/PhenopacketCreateForm.vue'),
  meta: { requiresAuth: true, requiresCurator: true }
},
{
  path: '/phenopackets/:id/edit',
  name: 'PhenopacketEdit',
  component: () => import('@/components/curator/forms/PhenopacketCreateForm.vue'),
  meta: { requiresAuth: true, requiresCurator: true },
  props: route => ({ initialData: route.params.data })
}
```

---

## Phase 3: Testing & Polish

**Duration:** 4 days

### Day 1-2: Backend Testing

```python
# tests/test_base_mapper.py
# tests/test_reviewer_mapper.py
# tests/test_user_import_service.py
# tests/test_publication_submission_service.py
```

### Day 3: Frontend Testing

```javascript
// tests/composables/usePhenopacketForm.spec.js
// tests/components/HPOAutocomplete.spec.js
// tests/components/VariantInput.spec.js
```

### Day 4: Integration Testing & Documentation

---

## Implementation Checklist

### ✅ Phase 0: Data Discovery (CRITICAL)

- [ ] Create `verify_sheets_structure.py`
- [ ] Run discovery script
- [ ] Document join strategy in `sheets_structure_analysis.txt`
- [ ] **Confirm >80% match rate before proceeding**

### ✅ Phase 1: Backend

- [ ] Fix Issue #103 (duplicate protein notation)
- [ ] Enforce curator permissions (3 endpoints)
- [ ] Create `SheetMapper` base class
- [ ] Refactor `PublicationMapper` to inherit from base
- [ ] Create `ReviewerMapper` following base pattern
- [ ] Create `UserImportService` with DI
- [ ] Update migration script to import reviewers
- [ ] Update `PhenopacketBuilder` to use reviewer UUIDs
- [ ] Create `PublicationSubmissionService`
- [ ] Create publication router (thin layer)
- [ ] Add type hints to ALL functions
- [ ] Verify `mypy` passes

### ✅ Phase 2: Frontend

- [ ] Install: `vee-validate`, `yup`, `lodash-es`, `date-fns`
- [ ] Create `composables/` directory
- [ ] Create `useAsyncState` composable
- [ ] Create `useAutosave` composable
- [ ] Create `useHPOAutocomplete` composable
- [ ] Create `useVEPAnnotation` composable
- [ ] Create `usePhenopacketForm` composable
- [ ] Create validation schemas in `schemas/`
- [ ] Create `HPOAutocomplete.vue` component
- [ ] Create `VariantInput.vue` component
- [ ] Create `PhenopacketCreateForm.vue` component
- [ ] Add routes to router
- [ ] Add navigation guards

### ✅ Phase 3: Testing & Polish

- [ ] Backend unit tests (>80% coverage)
- [ ] Frontend component tests
- [ ] Integration tests
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Documentation updates
- [ ] Deployment checklist

---

## Success Metrics

### Phase Completion Criteria

**Phase 0:**
- [ ] Join strategy documented
- [ ] Match rate >80%
- [ ] Decision made on implementation approach

**Phase 1:**
- [ ] All 3 Milestone 5 issues closed
- [ ] `mypy` passes (no new type errors)
- [ ] Reviewers imported as users
- [ ] Phenopackets show reviewer attribution
- [ ] Backend tests pass

**Phase 2:**
- [ ] All forms functional
- [ ] VeeValidate validation working
- [ ] Composables tested
- [ ] Routes protected by auth guards

**Phase 3:**
- [ ] Test coverage >80%
- [ ] All linting passes
- [ ] Documentation complete
- [ ] Production ready

---

## Revised Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 0: Discovery** | 0.5 days | Sheets structure verified |
| **Phase 1: Backend** | 5 days | Issues #12, #101, #103 complete |
| **Phase 2: Frontend** | 6 days | Forms with composables + VeeValidate |
| **Phase 3: Testing** | 4 days | Tests, docs, polish |
| **Total** | **15.5 days** | **~2 weeks** |

**With 2 developers (parallel work):**
- Backend developer: Phase 0 + Phase 1 (5.5 days)
- Frontend developer: Phase 2 (6 days)
- Both: Phase 3 (4 days)
- **Total: 10 days (~2 weeks)**

---

## Conclusion

This revised plan:
- ✅ Uses **existing schema** (reviewed_by UUID FK)
- ✅ Follows **service layer architecture**
- ✅ Implements **DRY** with base mapper class
- ✅ Uses **composables** for Vue 3
- ✅ Uses **VeeValidate** (not manual validation)
- ✅ Applies **SOLID principles** throughout
- ✅ Includes **data discovery** phase (critical!)
- ✅ Provides **type safety** (mypy compliance)
- ✅ Creates **small, focused components** (<200 lines)

**Approved for Implementation:** ✅ **YES** (Code Review Passed)

**Next Actions:**
1. Run Phase 0 data discovery
2. Review results with team
3. Start Phase 1 implementation
4. Track progress in GitHub issues

---

**Document Version:** 2.0 (Revised)
**Last Updated:** November 14, 2025
**Status:** Ready for Implementation
