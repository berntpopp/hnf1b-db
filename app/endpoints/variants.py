# File: app/endpoints/variants.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Variants")
async def get_variants(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of variants per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'variant_id' for ascending or '-variant_id' "
            "for descending order)"
        ),
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"status": "active", "variant_id": {"gt": "var1000"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "variant_id, hg19, hg19_INFO, hg38, hg38_INFO, variant_type, "
            "classifications.verdict, classifications.criteria, "
            "annotations.c_dot, annotations.p_dot, annotations.impact, "
            "annotations.variant_class"
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of variants.

    Variants can be filtered by a JSON filter and/or a free-text search query.
    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - variant_id
      - hg19, hg19_INFO
      - hg38, hg38_INFO
      - variant_type
      - classifications.verdict, classifications.criteria
      - annotations.c_dot, annotations.p_dot, annotations.impact,
        annotations.variant_class
    """
    raise HTTPException(
        status_code=503, detail="Variants endpoint temporarily unavailable"
    )
