"""Search services - Business logic layer.

Services orchestrate repositories and apply business rules.
They don't contain SQL - that's the repository's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.search.repositories import GlobalSearchRepository, PhenopacketSearchRepository
from app.search.schemas import (
    AutocompleteResponse,
    GlobalSearchResponse,
    SearchResultItem,
)
from app.utils.pagination import decode_cursor, encode_cursor


@dataclass
class PaginationParams:
    """Pagination parameters."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Calculate offset for SQL OFFSET clause."""
        return (self.page - 1) * self.page_size


class GlobalSearchService:
    """Service for global unified search across all entity types.

    Uses the global_search_index materialized view for fast
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
        """Execute global search with pagination.

        Args:
            query: Search query string (supports websearch syntax)
            pagination: Pagination parameters
            type_filter: Optional filter by entity type

        Returns:
            GlobalSearchResponse with results and metadata
        """
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

    async def autocomplete(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions.

        Args:
            query: Partial search term (min 2 chars)
            limit: Maximum suggestions to return

        Returns:
            AutocompleteResponse with suggestions
        """
        if not query or len(query.strip()) < 2:
            return AutocompleteResponse(results=[])

        results = await self.repo.autocomplete(query, limit)
        return AutocompleteResponse(results=[SearchResultItem(**r) for r in results])

    async def refresh_index(self, concurrently: bool = True) -> None:
        """Refresh the materialized view.

        Args:
            concurrently: If True, doesn't block reads during refresh
        """
        await self.repo.refresh(concurrently)


class PhenopacketSearchService:
    """Service for phenopacket-specific advanced search.

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

        Args:
            query: Full-text search query
            hpo_id: Filter by HPO term ID
            sex: Filter by subject sex
            gene: Filter by gene symbol
            pmid: Filter by publication PMID
            page_size: Results per page
            cursor_after: Cursor for next page
            cursor_before: Cursor for previous page

        Returns:
            Dict with data, meta, and links for JSON:API response
        """
        # Build filters dict
        filters = {}
        if hpo_id:
            filters["hpo_id"] = hpo_id
        if sex:
            filters["sex"] = sex
        if gene:
            filters["gene"] = gene
        if pmid:
            filters["pmid"] = pmid

        # Handle cursor pagination
        is_backward = cursor_before is not None
        cursor_data = None

        if cursor_after:
            cursor_data = decode_cursor(cursor_after)
        elif cursor_before:
            cursor_data = decode_cursor(cursor_before)

        # Execute search
        rows = await self.repo.search(
            query=query,
            filters=filters if filters else None,
            limit=page_size,
            cursor_data=cursor_data,
            is_backward=is_backward,
        )

        # Detect pagination
        has_more = len(rows) > page_size
        if has_more:
            rows = rows[:page_size]

        if is_backward:
            rows = list(reversed(rows))

        # Determine has_next and has_prev
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

        # Build cursors
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

        # Format response data
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
        """Build pagination links."""
        base = "/api/v2/phenopackets/search"

        # Build query params
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
        """Get facet counts for search filters.

        Args:
            query: Full-text search query
            hpo_id: HPO filter
            sex: Sex filter
            gene: Gene filter
            pmid: PMID filter

        Returns:
            Dict of facet lists by category
        """
        facet_service = FacetService(self.db)
        return await facet_service.get_facets(
            query=query,
            hpo_id=hpo_id,
            sex=sex,
            gene=gene,
            pmid=pmid,
        )


class FacetService:
    """Service for computing search facets.

    Facets show filter options with counts, helping users
    narrow down search results.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def get_facets(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute facet counts based on current filters.

        Returns facets for: sex, hasVariants, pathogenicity, genes, phenotypes
        """
        import json

        from sqlalchemy import text

        # Build base filter conditions
        conditions = ["deleted_at IS NULL"]
        params: dict[str, Any] = {}

        if query:
            conditions.append("search_vector @@ plainto_tsquery('english', :query)")
            params["query"] = query

        if hpo_id:
            conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])

        if gene:
            conditions.append("phenopacket->'interpretations' @> :gene_filter")
            params["gene_filter"] = json.dumps(
                [
                    {
                        "diagnosis": {
                            "genomicInterpretations": [
                                {
                                    "variantInterpretation": {
                                        "variationDescriptor": {
                                            "geneContext": {"symbol": gene}
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            )

        if pmid:
            pmid_val = pmid if pmid.startswith("PMID:") else f"PMID:{pmid}"
            pmid_cond = "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            conditions.append(pmid_cond)
            params["pmid_filter"] = json.dumps([{"id": pmid_val}])

        where_clause = " AND ".join(conditions)

        # Sex facets (exclude sex filter for this facet)
        sex_conditions = [c for c in conditions if "subject_sex" not in c]
        if sex:
            sex_conditions.append("subject_sex = :sex")
            params["sex"] = sex
        sex_where = " AND ".join(sex_conditions) if sex_conditions else "TRUE"

        sex_sql = text(f"""
            SELECT subject_sex AS value, COUNT(*) AS count
            FROM phenopackets
            WHERE {sex_where.replace("subject_sex = :sex", "TRUE")}
            GROUP BY subject_sex
            ORDER BY count DESC
        """)
        sex_params = {k: v for k, v in params.items() if k != "sex"}
        sex_result = await self.db.execute(sex_sql, sex_params)
        sex_facets = [
            {"value": r.value, "label": r.value or "Unknown", "count": r.count}
            for r in sex_result.fetchall()
        ]

        # Has variants facet
        interp_path = "phenopacket->'interpretations'"
        variants_sql = text(f"""
            SELECT
                CASE
                    WHEN jsonb_array_length(
                        COALESCE({interp_path}, '[]'::jsonb)
                    ) > 0
                    THEN true ELSE false
                END AS value,
                COUNT(*) AS count
            FROM phenopackets
            WHERE {where_clause}
            GROUP BY value
            ORDER BY value DESC
        """)
        variants_result = await self.db.execute(variants_sql, params)
        variants_facets = [
            {"value": r.value, "label": "Yes" if r.value else "No", "count": r.count}
            for r in variants_result.fetchall()
        ]

        # SQL path fragments for JSONB queries
        acmg_path = (
            "gi.value->'variantInterpretation'->>'acmgPathogenicityClassification'"
        )
        gi_join = (
            "COALESCE(interp.value->'diagnosis'->'genomicInterpretations', '[]'::jsonb)"
        )

        # Pathogenicity facet
        pathogenicity_sql = text(f"""
            SELECT {acmg_path} AS value, COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'interpretations', '[]'::jsonb)
            ) AS interp
            CROSS JOIN LATERAL jsonb_array_elements({gi_join}) AS gi
            WHERE p.deleted_at IS NULL
            AND {acmg_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        pathogenicity_result = await self.db.execute(pathogenicity_sql, {})
        pathogenicity_facets = [
            {"value": r.value, "label": r.value, "count": r.count}
            for r in pathogenicity_result.fetchall()
        ]

        # Top genes facet
        gene_symbol_path = (
            "gi.value->'variantInterpretation'"
            "->'variationDescriptor'->'geneContext'->>'symbol'"
        )
        genes_sql = text(f"""
            SELECT {gene_symbol_path} AS value, COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'interpretations', '[]'::jsonb)
            ) AS interp
            CROSS JOIN LATERAL jsonb_array_elements({gi_join}) AS gi
            WHERE p.deleted_at IS NULL
            AND {gene_symbol_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        genes_result = await self.db.execute(genes_sql, {})
        genes_facets = [
            {"value": r.value, "label": r.value, "count": r.count}
            for r in genes_result.fetchall()
        ]

        # Top phenotypes facet
        phenotypes_sql = text("""
            SELECT
                pf.value->'type'->>'id' AS hpo_id,
                pf.value->'type'->>'label' AS label,
                COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'phenotypicFeatures', '[]'::jsonb)) AS pf
            WHERE p.deleted_at IS NULL
            AND pf.value->'type'->>'id' IS NOT NULL
            GROUP BY hpo_id, label
            ORDER BY count DESC
            LIMIT 20
        """)
        phenotypes_result = await self.db.execute(phenotypes_sql, {})
        phenotypes_facets = [
            {"value": r.hpo_id, "label": r.label or r.hpo_id, "count": r.count}
            for r in phenotypes_result.fetchall()
        ]

        return {
            "sex": sex_facets,
            "hasVariants": variants_facets,
            "pathogenicity": pathogenicity_facets,
            "genes": genes_facets,
            "phenotypes": phenotypes_facets,
        }
