# File: app/endpoints/variants.py
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Variant
from app.database import db
from app.utils import parse_filters, parse_sort, build_pagination_meta

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Variants")
async def get_variants(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of variants per page"),
    sort: Optional[str] = Query(
        None, description="Sort field (e.g. 'variant_id' or '-variant_id')"
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of variants.

    The response includes variants with nested classifications and annotations.
    Supports JSON:API–style filtering via query parameters, e.g.:
        /variants?filter[status]=active&sort=-variant_id&page=2&page_size=10
    """
    # Build filters from the query parameters
    query_params = dict(request.query_params)
    filters = parse_filters(query_params)
    
    # Determine sort order; default to ascending by "variant_id"
    sort_option = parse_sort(sort) if sort else ("variant_id", 1)

    # Retrieve the collection and count the total documents matching filters
    collection = db.variants
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    # Build the MongoDB cursor using skip() and limit()
    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    variants = await cursor.to_list(length=page_size)

    if not variants:
        raise HTTPException(status_code=404, detail="No variants found")

    # Build pagination metadata
    base_url = str(request.url).split("?")[0]
    meta = build_pagination_meta(base_url, page, page_size, total)

    # Convert the data to JSON-friendly types (e.g. converting ObjectId to str)
    response_data = jsonable_encoder(
        {"data": variants, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
