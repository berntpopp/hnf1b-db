"""CRUD operations for phenopackets.

Basic create, read, update, delete operations for phenopacket resources.
Offset-based pagination (JSON:API v1.1) with page[number] and page[size].
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.database import get_db
from app.models.json_api import JsonApiResponse
from app.phenopackets.models import (
    Phenopacket,
    PhenopacketAudit,
    PhenopacketAuditResponse,
    PhenopacketCreate,
    PhenopacketDelete,
    PhenopacketResponse,
    PhenopacketUpdate,
)
from app.phenopackets.query_builders import (
    add_has_variants_filter,
    add_sex_filter,
    build_phenopacket_response,
)
from app.phenopackets.validator import PhenopacketSanitizer, PhenopacketValidator
from app.utils.audit import create_audit_entry
from app.utils.pagination import build_offset_response

router = APIRouter(tags=["phenopackets-crud"])

validator = PhenopacketValidator()
sanitizer = PhenopacketSanitizer()
logger = logging.getLogger(__name__)

# Force reload to pick up JSON:API changes


@router.get("/", response_model=JsonApiResponse)
async def list_phenopackets(
    request: Request,
    # Offset pagination (JSON:API v1.1)
    page_number: int = Query(
        1,
        alias="page[number]",
        ge=1,
        description="Page number (1-indexed)",
    ),
    page_size: int = Query(
        100,
        alias="page[size]",
        ge=1,
        le=1000,
        description="Items per page (max: 1000)",
    ),
    # Filters
    filter_sex: Optional[str] = Query(
        None, alias="filter[sex]", description="Filter by subject sex"
    ),
    filter_has_variants: Optional[bool] = Query(
        None,
        alias="filter[has_variants]",
        description="Filter by variant presence",
    ),
    # Sort
    sort: Optional[str] = Query(
        None, description="Comma-separated fields, prefix with '-' for desc"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List phenopackets with offset-based pagination.

    Uses page[number] and page[size] for direct page access.

    **Pagination:**
    - `page[number]`: Page number (1-indexed, default: 1)
    - `page[size]`: Items per page (default: 100, max: 1000)

    **Filtering:**
    - `filter[sex]`: MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX
    - `filter[has_variants]`: true/false

    **Sorting:**
    - `sort`: Comma-separated fields (e.g., `-created_at,subject_id`)
    - Supported: `created_at`, `subject_id`, `subject_sex`
    """
    # Build base query (exclude soft-deleted)
    query = select(Phenopacket).where(Phenopacket.deleted_at.is_(None))

    # Apply filters
    query = add_sex_filter(query, filter_sex)
    query = add_has_variants_filter(query, filter_has_variants)

    # Apply sort order
    if sort:
        sort_clauses = parse_sort_parameter(sort)
        query = query.order_by(
            *sort_clauses,
            Phenopacket.created_at.desc(),
            Phenopacket.id.desc(),
        )
    else:
        # Default sort by created_at descending
        query = query.order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())

    # Get total count
    count_query = (
        select(func.count())
        .select_from(Phenopacket)
        .where(Phenopacket.deleted_at.is_(None))
    )
    count_query = add_sex_filter(count_query, filter_sex)
    count_query = add_has_variants_filter(count_query, filter_has_variants)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply offset pagination
    offset = (page_number - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    rows = list(result.scalars().all())

    # Build filter dict for pagination links
    filters: Dict[str, Any] = {}
    if filter_sex:
        filters["filter[sex]"] = filter_sex
    if filter_has_variants is not None:
        filters["filter[has_variants]"] = filter_has_variants

    # Build JSON:API offset response
    base_url = str(request.url.path)
    data = [pp.phenopacket for pp in rows]

    return build_offset_response(
        data=data,
        current_page=page_number,
        page_size=page_size,
        total_records=total_count,
        base_url=base_url,
        filters=filters,
        sort=sort,
    )


def parse_sort_parameter(sort: str) -> list:
    """Parse JSON:API sort parameter into SQLAlchemy order clauses.

    Args:
        sort: Comma-separated fields, prefix with '-' for descending
              Example: "-created_at,subject_id"

    Returns:
        List of SQLAlchemy order clauses

    Raises:
        HTTPException: If sort field is not allowed
    """
    allowed_fields = {
        "created_at": Phenopacket.created_at,
        "subject_id": Phenopacket.subject_id,
        "subject_sex": Phenopacket.subject_sex,
    }

    order_clauses = []
    for field in sort.split(","):
        field = field.strip()
        descending = field.startswith("-")
        field_name = field[1:] if descending else field

        if field_name not in allowed_fields:
            allowed = ", ".join(allowed_fields.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field: {field_name}. Allowed: {allowed}",
            )

        sort_column = allowed_fields[field_name]

        # Apply natural sorting for subject_id to handle IDs like
        # "Var1", "Var2", "Var10" - extracts numeric suffix and sorts numerically
        if field_name == "subject_id":
            order_clauses.extend(
                get_natural_sort_clauses(Phenopacket.subject_id, descending)
            )
        else:
            # Apply sort direction
            if descending:
                order_clauses.append(sort_column.desc())
            else:
                order_clauses.append(sort_column.asc())

    return order_clauses


def get_natural_sort_clauses(column, descending: bool = False) -> list:
    """Generate SQLAlchemy order clauses for natural sorting.

    Natural sorting ensures "Var2" comes before "Var10" by:
    1. Sorting by the text prefix (e.g., "Var")
    2. Sorting by the numeric suffix as an integer (e.g., 2, 10)

    Args:
        column: SQLAlchemy column to sort
        descending: Whether to sort in descending order

    Returns:
        List of SQLAlchemy order clauses
    """
    # Extract text prefix (everything before the trailing digits)
    # regexp_replace removes trailing digits to get the prefix
    text_prefix = func.regexp_replace(column, r"[0-9]+$", "", "g")

    # Extract numeric suffix using substring with regex
    # This extracts the trailing digits and casts to integer
    # COALESCE handles cases with no trailing numbers (returns 0)
    numeric_suffix = func.coalesce(
        func.cast(
            func.substring(column, r"([0-9]+)$"),
            Integer,
        ),
        0,
    )

    if descending:
        return [text_prefix.desc(), numeric_suffix.desc()]
    else:
        return [text_prefix.asc(), numeric_suffix.asc()]


@router.get("/batch", response_model=List[Dict])
async def get_phenopackets_batch(
    phenopacket_ids: str = Query(
        ..., description="Comma-separated list of phenopacket IDs"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get multiple phenopackets by IDs in a single query.

    Prevents N+1 HTTP requests when fetching multiple phenopackets.

    Args:
        phenopacket_ids: Comma-separated phenopacket IDs (e.g., "id1,id2,id3")
        db: Database session dependency

    Returns:
        List of phenopacket documents

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [id.strip() for id in phenopacket_ids.split(",") if id.strip()]

    if not ids:
        return []

    # Single query for all phenopackets (no N+1, exclude soft-deleted)
    result = await db.execute(
        select(Phenopacket).where(
            and_(
                Phenopacket.phenopacket_id.in_(ids),
                Phenopacket.deleted_at.is_(None),
            )
        )
    )
    phenopackets = result.scalars().all()

    return [
        {
            "phenopacket_id": pp.phenopacket_id,
            "phenopacket": pp.phenopacket,
        }
        for pp in phenopackets
    ]


@router.get("/{phenopacket_id}", response_model=PhenopacketResponse)
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single phenopacket by ID with metadata (excludes soft-deleted)."""
    result = await db.execute(
        select(Phenopacket).where(
            and_(
                Phenopacket.phenopacket_id == phenopacket_id,
                Phenopacket.deleted_at.is_(None),
            )
        )
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return build_phenopacket_response(phenopacket)


@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Create a new phenopacket (requires curator role).

    Returns:
        201: Phenopacket created successfully
        400: Validation error
        409: Phenopacket with this ID already exists
        500: Database error
    """
    # Sanitize the phenopacket
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)

    # Validate phenopacket structure
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Create new phenopacket
    # Database UNIQUE constraint will prevent duplicates atomically
    new_phenopacket = Phenopacket(
        phenopacket_id=sanitized["id"],
        phenopacket=sanitized,
        subject_id=sanitized["subject"]["id"],
        subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
        created_by=phenopacket_data.created_by or current_user.username,
    )

    db.add(new_phenopacket)

    try:
        await db.commit()
        await db.refresh(new_phenopacket)
    except Exception as e:
        await db.rollback()
        # Check for integrity errors (duplicate keys, foreign key violations, etc.)
        error_str = str(e).lower()
        if (
            "duplicate" in error_str or "unique" in error_str
        ) and "phenopacket_id" in error_str:
            raise HTTPException(
                status_code=409,
                detail=f"Phenopacket with ID '{sanitized['id']}' already exists",
            ) from e
        # Re-raise other database errors
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e

    return build_phenopacket_response(new_phenopacket)


@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Update an existing phenopacket with optimistic locking and audit trail.

    Implements:
    - Optimistic locking via revision field (prevents lost updates)
    - Complete audit trail with JSON Patch
    - Conflict detection for concurrent edits
    - Soft-deleted records are filtered out

    Args:
        phenopacket_id: Phenopacket identifier
        phenopacket_data: Updated phenopacket with revision and change_reason
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated phenopacket with incremented revision

    Raises:
        404: Phenopacket not found or soft-deleted
        409: Conflict - revision mismatch (concurrent edit detected)
        400: Validation error
    """
    # Fetch existing phenopacket (exclude soft-deleted)
    result = await db.execute(
        select(Phenopacket).where(
            and_(
                Phenopacket.phenopacket_id == phenopacket_id,
                Phenopacket.deleted_at.is_(None),
            )
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Optimistic locking check (skip if revision not provided)
    if (
        phenopacket_data.revision is not None
        and existing.revision != phenopacket_data.revision
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Conflict detected",
                "message": (
                    f"Phenopacket was modified by another user. "
                    f"Expected revision {phenopacket_data.revision}, "
                    f"but current revision is {existing.revision}"
                ),
                "current_revision": existing.revision,
                "expected_revision": phenopacket_data.revision,
            },
        )

    # Store old value for audit trail
    old_phenopacket = existing.phenopacket.copy()

    # Sanitize the updated phenopacket
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)

    # Validate updated phenopacket
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Update the phenopacket
    existing.phenopacket = sanitized
    existing.subject_id = sanitized["subject"]["id"]
    existing.subject_sex = sanitized["subject"].get("sex", "UNKNOWN_SEX")
    existing.updated_by = phenopacket_data.updated_by or current_user.username
    existing.revision += 1  # Increment revision

    try:
        # Create audit entry
        await create_audit_entry(
            db=db,
            phenopacket_id=phenopacket_id,
            action="UPDATE",
            old_value=old_phenopacket,
            new_value=sanitized,
            changed_by=existing.updated_by,
            change_reason=phenopacket_data.change_reason,
        )

        await db.commit()
        await db.refresh(existing)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update phenopacket {phenopacket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return build_phenopacket_response(existing)


@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    delete_request: PhenopacketDelete,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Soft delete a phenopacket with audit trail (requires curator role).

    Implements soft delete pattern to preserve research data integrity.
    Records are marked as deleted but remain in the database for audit purposes.

    Args:
        phenopacket_id: Phenopacket identifier
        delete_request: Delete request with change_reason
            (uses body to avoid URL length limits)
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message with deletion details

    Raises:
        404: Phenopacket not found or already deleted
        500: Database error
    """
    from datetime import datetime, timezone

    # Fetch phenopacket (only non-deleted)
    result = await db.execute(
        select(Phenopacket).where(
            and_(
                Phenopacket.phenopacket_id == phenopacket_id,
                Phenopacket.deleted_at.is_(None),
            )
        )
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(
            status_code=404,
            detail="Phenopacket not found or already deleted",
        )

    # Store phenopacket data for audit trail before soft delete
    old_phenopacket = phenopacket.phenopacket.copy()

    # Soft delete: set deleted_at and deleted_by
    phenopacket.deleted_at = datetime.now(timezone.utc)
    phenopacket.deleted_by = current_user.username

    try:
        # Create audit entry
        await create_audit_entry(
            db=db,
            phenopacket_id=phenopacket_id,
            action="DELETE",
            old_value=old_phenopacket,
            new_value=None,
            changed_by=current_user.username,
            change_reason=delete_request.change_reason,
        )

        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete phenopacket {phenopacket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {
        "message": f"Phenopacket {phenopacket_id} deleted successfully",
        "deleted_at": phenopacket.deleted_at.isoformat(),
        "deleted_by": phenopacket.deleted_by,
    }


@router.get("/{phenopacket_id}/audit", response_model=List[PhenopacketAuditResponse])
async def get_phenopacket_audit_history(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Get audit history for a phenopacket.

    Returns all audit trail entries for the specified phenopacket,
    ordered by timestamp (most recent first).

    Args:
        phenopacket_id: Phenopacket identifier
        db: Database session
        current_user: Authenticated curator/admin user

    Returns:
        List of audit entries with change history, ordered by changed_at DESC

    Example response:
        [
            {
                "id": "uuid",
                "phenopacket_id": "HNF1B-001",
                "action": "UPDATE",
                "changed_by": "curator@example.com",
                "changed_at": "2024-11-16T20:00:00Z",
                "change_reason": "Updated patient sex",
                "change_summary": "Changed subject.sex: UNKNOWN_SEX → FEMALE",
                "change_patch": [
                    {"op": "replace", "path": "/subject/sex", "value": "FEMALE"}
                ]
            }
        ]
    """
    # Verify phenopacket exists (even if soft-deleted, we still want audit history)
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Fetch audit entries, ordered by most recent first
    audit_result = await db.execute(
        select(PhenopacketAudit)
        .where(PhenopacketAudit.phenopacket_id == phenopacket_id)
        .order_by(PhenopacketAudit.changed_at.desc())
    )
    audit_entries = audit_result.scalars().all()

    # Convert to response models
    return [
        PhenopacketAuditResponse(
            id=str(audit.id),
            phenopacket_id=audit.phenopacket_id,
            action=audit.action,
            changed_by=audit.changed_by,
            changed_at=audit.changed_at,
            change_reason=audit.change_reason,
            change_summary=audit.change_summary,
            change_patch=audit.change_patch,
            old_value=audit.old_value,
            new_value=audit.new_value,
        )
        for audit in audit_entries
    ]


@router.get("/by-variant/{variant_id}")
async def get_phenopackets_by_variant(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all phenopackets that contain a specific variant.

    Args:
        variant_id: The variant ID to search for
        db: Database session

    Returns:
        List of phenopackets containing this variant
    """
    # Use raw SQL with ORM mapping for reliability
    query = text(
        """
    SELECT id, phenopacket_id, version, phenopacket,
           created_at, updated_at, schema_version
    FROM phenopackets p
    WHERE EXISTS (
        SELECT 1
        FROM jsonb_array_elements(p.phenopacket->'interpretations') as interp,
             jsonb_array_elements(
                 interp->'diagnosis'->'genomicInterpretations'
             ) as gi
        WHERE gi->'variantInterpretation'->'variationDescriptor'->>'id'
              = :variant_id
    )
    ORDER BY p.created_at DESC
    """
    )

    result = await db.execute(query, {"variant_id": variant_id})
    rows = result.mappings().all()

    # Return structured response with metadata and phenopacket data
    # Note: phenopacket['id'] is the internal ID, not database record ID
    response_data = []
    for row in rows:
        item = {
            "phenopacket_id": row["phenopacket_id"],
            "version": row["version"],
            "phenopacket": row["phenopacket"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "schema_version": row["schema_version"],
        }
        response_data.append(item)
    return response_data


# ===== Publication Filter Endpoint =====


def validate_pmid(pmid: str) -> str:
    """Validate and normalize PMID format.

    Args:
        pmid: PMID string (format: "PMID:12345678" or "12345678")

    Returns:
        Normalized PMID (format: PMID:12345678)

    Raises:
        ValueError: If PMID format is invalid
    """
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format: PMID followed by 1-8 digits only
    if not re.match(r"^PMID:\d{1,8}$", pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")

    return pmid


@router.get("/by-publication/{pmid}", response_model=Dict)
async def get_by_publication(
    pmid: str,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Max records (max: 500)"),
    sex: Optional[str] = Query(
        None,
        pattern="^(MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)$",
        description="Filter by sex",
    ),
    has_variants: Optional[bool] = Query(
        None, description="Filter by variant presence"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get phenopackets citing a specific publication.

    **Security:** PMID is validated to prevent SQL injection.

    **Parameters:**
    - **pmid**: PubMed ID (format: PMID:12345678 or just 12345678)
    - **skip**: Pagination offset (default: 0)
    - **limit**: Max records to return (default: 100, max: 500)
    - **sex**: Filter by sex (MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)
    - **has_variants**: Filter by variant presence (true/false)

    **Returns:**
    - Phenopackets where metaData.externalReferences contains this PMID
    - Total count of matching phenopackets
    - Pagination metadata

    **Error Codes:**
    - 400: Invalid PMID format or parameters
    - 404: No phenopackets found for this publication
    - 500: Database error
    """
    try:
        # SECURITY: Validate PMID format to prevent SQL injection
        pmid = validate_pmid(pmid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # SECURITY: Cap limit to prevent excessive data exposure
    limit = min(limit, 500)

    # Build query with JSONB filtering (exclude soft-deleted)
    query = """
        SELECT
            phenopacket_id,
            phenopacket
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
        AND deleted_at IS NULL
    """

    # Build JSONB filter for PMID (parameterized - safe from injection)
    pmid_filter = json.dumps([{"id": pmid}])

    params = {"pmid_filter": pmid_filter, "skip": skip, "limit": limit}

    # Add optional filters with parameterized queries
    if sex:
        query += " AND subject_sex = :sex"
        params["sex"] = sex

    if has_variants is not None:
        if has_variants:
            query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            query += (
                " AND (phenopacket->'interpretations' IS NULL OR "
                "jsonb_array_length(phenopacket->'interpretations') = 0)"
            )

    # Count query (same filters, exclude soft-deleted)
    count_query = """
        SELECT COUNT(*)
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
        AND deleted_at IS NULL
    """

    # Add same filters to count query
    if sex:
        count_query += " AND subject_sex = :sex"
    if has_variants is not None:
        if has_variants:
            count_query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            count_query += (
                " AND (phenopacket->'interpretations' IS NULL OR "
                "jsonb_array_length(phenopacket->'interpretations') = 0)"
            )

    try:
        # Execute count query
        total_result = await db.execute(text(count_query), params)
        total = total_result.scalar()

        # Return 404 if no results found
        if total == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No phenopackets found citing publication {pmid}",
            )

        # Add pagination (parameters prevent injection)
        query += " ORDER BY phenopacket_id LIMIT :limit OFFSET :skip"

        # Execute query
        result = await db.execute(text(query), params)
        rows = result.fetchall()

        return {
            "data": [
                {"phenopacket_id": row.phenopacket_id, "phenopacket": row.phenopacket}
                for row in rows
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except HTTPException:
        # Re-raise HTTP exceptions (404, 400)
        raise
    except Exception as e:
        logger.error(f"Error fetching phenopackets for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{phenopacket_id}/timeline", response_model=Dict[str, Any])
async def get_phenotype_timeline(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get temporal timeline data for phenotypic features.

    Extracts phenotypic features with onset ages and evidence timestamps,
    suitable for rendering a timeline visualization.

    Args:
        phenopacket_id: Phenopacket identifier
        db: Database session

    Returns:
        Dictionary with timeline data:
        {
            "subject_id": "123",
            "current_age": "P45Y6M",
            "features": [
                {
                    "hpo_id": "HP:0000107",
                    "label": "Renal cyst",
                    "onset_age": "P5Y",
                    "onset_label": "Congenital onset",
                    "category": "Renal",
                    "severity": null,
                    "excluded": false,
                    "evidence": [...]
                }
            ]
        }
    """
    # Query phenopacket
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket_record = result.scalar_one_or_none()

    if not phenopacket_record:
        raise HTTPException(
            status_code=404, detail=f"Phenopacket '{phenopacket_id}' not found"
        )

    phenopacket_data = phenopacket_record.phenopacket

    # Extract subject info
    subject = phenopacket_data.get("subject", {})
    subject_id = subject.get("id")

    # Try to get current age from timeAtLastEncounter
    current_age = None
    current_age_years = None
    if "timeAtLastEncounter" in subject:
        time_at_last = subject["timeAtLastEncounter"]
        if isinstance(time_at_last, dict) and "age" in time_at_last:
            age_obj = time_at_last["age"]
            if isinstance(age_obj, dict):
                current_age = age_obj.get("iso8601duration")
                # Parse to years for use as default onset
                if current_age:
                    try:
                        # Simple parser for ISO8601 duration
                        match = re.match(
                            r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?", current_age
                        )
                        if match:
                            years = int(match.group(1) or 0)
                            months = int(match.group(2) or 0)
                            days = int(match.group(3) or 0)
                            current_age_years = years + (months / 12) + (days / 365)
                    except (ValueError, AttributeError):
                        pass

    # Extract phenotypic features with temporal data
    features = []
    phenotypic_features = phenopacket_data.get("phenotypicFeatures", [])

    for feature in phenotypic_features:
        feature_type = feature.get("type", {})
        hpo_id = feature_type.get("id")
        label = feature_type.get("label", "Unknown")

        # Extract onset information
        onset = feature.get("onset")
        onset_age = None
        onset_label = None

        if onset:
            # Handle age field - can be string or object
            if "age" in onset:
                age_value = onset["age"]
                if isinstance(age_value, str):
                    # Direct ISO8601 duration string
                    onset_age = age_value
                elif isinstance(age_value, dict):
                    # Object with iso8601duration field
                    onset_age = age_value.get("iso8601duration")

            # Handle direct iso8601duration field (alternative format)
            if not onset_age and "iso8601duration" in onset:
                onset_age = onset["iso8601duration"]

            # Handle ontology class for categorical onset
            if "ontologyClass" in onset:
                onset_class = onset["ontologyClass"]
                if isinstance(onset_class, dict):
                    onset_label = onset_class.get("label")

        # If no onset specified but feature is not excluded,
        # use subject's current age as the observation/report age
        # This represents when the feature was observed, not
        # necessarily when it began
        if not onset_age and not onset_label and not feature.get("excluded", False):
            if current_age:
                onset_age = current_age
                if current_age_years:
                    onset_label = f"Observed at age {int(current_age_years)}y"
                else:
                    onset_label = "Observed"

        # Extract severity
        severity = None
        if "severity" in feature:
            severity_obj = feature.get("severity", {})
            if isinstance(severity_obj, dict):
                severity = severity_obj.get("label")

        # Extract evidence with publications
        evidence_list = []
        evidence = feature.get("evidence", [])

        for ev in evidence:
            evidence_code = ev.get("evidenceCode", {})
            reference = ev.get("reference", {})

            evidence_item = {
                "evidence_code": evidence_code.get("label"),
                "pmid": None,
                "description": None,
                "recorded_at": None,
            }

            if reference:
                ref_id = reference.get("id", "")
                if ref_id.startswith("PMID:"):
                    evidence_item["pmid"] = ref_id.replace("PMID:", "")

                evidence_item["description"] = reference.get("description")
                evidence_item["recorded_at"] = reference.get("recordedAt")

            evidence_list.append(evidence_item)

        # Determine category (simplified - could use HPO hierarchy)
        category = "other"
        if hpo_id:
            if any(x in hpo_id for x in ["HP:0000107", "HP:0003111"]):
                category = "renal"
            elif "HP:0004904" in hpo_id:
                category = "diabetes"
            elif "HP:0000079" in hpo_id or "HP:0000119" in hpo_id:
                category = "genital"

        features.append(
            {
                "hpo_id": hpo_id,
                "label": label,
                "onset_age": onset_age,
                "onset_label": onset_label,
                "category": category,
                "severity": severity,
                "excluded": feature.get("excluded", False),
                "evidence": evidence_list,
            }
        )

    return {
        "subject_id": subject_id,
        "current_age": current_age,
        "features": features,
    }
