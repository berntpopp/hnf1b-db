# app/endpoints/variants.py
from fastapi import APIRouter, HTTPException
from typing import List
from app.models import Variant
from app.database import db

router = APIRouter()

@router.get("/", response_model=List[Variant])
async def get_variants(skip: int = 0, limit: int = 10):
    cursor = db.variants.find({}).skip(skip).limit(limit)
    variants = await cursor.to_list(length=limit)
    if not variants:
        raise HTTPException(status_code=404, detail="No variants found")
    return variants
