from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.search.services import GlobalSearchService
from app.search.schemas import AutocompleteResponse, GlobalSearchResponse

router = APIRouter(tags=["search"])

@router.get("/search/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get autocomplete suggestions for genes, variants, phenopackets, and publications.
    """
    results = await GlobalSearchService.autocomplete(db, q, limit)
    return {"results": results}

@router.get("/search/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., description="Search query"),
    type: str = Query(None, description="Filter by result type (e.g. 'Phenopacket', 'Variant')"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Perform a global full-text search across all data types.
    """
    offset = (page - 1) * page_size
    data = await GlobalSearchService.global_search(db, q, page_size, offset, type)
    
    return {
        "results": data["results"],
        "total": data["total"],
        "page": page,
        "page_size": page_size,
        "summary": data["summary"]
    }
