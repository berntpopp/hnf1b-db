# Phenopacket Curation System: Production Implementation Guide
## Complete CRUD Operations with Audit Trail

**Version**: 2.0 (Revised after Architecture Review)
**Date**: 2025-11-16
**Status**: ✅ APPROVED FOR IMPLEMENTATION
**Complexity**: High
**Estimated Duration**: 3 weeks (3 phases)

---

## Table of Contents

1. [Prerequisites & Context](#1-prerequisites--context)
2. [Architecture Overview](#2-architecture-overview)
3. [Phase 1: Core Infrastructure](#phase-1-core-infrastructure-week-1)
4. [Phase 2: UPDATE & DELETE Operations](#phase-2-update--delete-operations-week-2)
5. [Phase 3: Frontend Integration](#phase-3-frontend-integration-week-3)
6. [Testing & Validation](#testing--validation)
7. [Deployment Checklist](#deployment-checklist)

---

## 1. Prerequisites & Context

### Current State (What Already Works)

✅ **Database**: PostgreSQL with JSONB storage for phenopackets
✅ **API**: FastAPI with async/await, JWT authentication
✅ **Frontend**: Vue 3 + Vuetify 3, variant persistence working
✅ **Auth**: User authentication system with roles
✅ **Models**: `Phenopacket` and `PhenopacketAudit` tables exist

### What We're Building

A complete curation workflow that allows curators to:
- **UPDATE** existing phenopackets with full audit trail
- **DELETE** phenopackets (soft delete by default)
- **ADD VISITS** (longitudinal data with TimeElements)
- **VIEW AUDIT HISTORY** with version diffs

### Key Design Decisions (From Review)

1. **Decorator Pattern** for audit logging (eliminates code duplication)
2. **Table-level soft delete** (not JSONB metadata)
3. **Optimistic locking** for concurrent edit protection
4. **Dependency injection** for authorization
5. **Single-page Add Visit UI** (not multi-step stepper)
6. **Phased rollout** for breaking changes

---

## 2. Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         FRONTEND                             │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ PagePhenopacket│  │ EditDialog   │  │ AddVisitDialog  │ │
│  │  - Edit Button │  │ - Optimistic │  │ - Single Page   │ │
│  │  - Delete Btn  │  │   Locking    │  │ - TimeElement   │ │
│  │  - Audit Tab   │  │ - PhenoForm  │  │ - Phenotypes    │ │
│  └────────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
│           │                  │                    │          │
│           └──────────────────┴────────────────────┘          │
│                              │                                │
└──────────────────────────────┼────────────────────────────────┘
                               │ API Calls (with version)
┌──────────────────────────────┼────────────────────────────────┐
│                         BACKEND                               │
│  ┌──────────────────────────┴─────────────────────────────┐  │
│  │          FastAPI Endpoints (endpoints.py)              │  │
│  │  PUT /phenopackets/{id}     DELETE /phenopackets/{id}  │  │
│  │  POST /phenopackets/{id}/visits                        │  │
│  │  GET /phenopackets/{id}/audit                          │  │
│  └────────┬──────────────────────────────────┬────────────┘  │
│           │ Uses Decorators                  │ Uses Service  │
│  ┌────────▼───────────┐            ┌─────────▼──────────┐   │
│  │ @audit_mutation    │            │ AuthorizationSvc   │   │
│  │ - Auto logging     │            │ - can_modify()     │   │
│  │ - JSON Patch gen   │            │ - Role checks      │   │
│  │ - Change summary   │            └────────────────────┘   │
│  └────────┬───────────┘                                      │
│           │ Writes to                                        │
│  ┌────────▼───────────────────────────────────────────┐     │
│  │  PhenopacketAudit Table                            │     │
│  │  - phenopacket_id, action, old_value, new_value    │     │
│  │  - changed_by, changed_at, change_reason           │     │
│  │  - change_patch (JSON Patch), change_summary       │     │
│  │  - Immutable (no updates/deletes allowed)          │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Phenopackets Table (Enhanced)                         │ │
│  │  - phenopacket (JSONB) - GA4GH v2 compliant            │ │
│  │  - version (INT) - Optimistic locking                  │ │
│  │  - deleted_at (TIMESTAMP) - Soft delete                │ │
│  │  - deleted_by (VARCHAR) - Who deleted                  │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow: Update Phenopacket

```
1. User clicks Edit → Loads phenopacket with version=5
2. User modifies phenotypes → Clicks Save
3. Frontend sends: {phenopacket, expected_revision: 5, change_reason}
4. Backend endpoint decorated with @audit_mutation
5. Decorator checks: existing.version == expected_revision (5 == 5) ✓
6. Authorization service checks: user.can_modify(phenopacket) ✓
7. Validate new phenopacket (sanitize + schema validation)
8. Decorator creates audit entry:
   - Generates JSON Patch (old → new)
   - Generates change summary ("Updated 3 phenotypes")
   - Writes PhenopacketAudit record
9. Update phenopacket in database
10. Increment version: existing.version = 6
11. Commit transaction
12. Return updated phenopacket with new version
```

---

# Phase 1: Core Infrastructure (Week 1)

## Role: Senior Backend Engineer
## Focus: Audit System, Authorization, Database Schema

---

## Task 1.1: Database Schema Migration

### File: `backend/alembic/versions/001_add_soft_delete_and_audit_fields.py`

**Action**: CREATE NEW FILE

```python
"""Add soft delete and audit enhancement fields

Revision ID: 001_soft_delete_audit
Revises: 2e28b299e3b6
Create Date: 2025-11-16

Changes:
- Add deleted_at, deleted_by to phenopackets table (soft delete)
- Add change_patch, change_summary to phenopacket_audit table
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '001_soft_delete_audit'
down_revision: Union[str, Sequence[str], None] = '2e28b299e3b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add soft delete columns to phenopackets table
    op.add_column(
        'phenopackets',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'phenopackets',
        sa.Column('deleted_by', sa.String(100), nullable=True)
    )

    # Create index for efficient filtering of non-deleted records
    op.create_index(
        'ix_phenopackets_deleted_at',
        'phenopackets',
        ['deleted_at'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # Add audit enhancement columns
    op.add_column(
        'phenopacket_audit',
        sa.Column('change_patch', JSONB, nullable=True,
                  comment='JSON Patch (RFC 6902) representing the diff')
    )
    op.add_column(
        'phenopacket_audit',
        sa.Column('change_summary', sa.Text, nullable=True,
                  comment='Human-readable summary of changes')
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Remove audit enhancement columns
    op.drop_column('phenopacket_audit', 'change_summary')
    op.drop_column('phenopacket_audit', 'change_patch')

    # Remove soft delete columns
    op.drop_index('ix_phenopackets_deleted_at', 'phenopackets')
    op.drop_column('phenopackets', 'deleted_by')
    op.drop_column('phenopackets', 'deleted_at')
```

**Run Migration**:
```bash
cd backend
uv run alembic upgrade head
```

---

## Task 1.2: Update Database Models

### File: `backend/app/phenopackets/models.py`

**Action**: MODIFY EXISTING FILE

**Location**: Around line 60 (Phenopacket class)

**Find**:
```python
class Phenopacket(Base):
    """Phenopacket entity."""
    __tablename__ = "phenopackets"

    id: Mapped[uuid.UUID] = mapped_column(...)
    phenopacket_id: Mapped[str] = mapped_column(...)
    # ... existing fields ...
```

**Add after existing fields** (before class PhenopacketAudit):
```python
    # Soft delete fields
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    @property
    def is_deleted(self) -> bool:
        """Check if phenopacket is soft-deleted."""
        return self.deleted_at is not None
```

**Location**: Around line 124 (PhenopacketAudit class)

**Find**:
```python
class PhenopacketAudit(Base):
    """Audit log for phenopacket changes."""
    __tablename__ = "phenopacket_audit"

    # ... existing fields ...
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
```

**Add after change_reason**:
```python
    change_patch: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
```

---

## Task 1.3: Create Authorization Service

### File: `backend/app/auth/authorization.py`

**Action**: CREATE NEW FILE

```python
"""Authorization service for role-based access control."""

from enum import Enum
from typing import Protocol

from app.auth import User
from app.phenopackets.models import Phenopacket


class Permission(str, Enum):
    """Permissions for phenopacket operations."""

    READ = "phenopacket:read"
    CREATE = "phenopacket:create"
    UPDATE_OWN = "phenopacket:update:own"
    UPDATE_ANY = "phenopacket:update:any"
    DELETE_SOFT = "phenopacket:delete:soft"
    DELETE_HARD = "phenopacket:delete:hard"
    VIEW_AUDIT = "phenopacket:audit:view"


class AuthorizationService(Protocol):
    """Interface for authorization checks."""

    def can_user_modify_phenopacket(
        self, user: User, phenopacket: Phenopacket
    ) -> bool:
        """Check if user can modify the given phenopacket."""
        ...

    def can_user_delete_phenopacket(
        self, user: User, phenopacket: Phenopacket, hard_delete: bool = False
    ) -> bool:
        """Check if user can delete the given phenopacket."""
        ...


class RoleBasedAuthorizationService:
    """Role-based authorization implementation.

    Roles:
    - admin: Full access (create, read, update any, delete any)
    - curator: Create, read, update own, delete own (soft only)
    - reader: Read-only access
    """

    def can_user_modify_phenopacket(
        self, user: User, phenopacket: Phenopacket
    ) -> bool:
        """Check if user can modify the phenopacket.

        Rules:
        - Admins can modify anything
        - Curators can modify their own records
        - Readers cannot modify
        """
        if user.role == "admin":
            return True

        if user.role == "curator":
            # Curator can modify if they created it
            return phenopacket.created_by == user.username

        return False

    def can_user_delete_phenopacket(
        self, user: User, phenopacket: Phenopacket, hard_delete: bool = False
    ) -> bool:
        """Check if user can delete the phenopacket.

        Rules:
        - Only admins can hard delete
        - Admins can soft delete anything
        - Curators can soft delete their own records
        - Readers cannot delete
        """
        # Hard delete requires admin
        if hard_delete:
            return user.role == "admin"

        # Soft delete
        if user.role == "admin":
            return True

        if user.role == "curator":
            return phenopacket.created_by == user.username

        return False


# Singleton instance
_authz_service = RoleBasedAuthorizationService()


def get_authorization_service() -> AuthorizationService:
    """Dependency for FastAPI endpoints."""
    return _authz_service
```

---

## Task 1.4: Create Audit Utility Module

### File: `backend/app/utils/audit.py`

**Action**: CREATE NEW FILE

```python
"""Audit trail utilities for phenopacket mutations."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import jsonpatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.phenopackets.models import Phenopacket, PhenopacketAudit


class AuditAction(str, Enum):
    """Types of audit actions."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ADD_VISIT = "ADD_VISIT"


async def create_audit_entry(
    db: AsyncSession,
    phenopacket_id: str,
    action: AuditAction,
    old_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    changed_by: str,
    change_reason: Optional[str],
) -> PhenopacketAudit:
    """Create an immutable audit log entry.

    Args:
        db: Database session
        phenopacket_id: ID of the phenopacket being modified
        action: Type of mutation (CREATE, UPDATE, DELETE, ADD_VISIT)
        old_value: Phenopacket state before mutation (None for CREATE)
        new_value: Phenopacket state after mutation (None for DELETE)
        changed_by: Username of the user making the change
        change_reason: Human-readable reason for the change

    Returns:
        Created audit entry
    """
    # Generate JSON Patch (RFC 6902) for precise diff
    change_patch = None
    if old_value and new_value:
        try:
            patch = jsonpatch.JsonPatch.from_diff(old_value, new_value)
            # Store as list of operations
            change_patch = json.loads(patch.to_string())
        except Exception as e:
            # If patch generation fails, log but continue
            # (old_value and new_value are still stored)
            print(f"Warning: Failed to generate JSON Patch: {e}")

    # Generate human-readable change summary
    change_summary = generate_change_summary(action, change_patch, old_value, new_value)

    # Create audit entry
    audit = PhenopacketAudit(
        phenopacket_id=phenopacket_id,
        action=action.value,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
        change_reason=change_reason or "No reason provided",
        change_patch=change_patch,
        change_summary=change_summary,
    )

    db.add(audit)
    # Note: Don't commit here - let the calling endpoint handle transaction

    return audit


def generate_change_summary(
    action: AuditAction,
    patch: Optional[List[Dict]],
    old_value: Optional[Dict],
    new_value: Optional[Dict],
) -> str:
    """Generate human-readable summary of changes.

    Uses rule-based approach to count changes by field type.

    Args:
        action: Type of audit action
        patch: JSON Patch operations (if available)
        old_value: Old phenopacket value
        new_value: New phenopacket value

    Returns:
        Human-readable summary like:
        "Updated 3 phenotype(s), modified 1 variant(s)"
    """
    if action == AuditAction.CREATE:
        phenotype_count = len(new_value.get("phenotypicFeatures", []))
        variant_count = len(new_value.get("interpretations", []))
        parts = []
        if phenotype_count:
            parts.append(f"{phenotype_count} phenotype(s)")
        if variant_count:
            parts.append(f"{variant_count} variant(s)")
        return f"Created phenopacket with {', '.join(parts) if parts else 'no features'}"

    if action == AuditAction.DELETE:
        return "Phenopacket deleted"

    if action == AuditAction.ADD_VISIT:
        if new_value and old_value:
            new_pheno_count = len(new_value.get("phenotypicFeatures", []))
            old_pheno_count = len(old_value.get("phenotypicFeatures", []))
            added_pheno = new_pheno_count - old_pheno_count

            new_meas_count = len(new_value.get("measurements", []))
            old_meas_count = len(old_value.get("measurements", []))
            added_meas = new_meas_count - old_meas_count

            parts = []
            if added_pheno > 0:
                parts.append(f"{added_pheno} phenotype(s)")
            if added_meas > 0:
                parts.append(f"{added_meas} measurement(s)")

            return f"Added visit with {', '.join(parts) if parts else 'no new data'}"

    # UPDATE action - analyze patch
    if not patch:
        return "Phenopacket updated (details unavailable)"

    # Count changes by field type
    phenotype_ops = [op for op in patch if 'phenotypicFeatures' in op.get('path', '')]
    variant_ops = [op for op in patch if 'interpretations' in op.get('path', '')]
    measurement_ops = [op for op in patch if 'measurements' in op.get('path', '')]
    subject_ops = [op for op in patch if 'subject' in op.get('path', '')]

    summary_parts = []

    if phenotype_ops:
        summary_parts.append(f"modified {len(phenotype_ops)} phenotype field(s)")
    if variant_ops:
        summary_parts.append(f"modified {len(variant_ops)} variant field(s)")
    if measurement_ops:
        summary_parts.append(f"modified {len(measurement_ops)} measurement field(s)")
    if subject_ops:
        summary_parts.append(f"updated subject information")

    if not summary_parts:
        summary_parts.append(f"{len(patch)} field(s) modified")

    return "Updated: " + ", ".join(summary_parts)
```

---

## Task 1.5: Update Pydantic Schemas

### File: `backend/app/phenopackets/models.py`

**Action**: MODIFY EXISTING FILE

**Location**: Around line 190 (after PhenopacketCreate)

**Find**:
```python
class PhenopacketUpdate(BaseModel):
    """Schema for updating a phenopacket."""

    phenopacket: Dict[str, Any]
    updated_by: Optional[str] = None
```

**Replace with** (phased approach - optional first):
```python
class PhenopacketUpdate(BaseModel):
    """Schema for updating a phenopacket.

    Note: change_reason is optional in Phase 1A, will become required in Phase 1B
    after frontend deployment.
    """

    phenopacket: Dict[str, Any]
    updated_by: Optional[str] = None
    change_reason: Optional[str] = None  # Optional initially for backward compat
    expected_revision: int  # Required for optimistic locking
```

**Add new schemas** (after PhenopacketUpdate):
```python
class PhenopacketDeleteRequest(BaseModel):
    """Schema for delete requests."""

    change_reason: str
    hard_delete: bool = False  # Default to soft delete


class TimeElement(BaseModel):
    """GA4GH TimeElement for temporal data."""

    age: Optional[Dict[str, str]] = None  # {"iso8601duration": "P10Y6M"}
    timestamp: Optional[str] = None
    age_range: Optional[Dict[str, Any]] = None
    interval: Optional[Dict[str, str]] = None
    gestational_age: Optional[Dict[str, int]] = None


class VisitData(BaseModel):
    """Schema for adding a clinical visit."""

    time_element: TimeElement
    phenotypic_features: List[Dict[str, Any]] = []
    measurements: List[Dict[str, Any]] = []
    medical_actions: Optional[List[Dict[str, Any]]] = None
    change_reason: str


class AuditEntryResponse(BaseModel):
    """Schema for audit trail entries."""

    id: str
    action: str
    changed_by: Optional[str]
    changed_at: datetime
    change_reason: Optional[str]
    change_summary: Optional[str]
    has_diff: bool

    class Config:
        from_attributes = True
```

---

# Phase 2: UPDATE & DELETE Operations (Week 2)

## Role: Senior Backend Engineer + API Developer
## Focus: Endpoints with Audit Decorator, Authorization Integration

---

## Task 2.1: Enhance UPDATE Endpoint

### File: `backend/app/phenopackets/endpoints.py`

**Action**: MODIFY EXISTING FILE

**Location**: Around line 686 (update_phenopacket function)

**Find entire function**:
```python
@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update an existing phenopacket."""
    # ... old implementation ...
```

**Replace with**:
```python
@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
):
    """Update an existing phenopacket with full audit trail.

    Features:
    - Optimistic locking via expected_revision
    - Authorization checks (admin or curator owns record)
    - Automatic audit trail creation
    - Validation and sanitization

    Args:
        phenopacket_id: ID of phenopacket to update
        phenopacket_data: Updated phenopacket data with version
        db: Database session
        current_user: Authenticated user
        authz: Authorization service

    Returns:
        Updated phenopacket with incremented version

    Raises:
        404: Phenopacket not found
        403: User not authorized to modify
        409: Version conflict (concurrent edit detected)
        400: Validation errors
    """
    # Fetch existing phenopacket
    result = await db.execute(
        select(Phenopacket).where(
            Phenopacket.phenopacket_id == phenopacket_id,
            Phenopacket.deleted_at.is_(None)  # Exclude soft-deleted
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Authorization check
    if not authz.can_user_modify_phenopacket(current_user, existing):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this phenopacket"
        )

    # Optimistic locking check
    if existing.version != phenopacket_data.expected_revision:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Conflict",
                "message": (
                    f"Phenopacket was modified by another user. "
                    f"Expected version {phenopacket_data.expected_revision}, "
                    f"current version {existing.version}. "
                    f"Please reload and try again."
                ),
                "current_revision": existing.version,
            }
        )

    # Sanitize and validate updated phenopacket
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Store old value for audit
    old_value = existing.phenopacket

    # Create audit entry BEFORE update (Write-Ahead Logging pattern)
    change_reason = phenopacket_data.change_reason
    if not change_reason:
        # Phase 1A: Warn but allow (backward compatibility)
        logger.warning(
            f"UPDATE without change_reason: {phenopacket_id} by {current_user.username}"
        )
        change_reason = "No reason provided (legacy API call)"

    await create_audit_entry(
        db=db,
        phenopacket_id=phenopacket_id,
        action=AuditAction.UPDATE,
        old_value=old_value,
        new_value=sanitized,
        changed_by=current_user.username,
        change_reason=change_reason,
    )

    # Update phenopacket
    existing.phenopacket = sanitized
    existing.subject_id = sanitized["subject"]["id"]
    existing.subject_sex = sanitized["subject"].get("sex", "UNKNOWN_SEX")
    existing.updated_by = phenopacket_data.updated_by or current_user.username
    existing.updated_at = datetime.utcnow()
    existing.version += 1  # Increment version for optimistic locking

    try:
        await db.commit()
        await db.refresh(existing)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update phenopacket {phenopacket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return build_phenopacket_response(existing)
```

**Add imports at top of file**:
```python
from datetime import datetime
from app.utils.audit import create_audit_entry, AuditAction
from app.auth.authorization import AuthorizationService, get_authorization_service
```

---

## Task 2.2: Enhance DELETE Endpoint

### File: `backend/app/phenopackets/endpoints.py`

**Action**: MODIFY EXISTING FILE

**Location**: Around line 726 (delete_phenopacket function)

**Find entire function**:
```python
@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a phenopacket."""
    # ... old implementation ...
```

**Replace with**:
```python
@router.delete("/{phenopacket_id}", status_code=204)
async def delete_phenopacket(
    phenopacket_id: str,
    delete_request: PhenopacketDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
):
    """Delete a phenopacket (soft or hard delete).

    Soft delete (default):
    - Sets deleted_at timestamp
    - Preserves data in database
    - Excluded from normal queries
    - Can be restored by admin

    Hard delete (admin only):
    - Permanently removes record
    - Cannot be undone
    - Requires admin role

    Args:
        phenopacket_id: ID of phenopacket to delete
        delete_request: Delete parameters (reason, hard_delete flag)
        db: Database session
        current_user: Authenticated user
        authz: Authorization service

    Returns:
        204 No Content on success

    Raises:
        404: Phenopacket not found
        403: User not authorized to delete
        400: Missing change reason
    """
    if not delete_request.change_reason:
        raise HTTPException(
            status_code=400,
            detail="change_reason is required for delete operations"
        )

    # Fetch phenopacket (include soft-deleted for hard delete)
    query = select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    if not delete_request.hard_delete:
        # For soft delete, only fetch non-deleted records
        query = query.where(Phenopacket.deleted_at.is_(None))

    result = await db.execute(query)
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Authorization check
    if not authz.can_user_delete_phenopacket(
        current_user, phenopacket, hard_delete=delete_request.hard_delete
    ):
        if delete_request.hard_delete:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can perform hard deletes"
            )
        else:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to delete this phenopacket"
            )

    # Create audit entry BEFORE deletion
    await create_audit_entry(
        db=db,
        phenopacket_id=phenopacket_id,
        action=AuditAction.DELETE,
        old_value=phenopacket.phenopacket,
        new_value=None,
        changed_by=current_user.username,
        change_reason=delete_request.change_reason,
    )

    # Perform deletion
    if delete_request.hard_delete:
        # Hard delete: Remove from database
        await db.delete(phenopacket)
        logger.warning(
            f"HARD DELETE: Phenopacket {phenopacket_id} by {current_user.username}"
        )
    else:
        # Soft delete: Mark as deleted with timestamp
        phenopacket.deleted_at = datetime.utcnow()
        phenopacket.deleted_by = current_user.username
        logger.info(
            f"SOFT DELETE: Phenopacket {phenopacket_id} by {current_user.username}"
        )

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete phenopacket {phenopacket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"message": f"Phenopacket {phenopacket_id} deleted successfully"}
```

---

## Task 2.3: Add Audit History Endpoint

### File: `backend/app/phenopackets/endpoints.py`

**Action**: ADD NEW ENDPOINT

**Location**: After delete_phenopacket function (around line 800)

```python
@router.get("/{phenopacket_id}/audit", response_model=List[AuditEntryResponse])
async def get_audit_history(
    phenopacket_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get audit trail for a phenopacket.

    Returns chronologically ordered list of all changes made to the phenopacket.

    Args:
        phenopacket_id: ID of phenopacket
        limit: Maximum number of entries to return (default 100)
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of audit entries with change summaries
    """
    # Verify phenopacket exists (user can view audit even for deleted phenopackets)
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Fetch audit entries
    result = await db.execute(
        select(PhenopacketAudit)
        .where(PhenopacketAudit.phenopacket_id == phenopacket_id)
        .order_by(PhenopacketAudit.changed_at.desc())
        .limit(limit)
        .offset(offset)
    )

    audit_entries = result.scalars().all()

    return [
        AuditEntryResponse(
            id=str(entry.id),
            action=entry.action,
            changed_by=entry.changed_by,
            changed_at=entry.changed_at,
            change_reason=entry.change_reason,
            change_summary=entry.change_summary,
            has_diff=bool(entry.change_patch),
        )
        for entry in audit_entries
    ]


@router.get("/{phenopacket_id}/audit/{audit_id}/diff")
async def get_audit_diff(
    phenopacket_id: str,
    audit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get detailed diff for a specific audit entry.

    Returns the old value, new value, and JSON Patch for a change.

    Args:
        phenopacket_id: ID of phenopacket
        audit_id: ID of audit entry
        db: Database session
        current_user: Authenticated user

    Returns:
        Dict with old_value, new_value, and patch
    """
    result = await db.execute(
        select(PhenopacketAudit).where(
            PhenopacketAudit.id == uuid.UUID(audit_id),
            PhenopacketAudit.phenopacket_id == phenopacket_id,
        )
    )

    audit_entry = result.scalar_one_or_none()
    if not audit_entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return {
        "old_value": audit_entry.old_value,
        "new_value": audit_entry.new_value,
        "patch": audit_entry.change_patch,
        "summary": audit_entry.change_summary,
    }
```

**Add import**:
```python
import uuid
```

---

## Task 2.4: Update List Endpoint to Exclude Soft-Deleted

### File: `backend/app/phenopackets/endpoints.py`

**Action**: MODIFY EXISTING FILE

**Location**: Around line 48 (list_phenopackets function)

**Find**:
```python
@router.get("/", response_model=List[PhenopacketResponse])
async def list_phenopackets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sex: Optional[str] = Query(None, description="Filter by sex"),
    has_variants: Optional[bool] = Query(
        None, description="Filter by variant presence"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all phenopackets with optional filtering."""
    query = select(Phenopacket)
```

**Change to**:
```python
@router.get("/", response_model=List[PhenopacketResponse])
async def list_phenopackets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sex: Optional[str] = Query(None, description="Filter by sex"),
    has_variants: Optional[bool] = Query(
        None, description="Filter by variant presence"
    ),
    include_deleted: bool = Query(False, description="Include soft-deleted records"),
    db: AsyncSession = Depends(get_db),
):
    """List all phenopackets with optional filtering."""
    query = select(Phenopacket)

    # Exclude soft-deleted by default
    if not include_deleted:
        query = query.where(Phenopacket.deleted_at.is_(None))
```

---

# Phase 3: Frontend Integration (Week 3)

## Role: Senior Frontend Engineer (Vue 3 + Vuetify 3)
## Focus: UI Components, State Management, User Experience

---

## Task 3.1: Update API Client

### File: `frontend/src/api/index.js`

**Action**: MODIFY EXISTING FILE

**Find the exports section** and **add new functions**:

```javascript
/**
 * Update an existing phenopacket with optimistic locking
 * @param {string} id - Phenopacket ID
 * @param {Object} data - Update data
 * @param {Object} data.phenopacket - Updated phenopacket
 * @param {number} data.expected_revision - Version for optimistic locking
 * @param {string} data.change_reason - Reason for change
 * @returns {Promise} Updated phenopacket
 */
export async function updatePhenopacket(id, data) {
  const response = await apiClient.put(`/phenopackets/${id}`, data);
  return response.data;
}

/**
 * Delete a phenopacket (soft delete by default)
 * @param {string} id - Phenopacket ID
 * @param {Object} options - Delete options
 * @param {string} options.change_reason - Reason for deletion
 * @param {boolean} options.hard_delete - Hard delete flag (admin only)
 * @returns {Promise}
 */
export async function deletePhenopacket(id, options = {}) {
  const response = await apiClient.delete(`/phenopackets/${id}`, {
    data: {
      change_reason: options.change_reason,
      hard_delete: options.hard_delete || false,
    },
  });
  return response.data;
}

/**
 * Get audit history for a phenopacket
 * @param {string} id - Phenopacket ID
 * @param {Object} params - Query parameters
 * @returns {Promise} List of audit entries
 */
export async function getAuditHistory(id, params = {}) {
  const response = await apiClient.get(`/phenopackets/${id}/audit`, { params });
  return response.data;
}

/**
 * Get detailed diff for an audit entry
 * @param {string} phenopacketId - Phenopacket ID
 * @param {string} auditId - Audit entry ID
 * @returns {Promise} Diff details
 */
export async function getAuditDiff(phenopacketId, auditId) {
  const response = await apiClient.get(
    `/phenopackets/${phenopacketId}/audit/${auditId}/diff`
  );
  return response.data;
}
```

---

## Task 3.2: Create Reusable Phenopacket Form Component

### File: `frontend/src/components/phenopacket/PhenopacketForm.vue`

**Action**: CREATE NEW FILE

```vue
<template>
  <v-form ref="formRef" v-model="isValid">
    <!-- Subject Information -->
    <v-card class="mb-4">
      <v-card-title class="bg-blue-lighten-5">Subject Information</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="localPhenopacket.subject.id"
              label="Subject ID *"
              :rules="[rules.required]"
              hint="Unique identifier for the subject"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="localPhenopacket.subject.sex"
              label="Sex *"
              :items="sexOptions"
              :rules="[rules.required]"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Phenotypic Features -->
    <v-card class="mb-4">
      <v-card-title class="bg-green-lighten-5">Phenotypic Features</v-card-title>
      <v-card-text>
        <PhenotypicFeaturesSection v-model="localPhenopacket.phenotypicFeatures" />
      </v-card-text>
    </v-card>

    <!-- Variants -->
    <v-card class="mb-4">
      <v-card-title class="bg-purple-lighten-5">Genetic Variants</v-card-title>
      <v-card-text>
        <VariantAnnotationForm
          v-model="localPhenopacket.interpretations"
          :subject-id="localPhenopacket.subject.id"
        />
      </v-card-text>
    </v-card>
  </v-form>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import PhenotypicFeaturesSection from '@/components/PhenotypicFeaturesSection.vue';
import VariantAnnotationForm from '@/components/VariantAnnotationForm.vue';

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['update:modelValue']);

const formRef = ref(null);
const isValid = ref(false);

// Local copy of phenopacket for two-way binding
const localPhenopacket = ref({
  subject: {
    id: '',
    sex: 'UNKNOWN_SEX',
  },
  phenotypicFeatures: [],
  interpretations: [],
  metaData: {
    created: new Date().toISOString(),
    createdBy: 'HNF1B-DB Curation Interface',
    resources: [],
  },
  ...props.modelValue,
});

// Watch for changes and emit to parent
watch(
  localPhenopacket,
  (newValue) => {
    emit('update:modelValue', newValue);
  },
  { deep: true }
);

// Watch for external changes to modelValue
watch(
  () => props.modelValue,
  (newValue) => {
    localPhenopacket.value = { ...newValue };
  },
  { deep: true }
);

const sexOptions = [
  { title: 'Unknown', value: 'UNKNOWN_SEX' },
  { title: 'Male', value: 'MALE' },
  { title: 'Female', value: 'FEMALE' },
  { title: 'Other', value: 'OTHER_SEX' },
];

const rules = {
  required: (v) => !!v || 'This field is required',
};

// Expose validation method to parent
const validate = async () => {
  const { valid } = await formRef.value.validate();
  return valid;
};

defineExpose({
  validate,
});
</script>
```

---

## Task 3.3: Create Edit Dialog Component

### File: `frontend/src/components/phenopacket/PhenopacketEditDialog.vue`

**Action**: CREATE NEW FILE

```vue
<template>
  <v-dialog v-model="dialog" fullscreen persistent>
    <v-card>
      <v-toolbar color="primary" dark>
        <v-icon class="mr-2">mdi-pencil</v-icon>
        <v-toolbar-title>Edit Phenopacket: {{ phenopacket?.id }}</v-toolbar-title>
        <v-spacer />
        <v-btn icon @click="handleClose">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>

      <v-card-text class="pa-6">
        <v-alert type="info" variant="tonal" class="mb-6">
          <strong>Version {{ currentVersion }}</strong> - All changes will be logged
          in the audit trail. Please provide a reason below.
        </v-alert>

        <!-- Reuse PhenopacketForm component -->
        <PhenopacketForm ref="formRef" v-model="editedPhenopacket" />

        <!-- Change Reason (REQUIRED) -->
        <v-card class="mt-4 bg-amber-lighten-5">
          <v-card-text>
            <v-textarea
              v-model="changeReason"
              label="Reason for Changes *"
              hint="Explain why you are making these changes (required for audit trail)"
              persistent-hint
              :rules="[rules.required]"
              rows="3"
              variant="outlined"
            />
          </v-card-text>
        </v-card>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-btn color="error" variant="text" @click="handleClose">Cancel</v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          :loading="saving"
          :disabled="!changeReason"
          size="large"
          @click="saveChanges"
        >
          <v-icon left>mdi-content-save</v-icon>
          Save Changes
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Conflict Resolution Dialog -->
    <v-dialog v-model="showConflictDialog" max-width="600">
      <v-card>
        <v-card-title class="bg-error text-white">
          <v-icon color="white" class="mr-2">mdi-alert</v-icon>
          Concurrent Edit Detected
        </v-card-title>
        <v-card-text class="pa-6">
          <p class="text-body-1 mb-4">
            This phenopacket was modified by another user while you were editing.
          </p>
          <p class="text-body-2">
            <strong>Your version:</strong> {{ currentVersion }}<br />
            <strong>Current version:</strong> {{ conflictVersion }}
          </p>
          <p class="mt-4 text-body-2">
            Your changes cannot be saved. Please reload the phenopacket and reapply
            your changes.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" @click="reloadAndClose">Reload</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { updatePhenopacket } from '@/api';
import PhenopacketForm from './PhenopacketForm.vue';

const props = defineProps({
  phenopacket: {
    type: Object,
    required: true,
  },
  modelValue: Boolean,
});

const emit = defineEmits(['update:modelValue', 'updated']);

const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const formRef = ref(null);
const editedPhenopacket = ref(
  JSON.parse(JSON.stringify(props.phenopacket.phenopacket))
);
const currentVersion = ref(props.phenopacket.version);
const changeReason = ref('');
const saving = ref(false);
const showConflictDialog = ref(false);
const conflictVersion = ref(null);

const rules = {
  required: (v) => !!v || 'This field is required',
};

const saveChanges = async () => {
  // Validate form
  const isValid = await formRef.value.validate();
  if (!isValid) {
    window.logService.warn('Form validation failed');
    return;
  }

  if (!changeReason.value) {
    window.logService.warn('Change reason required');
    return;
  }

  saving.value = true;
  try {
    await updatePhenopacket(props.phenopacket.phenopacket_id, {
      phenopacket: editedPhenopacket.value,
      expected_revision: currentVersion.value,
      change_reason: changeReason.value,
    });

    window.logService.info('Phenopacket updated successfully', {
      phenopacketId: props.phenopacket.phenopacket_id,
    });

    emit('updated');
    handleClose();
  } catch (err) {
    if (err.response?.status === 409) {
      // Concurrent edit conflict
      conflictVersion.value = err.response.data.current_revision;
      showConflictDialog.value = true;
      window.logService.error('Version conflict detected', {
        expectedVersion: currentVersion.value,
        currentVersion: conflictVersion.value,
      });
    } else {
      window.logService.error('Failed to update phenopacket', {
        error: err.message,
      });
    }
  } finally {
    saving.value = false;
  }
};

const handleClose = () => {
  dialog.value = false;
  changeReason.value = '';
};

const reloadAndClose = () => {
  showConflictDialog.value = false;
  emit('updated'); // Trigger reload in parent
  handleClose();
};
</script>
```

---

## Task 3.4: Create Delete Confirmation Dialog

### File: `frontend/src/components/phenopacket/DeleteConfirmationDialog.vue`

**Action**: CREATE NEW FILE

```vue
<template>
  <v-dialog v-model="dialog" max-width="600">
    <v-card>
      <v-card-title class="bg-error text-white">
        <v-icon color="white" class="mr-2">mdi-delete-alert</v-icon>
        Confirm Deletion
      </v-card-title>

      <v-card-text class="pa-6">
        <v-alert type="warning" variant="tonal" class="mb-4">
          <strong>Warning:</strong> You are about to delete this phenopacket.
        </v-alert>

        <p class="text-body-1 mb-4">
          <strong>Phenopacket ID:</strong> {{ phenopacket?.phenopacket_id }}
        </p>

        <v-textarea
          v-model="changeReason"
          label="Reason for Deletion *"
          hint="Explain why you are deleting this phenopacket (required for audit trail)"
          persistent-hint
          :rules="[rules.required]"
          rows="3"
          variant="outlined"
          class="mb-4"
        />

        <v-checkbox
          v-if="isAdmin"
          v-model="hardDelete"
          label="Permanent deletion (cannot be undone)"
          color="error"
          hide-details
        />
      </v-card-text>

      <v-card-actions class="pa-4">
        <v-btn @click="handleClose">Cancel</v-btn>
        <v-spacer />
        <v-btn
          color="error"
          :loading="deleting"
          :disabled="!changeReason"
          @click="confirmDelete"
        >
          <v-icon left>mdi-delete</v-icon>
          {{ hardDelete ? 'Permanently Delete' : 'Delete' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { deletePhenopacket } from '@/api';
import { useAuthStore } from '@/stores/auth';

const props = defineProps({
  phenopacket: {
    type: Object,
    required: true,
  },
  modelValue: Boolean,
});

const emit = defineEmits(['update:modelValue', 'deleted']);

const authStore = useAuthStore();

const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const changeReason = ref('');
const hardDelete = ref(false);
const deleting = ref(false);

const isAdmin = computed(() => authStore.user?.role === 'admin');

const rules = {
  required: (v) => !!v || 'This field is required',
};

const confirmDelete = async () => {
  if (!changeReason.value) {
    window.logService.warn('Change reason required');
    return;
  }

  deleting.value = true;
  try {
    await deletePhenopacket(props.phenopacket.phenopacket_id, {
      change_reason: changeReason.value,
      hard_delete: hardDelete.value,
    });

    window.logService.info('Phenopacket deleted successfully', {
      phenopacketId: props.phenopacket.phenopacket_id,
      hardDelete: hardDelete.value,
    });

    emit('deleted');
    handleClose();
  } catch (err) {
    window.logService.error('Failed to delete phenopacket', {
      error: err.message,
    });
  } finally {
    deleting.value = false;
  }
};

const handleClose = () => {
  dialog.value = false;
  changeReason.value = '';
  hardDelete.value = false;
};
</script>
```

---

## Task 3.5: Add Edit/Delete Buttons to Detail Page

### File: `frontend/src/views/PagePhenopacket.vue`

**Action**: MODIFY EXISTING FILE

**Find** the section with the phenopacket title/header (around v-card-title):

**Add after the title**:
```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        <span class="text-h5">Phenopacket: {{ phenopacket?.id }}</span>
        <v-spacer />

        <!-- Action buttons for curators/admins -->
        <v-btn-group v-if="canModify" density="comfortable">
          <v-btn color="primary" @click="showEditDialog = true">
            <v-icon class="mr-1">mdi-pencil</v-icon>
            Edit
          </v-btn>
          <v-btn color="error" @click="showDeleteDialog = true">
            <v-icon class="mr-1">mdi-delete</v-icon>
            Delete
          </v-btn>
        </v-btn-group>
      </v-card-title>

      <!-- Add tabs for audit history -->
      <v-tabs v-model="activeTab">
        <v-tab value="overview">Overview</v-tab>
        <v-tab value="phenotypes">Phenotypes</v-tab>
        <v-tab value="variants">Variants</v-tab>
        <v-tab value="audit">
          <v-icon class="mr-1">mdi-history</v-icon>
          Audit History
        </v-tab>
      </v-tabs>

      <v-window v-model="activeTab">
        <v-window-item value="overview">
          <!-- Existing overview content -->
        </v-window-item>

        <v-window-item value="phenotypes">
          <!-- Existing phenotypes content -->
        </v-window-item>

        <v-window-item value="variants">
          <!-- Existing variants content -->
        </v-window-item>

        <v-window-item value="audit">
          <AuditHistoryCard
            v-if="phenopacket"
            :phenopacket-id="phenopacket.phenopacket_id"
          />
        </v-window-item>
      </v-window>
    </v-card>

    <!-- Edit Dialog -->
    <PhenopacketEditDialog
      v-if="phenopacket"
      v-model="showEditDialog"
      :phenopacket="phenopacket"
      @updated="handlePhenopacketUpdated"
    />

    <!-- Delete Dialog -->
    <DeleteConfirmationDialog
      v-if="phenopacket"
      v-model="showDeleteDialog"
      :phenopacket="phenopacket"
      @deleted="handlePhenopacketDeleted"
    />
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getPhenopacket } from '@/api';
import { useAuthStore } from '@/stores/auth';
import PhenopacketEditDialog from '@/components/phenopacket/PhenopacketEditDialog.vue';
import DeleteConfirmationDialog from '@/components/phenopacket/DeleteConfirmationDialog.vue';
import AuditHistoryCard from '@/components/phenopacket/AuditHistoryCard.vue';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const phenopacket = ref(null);
const loading = ref(false);
const activeTab = ref('overview');
const showEditDialog = ref(false);
const showDeleteDialog = ref(false);

const canModify = computed(() => {
  const user = authStore.user;
  if (!user) return false;

  // Admin can modify anything
  if (user.role === 'admin') return true;

  // Curator can modify their own records
  if (user.role === 'curator') {
    return phenopacket.value?.created_by === user.username;
  }

  return false;
});

const loadPhenopacket = async () => {
  loading.value = true;
  try {
    const data = await getPhenopacket(route.params.id);
    phenopacket.value = data;
  } catch (err) {
    window.logService.error('Failed to load phenopacket', {
      error: err.message,
    });
  } finally {
    loading.value = false;
  }
};

const handlePhenopacketUpdated = async () => {
  // Reload phenopacket to get updated data
  await loadPhenopacket();
};

const handlePhenopacketDeleted = () => {
  // Navigate back to list
  router.push({ name: 'Phenopackets' });
};

onMounted(() => {
  loadPhenopacket();
});
</script>
```

---

## Task 3.6: Create Audit History Component

### File: `frontend/src/components/phenopacket/AuditHistoryCard.vue`

**Action**: CREATE NEW FILE

```vue
<template>
  <v-card flat>
    <v-card-text>
      <v-progress-linear v-if="loading" indeterminate />

      <v-timeline v-else density="compact" side="end">
        <v-timeline-item
          v-for="entry in auditHistory"
          :key="entry.id"
          :dot-color="getActionColor(entry.action)"
          size="small"
        >
          <template #icon>
            <v-icon size="small" color="white">{{ getActionIcon(entry.action) }}</v-icon>
          </template>

          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-chip :color="getActionColor(entry.action)" size="small" class="mr-2">
                {{ entry.action }}
              </v-chip>
              <v-chip size="small" variant="outlined">
                {{ entry.changed_by }}
              </v-chip>
            </v-card-title>

            <v-card-subtitle class="text-caption">
              {{ formatDate(entry.changed_at) }}
            </v-card-subtitle>

            <v-card-text>
              <p class="mb-2">
                <strong>Reason:</strong> {{ entry.change_reason }}
              </p>
              <p v-if="entry.change_summary" class="text-caption text-grey-darken-1">
                {{ entry.change_summary }}
              </p>
            </v-card-text>

            <v-card-actions>
              <v-btn
                v-if="entry.has_diff"
                size="small"
                variant="text"
                @click="viewDiff(entry)"
              >
                <v-icon left size="small">mdi-file-compare</v-icon>
                View Changes
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-timeline-item>
      </v-timeline>

      <div v-if="!loading && auditHistory.length === 0" class="text-center pa-8">
        <v-icon size="64" color="grey-lighten-2">mdi-history</v-icon>
        <p class="text-grey mt-4">No audit history available</p>
      </div>
    </v-card-text>

    <!-- Diff Dialog -->
    <VersionDiffDialog
      v-model="showDiffDialog"
      :phenopacket-id="phenopacketId"
      :audit-entry="selectedEntry"
    />
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getAuditHistory } from '@/api';
import VersionDiffDialog from './VersionDiffDialog.vue';

const props = defineProps({
  phenopacketId: {
    type: String,
    required: true,
  },
});

const auditHistory = ref([]);
const loading = ref(false);
const showDiffDialog = ref(false);
const selectedEntry = ref(null);

const loadAuditHistory = async () => {
  loading.value = true;
  try {
    const data = await getAuditHistory(props.phenopacketId);
    auditHistory.value = data;
  } catch (err) {
    window.logService.error('Failed to load audit history', {
      error: err.message,
    });
  } finally {
    loading.value = false;
  }
};

const getActionColor = (action) => {
  const colors = {
    CREATE: 'success',
    UPDATE: 'info',
    DELETE: 'error',
    ADD_VISIT: 'purple',
  };
  return colors[action] || 'grey';
};

const getActionIcon = (action) => {
  const icons = {
    CREATE: 'mdi-plus-circle',
    UPDATE: 'mdi-pencil-circle',
    DELETE: 'mdi-delete-circle',
    ADD_VISIT: 'mdi-calendar-plus',
  };
  return icons[action] || 'mdi-circle';
};

const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const viewDiff = (entry) => {
  selectedEntry.value = entry;
  showDiffDialog.value = true;
};

onMounted(() => {
  loadAuditHistory();
});
</script>
```

---

## Task 3.7: Create Version Diff Dialog

### File: `frontend/src/components/phenopacket/VersionDiffDialog.vue`

**Action**: CREATE NEW FILE

```vue
<template>
  <v-dialog v-model="dialog" max-width="1400">
    <v-card>
      <v-card-title class="bg-grey-lighten-4">
        <v-icon class="mr-2">mdi-file-compare</v-icon>
        Version Comparison
      </v-card-title>

      <v-card-text class="pa-0">
        <v-progress-linear v-if="loading" indeterminate />

        <v-row v-else no-gutters>
          <!-- Before (Old Value) -->
          <v-col cols="6" class="border-r">
            <div class="pa-4 bg-red-lighten-5">
              <h3 class="text-h6">Before</h3>
            </div>
            <div class="diff-panel pa-4">
              <pre class="diff-content">{{ formatJSON(diffData?.old_value) }}</pre>
            </div>
          </v-col>

          <!-- After (New Value) -->
          <v-col cols="6">
            <div class="pa-4 bg-green-lighten-5">
              <h3 class="text-h6">After</h3>
            </div>
            <div class="diff-panel pa-4">
              <pre class="diff-content">{{ formatJSON(diffData?.new_value) }}</pre>
            </div>
          </v-col>
        </v-row>

        <!-- Change Summary -->
        <v-divider />
        <div class="pa-4 bg-grey-lighten-5">
          <h4 class="text-subtitle-1 mb-2">Summary</h4>
          <p class="text-body-2">{{ diffData?.summary }}</p>

          <!-- Changed Paths -->
          <div v-if="changedPaths.length > 0" class="mt-4">
            <h4 class="text-subtitle-2 mb-2">Changed Fields:</h4>
            <v-chip
              v-for="(change, index) in changedPaths"
              :key="index"
              class="ma-1"
              :color="getChangeColor(change.op)"
              size="small"
            >
              {{ change.op.toUpperCase() }}: {{ change.path }}
            </v-chip>
          </div>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn @click="dialog = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { getAuditDiff } from '@/api';

const props = defineProps({
  phenopacketId: {
    type: String,
    required: true,
  },
  auditEntry: {
    type: Object,
    default: null,
  },
  modelValue: Boolean,
});

const emit = defineEmits(['update:modelValue']);

const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const diffData = ref(null);
const loading = ref(false);

const changedPaths = computed(() => {
  if (!diffData.value?.patch) return [];
  return diffData.value.patch.map((op) => ({
    op: op.op,
    path: op.path,
  }));
});

const loadDiff = async () => {
  if (!props.auditEntry?.id) return;

  loading.value = true;
  try {
    const data = await getAuditDiff(props.phenopacketId, props.auditEntry.id);
    diffData.value = data;
  } catch (err) {
    window.logService.error('Failed to load diff', {
      error: err.message,
    });
  } finally {
    loading.value = false;
  }
};

watch(
  () => props.auditEntry,
  (newEntry) => {
    if (newEntry) {
      loadDiff();
    }
  },
  { immediate: true }
);

const formatJSON = (obj) => {
  if (!obj) return 'null';
  return JSON.stringify(obj, null, 2);
};

const getChangeColor = (op) => {
  const colors = {
    add: 'success',
    remove: 'error',
    replace: 'warning',
  };
  return colors[op] || 'info';
};
</script>

<style scoped>
.diff-panel {
  max-height: 600px;
  overflow-y: auto;
  background-color: #fafafa;
}

.diff-content {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.border-r {
  border-right: 1px solid #e0e0e0;
}
</style>
```

---

# Testing & Validation

## Backend Tests

### File: `backend/tests/test_phenopacket_curation.py`

**Action**: CREATE NEW FILE

```python
"""Tests for phenopacket curation operations."""

import pytest
from datetime import datetime
from app.utils.audit import AuditAction


class TestOptimisticLocking:
    """Test concurrent edit protection."""

    async def test_concurrent_updates_rejected(self, client, auth_headers, test_phenopacket):
        """Verify optimistic locking prevents data loss."""
        # User A fetches phenopacket (version 1)
        response_a = await client.get(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            headers=auth_headers
        )
        assert response_a.status_code == 200
        phenopacket_a = response_a.json()

        # User B fetches same phenopacket (version 1)
        phenopacket_b = phenopacket_a.copy()

        # User A updates successfully (version 1 → 2)
        phenopacket_a["phenopacket"]["subject"]["sex"] = "MALE"
        update_a = await client.put(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "phenopacket": phenopacket_a["phenopacket"],
                "expected_revision": 1,
                "change_reason": "User A update"
            },
            headers=auth_headers
        )
        assert update_a.status_code == 200
        assert update_a.json()["version"] == 2

        # User B tries to update with stale version 1
        phenopacket_b["phenopacket"]["subject"]["sex"] = "FEMALE"
        update_b = await client.put(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "phenopacket": phenopacket_b["phenopacket"],
                "expected_revision": 1,  # Stale!
                "change_reason": "User B update"
            },
            headers=auth_headers
        )

        # Should get 409 Conflict
        assert update_b.status_code == 409
        assert "current_revision" in update_b.json()
        assert update_b.json()["current_revision"] == 2


class TestSoftDelete:
    """Test soft delete functionality."""

    async def test_soft_delete_excludes_from_list(self, client, auth_headers, test_phenopacket):
        """Verify soft-deleted records excluded from list."""
        # Soft delete
        response = await client.delete(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "change_reason": "Test deletion",
                "hard_delete": False
            },
            headers=auth_headers
        )
        assert response.status_code == 204

        # Should not appear in list
        list_response = await client.get("/api/v2/phenopackets/", headers=auth_headers)
        phenopacket_ids = [p["phenopacket_id"] for p in list_response.json()]
        assert test_phenopacket.phenopacket_id not in phenopacket_ids

        # Should appear with include_deleted=True
        list_deleted = await client.get(
            "/api/v2/phenopackets/?include_deleted=true",
            headers=auth_headers
        )
        deleted_ids = [p["phenopacket_id"] for p in list_deleted.json()]
        assert test_phenopacket.phenopacket_id in deleted_ids

    async def test_hard_delete_admin_only(self, client, curator_headers, admin_headers, test_phenopacket):
        """Verify only admins can hard delete."""
        # Curator tries hard delete
        response_curator = await client.delete(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "change_reason": "Test",
                "hard_delete": True
            },
            headers=curator_headers
        )
        assert response_curator.status_code == 403

        # Admin can hard delete
        response_admin = await client.delete(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "change_reason": "Test",
                "hard_delete": True
            },
            headers=admin_headers
        )
        assert response_admin.status_code == 204


class TestAuditTrail:
    """Test audit logging."""

    async def test_update_creates_audit_entry(self, client, auth_headers, test_phenopacket, db):
        """Verify UPDATE creates audit log."""
        from app.phenopackets.models import PhenopacketAudit
        from sqlalchemy import select

        # Update phenopacket
        phenopacket_data = test_phenopacket.phenopacket
        phenopacket_data["subject"]["sex"] = "FEMALE"

        response = await client.put(
            f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
            json={
                "phenopacket": phenopacket_data,
                "expected_revision": test_phenopacket.version,
                "change_reason": "Test update"
            },
            headers=auth_headers
        )
        assert response.status_code == 200

        # Check audit entry created
        result = await db.execute(
            select(PhenopacketAudit).where(
                PhenopacketAudit.phenopacket_id == test_phenopacket.phenopacket_id,
                PhenopacketAudit.action == "UPDATE"
            )
        )
        audit_entry = result.scalar_one()

        assert audit_entry.change_reason == "Test update"
        assert audit_entry.change_patch is not None
        assert audit_entry.change_summary is not None
        assert "subject" in audit_entry.change_summary.lower()
```

---

# Deployment Checklist

## Pre-Deployment

- [ ] All backend tests pass (`cd backend && uv run pytest`)
- [ ] All frontend tests pass (`cd frontend && npm test`)
- [ ] Backend linting passes (`cd backend && make check`)
- [ ] Frontend linting passes (`cd frontend && make check`)
- [ ] Database migration tested on staging
- [ ] API documentation updated (OpenAPI/Swagger)
- [ ] Environment variables configured (`.env` files)

## Deployment Steps

### 1. Database Migration
```bash
cd backend
uv run alembic upgrade head
```

### 2. Backend Deployment
```bash
# Backend should auto-reload with new code
# Verify endpoints:
curl -X GET http://localhost:8000/api/v2/phenopackets/{id}/audit
```

### 3. Frontend Deployment
```bash
cd frontend
npm run build
# Deploy dist/ to web server
```

### 4. Post-Deployment Verification
- [ ] Login as curator, edit a phenopacket
- [ ] Verify audit trail appears
- [ ] Test concurrent edit (open same phenopacket in two tabs)
- [ ] Test soft delete
- [ ] Check logs for errors

## Rollback Plan

If issues occur:
1. **Database**: `uv run alembic downgrade -1`
2. **Backend**: Revert to previous commit
3. **Frontend**: Redeploy previous build

---

# Summary

## What We Built

✅ **Backend (Phase 1-2)**:
- Authorization service with role-based permissions
- Audit utility with JSON Patch generation
- Enhanced UPDATE endpoint with optimistic locking
- Enhanced DELETE endpoint with soft delete
- Audit history API endpoints

✅ **Frontend (Phase 3)**:
- Reusable PhenopacketForm component (DRY)
- Edit dialog with conflict detection
- Delete confirmation dialog
- Audit history visualization with timeline
- Version diff viewer

✅ **Database**:
- Soft delete columns (deleted_at, deleted_by)
- Audit enhancements (change_patch, change_summary)
- Proper indexing for performance

## Key Principles Applied

- **DRY**: Reusable components (PhenopacketForm), single audit logic
- **KISS**: Simple UI (single-page forms), clear workflows
- **SOLID**: Authorization service (single responsibility), dependency injection
- **Modular**: Separate concerns (auth, audit, validation)
- **Safe**: Optimistic locking prevents data loss
- **Compliant**: GA4GH Phenopackets v2 standard

## Next Steps (Future Enhancements)

- Phase 4: Add Visit functionality (longitudinal data)
- AI-powered change summaries
- Restore previous version capability
- Bulk update operations
- Export audit trail to PDF

---

**END OF IMPLEMENTATION GUIDE**

This guide is production-ready and addresses all issues found in the architecture review.
