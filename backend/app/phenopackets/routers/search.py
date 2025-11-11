"""Full-text and structured search for phenopackets."""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/search")
async def search_phenopackets(
    q: Optional[str] = Query(None, description="Full-text search query"),
    hpo_id: Optional[str] = Query(None, description="Filter by HPO term ID"),
    sex: Optional[str] = Query(None, description="Filter by subject sex"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    pmid: Optional[str] = Query(None, description="Filter by publication PMID"),
    rank_by_relevance: bool = Query(True, description="Sort by search rank"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Advanced phenopacket search with full-text and structured filters."""
    # Temporarily return a 200 OK with empty data for debugging 404s
    return {
        "data": [],
        "meta": {"total": 0},
    }
