# File: app/endpoints/search.py
import time
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from bson import ObjectId

from app.database import db

router = APIRouter()


def get_nested_value(doc: dict, field: str) -> Any:
    """
    Retrieve a nested value from a document using dot notation.
    If the value is encountered within a list, returns a list of values.
    """
    parts = field.split('.')
    current = doc
    for part in parts:
        if isinstance(current, list):
            values = []
            for item in current:
                if isinstance(item, dict) and part in item:
                    values.append(item[part])
            current = values
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


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
    reduce_doc: bool = Query(
        True,
        description=(
            "If true, only return minimal info for each matching document: "
            "the _id, the identifier field (individual_id, variant_id, or publication_id), "
            "and a dictionary of matched field values."
        ),
    ),
) -> Dict[str, Any]:
    """
    Performs a case-insensitive search against a predefined set of fields in the
    individuals, variants, and publications collections.

    If the `collection` parameter is specified, only that collection is searched.
    
    When `reduce_doc` is true, each matching document is reduced to include only:
      - _id (as a string)
      - The collection-specific identifier (individual_id, variant_id, or publication_id)
      - A "matched" dictionary containing only the fields that matched the query.

    Example:
        /api/search?q=HNF1B&collection=variants&page=1&page_size=10
    """
    start_time = time.perf_counter()
    pattern = re.compile(q, re.IGNORECASE)

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

    # Define the fields to search for each collection.
    # For nested fields, use dot notation (e.g., "classifications.verdict").
    search_fields = {
        "individuals": [
            "individual_id", "Sex", "individual_DOI", "IndividualIdentifier", "family_history", "age_onset", "cohort"
        ],
        "variants": [
            "variant_id",
            "hg19",
            "hg19_INFO",
            "hg38",
            "hg38_INFO",
            "variant_type",
            "classifications.verdict",
            "classifications.criteria",
            "annotations.c_dot",
            "annotations.p_dot",
            "annotations.impact",
            "annotations.variant_class",
        ],
        "publications": [
            "publication_id",
            "publication_type",
            "title",
            "abstract",
            "DOI",
            "PMID",
            "journal"
        ],
    }

    # Map each collection to its primary identifier field.
    identifier_fields = {
        "individuals": "individual_id",
        "variants": "variant_id",
        "publications": "publication_id",
    }

    results: Dict[str, Any] = {}

    for coll in collections_to_search:
        # Build a filter that matches if any of the specified fields match the regex.
        filter_query = {
            "$or": [{field: {"$regex": q, "$options": "i"}} for field in search_fields.get(coll, [])]
        }
        skip_count = (page - 1) * page_size
        cursor = db[coll].find(filter_query).skip(skip_count).limit(page_size)
        documents = await cursor.to_list(length=page_size)

        if reduce_doc:
            reduced_documents = []
            for doc in documents:
                reduced_doc = {
                    "_id": str(doc.get("_id")),
                    "id": doc.get(identifier_fields[coll]),
                }
                matched = {}
                for field in search_fields.get(coll, []):
                    value = get_nested_value(doc, field)
                    if value is None:
                        continue
                    # If the value is a list, collect all matching string elements.
                    if isinstance(value, list):
                        matches = [v for v in value if isinstance(v, str) and pattern.search(v)]
                        if matches:
                            matched[field] = matches
                    elif isinstance(value, str):
                        if pattern.search(value):
                            matched[field] = value
                    else:
                        # For non-string types, convert to string before matching.
                        s = str(value)
                        if pattern.search(s):
                            matched[field] = s
                reduced_doc["matched"] = matched
                reduced_documents.append(reduced_doc)
            results[coll] = {"data": reduced_documents}
        else:
            results[coll] = {"data": documents}

    end_time = time.perf_counter()
    execution_time_ms = round((end_time - start_time) * 1000, 2)
    response = {"results": results, "execution_time_ms": execution_time_ms}

    # Use a custom encoder for ObjectId to avoid JSON serialization errors.
    return jsonable_encoder(response, custom_encoder={ObjectId: lambda o: str(o)})
