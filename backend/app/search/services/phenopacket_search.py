"""Phenopacket-specific advanced search service.

Extracted from the monolithic ``search/services.py`` during Wave 4.
Wraps :class:`PhenopacketSearchRepository` with cursor-based
pagination, filter composition, and facet delegation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.search.repositories import PhenopacketSearchRepository
from app.utils.pagination import decode_cursor, encode_cursor

from .facet import FacetService


class PhenopacketSearchService:
    """Phenopacket-specific advanced search.

    Supports:

    - Full-text search
    - HPO term filtering
    - Sex filtering
    - Gene symbol filtering
    - Publication PMID filtering
    - Cursor-based pagination for stable results
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.repo = PhenopacketSearchRepository(db)
        self.db = db

    async def search(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
        page_size: int = 20,
        cursor_after: str | None = None,
        cursor_before: str | None = None,
    ) -> dict[str, Any]:
        """Search phenopackets with filters and cursor pagination.

        Returns a JSON:API-ready dict containing ``data``, ``meta``,
        and ``links``. Pagination cursors are opaque base64 blobs
        encoded by :func:`encode_cursor`.
        """
        filters: dict[str, Any] = {}
        if hpo_id:
            filters["hpo_id"] = hpo_id
        if sex:
            filters["sex"] = sex
        if gene:
            filters["gene"] = gene
        if pmid:
            filters["pmid"] = pmid

        # Handle cursor pagination.
        is_backward = cursor_before is not None
        cursor_data = None

        if cursor_after:
            cursor_data = decode_cursor(cursor_after)
        elif cursor_before:
            cursor_data = decode_cursor(cursor_before)

        rows = await self.repo.search(
            query=query,
            filters=filters if filters else None,
            limit=page_size,
            cursor_data=cursor_data,
            is_backward=is_backward,
        )

        has_more = len(rows) > page_size
        if has_more:
            rows = rows[:page_size]

        if is_backward:
            rows = list(reversed(rows))

        # Determine has_next / has_prev.
        if is_backward:
            has_next = True  # We came from a next page
            has_prev = has_more
        elif cursor_after:
            has_next = has_more
            has_prev = True  # We came from a previous page
        else:
            # First page
            has_next = has_more
            has_prev = False

        # Build cursors.
        start_cursor = end_cursor = None
        if rows:
            start_cursor = encode_cursor(
                {
                    "created_at": rows[0]["created_at"],
                    "id": rows[0]["id"],
                }
            )
            end_cursor = encode_cursor(
                {
                    "created_at": rows[-1]["created_at"],
                    "id": rows[-1]["id"],
                }
            )

        # Format response data.
        data = []
        for row in rows:
            result = {
                "id": row["phenopacket_id"],
                "type": "phenopacket",
                "attributes": row["phenopacket"],
            }
            if query and "rank" in row:
                result["meta"] = {"search_rank": row["rank"]}
            data.append(result)

        return {
            "data": data,
            "meta": {
                "page": {
                    "pageSize": page_size,
                    "hasNextPage": has_next,
                    "hasPreviousPage": has_prev,
                    "startCursor": start_cursor,
                    "endCursor": end_cursor,
                }
            },
            "links": self._build_links(
                query=query,
                filters=filters,
                page_size=page_size,
                has_next=has_next,
                has_prev=has_prev,
                start_cursor=start_cursor,
                end_cursor=end_cursor,
            ),
        }

    def _build_links(
        self,
        query: str | None,
        filters: dict[str, Any],
        page_size: int,
        has_next: bool,
        has_prev: bool,
        start_cursor: str | None,
        end_cursor: str | None,
    ) -> dict[str, str | None]:
        """Build pagination links for the JSON:API envelope."""
        base = "/api/v2/phenopackets/search"

        params = []
        if query:
            params.append(f"q={query}")
        for key, value in filters.items():
            params.append(f"{key}={value}")
        params.append(f"page[size]={page_size}")

        param_str = "&".join(params)

        prev_link = None
        next_link = None
        if has_prev and start_cursor:
            prev_link = f"{base}?{param_str}&page[before]={start_cursor}"
        if has_next and end_cursor:
            next_link = f"{base}?{param_str}&page[after]={end_cursor}"

        return {
            "self": f"{base}?{param_str}",
            "first": f"{base}?{param_str}",
            "prev": prev_link,
            "next": next_link,
        }

    async def get_facets(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Delegate facet computation to :class:`FacetService`."""
        facet_service = FacetService(self.db)
        return await facet_service.get_facets(
            query=query,
            hpo_id=hpo_id,
            sex=sex,
            gene=gene,
            pmid=pmid,
        )
