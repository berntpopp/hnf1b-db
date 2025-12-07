"""Search schemas - Pydantic models for search API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    """Individual search result item."""

    id: str = Field(..., description="Unique identifier")
    label: str = Field(..., description="Display label")
    type: str = Field(..., description="Entity type (Gene, Variant, Phenopacket, etc.)")
    subtype: str | None = Field(None, description="Entity subtype")
    extra_info: str | None = Field(None, description="Additional context info")
    score: float | None = Field(None, description="Search relevance score")

    model_config = {"from_attributes": True}


class AutocompleteResponse(BaseModel):
    """Response for autocomplete endpoint."""

    results: list[SearchResultItem] = Field(default_factory=list)


class GlobalSearchResponse(BaseModel):
    """Response for global search endpoint."""

    results: list[SearchResultItem] = Field(default_factory=list)
    total: int = Field(..., description="Total matching results across all types")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Results per page")
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Result counts grouped by type",
    )


class CursorPageInfo(BaseModel):
    """Cursor pagination metadata."""

    page_size: int = Field(..., alias="pageSize")
    has_next_page: bool = Field(..., alias="hasNextPage")
    has_previous_page: bool = Field(..., alias="hasPreviousPage")
    start_cursor: str | None = Field(None, alias="startCursor")
    end_cursor: str | None = Field(None, alias="endCursor")

    model_config = {"populate_by_name": True}


class PhenopacketSearchResult(BaseModel):
    """Individual phenopacket in search results."""

    id: str
    type: str = "phenopacket"
    attributes: dict[str, Any]
    meta: dict[str, Any] | None = None


class PhenopacketSearchResponse(BaseModel):
    """Response for phenopacket search endpoint."""

    data: list[PhenopacketSearchResult]
    meta: dict[str, Any] = Field(default_factory=dict)
    links: dict[str, str | None] = Field(default_factory=dict)


class FacetItem(BaseModel):
    """Individual facet value with count."""

    value: str | bool
    label: str
    count: int


class SearchFacetsResponse(BaseModel):
    """Response for search facets endpoint."""

    facets: dict[str, list[FacetItem]]
