# File: app/endpoints/individuals.py
import json
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Individual
from app.database import db
from app.utils import (
    parse_sort,
    build_pagination_meta,
    parse_filter_json,
    parse_deep_object_filters,
)

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Individuals")
async def get_individuals(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of individuals per page"),
    sort: Optional[str] = Query(
        None,
        description="Sort field (e.g. 'individual_id' for ascending or '-individual_id' for descending order)",
    ),
    filter: Optional[str] = Query(
        None,
        description=(
            "Filtering criteria as a JSON string. Example: "
            "{\"Sex\": \"male\", \"individual_id\": {\"gt\": \"ind0930\"}}"
        ),
    ),
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of individuals.

    The filter parameter should be provided as a JSON string.
    
    Example:
      /individuals?sort=-individual_id&page=1&page_size=10&filter={"Sex": "male", "individual_id": {"gt": "ind0930"}}
    """
    start_time = time.perf_counter()  # Start measuring execution time

    # Parse the JSON filter into a dictionary.
    raw_filter = parse_filter_json(filter)
    filters = parse_deep_object_filters(raw_filter)

    # Determine the sort option (default to ascending by "individual_id").
    sort_option = parse_sort(sort) if sort else ("individual_id", 1)

    collection = db.individuals
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    individuals = await cursor.to_list(length=page_size)

    if not individuals:
        raise HTTPException(status_code=404, detail="No individuals found")

    base_url = str(request.url).split("?")[0]
    end_time = time.perf_counter()  # End timing
    execution_time = end_time - start_time

    # Build pagination metadata, including execution time in milliseconds.
    meta = build_pagination_meta(base_url, page, page_size, total, execution_time=execution_time)

    # Convert MongoDB documents (with ObjectId values) to JSON-friendly data.
    response_data = jsonable_encoder(
        {"data": individuals, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)},
    )
    return response_data
