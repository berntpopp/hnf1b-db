"""``GET /api/v2/publications/`` list endpoint with JSON:API pagination."""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.json_api import JsonApiResponse
from app.utils.pagination import build_offset_response, parse_sort_parameter

logger = logging.getLogger(__name__)

# Allowed sort fields for publications.
PUBLICATION_SORT_FIELDS = {
    "pmid",
    "title",
    "year",
    "journal",
    "phenopacket_count",
    "first_added",
}

router = APIRouter(tags=["publications"])


def _build_where_clauses(
    *,
    filter_year: Optional[int],
    filter_year_gte: Optional[int],
    filter_year_lte: Optional[int],
    filter_has_doi: Optional[bool],
    q: Optional[str],
) -> tuple[List[str], Dict[str, Any]]:
    """Return ``(where_fragments, bind_params)`` for the list query.

    Shared between the main query and the count query so the two
    stay in sync.
    """
    clauses: List[str] = []
    params: Dict[str, Any] = {}

    if filter_year is not None:
        clauses.append("pm.year = :filter_year")
        params["filter_year"] = filter_year

    if filter_year_gte is not None:
        clauses.append("pm.year >= :filter_year_gte")
        params["filter_year_gte"] = filter_year_gte

    if filter_year_lte is not None:
        clauses.append("pm.year <= :filter_year_lte")
        params["filter_year_lte"] = filter_year_lte

    if filter_has_doi is not None:
        if filter_has_doi:
            clauses.append("pm.doi IS NOT NULL AND pm.doi != ''")
        else:
            clauses.append("(pm.doi IS NULL OR pm.doi = '')")

    if q:
        clauses.append("""(
            pc.pmid ILIKE :search_query
            OR pm.title ILIKE :search_query
            OR pm.journal ILIKE :search_query
            OR pm.authors::text ILIKE :search_query
        )""")
        params["search_query"] = f"%{q}%"

    return clauses, params


def _format_authors(raw_authors) -> Optional[str]:
    """Convert a JSONB authors list into an ``"First A, Second B et al."`` string."""
    if not raw_authors:
        return None
    if not isinstance(raw_authors, list):
        return None
    names = [a.get("name", "") for a in raw_authors if a.get("name")]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{names[0]} et al."


@router.get(
    "/",
    response_model=JsonApiResponse,
    summary="List publications with offset pagination",
    description="""
    List all publications with offset-based pagination, filtering, sorting, and search.

    **Pagination (JSON:API v1.1 Offset):**
    - `page[number]`: Page number (1-indexed, default: 1)
    - `page[size]`: Items per page (default: 20, max: 100)

    **Filtering:**
    - `filter[year]`: Exact year match
    - `filter[year_gte]`: Year >= value
    - `filter[year_lte]`: Year <= value
    - `filter[has_doi]`: true/false

    **Sorting:**
    - `sort`: Comma-separated fields, prefix with `-` for descending
    - Allowed fields: pmid, title, year, journal, phenopacket_count, first_added
    - Default: `-phenopacket_count` (most individuals first)

    **Search:**
    - `q`: Full-text search in PMID, title, authors, journal

    **Response:**
    - Returns JSON:API envelope with `data`, `meta`, `links`
    - Includes page numbers for direct navigation
    """,
)
async def list_publications(
    request: Request,
    page_number: int = Query(1, alias="page[number]", ge=1, description="Page number"),
    page_size: int = Query(
        20, alias="page[size]", ge=1, le=1000, description="Page size"
    ),
    filter_year: Optional[int] = Query(
        None, alias="filter[year]", description="Exact year"
    ),
    filter_year_gte: Optional[int] = Query(
        None, alias="filter[year_gte]", description="Year >="
    ),
    filter_year_lte: Optional[int] = Query(
        None, alias="filter[year_lte]", description="Year <="
    ),
    filter_has_doi: Optional[bool] = Query(
        None, alias="filter[has_doi]", description="Has DOI"
    ),
    sort: str = Query(
        "-phenopacket_count",
        description="Sort fields (comma-separated, - for desc)",
    ),
    q: Optional[str] = Query(None, description="Search in title, authors, journal"),
    db: AsyncSession = Depends(get_db),
):
    """List publications with offset pagination, filtering, sorting, and search."""
    try:
        sort_fields = parse_sort_parameter(sort, PUBLICATION_SORT_FIELDS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not sort_fields:
        sort_fields = [("phenopacket_count", "desc"), ("first_added", "desc")]

    base_query = """
    WITH pub_counts AS (
        SELECT
            REPLACE(ext_ref->>'id', 'PMID:', '') as pmid,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count,
            MIN(created_at) as first_added
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
        GROUP BY ext_ref->>'id'
    )
    SELECT
        pc.pmid,
        pm.title,
        pm.authors,
        pm.journal,
        pm.year,
        pm.doi,
        pc.phenopacket_count,
        pc.first_added
    FROM pub_counts pc
    LEFT JOIN publication_metadata pm ON pm.pmid = CONCAT('PMID:', pc.pmid)
    """

    where_clauses, params = _build_where_clauses(
        filter_year=filter_year,
        filter_year_gte=filter_year_gte,
        filter_year_lte=filter_year_lte,
        filter_has_doi=filter_has_doi,
        q=q,
    )

    query = base_query
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    order_parts = []
    for field, direction in sort_fields:
        col = {
            "pmid": "pc.pmid",
            "phenopacket_count": "pc.phenopacket_count",
            "first_added": "pc.first_added",
            "title": "pm.title",
            "year": "pm.year",
            "journal": "pm.journal",
        }.get(field, f"pc.{field}")
        order_parts.append(f"{col} {direction.upper()} NULLS LAST")

    order_parts.append("pc.pmid DESC NULLS LAST")
    query += " ORDER BY " + ", ".join(order_parts)

    offset = (page_number - 1) * page_size
    query += " OFFSET :offset LIMIT :limit"
    params["offset"] = offset
    params["limit"] = page_size

    result = await db.execute(text(query), params)
    rows = list(result.fetchall())

    # Count query (same WHERE clauses, no ORDER/LIMIT).
    count_query = """
    WITH pub_counts AS (
        SELECT
            REPLACE(ext_ref->>'id', 'PMID:', '') as pmid,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
        GROUP BY ext_ref->>'id'
    )
    SELECT COUNT(*) as total
    FROM pub_counts pc
    LEFT JOIN publication_metadata pm ON pm.pmid = CONCAT('PMID:', pc.pmid)
    """
    count_clauses, count_params = _build_where_clauses(
        filter_year=filter_year,
        filter_year_gte=filter_year_gte,
        filter_year_lte=filter_year_lte,
        filter_has_doi=filter_has_doi,
        q=q,
    )
    if count_clauses:
        count_query += " WHERE " + " AND ".join(count_clauses)

    count_result = await db.execute(text(count_query), count_params)
    total_count = count_result.scalar() or 0

    # Build response rows.
    data = []
    for row in rows:
        data.append(
            {
                "pmid": row.pmid,
                "title": row.title or "Title unavailable",
                "authors": _format_authors(row.authors) or "-",
                "journal": row.journal,
                "year": row.year,
                "doi": row.doi,
                "phenopacket_count": row.phenopacket_count,
                "first_added": row.first_added.isoformat() if row.first_added else None,
            }
        )

    # Build filter dict for pagination links.
    filters: Dict[str, Any] = {}
    if filter_year is not None:
        filters["filter[year]"] = filter_year
    if filter_year_gte is not None:
        filters["filter[year_gte]"] = filter_year_gte
    if filter_year_lte is not None:
        filters["filter[year_lte]"] = filter_year_lte
    if filter_has_doi is not None:
        filters["filter[has_doi]"] = str(filter_has_doi).lower()
    if q:
        filters["q"] = q

    response = build_offset_response(
        data=data,
        current_page=page_number,
        page_size=page_size,
        total_records=total_count,
        base_url=str(request.url.path),
        filters=filters,
        sort=sort,
    )

    logger.info(
        "Listed publications",
        extra={
            "count": len(data),
            "page": page_number,
            "page_size": page_size,
            "total": total_count,
        },
    )

    return response
