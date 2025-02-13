# File: app/endpoints/search.py
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId

from app.database import db
from app.utils import build_pagination_meta

router = APIRouter()


@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="Search across Individuals, Variants, and Publications",
)
async def search_documents(
    request: Request,
    q: str = Query(..., description="Search query string"),
    collection: Optional[str] = Query(
        None,
        description=(
            "Optional: Limit search to a specific collection. Allowed values: "
            "'individuals', 'variants', or 'publications'."
        ),
    ),
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of items per page"),
) -> Dict[str, Any]:
    """
    Performs a case-insensitive search against a predefined set of fields in the
    individuals, variants, and publications collections.

    If the `collection` parameter is specified, only that collection is searched.
    The response follows JSON:API recommendations, including pagination metadata.

    Example:
        /api/search?q=HNF1B&collection=individuals&page=1&page_size=10
    """
    start_time = time.perf_counter()

    allowed_collections = ["individuals", "variants", "publications"]
    if collection:
        if collection not in allowed_collections:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid collection. Allowed values are: {', '.join(allowed_collections)}",
            )
        collections_to_search = [collection]
    else:
        collections_to_search = allowed_collections

    # Define search fields per collection for regex matching.
    search_fields = {
        "individuals": ["individual_id", "Sex", "individual_DOI", "IndividualIdentifier"],
        "variants": ["variant_id", "hg19", "hg19_INFO", "hg38", "hg38_INFO", "variant_type"],
        "publications": ["publication_id", "publication_type", "title", "abstract", "DOI", "PMID", "journal"],
    }

    # Create a case-insensitive regex filter.
    regex = {"$regex": q, "$options": "i"}
    results: Dict[str, Any] = {}

    for coll in collections_to_search:
        # Build a filter that matches if any of the specified fields match the regex.
        filter_query = {"$or": [{field: regex} for field in search_fields.get(coll, [])]}
        total = await db[coll].count_documents(filter_query)
        skip_count = (page - 1) * page_size
        cursor = db[coll].find(filter_query).skip(skip_count).limit(page_size)
        documents = await cursor.to_list(length=page_size)
        base_url = str(request.url).split("?")[0]
        meta = build_pagination_meta(
            base_url, page, page_size, total, query_params={"q": q, "collection": coll}
        )
        results[coll] = {"data": documents, "meta": meta}

    end_time = time.perf_counter()
    execution_time_ms = round((end_time - start_time) * 1000, 2)
    response = {"results": results, "execution_time_ms": execution_time_ms}

    # Use custom encoder for ObjectId to avoid JSON serialization errors.
    return jsonable_encoder(response, custom_encoder={ObjectId: lambda o: str(o)})
