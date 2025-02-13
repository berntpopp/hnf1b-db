# File: app/endpoints/variants.py
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from app.models import Variant
from app.database import db
from app.utils import (
    parse_sort,
    build_pagination_meta,
    parse_filter_json,
    parse_deep_object_filters,
)

router = APIRouter()

@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="Get Variants"
)
async def get_variants(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of variants per page"),
    sort: Optional[str] = Query(
        None,
        description="Sort field (e.g. 'variant_id' for ascending or '-variant_id' for descending order)"
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"status": "active", "variant_id": {"gt": "var1000"}}'
        )
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "variant_id, hg19, hg19_INFO, hg38, hg38_INFO, variant_type, "
            "classifications.verdict, classifications.criteria, "
            "annotations.c_dot, annotations.p_dot, annotations.impact, "
            "annotations.variant_class"
        )
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of variants, optionally filtered by a JSON filter
    and/or a free-text search query.

    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - variant_id
      - hg19, hg19_INFO
      - hg38, hg38_INFO
      - variant_type
      - classifications.verdict, classifications.criteria
      - annotations.c_dot, annotations.p_dot, annotations.impact, annotations.variant_class

    Example:
      /variants?sort=-variant_id&page=1&page_size=10&filter={"status": "active"}&q=SNV
    """
    start_time = time.perf_counter()  # Start timing

    # Parse the JSON filter (if provided) into a MongoDB filter.
    raw_filter = parse_filter_json(filter_query)
    filters = parse_deep_object_filters(raw_filter)

    # If a search query 'q' is provided, build a search filter for predefined variant fields.
    if q:
        search_fields = [
            "variant_id",
            "hg19", "hg19_INFO",
            "hg38", "hg38_INFO",
            "variant_type",
            "classifications.verdict", "classifications.criteria",
            "annotations.c_dot", "annotations.p_dot", "annotations.impact", "annotations.variant_class",
        ]
        search_filter = {"$or": [{field: {"$regex": q, "$options": "i"}} for field in search_fields]}
        filters = {"$and": [filters, search_filter]} if filters else search_filter

    # Determine the sort option (default to ascending by "variant_id").
    sort_option = parse_sort(sort) if sort else ("variant_id", 1)

    collection = db.variants
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    variants = await cursor.to_list(length=page_size)

    if not variants:
        raise HTTPException(status_code=404, detail="No variants found")

    base_url = str(request.url).split("?")[0]
    end_time = time.perf_counter()  # End timing
    execution_time = end_time - start_time

    # Prepare extra query parameters (including sort, filter, and search query) for pagination links.
    extra_params: Dict[str, Any] = {}
    if sort:
        extra_params["sort"] = sort
    if filter_query:
        extra_params["filter"] = filter_query
    if q:
        extra_params["q"] = q

    # Build pagination metadata including execution time (in ms).
    meta = build_pagination_meta(
        base_url, page, page_size, total,
        query_params=extra_params,
        execution_time=execution_time
    )

    # Convert MongoDB documents (with ObjectId values) to JSON-friendly data.
    response_data = jsonable_encoder(
        {"data": variants, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
