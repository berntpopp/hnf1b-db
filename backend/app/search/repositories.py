"""Search repositories - Data access layer for search operations.

Following the Repository Pattern for clean separation between
business logic and data access.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class GlobalSearchRepository:
    """Repository for global materialized view search.

    Uses PostgreSQL full-text search with websearch_to_tsquery for
    Google-like query syntax support (quotes, OR, -exclude).
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search global index with optional type filter.

        Args:
            query: Search query string
            limit: Maximum results to return
            offset: Pagination offset
            type_filter: Optional filter by entity type

        Returns:
            List of search result dictionaries
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        filter_clause = ""

        if type_filter:
            filter_clause = "AND type = :type_filter"
            params["type_filter"] = type_filter

        sql = text(f"""
            SELECT id, label, type, subtype, extra_info,
                   ts_rank(search_vector,
                           websearch_to_tsquery('english', :query)) as score
            FROM global_search_index
            WHERE search_vector @@ websearch_to_tsquery('english', :query)
            {filter_clause}
            ORDER BY score DESC, label ASC
            LIMIT :limit OFFSET :offset
        """)

        result = await self.db.execute(sql, params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def count(self, query: str, type_filter: str | None = None) -> dict[str, int]:
        """Get counts grouped by type.

        Args:
            query: Search query string
            type_filter: Optional filter (not used for grouping)

        Returns:
            Dictionary mapping type names to counts
        """
        sql = text("""
            SELECT type, COUNT(*) as count
            FROM global_search_index
            WHERE search_vector @@ websearch_to_tsquery('english', :query)
            GROUP BY type
            ORDER BY count DESC
        """)
        result = await self.db.execute(sql, {"query": query})
        rows = result.fetchall()
        return {str(r._mapping["type"]): int(r._mapping["count"]) for r in rows}

    async def autocomplete(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fast autocomplete using trigram + prefix matching.

        Prioritizes:
        1. Prefix matches (ILIKE 'query%')
        2. High similarity matches (pg_trgm)

        Args:
            query: Partial search term
            limit: Maximum suggestions to return

        Returns:
            List of autocomplete suggestions
        """
        sql = text("""
            SELECT id, label, type, subtype, extra_info,
                   similarity(label, :query) as score
            FROM global_search_index
            WHERE label ILIKE :prefix
               OR label % :query
            ORDER BY
                CASE WHEN label ILIKE :prefix THEN 0 ELSE 1 END,
                score DESC,
                label ASC
            LIMIT :limit
        """)

        result = await self.db.execute(
            sql,
            {
                "query": query,
                "prefix": f"{query}%",
                "limit": limit,
            },
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def refresh(self, concurrently: bool = True) -> None:
        """Refresh the materialized view.

        Args:
            concurrently: If True, doesn't block reads during refresh.
                         Requires a unique index on the MV.
        """
        keyword = "CONCURRENTLY" if concurrently else ""
        refresh_sql = f"REFRESH MATERIALIZED VIEW {keyword} global_search_index"
        await self.db.execute(text(refresh_sql))
        await self.db.commit()


class PhenopacketSearchRepository:
    """Repository for phenopacket-specific search.

    Uses direct table queries for detailed filtering and
    cursor-based pagination for stable results.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def search(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        cursor_data: dict[str, Any] | None = None,
        is_backward: bool = False,
    ) -> list[dict[str, Any]]:
        """Search phenopackets with filters and cursor pagination.

        Args:
            query: Optional full-text search query
            filters: Dict of filter conditions (hpo_id, sex, gene, pmid)
            limit: Maximum results to return
            cursor_data: Cursor data for pagination (created_at, id)
            is_backward: True if paginating backwards

        Returns:
            List of phenopacket search results
        """
        import json

        filters = filters or {}
        params: dict[str, Any] = {"limit": limit + 1}  # +1 to detect more pages
        conditions = ["deleted_at IS NULL"]
        select_extra = ""

        # Full-text search
        if query:
            select_extra = (
                ", ts_rank(search_vector, plainto_tsquery('english', :query)) AS rank"
            )
            conditions.append("search_vector @@ plainto_tsquery('english', :query)")
            params["query"] = query

        # HPO filter
        if filters.get("hpo_id"):
            conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": filters["hpo_id"]}}])

        # Sex filter
        if filters.get("sex"):
            conditions.append("subject_sex = :sex")
            params["sex"] = filters["sex"]

        # Gene filter
        if filters.get("gene"):
            conditions.append("phenopacket->'interpretations' @> :gene_filter")
            params["gene_filter"] = json.dumps(
                [
                    {
                        "diagnosis": {
                            "genomicInterpretations": [
                                {
                                    "variantInterpretation": {
                                        "variationDescriptor": {
                                            "geneContext": {"symbol": filters["gene"]}
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            )

        # PMID filter
        if filters.get("pmid"):
            pmid = filters["pmid"]
            if not pmid.startswith("PMID:"):
                pmid = f"PMID:{pmid}"
            pmid_cond = "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            conditions.append(pmid_cond)
            params["pmid_filter"] = json.dumps([{"id": pmid}])

        # Cursor pagination
        if cursor_data:
            cursor_created_at = cursor_data.get("created_at")
            cursor_id = cursor_data.get("id")
            if cursor_created_at and cursor_id:
                if is_backward:
                    conditions.append("""(
                        created_at > :cursor_created_at
                        OR (created_at = :cursor_created_at AND id > :cursor_id)
                    )""")
                else:
                    conditions.append("""(
                        created_at < :cursor_created_at
                        OR (created_at = :cursor_created_at AND id < :cursor_id)
                    )""")
                params["cursor_created_at"] = cursor_created_at
                params["cursor_id"] = str(cursor_id)

        where_clause = " AND ".join(conditions)

        # Order by
        if query:
            order_by = "ORDER BY rank DESC, created_at DESC, id DESC"
        else:
            order_by = "ORDER BY created_at DESC, id DESC"

        if is_backward:
            order_by = order_by.replace("DESC", "ASC")

        sql = text(f"""
            SELECT id, phenopacket_id, phenopacket, created_at{select_extra}
            FROM phenopackets
            WHERE {where_clause}
            {order_by}
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def count(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count matching phenopackets.

        Args:
            query: Optional full-text search query
            filters: Dict of filter conditions

        Returns:
            Total count of matching records
        """
        import json

        filters = filters or {}
        params: dict[str, Any] = {}
        conditions = ["deleted_at IS NULL"]

        if query:
            conditions.append("search_vector @@ plainto_tsquery('english', :query)")
            params["query"] = query

        if filters.get("hpo_id"):
            conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": filters["hpo_id"]}}])

        if filters.get("sex"):
            conditions.append("subject_sex = :sex")
            params["sex"] = filters["sex"]

        if filters.get("gene"):
            conditions.append("phenopacket->'interpretations' @> :gene_filter")
            params["gene_filter"] = json.dumps(
                [
                    {
                        "diagnosis": {
                            "genomicInterpretations": [
                                {
                                    "variantInterpretation": {
                                        "variationDescriptor": {
                                            "geneContext": {"symbol": filters["gene"]}
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            )

        if filters.get("pmid"):
            pmid = filters["pmid"]
            if not pmid.startswith("PMID:"):
                pmid = f"PMID:{pmid}"
            pmid_cond = "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            conditions.append(pmid_cond)
            params["pmid_filter"] = json.dumps([{"id": pmid}])

        where_clause = " AND ".join(conditions)

        count_sql = f"SELECT COUNT(*) FROM phenopackets WHERE {where_clause}"
        sql = text(count_sql)
        result = await self.db.execute(sql, params)
        return result.scalar() or 0
