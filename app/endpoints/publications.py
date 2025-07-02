# File: app/endpoints/publications.py
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from app.models import Publication
from app.database import db
from app.utils import (
    parse_sort,
    build_pagination_meta,
    parse_filter_json,
    parse_deep_object_filters,
)

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Publications")
async def get_publications(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of publications per page"),
    sort: Optional[str] = Query(
        None,
        description="Sort field (e.g. 'publication_id' for ascending or '-publication_id' for descending order)",
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"status": "active", "publication_date": {"gt": "2021-01-01"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "publication_id, publication_type, title, abstract, DOI, PMID, journal"
        ),
    ),
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of publications, optionally filtered by a JSON filter
    and/or a search query.

    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - publication_id
      - publication_type
      - title
      - abstract
      - DOI
      - PMID
      - journal

    Example:
      /publications?sort=-publication_id&page=1&page_size=10&filter={"status": "active"}&q=2021
    """
    start_time = time.perf_counter()  # Start timing

    # Parse the JSON filter (if provided) into a MongoDB filter.
    raw_filter = parse_filter_json(filter_query)
    filters = parse_deep_object_filters(raw_filter)

    # If a search query 'q' is provided, build a search filter for predefined publication fields.
    if q:
        search_fields = [
            "publication_id",
            "publication_type",
            "title",
            "abstract",
            "DOI",
            "PMID",
            "journal",
        ]
        search_filter = {
            "$or": [{field: {"$regex": q, "$options": "i"}} for field in search_fields]
        }
        filters = {"$and": [filters, search_filter]} if filters else search_filter

    # Determine sort option (default to ascending by "publication_id").
    sort_option = parse_sort(sort) if sort else ("publication_id", 1)

    collection = db.publications
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    publications = await cursor.to_list(length=page_size)

    if not publications:
        raise HTTPException(status_code=404, detail="No publications found")

    base_url = str(request.url).split("?")[0]
    end_time = time.perf_counter()  # End timing
    exec_time = end_time - start_time

    # Prepare extra query parameters (including sort, filter, and search query).
    extra_params: Dict[str, Any] = {}
    if sort:
        extra_params["sort"] = sort
    if filter_query:
        extra_params["filter"] = filter_query
    if q:
        extra_params["q"] = q

    # Build pagination metadata including execution time (in ms).
    meta = build_pagination_meta(
        base_url,
        page,
        page_size,
        total,
        query_params=extra_params,
        execution_time=exec_time,
    )

    # Convert MongoDB documents (with ObjectId values) to JSON-friendly data.
    response_data = jsonable_encoder(
        {"data": publications, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)},
    )
    return response_data
