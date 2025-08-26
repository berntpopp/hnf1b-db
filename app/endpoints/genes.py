# File: app/endpoints/genes.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Genes")
async def get_genes(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of genes per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'gene_symbol' for ascending or '-gene_symbol' "
            "for descending order)"
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of genes with structure data."""
    raise HTTPException(
        status_code=503, detail="Genes endpoint temporarily unavailable"
    )
