# File: app/endpoints/genes.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.models import Gene
from app.database import db
from app.dependencies import parse_filter

router = APIRouter()

@router.get("/", response_model=List[Gene])
async def get_genes(
    filters: Dict[str, Any] = Depends(parse_filter),
    page_after: Optional[str] = Query(
        None,
        alias="page[after]",
        description="Cursor pagination: last gene_symbol from the previous page"
    ),
    page_size: int = Query(
        10,
        alias="page[size]",
        description="Page size"
    )
):
    """
    Retrieve a paginated list of genes.

    This endpoint returns the gene structure data stored in the 'genes' collection.
    Optional filters can be applied, and results are paginated based on the gene_symbol field.
    """
    query = {}
    if filters:
        query.update(filters)
    if page_after is not None:
        query["gene_symbol"] = {"$gt": page_after}

    cursor = db.genes.find(query).sort("gene_symbol", 1).limit(page_size)
    genes = await cursor.to_list(length=page_size)
    if not genes:
        raise HTTPException(status_code=404, detail="No genes found")
    return genes
