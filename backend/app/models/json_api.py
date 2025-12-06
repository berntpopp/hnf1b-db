"""JSON:API response envelope models.

This module implements JSON:API v1.1 compliant response structures
for wrapping GA4GH Phenopackets data with pagination metadata and links.

References:
- JSON:API v1.1 Specification: https://jsonapi.org/format/1.1/
- GA4GH Phenopackets v2: https://phenopacket-schema.readthedocs.io/
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Generic type for wrapped data
T = TypeVar("T")


class PageMeta(BaseModel):
    """Pagination metadata for offset-based pagination.

    Attributes:
        current_page: Current page number (1-indexed)
        page_size: Number of items per page
        total_pages: Total number of pages available
        total_records: Total number of records matching filters
    """

    current_page: int = Field(..., alias="currentPage", ge=1)
    page_size: int = Field(..., alias="pageSize", ge=1, le=1000)
    total_pages: int = Field(..., alias="totalPages", ge=0)
    total_records: int = Field(..., alias="totalRecords", ge=0)

    model_config = ConfigDict(populate_by_name=True)


class MetaObject(BaseModel):
    """JSON:API meta object containing pagination metadata."""

    page: PageMeta


class LinksObject(BaseModel):
    """JSON:API links object for pagination navigation.

    Attributes:
        self: Link to current page
        first: Link to first page
        prev: Link to previous page (None if on first page)
        next: Link to next page (None if on last page)
        last: Link to last page
    """

    self: str
    first: str
    prev: Optional[str] = None
    next: Optional[str] = None
    last: str


class JsonApiResponse(BaseModel, Generic[T]):
    """JSON:API compliant response envelope.

    Wraps GA4GH Phenopackets data with pagination metadata and navigation links.
    This allows the frontend to display pagination info like "Page 1 of 44"
    and intelligently enable/disable navigation buttons.

    Type Parameters:
        T: The type of data being wrapped (e.g., PhenopacketDocument)

    Attributes:
        data: List of data items (e.g., phenopackets)
        meta: Pagination metadata
        links: Navigation links for pagination

    Example:
        >>> response = JsonApiResponse(
        ...     data=[phenopacket1, phenopacket2, ...],
        ...     meta=MetaObject(page=PageMeta(
        ...         current_page=1,
        ...         page_size=20,
        ...         total_pages=44,
        ...         total_records=864
        ...     )),
        ...     links=LinksObject(
        ...         self="/phenopackets?page[number]=1&page[size]=20",
        ...         first="/phenopackets?page[number]=1&page[size]=20",
        ...         prev=None,
        ...         next="/phenopackets?page[number]=2&page[size]=20",
        ...         last="/phenopackets?page[number]=44&page[size]=20"
        ...     )
        ... )
    """

    data: List[T]
    meta: MetaObject
    links: LinksObject


class CursorPageMeta(BaseModel):
    """Cursor pagination metadata for stable pagination.

    Cursor pagination prevents duplicate/missing records when data changes
    during pagination (e.g., records added/deleted while user browses).

    Per JSON:API Cursor Pagination Profile, includes optional total count.
    Reference: https://jsonapi.org/profiles/ethanresnick/cursor-pagination/

    Attributes:
        page_size: Number of items per page
        total: Total number of records matching filters (optional per spec)
        has_next_page: Whether there are more records after current page
        has_previous_page: Whether there are records before current page
        start_cursor: Opaque cursor pointing to first record in page
        end_cursor: Opaque cursor pointing to last record in page
    """

    page_size: int = Field(..., alias="pageSize", ge=1, le=1000)
    total: Optional[int] = Field(
        None, ge=0, description="Total records matching filters"
    )
    has_next_page: bool = Field(..., alias="hasNextPage")
    has_previous_page: bool = Field(..., alias="hasPreviousPage")
    start_cursor: Optional[str] = Field(None, alias="startCursor")
    end_cursor: Optional[str] = Field(None, alias="endCursor")

    model_config = ConfigDict(populate_by_name=True)


class CursorMetaObject(BaseModel):
    """JSON:API meta object for cursor pagination."""

    page: CursorPageMeta


class CursorLinksObject(BaseModel):
    """JSON:API links object for cursor pagination navigation.

    Attributes:
        self: Link to current page
        first: Link to first page
        prev: Link to previous page (None if no previous page)
        next: Link to next page (None if no next page)
    """

    self: str
    first: str
    prev: Optional[str] = None
    next: Optional[str] = None


class JsonApiCursorResponse(BaseModel, Generic[T]):
    """JSON:API response with cursor-based pagination.

    Used for stable pagination when data changes frequently.
    Cursor tokens are opaque Base64-encoded strings that reference
    specific records in the result set.

    Type Parameters:
        T: The type of data being wrapped

    Attributes:
        data: List of data items
        meta: Cursor pagination metadata
        links: Navigation links with cursor parameters

    Example:
        >>> response = JsonApiCursorResponse(
        ...     data=[phenopacket1, phenopacket2, ...],
        ...     meta=CursorMetaObject(page=CursorPageMeta(
        ...         page_size=20,
        ...         has_next_page=True,
        ...         has_previous_page=False,
        ...         start_cursor="eyJpZCI6MX0=",
        ...         end_cursor="eyJpZCI6MjB9"
        ...     )),
        ...     links=CursorLinksObject(
        ...         self="/phenopackets?page[size]=20",
        ...         first="/phenopackets?page[size]=20",
        ...         prev=None,
        ...         next="/phenopackets?page[size]=20&page[after]=eyJpZCI6MjB9"
        ...     )
        ... )
    """

    data: List[T]
    meta: CursorMetaObject
    links: CursorLinksObject
