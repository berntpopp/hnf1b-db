# File: app/endpoints/variants.py
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
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
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of variants.

    The filter parameter should be provided as a JSON string.
    
    Example:
      /variants?sort=-variant_id&page=1&page_size=10&filter={"status": "active", "variant_id": {"gt": "var1000"}}
    """
    start_time = time.perf_counter()  # Start timing

    # Parse the JSON filter string into a dictionary.
    raw_filter = parse_filter_json(filter_query)
    filters = parse_deep_object_filters(raw_filter)
    
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

    # Prepare extra query parameters for pagination links.
    extra_params: Dict[str, Any] = {}
    if sort:
        extra_params["sort"] = sort
    if filter_query:
        extra_params["filter"] = filter_query

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
