# File: app/endpoints/publications.py
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Publication
from app.database import db
from app.utils import parse_filters, parse_sort, build_pagination_meta

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Publications")
async def get_publications(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of publications per page"),
    sort: Optional[str] = Query(
        None, description="Sort field (e.g. 'publication_id' or '-publication_id')"
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of publications.

    Supports JSON:API–style filtering via query parameters.
    For example:
      /publications?filter[status]=active&filter[publication_date][gt]=2021-01-01&sort=-publication_id
    """
    # Extract all query parameters and build the filter dict.
    query_params = dict(request.query_params)
    filters = parse_filters(query_params)
    
    # Use the provided sort parameter or default to sorting by publication_id ascending.
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
    meta = build_pagination_meta(base_url, page, page_size, total)

    # Convert the publications to JSON-friendly format.
    response_data = jsonable_encoder(
        {"data": publications, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
