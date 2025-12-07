from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.search.schemas import SearchResultItem

class GlobalSearchService:
    @staticmethod
    async def autocomplete(
        db: AsyncSession, query: str, limit: int = 10
    ) -> List[SearchResultItem]:
        """
        Autocomplete suggestions using Trigram similarity and Prefix matching.
        """
        # We prioritize:
        # 1. Prefix matches (ILIKE 'query%')
        # 2. High similarity matches (pg_trgm)
        
        sql = text("""
            SELECT id, label, type, subtype, extra_info,
                   similarity(label, :query) as sim
            FROM global_search_index
            WHERE label ILIKE :prefix 
               OR label % :query
            ORDER BY 
                CASE WHEN label ILIKE :prefix THEN 1 ELSE 2 END,
                sim DESC, 
                label ASC
            LIMIT :limit
        """)
        
        result = await db.execute(sql, {"query": query, "prefix": f"{query}%", "limit": limit})
        rows = result.fetchall()
        
        return [
            SearchResultItem(
                id=row.id,
                label=row.label,
                type=row.type,
                subtype=row.subtype,
                extra_info=row.extra_info,
                score=row.sim
            ) for row in rows
        ]

    @staticmethod
    async def global_search(
        db: AsyncSession, query: str, limit: int = 20, offset: int = 0, type_filter: str = None
    ) -> Dict[str, Any]:
        """
        Full-text search across all entities using the Materialized View.
        """
        if not query:
            return {"results": [], "total": 0, "summary": {}}

        # Use websearch_to_tsquery for advanced syntax (quotes, OR, -minus)
        # Fallback to plainto_tsquery if needed, but websearch is standard 'Google-like'
        
        search_query_func = "websearch_to_tsquery"
        
        # Build filter clause
        filter_clause = ""
        params = {"query": query, "limit": limit, "offset": offset}
        if type_filter:
            filter_clause = "AND type = :type_filter"
            params["type_filter"] = type_filter
        
        # Main search query
        sql_search = text(f"""
            SELECT id, label, type, subtype, extra_info,
                   ts_rank(search_vector, {search_query_func}('english', :query)) as rank
            FROM global_search_index
            WHERE search_vector @@ {search_query_func}('english', :query)
            {filter_clause}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)
        
        # Summary counts (grouped by type) - Always get full counts regardless of filter
        sql_count = text(f"""
            SELECT type, COUNT(*) as count
            FROM global_search_index
            WHERE search_vector @@ {search_query_func}('english', :query)
            GROUP BY type
        """)
        
        # Execute queries
        # Note: In a real high-load scenario, we might want to combine these or cache counts
        res_search = await db.execute(sql_search, params)
        rows_search = res_search.fetchall()
        
        res_count = await db.execute(sql_count, {"query": query})
        rows_count = res_count.fetchall()
        
        summary = {row.type: row.count for row in rows_count}
        total = sum(summary.values())
        
        results = [
            SearchResultItem(
                id=row.id,
                label=row.label,
                type=row.type,
                subtype=row.subtype,
                extra_info=row.extra_info,
                score=row.rank
            ) for row in rows_search
        ]
        
        return {
            "results": results,
            "total": total,
            "summary": summary
        }
    
    @staticmethod
    async def refresh_index(db: AsyncSession):
        """Refreshes the Materialized View. Call this after bulk updates."""
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY global_search_index"))
        await db.commit()
