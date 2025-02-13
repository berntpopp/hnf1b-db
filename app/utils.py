import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

def parse_filters(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses query parameters that follow JSON:API filter syntax.
    
    Supported examples:
      - filter[price]=100             -> { "price": "100" }
      - filter[price][gt]=100         -> { "price": { "$gt": "100" } }
      - filter[price][lt]=200         -> { "price": { "$lt": "200" } }
      - filter[status]=active         -> { "status": "active" }
      - filter[category][in]=A,B,C    -> { "category": { "$in": ["A", "B", "C"] } }
    
    Note: Conversion (e.g. to int or datetime) should be handled in your model or later.
    """
    filters: Dict[str, Any] = {}
    # Loop through each query parameter key/value pair
    for key, value in query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
            # Look for pattern: filter[field] OR filter[field][operator]
            match = re.fullmatch(r"filter\[(\w+)(?:\]\[(\w+)\])?\]", key)
            if match:
                field = match.group(1)
                operator = match.group(2)
                if operator:
                    op_map = {
                        "gt": "$gt",
                        "gte": "$gte",
                        "lt": "$lt",
                        "lte": "$lte",
                        "ne": "$ne",
                        "in": "$in",
                        # You can add more operators here
                    }
                    mongo_op = op_map.get(operator)
                    if not mongo_op:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Unsupported operator: {operator}"
                        )
                    # For "$in", split the value by commas into a list.
                    if mongo_op == "$in":
                        filters[field] = {mongo_op: value.split(",")}
                    else:
                        filters.setdefault(field, {})[mongo_op] = value
                else:
                    # No operator means equality.
                    filters[field] = value
    return filters

def parse_sort(sort: Optional[str]) -> Optional[Tuple[str, int]]:
    """
    Parse the sort query parameter.
    
    Accepts:
      - sort=trade_date_time        -> ("trade_date_time", ASCENDING)
      - sort=-price                 -> ("price", DESCENDING)
    """
    if not sort:
        return None
    if sort.startswith("-"):
        return (sort[1:], DESCENDING)
    return (sort, ASCENDING)

def build_pagination_meta(
    base_url: str, page: int, page_size: int, total: int
) -> Dict[str, Any]:
    """
    Returns a metadata dictionary following JSON:API conventions.
    
    Contains:
      - total: total number of documents.
      - page: current page number.
      - page_size: number of items per page.
      - links: URLs to prev/next pages (if applicable).
    """
    meta = {"total": total, "page": page, "page_size": page_size}
    links = {}
    if page > 1:
        links["prev"] = f"{base_url}?page={page - 1}&page_size={page_size}"
    if page * page_size < total:
        links["next"] = f"{base_url}?page={page + 1}&page_size={page_size}"
    meta["links"] = links
    return meta
