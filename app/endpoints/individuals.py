# File: app/endpoints/individuals.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.models import Individual
from app.database import db
from app.dependencies import parse_filter

router = APIRouter()

@router.get("/", response_model=List[Individual])
async def get_individuals(
    filters: Dict[str, Any] = Depends(parse_filter),
    page_after: Optional[int] = Query(
        None,
        alias="page[after]",
        description="Cursor pagination: last individual_id"
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
        # Use a greater-than operator for cursor pagination on individual_id
        query["individual_id"] = {"$gt": page_after}
    
    cursor = db.individuals.find(query).sort("individual_id", 1).limit(page_size)
    individuals = await cursor.to_list(length=page_size)
    if not individuals:
        raise HTTPException(status_code=404, detail="No individuals found")
    return individuals
