# File: app/endpoints/proteins.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.models import Protein
from app.database import db
from app.dependencies import parse_filter

router = APIRouter()

@router.get("/", response_model=List[Protein])
async def get_proteins(
    filters: Dict[str, Any] = Depends(parse_filter),
    page_after: Optional[str] = Query(
        None,
        alias="page[after]",
        description="Cursor pagination: last gene value from the previous page"
    ),
    page_size: int = Query(
        10,
        alias="page[size]",
        description="Page size"
    )
):
    """
    Retrieve a paginated list of proteins.

    This endpoint queries the `proteins` collection for protein structure and domain data.
    Optionally, you may supply a filter dictionary and cursor-based pagination by the gene field.
    """
    query = {}
    if filters:
        query.update(filters)
    # For pagination, we assume that the 'gene' field is used as a cursor.
    if page_after is not None:
        query["gene"] = {"$gt": page_after}

    cursor = db.proteins.find(query).sort("gene", 1).limit(page_size)
    proteins = await cursor.to_list(length=page_size)
    if not proteins:
        raise HTTPException(status_code=404, detail="No proteins found")
    return proteins
