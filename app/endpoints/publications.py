# File: app/endpoints/publications.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.models import Publication
from app.database import db
from app.dependencies import parse_filter

router = APIRouter()

@router.get("/", response_model=List[Publication])
async def get_publications(
    filters: Dict[str, Any] = Depends(parse_filter),
    page_after: Optional[int] = Query(
        None,
        alias="page[after]",
        description="Cursor pagination: last publication_id"
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
        query["publication_id"] = {"$gt": page_after}
    
    cursor = db.publications.find(query).sort("publication_id", 1).limit(page_size)
    publications = await cursor.to_list(length=page_size)
    if not publications:
        raise HTTPException(status_code=404, detail="No publications found")
    return publications
