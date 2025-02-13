# File: app/endpoints/proteins.py
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Protein
from app.database import db
from app.utils import parse_filters, parse_sort, build_pagination_meta

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Proteins")
async def get_proteins(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of proteins per page"),
    sort: Optional[str] = Query(
        None, description="Sort field (e.g. 'gene' for ascending or '-gene' for descending order). Defaults to sorting by gene."
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of proteins.

    This endpoint queries the `proteins` collection for protein structure and domain data.
    It supports JSON:API–style filtering via query parameters.
    For example:
      /proteins?filter[domain]=kinase&sort=-gene&page=2&page_size=10
    """
    start_time = time.perf_counter()  # Start timing

    # Build filters from the request query parameters.
    query_params = dict(request.query_params)
    filters = parse_filters(query_params)
    
    # Use provided sort or default to sorting by "gene" ascending.
    sort_option = parse_sort(sort) if sort else ("gene", 1)
    
    collection = db.proteins
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    proteins = await cursor.to_list(length=page_size)

    if not proteins:
        raise HTTPException(status_code=404, detail="No proteins found")

    base_url = str(request.url).split("?")[0]
    end_time = time.perf_counter()  # End timing
    exec_time = end_time - start_time

    # Build pagination metadata including execution time.
    meta = build_pagination_meta(base_url, page, page_size, total, execution_time=exec_time)
    
    # Convert the proteins and metadata into JSON-friendly types.
    response_data = jsonable_encoder(
        {"data": proteins, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
