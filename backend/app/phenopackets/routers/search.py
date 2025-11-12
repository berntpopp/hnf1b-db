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
    # Base query parts
    select_clause = "SELECT id, phenopacket_id, phenopacket"
    from_clause = "FROM phenopackets"
    where_conditions = []
    params: Dict[str, Any] = {"limit": limit, "offset": skip}
    order_by_clause = ""

    # Full-text search
    if q:
        select_clause += (
            ", ts_rank(search_vector, plainto_tsquery('english', :search_query))"
            " AS search_rank"
        )
        where_conditions.append(
            "search_vector @@ plainto_tsquery('english', :search_query)"
        )
        params["search_query"] = q
        if rank_by_relevance:
            order_by_clause = "ORDER BY search_rank DESC"

    # Structured filters
    if hpo_id:
        where_conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
        params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])
    if sex:
        where_conditions.append("subject_sex = :sex")
        params["sex"] = sex
    if gene:
        where_conditions.append("phenopacket->'interpretations' @> :gene_filter")
        params["gene_filter"] = json.dumps(
            [
                {
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "geneContext": {"symbol": gene}
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        )
    if pmid:
        where_conditions.append(
            "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
        )
        params["pmid_filter"] = json.dumps([{"id": f"PMID:{pmid}"}])

    # Construct the final query
    where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

    # Get total count
    count_query_str = f"SELECT COUNT(*) {from_clause} {where_clause}"
    total_result = await db.execute(text(count_query_str), params)
    total = total_result.scalar_one()

    # Get paginated results
    query_str = (
        f"{select_clause} {from_clause} {where_clause} {order_by_clause} "
        "LIMIT :limit OFFSET :offset"
    )
    result = await db.execute(text(query_str), params)
    phenopackets = result.fetchall()

    # Format response
    data = [
        {
            "id": pp.phenopacket_id,
            "type": "phenopacket",
            "attributes": pp.phenopacket,
            "meta": {"search_rank": pp.search_rank if q else None},
        }
        for pp in phenopackets
    ]

    return {
        "data": data,
        "meta": {"total": total},
    }
