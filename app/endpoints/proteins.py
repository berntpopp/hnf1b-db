# File: app/endpoints/proteins.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Proteins")
async def get_proteins(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of proteins per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'gene' for ascending or '-gene' for descending order). "
            "Defaults to sorting by gene."
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of proteins with structure and domain data."""
    raise HTTPException(
        status_code=503, detail="Protein endpoint temporarily unavailable"
    )
