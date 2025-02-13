# File: app/endpoints/genes.py
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional
from bson import ObjectId
from app.models import Gene
from app.database import db
from app.utils import parse_filters, parse_sort, build_pagination_meta

router = APIRouter()

@router.get("/", response_model=Dict[str, Any], summary="Get Genes")
async def get_genes(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of genes per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'gene_symbol' for ascending or '-gene_symbol' for descending order)"
        )
    )
) -> Dict[str, Any]:
    """
    Retrieve a paginated list of genes.

    This endpoint returns gene structure data stored in the 'genes' collection.
    It supports JSON:API–style filtering via query parameters, for example:
      /genes?filter[status]=active&sort=-gene_symbol&page=2&page_size=10
    """
    start_time = time.perf_counter()  # Start timing

    # Build filters from query parameters.
    query_params = dict(request.query_params)
    filters = parse_filters(query_params)
    
    # Determine the sort option (default is ascending by "gene_symbol").
    sort_option = parse_sort(sort) if sort else ("gene_symbol", 1)
    
    collection = db.genes
    total = await collection.count_documents(filters)
    skip_count = (page - 1) * page_size

    # Build the MongoDB cursor using skip() and limit().
    cursor = collection.find(filters)
    if sort_option:
        cursor = cursor.sort(*sort_option)
    cursor = cursor.skip(skip_count).limit(page_size)
    genes = await cursor.to_list(length=page_size)

    if not genes:
        raise HTTPException(status_code=404, detail="No genes found")

    base_url = str(request.url).split("?")[0]
    end_time = time.perf_counter()  # End timing
    exec_time = end_time - start_time

    # Build extra query parameters (retain all except pagination-specific ones).
    extra_params: Dict[str, Any] = {
        k: v for k, v in request.query_params.items() if k not in {"page", "page_size"}
    }

    # Build pagination metadata including execution time.
    meta = build_pagination_meta(
        base_url, page, page_size, total, query_params=extra_params, execution_time=exec_time
    )

    # Convert the result to JSON-friendly data (e.g., convert ObjectId to str).
    response_data = jsonable_encoder(
        {"data": genes, "meta": meta},
        custom_encoder={ObjectId: lambda o: str(o)}
    )
    return response_data
