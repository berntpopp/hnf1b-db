from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Individual
from app.database import db
from app.utils import parse_filters, parse_sort, build_pagination_meta

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Individuals")
async def get_individuals(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of individuals per page"),
    sort: Optional[str] = Query(
        None, description="Sort field (e.g. 'individual_id' or '-individual_id')"
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of individuals.

    Supports JSON:API filtering via query parameters.
    """
    query_params = dict(request.query_params)
    filters = parse_filters(query_params)
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
    meta = build_pagination_meta(base_url, page, page_size, total)
    
    # Use a custom encoder that converts ObjectId to str
    response_data = jsonable_encoder(
        {"data": individuals, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
