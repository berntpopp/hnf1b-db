"""Pagination utilities for JSON:API v1.1 responses.

This module provides offset-based pagination (page[number]/page[size]) for
direct page access and navigation. All endpoints use offset pagination
for consistency and best user experience.

Usage:
    from app.utils.pagination import (
        build_offset_links,
        build_offset_response,
        parse_sort_parameter,
        # Legacy cursor functions (deprecated)
        encode_cursor,
        decode_cursor,
        build_cursor_links,
        build_cursor_response,
    )
"""

import base64
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from fastapi import HTTPException, status

from app.models.json_api import (
    # Cursor pagination models (legacy)
    CursorLinksObject,
    CursorMetaObject,
    CursorPageMeta,
    JsonApiCursorResponse,
    # Offset pagination models
    JsonApiResponse,
    LinksObject,
    MetaObject,
    PageMeta,
)

# =============================================================================
# OFFSET-BASED PAGINATION (Primary - Recommended)
# =============================================================================


def build_offset_links(
    base_url: str,
    current_page: int,
    page_size: int,
    total_pages: int,
    filters: Dict[str, Any],
    sort: Optional[str] = None,
) -> LinksObject:
    """Build offset pagination links for JSON:API response.

    Args:
        base_url: Base URL without query parameters
        current_page: Current page number (1-indexed)
        page_size: Number of items per page
        total_pages: Total number of pages
        filters: Dictionary of filter parameters to preserve
        sort: Sort parameter to preserve

    Returns:
        LinksObject with navigation links (self, first, prev, next, last)

    Example:
        >>> links = build_offset_links(
        ...     base_url="/api/v2/phenopackets/",
        ...     current_page=2,
        ...     page_size=20,
        ...     total_pages=44,
        ...     filters={"filter[sex]": "MALE"},
        ...     sort="-created_at"
        ... )
    """

    def build_url(page: int) -> str:
        params: Dict[str, Any] = {
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
        first=build_url(1),
        prev=build_url(current_page - 1) if current_page > 1 else None,
        next=build_url(current_page + 1) if current_page < total_pages else None,
        last=build_url(total_pages) if total_pages > 0 else build_url(1),
    )


def build_offset_response(
    data: List[Any],
    current_page: int,
    page_size: int,
    total_records: int,
    base_url: str,
    filters: Dict[str, Any],
    sort: Optional[str] = None,
) -> JsonApiResponse:
    """Build a complete JSON:API offset pagination response.

    Args:
        data: List of data items to return
        current_page: Current page number (1-indexed)
        page_size: Items per page
        total_records: Total count of matching records
        base_url: Base URL without query parameters
        filters: Dictionary of filter parameters
        sort: Sort parameter string

    Returns:
        JsonApiResponse with data, meta, and links

    Example:
        >>> response = build_offset_response(
        ...     data=[{"id": "1", "title": "Test"}],
        ...     current_page=1,
        ...     page_size=20,
        ...     total_records=864,
        ...     base_url="/api/v2/phenopackets",
        ...     filters={},
        ...     sort="-created_at"
        ... )
    """
    total_pages = (
        (total_records + page_size - 1) // page_size if total_records > 0 else 0
    )

    return JsonApiResponse(
        data=data,
        meta=MetaObject(
            page=PageMeta(
                currentPage=current_page,
                pageSize=page_size,
                totalPages=total_pages,
                totalRecords=total_records,
            )
        ),
        links=build_offset_links(
            base_url,
            current_page,
            page_size,
            total_pages,
            filters,
            sort,
        ),
    )


# =============================================================================
# CURSOR-BASED PAGINATION (Legacy - Deprecated)
# =============================================================================


def encode_cursor(data: Dict[str, Any]) -> str:
    """Encode cursor data to opaque Base64 token.

    The cursor contains fields that uniquely identify a record position
    for stable pagination (typically id + created_at for deterministic ordering).

    Args:
        data: Dictionary with cursor fields
              (e.g., {"id": UUID, "created_at": datetime})

    Returns:
        Base64-encoded URL-safe string

    Example:
        >>> encode_cursor({"id": uuid.UUID("..."), "created_at": dt})
        'eyJpZCI6Ii4uLiIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTAxIn0='
    """
    serializable_data = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            serializable_data[key] = str(value)
        elif hasattr(value, "__str__"):
            serializable_data[key] = str(value)
        else:
            serializable_data[key] = value

    json_str = json.dumps(serializable_data, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> Dict[str, Any]:
    """Decode cursor token to data dictionary.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        Dictionary with cursor data (id as UUID, created_at as datetime)

    Raises:
        HTTPException: If cursor format is invalid

    Example:
        >>> decode_cursor('eyJpZCI6Ii4uLiIsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTAxIn0=')
        {"id": UUID("..."), "created_at": datetime(...)}
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
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cursor format: {e}",
        )


def build_cursor_links(
    base_url: str,
    page_size: int,
    start_cursor: Optional[str],
    end_cursor: Optional[str],
    has_next: bool,
    has_prev: bool,
    filters: Dict[str, Any],
    sort: Optional[str] = None,
) -> CursorLinksObject:
    """Build cursor pagination links for JSON:API response.

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
        >>> links = build_cursor_links(
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
        params: Dict[str, Any] = {"page[size]": page_size}
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


def build_cursor_response(
    data: List[Any],
    page_size: int,
    has_next: bool,
    has_prev: bool,
    start_cursor: Optional[str],
    end_cursor: Optional[str],
    base_url: str,
    filters: Dict[str, Any],
    sort: Optional[str] = None,
    total: Optional[int] = None,
) -> JsonApiCursorResponse:
    """Build a complete JSON:API cursor pagination response.

    Args:
        data: List of data items to return
        page_size: Items per page
        has_next: Whether there's a next page
        has_prev: Whether there's a previous page
        start_cursor: Cursor for first record in current page
        end_cursor: Cursor for last record in current page
        base_url: Base URL without query parameters
        filters: Dictionary of filter parameters
        sort: Sort parameter string
        total: Total count of matching records (optional per JSON:API spec)

    Returns:
        JsonApiCursorResponse with data, meta, and links

    Example:
        >>> response = build_cursor_response(
        ...     data=[{"id": "1", "title": "Test"}],
        ...     page_size=20,
        ...     has_next=True,
        ...     has_prev=False,
        ...     start_cursor="abc123",
        ...     end_cursor="xyz789",
        ...     base_url="/api/v2/publications",
        ...     filters={},
        ...     sort="-phenopacket_count"
        ... )
    """
    return JsonApiCursorResponse(
        data=data,
        meta=CursorMetaObject(
            page=CursorPageMeta(
                pageSize=page_size,
                total=total,
                hasNextPage=has_next,
                hasPreviousPage=has_prev,
                startCursor=start_cursor,
                endCursor=end_cursor,
            )
        ),
        links=build_cursor_links(
            base_url,
            page_size,
            start_cursor,
            end_cursor,
            has_next,
            has_prev,
            filters,
            sort,
        ),
    )


def parse_sort_parameter(
    sort: Optional[str], allowed_fields: set[str]
) -> List[Tuple[str, str]]:
    """Parse JSON:API sort parameter into field/direction tuples.

    Args:
        sort: Comma-separated fields, '-' prefix for descending
        allowed_fields: Set of allowed field names for security

    Returns:
        List of (field, direction) tuples where direction is "asc" or "desc"

    Raises:
        ValueError: If a field is not in allowed_fields

    Example:
        >>> parse_sort_parameter("-year,title", {"year", "title"})
        [("year", "desc"), ("title", "asc")]
    """
    if not sort:
        return []

    result = []
    for field in sort.split(","):
        field = field.strip()
        if not field:
            continue

        if field.startswith("-"):
            direction = "desc"
            field_name = field[1:]
        elif field.startswith("+"):
            direction = "asc"
            field_name = field[1:]
        else:
            direction = "asc"
            field_name = field

        if field_name not in allowed_fields:
            allowed = ", ".join(sorted(allowed_fields))
            raise ValueError(f"Invalid sort field: {field_name}. Allowed: {allowed}")

        result.append((field_name, direction))

    return result


def calculate_range_text(current_start: int, current_end: int, has_more: bool) -> str:
    """Calculate display text for cursor pagination range.

    Since cursor pagination doesn't know total count, we show
    a relative position indicator.

    Args:
        current_start: Index of first item on current page (1-indexed)
        current_end: Index of last item on current page
        has_more: Whether there are more pages

    Returns:
        Range text like "1-20" or "21-40 ..."

    Example:
        >>> calculate_range_text(1, 20, True)
        "1-20 ..."
        >>> calculate_range_text(21, 40, False)
        "21-40"
    """
    if has_more:
        return f"{current_start}-{current_end} ..."
    return f"{current_start}-{current_end}"
