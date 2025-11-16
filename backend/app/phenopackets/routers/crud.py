"""CRUD operations for phenopackets.

Basic create, read, update, delete operations for phenopacket resources.
"""

import base64
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.database import get_db
from app.models.json_api import (
    CursorLinksObject,
    CursorMetaObject,
    CursorPageMeta,
    JsonApiCursorResponse,
    JsonApiResponse,
    LinksObject,
    MetaObject,
    PageMeta,
)
from app.phenopackets.models import (
    Phenopacket,
    PhenopacketCreate,
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

router = APIRouter(tags=["phenopackets-crud"])

validator = PhenopacketValidator()
sanitizer = PhenopacketSanitizer()
logger = logging.getLogger(__name__)

# Force reload to pick up JSON:API changes


@router.get("/")
async def list_phenopackets(
    # JSON:API cursor pagination parameters
    page_after: Optional[str] = Query(
        None,
        alias="page[after]",
        description="Cursor for next page (opaque token)",
    ),
    page_before: Optional[str] = Query(
        None,
        alias="page[before]",
        description="Cursor for previous page (opaque token)",
    ),
    # JSON:API offset pagination parameters
    page_number: int = Query(
        1, alias="page[number]", ge=1, description="Page number (1-indexed)"
    ),
    page_size: int = Query(
        100,
        alias="page[size]",
        ge=1,
        le=1000,
        description="Items per page (max: 1000)",
    ),
    # JSON:API filter parameters
    filter_sex: Optional[str] = Query(
        None, alias="filter[sex]", description="Filter by subject sex"
    ),
    filter_has_variants: Optional[bool] = Query(
        None,
        alias="filter[has_variants]",
        description="Filter by variant presence",
    ),
    # JSON:API sort parameter
    sort: Optional[str] = Query(
        None, description="Comma-separated fields, prefix with '-' for desc"
    ),
    # Legacy parameters (backwards compatibility - deprecated)
    skip: Optional[int] = Query(
        None, ge=0, deprecated=True, description="DEPRECATED: Use page[number]"
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=1000,
        deprecated=True,
        description="DEPRECATED: Use page[size]",
    ),
    sex: Optional[str] = Query(
        None, deprecated=True, description="DEPRECATED: Use filter[sex]"
    ),
    has_variants: Optional[bool] = Query(
        None,
        deprecated=True,
        description="DEPRECATED: Use filter[has_variants]",
    ),
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    """List phenopackets with JSON:API pagination, filtering, and sorting.

    **Pagination (JSON:API standard):**

    Two pagination strategies are supported:

    1. **Cursor-based pagination** (recommended for stable browsing):
       - `page[after]`: Cursor token for next page
       - `page[before]`: Cursor token for previous page
       - `page[size]`: Items per page (default: 100, max: 1000)
       - Returns stable results even when data changes
       - Cursors are opaque tokens (do not parse)

    2. **Offset-based pagination** (simple cases only):
       - `page[number]`: Page number (1-indexed, default: 1)
       - `page[size]`: Items per page (default: 100, max: 1000)
       - May return inconsistent results if data changes during browsing

    **Filtering:**
    - `filter[sex]`: Filter by subject sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
    - `filter[has_variants]`: Filter by variant presence (true/false)

    **Sorting:**
    - `sort`: Comma-separated fields (e.g., `-created_at,subject_id`)
    - Prefix with `-` for descending order
    - Supported fields: `created_at`, `subject_id`, `subject_sex`

    **Response Format:**
    Returns JSON:API compliant response with:
    - `data`: Array of phenopacket documents
    - `meta.page` or `meta.cursor`: Pagination metadata
    - `links`: Navigation links (self, first, prev, next, last)

    **Examples:**
    ```
    # Cursor pagination (stable results)
    GET /phenopackets?page[size]=20
    GET /phenopackets?page[after]=eyJpZCI6ImFiYzEyMyIsI...&page[size]=20

    # Offset pagination (simple)
    GET /phenopackets?page[number]=1&page[size]=20
    GET /phenopackets?page[number]=2&page[size]=50&filter[sex]=MALE
    GET /phenopackets?page[number]=1&page[size]=100&sort=-created_at
    GET /phenopackets?page[number]=3&page[size]=20&filter[has_variants]=true
    ```

    **Backwards Compatibility:**
    Legacy `skip`, `limit`, `sex`, `has_variants` parameters still work
    but are deprecated. They will be converted to JSON:API parameters.
    """
    # Handle backwards compatibility: convert legacy pagination to page-based
    if skip is not None or limit is not None:
        actual_skip = skip if skip is not None else (page_number - 1) * page_size
        actual_limit = limit if limit is not None else page_size
        page_number = (actual_skip // actual_limit) + 1
        page_size = actual_limit

    # Handle legacy filter parameters
    filter_sex = filter_sex or sex
    if filter_has_variants is None:
        filter_has_variants = has_variants

    # Detect pagination strategy: cursor-based vs offset-based
    use_cursor_pagination = page_after is not None or page_before is not None

    if use_cursor_pagination:
        # Route to cursor-based pagination (stable, recommended)
        return await _list_with_cursor_pagination(
            page_after=page_after,
            page_before=page_before,
            page_size=page_size,
            filter_sex=filter_sex,
            filter_has_variants=filter_has_variants,
            sort=sort,
            db=db,
            request=request,
        )

    # Otherwise, use offset-based pagination (legacy, simple cases)
    # Build query (exclude soft-deleted records)
    query = select(Phenopacket).where(Phenopacket.deleted_at.is_(None))

    # Apply filters using query builder utilities
    query = add_sex_filter(query, filter_sex)
    query = add_has_variants_filter(query, filter_has_variants)

    # Count total records (with filters applied)
    count_query = select(func.count()).select_from(query.alias())
    total_records = await db.scalar(count_query) or 0

    # Apply sorting
    if sort:
        order_clauses = parse_sort_parameter(sort)
        for order_clause in order_clauses:
            query = query.order_by(order_clause)
    else:
        # Default sort by created_at DESC
        query = query.order_by(Phenopacket.created_at.desc())

    # Apply pagination
    offset = (page_number - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    phenopackets = result.scalars().all()

    # Calculate pagination metadata
    if total_records > 0:
        total_pages = (total_records + page_size - 1) // page_size
    else:
        total_pages = 0

    # Build response
    meta = MetaObject(
        page=PageMeta(
            currentPage=page_number,
            pageSize=page_size,
            totalPages=total_pages,
            totalRecords=total_records,
        )
    )

    # Build pagination links
    base_url = str(request.url).split("?")[0] if request else "/api/v2/phenopackets/"
    links = build_pagination_links(
        base_url=base_url,
        current_page=page_number,
        page_size=page_size,
        total_pages=total_pages,
        filters={
            "filter[sex]": filter_sex,
            "filter[has_variants]": filter_has_variants,
        },
        sort=sort,
    )

    # Convert phenopackets to response format
    # Use the phenopacket JSONB directly (GA4GH Phenopackets v2 format)
    data = [pp.phenopacket for pp in phenopackets]

    return JsonApiResponse(
        data=data,
        meta=meta,
        links=links,
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

        # Get the sort column (no special handling for subject_id)
        # Note: Previously tried numeric casting for subject_id, but this fails
        # with non-numeric IDs like "integration_patient_000" in tests.
        # Alphabetic sorting works for both numeric and non-numeric IDs.
        sort_column = allowed_fields[field_name]

        # Apply sort direction
        if descending:
            order_clauses.append(sort_column.desc())
        else:
            order_clauses.append(sort_column.asc())

    return order_clauses


def build_pagination_links(
    base_url: str,
    current_page: int,
    page_size: int,
    total_pages: int,
    filters: dict,
    sort: Optional[str] = None,
) -> LinksObject:
    """Build JSON:API pagination links.

    Args:
        base_url: Base URL without query parameters
        current_page: Current page number (1-indexed)
        page_size: Items per page
        total_pages: Total number of pages
        filters: Dictionary of filter parameters
        sort: Sort parameter string

    Returns:
        LinksObject with self, first, prev, next, last links
    """

    def build_url(page: int) -> str:
        params: dict[str, Any] = {
            "page[number]": page,
            "page[size]": page_size,
        }
        # Add filters (exclude None values)
        for key, value in filters.items():
            if value is not None:
                params[key] = value
        # Add sort
        if sort:
            params["sort"] = sort

        return f"{base_url}?{urlencode(params)}"

    return LinksObject(
        self=build_url(current_page),
        first=build_url(1) if total_pages > 0 else build_url(current_page),
        prev=build_url(current_page - 1) if current_page > 1 else None,
        next=build_url(current_page + 1) if current_page < total_pages else None,
        last=build_url(total_pages) if total_pages > 0 else build_url(current_page),
    )


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


@router.get("/{phenopacket_id}", response_model=Dict)
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single phenopacket by ID (excludes soft-deleted)."""
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

    return phenopacket.phenopacket


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

    # Optimistic locking check
    if existing.revision != phenopacket_data.revision:
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
    change_reason: str = Query(
        ..., min_length=1, description="Reason for deletion (required for audit)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Soft delete a phenopacket with audit trail (requires curator role).

    Implements soft delete pattern to preserve research data integrity.
    Records are marked as deleted but remain in the database for audit purposes.

    Args:
        phenopacket_id: Phenopacket identifier
        change_reason: Reason for deletion (required for audit trail)
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
            change_reason=change_reason,
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


# ===== Cursor Pagination Implementation =====


async def _list_with_cursor_pagination(
    page_after: Optional[str],
    page_before: Optional[str],
    page_size: int,
    filter_sex: Optional[str],
    filter_has_variants: Optional[bool],
    sort: Optional[str],
    db: AsyncSession,
    request: Request,
) -> JsonApiCursorResponse:
    """Implement cursor-based pagination for stable browsing.

    Cursor pagination prevents duplicate/missing records when data changes
    during pagination (e.g., records added/deleted while user browses).

    Args:
        page_after: Cursor for next page (get records after this cursor)
        page_before: Cursor for previous page (get records before this cursor)
        page_size: Number of items per page
        filter_sex: Filter by subject sex
        filter_has_variants: Filter by variant presence
        sort: Sort parameter (currently ignored, uses created_at for stability)
        db: Database session
        request: FastAPI request object

    Returns:
        JsonApiCursorResponse with data, metadata, and navigation links

    Cursor format:
        Base64-encoded JSON: {"id": UUID, "created_at": ISO-8601}
        Example: {"id": "123e4567-...", "created_at": "2025-01-01T..."}

    Algorithm:
        1. Decode cursor (if provided)
        2. Build base query with filters
        3. Add cursor WHERE condition (created_at/id comparison)
        4. Apply stable sort (created_at ASC/DESC + id ASC/DESC)
        5. Fetch page_size + 1 records (to detect next page)
        6. Generate start/end cursors for current page
        7. Build navigation links with cursors
    """
    # Decode cursor and determine direction
    cursor_data = None
    if page_after:
        cursor_data = decode_cursor(page_after)
        is_forward = True
    elif page_before:
        cursor_data = decode_cursor(page_before)
        is_forward = False
    else:
        is_forward = True

    # Build base query (exclude soft-deleted)
    query = select(Phenopacket).where(Phenopacket.deleted_at.is_(None))

    # Apply filters
    query = add_sex_filter(query, filter_sex)
    query = add_has_variants_filter(query, filter_has_variants)

    # Apply cursor condition for range-based pagination
    if cursor_data:
        cursor_created_at = cursor_data["created_at"]
        cursor_id = cursor_data["id"]

        if is_forward:
            # page[after]: Get records AFTER cursor
            # created_at > cursor.created_at OR
            # (created_at = cursor.created_at AND id > cursor.id)
            query = query.where(
                or_(
                    Phenopacket.created_at > cursor_created_at,
                    and_(
                        Phenopacket.created_at == cursor_created_at,
                        Phenopacket.id > cursor_id,
                    ),
                )
            )
        else:
            # page[before]: Get records BEFORE cursor
            # created_at < cursor.created_at OR
            # (created_at = cursor.created_at AND id < cursor.id)
            query = query.where(
                or_(
                    Phenopacket.created_at < cursor_created_at,
                    and_(
                        Phenopacket.created_at == cursor_created_at,
                        Phenopacket.id < cursor_id,
                    ),
                )
            )

    # Apply stable sort (cursor pagination requires deterministic order)
    # Always sort by created_at + id for stability
    if is_forward:
        query = query.order_by(Phenopacket.created_at.asc(), Phenopacket.id.asc())
    else:
        # For page[before], reverse sort to get records before cursor
        query = query.order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())

    # Fetch one extra record to check if there's a next/prev page
    query = query.limit(page_size + 1)

    # Execute query
    result = await db.execute(query)
    phenopackets = result.scalars().all()

    # Check for more pages
    has_more = len(phenopackets) > page_size
    if has_more:
        phenopackets = phenopackets[:page_size]  # Remove the extra record

    # Reverse results if page[before] was used (to maintain correct order)
    if not is_forward:
        phenopackets = list(reversed(phenopackets))

    # Generate cursors for current page
    start_cursor = None
    end_cursor = None
    if phenopackets:
        start_cursor = encode_cursor(
            {
                "id": phenopackets[0].id,
                "created_at": phenopackets[0].created_at.isoformat(),
            }
        )
        end_cursor = encode_cursor(
            {
                "id": phenopackets[-1].id,
                "created_at": phenopackets[-1].created_at.isoformat(),
            }
        )

    # Build pagination metadata
    meta = CursorMetaObject(
        page=CursorPageMeta(
            pageSize=page_size,
            # has_next: If forward and extra record found, there's next page
            hasNextPage=has_more if is_forward else (cursor_data is not None),
            # has_prev: If forward pagination and cursor exists, there's a prev page
            hasPreviousPage=(cursor_data is not None) if is_forward else has_more,
            startCursor=start_cursor,
            endCursor=end_cursor,
        )
    )

    # Build navigation links
    base_url = str(request.url).split("?")[0] if request else "/api/v2/phenopackets/"
    links = build_cursor_pagination_links(
        base_url=base_url,
        page_size=page_size,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        has_next=meta.page.has_next_page,
        has_prev=meta.page.has_previous_page,
        filters={
            "filter[sex]": filter_sex,
            "filter[has_variants]": filter_has_variants,
        },
        sort=sort,
    )

    return JsonApiCursorResponse(
        data=[p.phenopacket for p in phenopackets],
        meta=meta,
        links=links,
    )


# ===== Cursor Pagination Helper Functions =====


def encode_cursor(data: dict) -> str:
    """Encode cursor data to opaque Base64 token.

    Args:
        data: Dictionary with cursor fields
              (e.g., {"id": UUID, "created_at": ISO-8601})

    Returns:
        Base64-encoded URL-safe string

    Example:
        >>> encode_cursor({"id": "123e4567...", "created_at": "2025-01..."})
        'eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCIsIm...'
    """
    # Convert UUID objects to strings for JSON serialization
    serializable_data = {}
    for key, value in data.items():
        if hasattr(value, "__str__"):
            serializable_data[key] = str(value)
        else:
            serializable_data[key] = value

    json_str = json.dumps(serializable_data, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode cursor token to data dictionary.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        Dictionary with cursor data

    Raises:
        HTTPException: If cursor format is invalid

    Example:
        >>> decode_cursor('eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LT...')
        {"id": "123e4567-e89b-12d3-a456-426614174000", "created_at": ...}
    """
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(json_str)

        # Convert created_at string back to datetime
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )

        # Convert id string back to UUID
        if "id" in data:
            data["id"] = uuid.UUID(data["id"])

        return data
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid cursor format: {str(e)}")


def build_cursor_pagination_links(
    base_url: str,
    page_size: int,
    start_cursor: Optional[str],
    end_cursor: Optional[str],
    has_next: bool,
    has_prev: bool,
    filters: dict,
    sort: Optional[str] = None,
) -> CursorLinksObject:
    """Build cursor pagination links.

    Args:
        base_url: Base URL without query parameters
        page_size: Number of items per page
        start_cursor: Cursor for first record in current page
        end_cursor: Cursor for last record in current page
        has_next: Whether there's a next page
        has_prev: Whether there's a previous page
        filters: Dictionary of filter parameters to preserve
        sort: Sort parameter to preserve

    Returns:
        CursorLinksObject with navigation links

    Example:
        >>> links = build_cursor_pagination_links(
        ...     base_url="/api/v2/phenopackets/",
        ...     page_size=20,
        ...     start_cursor="eyJpZCI6MX0=",
        ...     end_cursor="eyJpZCI6MjB9",
        ...     has_next=True,
        ...     has_prev=False,
        ...     filters={"filter[sex]": "MALE"},
        ...     sort="-created_at"
        ... )
    """

    def build_url(
        cursor_param: Optional[str] = None, cursor_value: Optional[str] = None
    ) -> str:
        params: dict[str, Any] = {"page[size]": page_size}
        if cursor_param and cursor_value:
            params[cursor_param] = cursor_value
        # Add filters (exclude None values)
        for key, value in filters.items():
            if value is not None:
                params[key] = value
        # Add sort
        if sort:
            params["sort"] = sort
        return f"{base_url}?{urlencode(params)}"

    return CursorLinksObject(
        self=build_url(),
        first=build_url(),
        prev=build_url("page[before]", start_cursor) if has_prev else None,
        next=build_url("page[after]", end_cursor) if has_next else None,
    )


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
        regex="^(MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)$",
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
