"""Global search API endpoints - Thin controller layer.

Routes delegate to services for business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.search.schemas import AutocompleteResponse, GlobalSearchResponse
from app.search.services import GlobalSearchService, PaginationParams

router = APIRouter(tags=["search"])


@router.get("/search/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=2, description="Search query (min 2 chars)"),
    limit: int = Query(10, ge=1, le=50, description="Max suggestions"),
    db: AsyncSession = Depends(get_db),
) -> AutocompleteResponse:
    """Get autocomplete suggestions across all entity types.

    Returns suggestions from genes, variants, phenopackets, and publications
    using trigram similarity matching for fuzzy search support.

    **Example:**
    ```
    GET /api/v2/search/autocomplete?q=HNF&limit=5
    ```

    **Response:**
    ```json
    {
      "results": [
        {"id": "gene_1", "label": "HNF1B", "type": "Gene", "score": 0.9},
        {"id": "var_123", "label": "HNF1B:c.544+1G>A", "type": "Variant", "score": 0.7}
      ]
    }
    ```
    """
    service = GlobalSearchService(db)
    return await service.autocomplete(q, limit)


@router.get("/search/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(
        None,
        description="Filter by type (Gene, Variant, Phenopacket, Publication)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> GlobalSearchResponse:
    """Perform global full-text search across all entity types.

    Supports websearch query syntax:
    - Quotes for exact phrases: `"HNF1B deletion"`
    - OR for alternatives: `deletion OR duplication`
    - Minus for exclusion: `HNF1B -missense`

    **Example:**
    ```
    GET /api/v2/search/global?q=HNF1B+deletion&type=Variant&page=1&page_size=20
    ```

    **Response:**
    ```json
    {
      "results": [...],
      "total": 45,
      "page": 1,
      "page_size": 20,
      "summary": {
        "Gene": 1,
        "Variant": 30,
        "Phenopacket": 14
      }
    }
    ```
    """
    service = GlobalSearchService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    return await service.search(q, pagination, type)


@router.post("/search/refresh", include_in_schema=False)
async def refresh_search_index(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Manually refresh the search index (admin only).

    This endpoint refreshes the global_search_index materialized view.
    Normally this happens automatically, but can be triggered manually
    after bulk data imports.
    """
    service = GlobalSearchService(db)
    await service.refresh_index()
    return {"status": "ok", "message": "Search index refreshed"}
