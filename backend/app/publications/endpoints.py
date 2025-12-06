"""API endpoints for publication metadata.

Provides JSON:API v1.1 compliant endpoints for publications with:
- Offset-based pagination (page[number], page[size])
- Filtering (filter[year], filter[has_doi])
- Sorting (sort=-phenopacket_count,year)
- Full-text search (q=HNF1B)
- Admin sync endpoint for batch PubMed metadata fetching
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.json_api import JsonApiResponse
from app.publications.service import (
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError,
    get_publication_metadata,
)
from app.utils.pagination import (
    build_offset_response,
    parse_sort_parameter,
)

logger = logging.getLogger(__name__)

# Allowed sort fields for publications
PUBLICATION_SORT_FIELDS = {
    "pmid",
    "title",
    "year",
    "journal",
    "phenopacket_count",
    "first_added",
}

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])


# Pydantic response models
class AuthorModel(BaseModel):
    """Author information."""

    name: str
    affiliation: Optional[str] = None


class PublicationMetadataResponse(BaseModel):
    """Publication metadata response model."""

    pmid: str = Field(..., description="PubMed ID in format PMID:12345678")
    title: str = Field(..., description="Publication title")
    authors: list[AuthorModel] = Field(
        ..., description="List of authors with affiliations"
    )
    journal: Optional[str] = Field(None, description="Journal name")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI identifier")
    abstract: Optional[str] = Field(None, description="Abstract text (may be null)")
    data_source: str = Field(default="PubMed", description="Data source")
    fetched_at: str = Field(..., description="Storage timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pmid": "PMID:30791938",
                "title": "HNF1B-related disorder: clinical characteristics and genetic findings",
                "authors": [
                    {"name": "Smith J", "affiliation": "Department of Medicine"},
                    {"name": "Doe A", "affiliation": "Department of Genetics"},
                ],
                "journal": "Journal of Medical Genetics",
                "year": 2019,
                "doi": "10.1136/jmedgenet-2018-105729",
                "abstract": None,
                "data_source": "PubMed",
                "fetched_at": "2025-10-22T14:30:00",
            }
        }
    )


@router.get(
    "/{pmid}/metadata",
    response_model=PublicationMetadataResponse,
    summary="Get publication metadata from PubMed",
    description="""
    Fetch publication metadata with permanent database storage.

    **Features:**
    - Permanent database storage (fetched once, stored forever)
    - PMID validation (SQL injection prevention)
    - Rate limiting handling
    - Provenance tracking

    **PMID Format:**
    - Accepts: "30791938" or "PMID:30791938"
    - Returns: Normalized "PMID:12345678"

    **Response Time:**
    - Database hit: < 50ms
    - PubMed fetch: < 1000ms (for new PMIDs)

    **Error Handling:**
    - 400: Invalid PMID format
    - 404: Publication not found in PubMed
    - 429: Rate limit exceeded (retry after N seconds)
    - 500: PubMed API error
    - 504: Timeout fetching from PubMed
    """,
    responses={
        200: {
            "description": "Publication metadata retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "pmid": "PMID:30791938",
                        "title": "HNF1B-related disorder",
                        "authors": [
                            {"name": "Smith J", "affiliation": "Dept Medicine"}
                        ],
                        "journal": "J Med Genet",
                        "year": 2019,
                        "doi": "10.1136/jmedgenet-2018-105729",
                        "abstract": None,
                        "data_source": "PubMed",
                        "fetched_at": "2025-10-22T14:30:00",
                    }
                }
            },
        },
        400: {"description": "Invalid PMID format"},
        404: {"description": "Publication not found in PubMed"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "PubMed API error"},
        504: {"description": "Timeout fetching from PubMed"},
    },
)
async def get_publication_metadata_endpoint(
    pmid: str, db: AsyncSession = Depends(get_db)
):
    """Get publication metadata by PMID.

    Args:
        pmid: PubMed ID (format: PMID:12345678 or 12345678)
        db: Database session (injected)

    Returns:
        PublicationMetadataResponse: Publication metadata

    Raises:
        HTTPException: Various error conditions
    """
    try:
        # Fetch metadata with caching
        metadata = await get_publication_metadata(pmid, db, fetched_by="api")

        # Convert datetime to ISO string
        metadata["fetched_at"] = metadata["fetched_at"].isoformat()

        logger.info(f"Successfully retrieved metadata for {pmid}", extra={"pmid": pmid})

        return metadata

    except ValueError as e:
        # Invalid PMID format
        logger.warning(
            f"Invalid PMID format: {pmid}", extra={"pmid": pmid, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid PMID format: {e}"
        )

    except PubMedNotFoundError as e:
        # PMID not found in PubMed
        logger.warning(f"PMID not found: {pmid}", extra={"pmid": pmid})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except PubMedRateLimitError as e:
        # Rate limit exceeded
        logger.error(f"Rate limit exceeded for {pmid}", extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "60"},
        )

    except PubMedTimeoutError as e:
        # Timeout fetching from PubMed
        logger.error(f"Timeout fetching {pmid}", extra={"pmid": pmid})
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))

    except PubMedAPIError as e:
        # General PubMed API error
        logger.error(
            f"PubMed API error for {pmid}: {e}", extra={"pmid": pmid, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PubMed API error: {e}",
        )

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error fetching {pmid}: {e}", extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# =============================================================================
# Publications List Endpoint (JSON:API v1.1 cursor pagination)
# =============================================================================


class PublicationListItem(BaseModel):
    """Publication item for list endpoint."""

    pmid: str = Field(..., description="PubMed ID (without PMID: prefix)")
    title: Optional[str] = Field(None, description="Publication title")
    authors: Optional[str] = Field(None, description="Formatted author string")
    journal: Optional[str] = Field(None, description="Journal name")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI identifier")
    phenopacket_count: int = Field(..., description="Number of associated phenopackets")
    first_added: Optional[str] = Field(None, description="When first added to database")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pmid": "30791938",
                "title": "HNF1B-related disorder: clinical characteristics",
                "authors": "Smith J et al.",
                "journal": "J Med Genet",
                "year": 2019,
                "doi": "10.1136/jmedgenet-2018-105729",
                "phenopacket_count": 42,
                "first_added": "2024-01-15T10:30:00",
            }
        }
    )


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
    - `q`: Full-text search in title, authors, journal

    **Response:**
    - Returns JSON:API envelope with `data`, `meta`, `links`
    - Includes page numbers for direct navigation
    """,
)
async def list_publications(
    request: Request,
    # Offset Pagination
    page_number: int = Query(1, alias="page[number]", ge=1, description="Page number"),
    page_size: int = Query(
        20, alias="page[size]", ge=1, le=1000, description="Page size"
    ),
    # Filtering
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
    # Sorting
    sort: str = Query(
        "-phenopacket_count", description="Sort fields (comma-separated, - for desc)"
    ),
    # Search
    q: Optional[str] = Query(None, description="Search in title, authors, journal"),
    db: AsyncSession = Depends(get_db),
):
    """List publications with offset pagination, filtering, sorting, and search.

    Publications are aggregated from phenopackets and enriched with stored
    PubMed metadata (title, authors, journal, year, DOI).
    """
    # Parse sort parameter
    try:
        sort_fields = parse_sort_parameter(sort, PUBLICATION_SORT_FIELDS)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Default sort by phenopacket_count DESC, then first_added DESC
    if not sort_fields:
        sort_fields = [("phenopacket_count", "desc"), ("first_added", "desc")]

    # Build base query with CTE for publication counts
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

    # Build WHERE clauses
    where_clauses: List[str] = []
    params: Dict[str, Any] = {}

    if filter_year is not None:
        where_clauses.append("pm.year = :filter_year")
        params["filter_year"] = filter_year

    if filter_year_gte is not None:
        where_clauses.append("pm.year >= :filter_year_gte")
        params["filter_year_gte"] = filter_year_gte

    if filter_year_lte is not None:
        where_clauses.append("pm.year <= :filter_year_lte")
        params["filter_year_lte"] = filter_year_lte

    if filter_has_doi is not None:
        if filter_has_doi:
            where_clauses.append("pm.doi IS NOT NULL AND pm.doi != ''")
        else:
            where_clauses.append("(pm.doi IS NULL OR pm.doi = '')")

    if q:
        where_clauses.append("""(
            pm.title ILIKE :search_query
            OR pm.journal ILIKE :search_query
            OR pm.authors::text ILIKE :search_query
        )""")
        params["search_query"] = f"%{q}%"

    # Build final query with WHERE clauses
    query = base_query
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    # Add ORDER BY
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

    # Always add pmid as tiebreaker
    order_parts.append("pc.pmid DESC NULLS LAST")
    query += " ORDER BY " + ", ".join(order_parts)

    # Add OFFSET and LIMIT for pagination
    offset = (page_number - 1) * page_size
    query += " OFFSET :offset LIMIT :limit"
    params["offset"] = offset
    params["limit"] = page_size

    # Execute main query
    result = await db.execute(text(query), params)
    rows = list(result.fetchall())

    # Get total count for pagination metadata
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
    count_where_clauses: List[str] = []
    count_params: Dict[str, Any] = {}

    if filter_year is not None:
        count_where_clauses.append("pm.year = :filter_year")
        count_params["filter_year"] = filter_year

    if filter_year_gte is not None:
        count_where_clauses.append("pm.year >= :filter_year_gte")
        count_params["filter_year_gte"] = filter_year_gte

    if filter_year_lte is not None:
        count_where_clauses.append("pm.year <= :filter_year_lte")
        count_params["filter_year_lte"] = filter_year_lte

    if filter_has_doi is not None:
        if filter_has_doi:
            count_where_clauses.append("pm.doi IS NOT NULL AND pm.doi != ''")
        else:
            count_where_clauses.append("(pm.doi IS NULL OR pm.doi = '')")

    if q:
        count_where_clauses.append("""(
            pm.title ILIKE :search_query
            OR pm.journal ILIKE :search_query
            OR pm.authors::text ILIKE :search_query
        )""")
        count_params["search_query"] = f"%{q}%"

    if count_where_clauses:
        count_query += " WHERE " + " AND ".join(count_where_clauses)

    count_result = await db.execute(text(count_query), count_params)
    total_count = count_result.scalar() or 0

    # Format response data
    data = []
    for row in rows:
        # Format authors from JSONB to string
        authors_str = None
        if row.authors:
            if isinstance(row.authors, list):
                author_names = [a.get("name", "") for a in row.authors if a.get("name")]
                if len(author_names) == 1:
                    authors_str = author_names[0]
                elif len(author_names) <= 3:
                    authors_str = ", ".join(author_names)
                elif author_names:
                    authors_str = f"{author_names[0]} et al."

        data.append(
            {
                "pmid": row.pmid,
                "title": row.title or "Title unavailable",
                "authors": authors_str or "-",
                "journal": row.journal,
                "year": row.year,
                "doi": row.doi,
                "phenopacket_count": row.phenopacket_count,
                "first_added": row.first_added.isoformat() if row.first_added else None,
            }
        )

    # Build filter dict for pagination links
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

    # Build JSON:API offset response
    base_url = str(request.url.path)
    response = build_offset_response(
        data=data,
        current_page=page_number,
        page_size=page_size,
        total_records=total_count,
        base_url=base_url,
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


# =============================================================================
# Admin Sync Endpoint
# =============================================================================


class SyncResponse(BaseModel):
    """Response for sync operation."""

    status: str = Field(..., description="Status of the operation")
    message: str = Field(..., description="Human-readable message")
    total_pmids: Optional[int] = Field(None, description="Total PMIDs to sync")
    already_stored: Optional[int] = Field(None, description="PMIDs already stored")
    to_fetch: Optional[int] = Field(None, description="PMIDs to fetch from PubMed")


async def _sync_publications_background(db: AsyncSession) -> None:
    """Background task to sync all publication metadata from PubMed.

    1. Get all unique PMIDs from phenopackets
    2. Filter out already-stored entries
    3. Batch fetch from PubMed (respecting rate limits)
    4. Store permanently in publication_metadata table
    """
    import asyncio

    logger.info("Starting background publication sync")

    # Get all unique PMIDs from phenopackets
    query = text("""
        SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
    """)
    result = await db.execute(query)
    all_pmids = [row.pmid for row in result.fetchall()]

    logger.info(f"Found {len(all_pmids)} unique PMIDs in phenopackets")

    # Check which are already stored
    stored_query = text("""
        SELECT REPLACE(pmid, 'PMID:', '') as pmid
        FROM publication_metadata
    """)
    stored_result = await db.execute(stored_query)
    stored_pmids = {row.pmid for row in stored_result.fetchall()}

    # Filter to only unstored
    to_fetch = [pmid for pmid in all_pmids if pmid not in stored_pmids]

    logger.info(
        f"Need to fetch {len(to_fetch)} PMIDs ({len(stored_pmids)} already stored)"
    )

    # Fetch in batches respecting rate limits (3 req/sec without API key)
    fetched = 0
    errors = 0

    for pmid in to_fetch:
        try:
            await get_publication_metadata(pmid, db, fetched_by="sync")
            fetched += 1
            if fetched % 10 == 0:
                logger.info(f"Synced {fetched}/{len(to_fetch)} publications")
        except Exception as e:
            errors += 1
            logger.warning(f"Failed to fetch {pmid}: {e}")

        # Rate limiting: 3 req/sec = ~333ms between requests
        await asyncio.sleep(0.35)

    logger.info(f"Sync complete: {fetched} fetched, {errors} errors")


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync publication metadata from PubMed (admin only)",
    description="""
    Batch sync all publication metadata from PubMed for PMIDs found in phenopackets.

    **Requires:** Admin authentication

    **Process:**
    1. Find all unique PMIDs referenced in phenopackets
    2. Filter out already-stored entries
    3. Queue background task to fetch remaining from PubMed
    4. Respects PubMed rate limits (3 req/sec without API key)

    **Note:** This is an async operation. The endpoint returns immediately
    and fetching continues in the background.
    """,
    dependencies=[Depends(require_admin)],
)
async def sync_publications(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Sync all publication metadata from PubMed.

    Admin-only endpoint that triggers background sync of all PMIDs
    found in phenopackets that aren't already stored.
    """
    # Get counts for response
    all_query = text("""
        SELECT COUNT(DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '')) as count
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
    """)
    all_result = await db.execute(all_query)
    total_pmids = all_result.scalar() or 0

    stored_query = text("""
        SELECT COUNT(*) as count
        FROM publication_metadata
    """)
    stored_result = await db.execute(stored_query)
    already_stored = stored_result.scalar() or 0

    to_fetch = max(0, total_pmids - already_stored)

    # Queue background task
    background_tasks.add_task(_sync_publications_background, db)

    logger.info(
        "Publication sync initiated",
        extra={"total": total_pmids, "stored": already_stored, "to_fetch": to_fetch},
    )

    return SyncResponse(
        status="sync_started",
        message=f"Background sync initiated for {to_fetch} publications",
        total_pmids=total_pmids,
        already_stored=already_stored,
        to_fetch=to_fetch,
    )
