# File: app/endpoints/variants.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.models import Variant
from app.database import db
from app.dependencies import parse_filter

router = APIRouter()

@router.get("/", response_model=List[Variant])
async def get_variants(
    filters: Dict[str, Any] = Depends(parse_filter),
    page_after: Optional[int] = Query(
        None,
        alias="page[after]",
        description="Cursor pagination: last variant_id"
    ),
    page_size: int = Query(
        10,
        alias="page[size]",
        description="Page size"
    )
):
    query = {}
    if filters:
        query.update(filters)
    if page_after is not None:
        query["variant_id"] = {"$gt": page_after}
    
    cursor = db.variants.find(query).sort("variant_id", 1).limit(page_size)
    variants = await cursor.to_list(length=page_size)
    if not variants:
        raise HTTPException(status_code=404, detail="No variants found")
    return variants
