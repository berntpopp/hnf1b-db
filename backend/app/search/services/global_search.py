"""Global unified search service.

Extracted from the monolithic ``search/services.py`` during Wave 4.
Orchestrates :class:`GlobalSearchRepository` — no SQL lives here.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.search.repositories import GlobalSearchRepository
from app.search.schemas import (
    AutocompleteResponse,
    GlobalSearchResponse,
    SearchResultItem,
)

from .pagination import PaginationParams


class GlobalSearchService:
    """Global unified search across all entity types.

    Uses the ``global_search_index`` materialised view for fast
    full-text search and autocomplete.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.repo = GlobalSearchRepository(db)

    async def search(
        self,
        query: str,
        pagination: PaginationParams,
        type_filter: str | None = None,
    ) -> GlobalSearchResponse:
        """Execute global search with pagination."""
        if not query or len(query.strip()) < 1:
            return GlobalSearchResponse(
                results=[],
                total=0,
                page=pagination.page,
                page_size=pagination.page_size,
                summary={},
            )

        results = await self.repo.search(
            query=query,
            limit=pagination.page_size,
            offset=pagination.offset,
            type_filter=type_filter,
        )

        summary = await self.repo.count(query)
        total = sum(summary.values())

        return GlobalSearchResponse(
            results=[SearchResultItem(**r) for r in results],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            summary=summary,
        )

    async def autocomplete(
        self, query: str, limit: int = 10
    ) -> AutocompleteResponse:
        """Get autocomplete suggestions.

        Returns an empty response when ``query`` is shorter than two
        characters to avoid abusing the materialised view.
        """
        if not query or len(query.strip()) < 2:
            return AutocompleteResponse(results=[])

        results = await self.repo.autocomplete(query, limit)
        return AutocompleteResponse(
            results=[SearchResultItem(**r) for r in results]
        )

    async def refresh_index(self, concurrently: bool = True) -> None:
        """Refresh the materialized view.

        Args:
            concurrently: If True, doesn't block reads during refresh.
        """
        await self.repo.refresh(concurrently)
