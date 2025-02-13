# File: app/endpoints/individuals.py
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
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
    summary="Get Individuals"
)
async def get_individuals(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of individuals per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'individual_id' for ascending or '-individual_id' "
            "for descending order)"
        ),
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"Sex": "male", "individual_id": {"gt": "ind0930"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "individual_id, Sex, individual_DOI, IndividualIdentifier, family_history, age_onset, cohort"
        ),
    ),
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of individuals, optionally filtered by a JSON filter
    and/or a search query.

    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - individual_id
      - Sex
      - individual_DOI
      - IndividualIdentifier
      - family_history
      - age_onset
      - cohort

    Example:
      /individuals?sort=-individual_id&page=1&page_size=10&filter={"Sex": "male"}&q=ind0930
    """
    start_time = time.perf_counter()  # Start measuring execution time

    # Parse and convert the JSON filter (if provided) into a MongoDB filter.
    raw_filter = parse_filter_json(filter_query)
    filters = parse_deep_object_filters(raw_filter)

    # If a search query 'q' is provided, build a search filter for predefined fields.
    if q:
        search_fields = [
            "individual_id", "Sex", "individual_DOI", "IndividualIdentifier",
            "family_history", "age_onset", "cohort"
        ]
        search_filter = {"$or": [{field: {"$regex": q, "$options": "i"}} for field in search_fields]}
        filters = {"$and": [filters, search_filter]} if filters else search_filter

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

    # Build the base URL (without query parameters)
    base_url = str(request.url).split("?")[0]

    # Include current query parameters (e.g., sort, filter, and search query) in pagination links.
    extra_params: Dict[str, Any] = {}
    if sort:
        extra_params["sort"] = sort
    if filter_query:
        extra_params["filter"] = filter_query
    if q:
        extra_params["q"] = q

    end_time = time.perf_counter()  # End timing
    execution_time = end_time - start_time

    # Build pagination metadata, including execution time in milliseconds.
    meta = build_pagination_meta(
        base_url, page, page_size, total,
        query_params=extra_params,
        execution_time=execution_time
    )

    # Convert MongoDB documents (with ObjectId values) to JSON-friendly data.
    response_data = jsonable_encoder(
        {"data": individuals, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)},
    )
    return response_data
