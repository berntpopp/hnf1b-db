# app/endpoints/reports.py
from fastapi import APIRouter, HTTPException
from typing import List
from app.models import Report
from app.database import db

router = APIRouter()

@router.get("/", response_model=List[Report])
async def get_reports(skip: int = 0, limit: int = 10):
    cursor = db.reports.find({}).skip(skip).limit(limit)
    reports = await cursor.to_list(length=limit)
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")
    return reports
