"""CRUD operations for phenopackets.

Basic create, read, update, delete operations for phenopacket resources.
"""

import base64
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
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

router = APIRouter(prefix="/api/v2/phenopackets", tags=["phenopackets-crud"])

validator = PhenopacketValidator()
sanitizer = PhenopacketSanitizer()

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
    # Build query
    query = select(Phenopacket)

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
        if field.startswith("-"):
            # Descending
            field_name = field[1:]
            if field_name not in allowed_fields:
                allowed = ", ".join(allowed_fields.keys())
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field: {field_name}. Allowed: {allowed}",
                )
            order_clauses.append(allowed_fields[field_name].desc())
        else:
            # Ascending
            if field not in allowed_fields:
                allowed = ", ".join(allowed_fields.keys())
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field: {field}. Allowed: {allowed}",
                )
            order_clauses.append(allowed_fields[field].asc())

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

    # Single query for all phenopackets (no N+1)
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id.in_(ids))
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
    """Get a single phenopacket by ID."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return phenopacket.phenopacket


@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new phenopacket.

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
    current_user=Depends(get_current_user),
):
    """Update an existing phenopacket."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

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

    try:
        await db.commit()
        await db.refresh(existing)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return build_phenopacket_response(existing)


@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a phenopacket."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    await db.delete(phenopacket)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"message": "Phenopacket deleted successfully"}


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

    # Build base query
    query = select(Phenopacket)

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
        raise HTTPException(
            status_code=400, detail=f"Invalid cursor format: {str(e)}"
        )


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
