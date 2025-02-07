# app/endpoints/publications.py
from fastapi import APIRouter, HTTPException
from typing import List
from app.models import Publication
from app.database import db

router = APIRouter()

@router.get("/", response_model=List[Publication])
async def get_publications(skip: int = 0, limit: int = 10):
    cursor = db.publications.find({}).skip(skip).limit(limit)
    publications = await cursor.to_list(length=limit)
    if not publications:
        raise HTTPException(status_code=404, detail="No publications found")
    return publications
