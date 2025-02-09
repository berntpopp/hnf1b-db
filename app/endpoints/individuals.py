# app/endpoints/individuals.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models import Individual
from app.database import db

router = APIRouter()

@router.get("/", response_model=List[Individual])
async def get_individuals(
    skip: int = 0,
    limit: int = 10,
    Sex: Optional[str] = Query(None, description="Filter by sex")
):
    query = {}
    if Sex:
        query["Sex"] = sex
    cursor = db.individuals.find(query).skip(skip).limit(limit)
    individuals = await cursor.to_list(length=limit)
    if not individuals:
        raise HTTPException(status_code=404, detail="No individuals found")
    return individuals
