import json
import re
import urllib.parse
import math
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

# Pre-compile the regex pattern used for filter parsing.
_FILTER_REGEX = re.compile(r"filter\[(\w+)(?:\]\[(\w+)\])?\]")


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
    op_map = {
        "gt": "$gt",
        "gte": "$gte",
        "lt": "$lt",
        "lte": "$lte",
        "ne": "$ne",
        "in": "$in",
    }
    for key, value in query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
            match = _FILTER_REGEX.fullmatch(key)
            if match:
                field = match.group(1)
                operator = match.group(2)
                if operator:
                    mongo_op = op_map.get(operator)
                    if not mongo_op:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Unsupported operator: {operator}"
                        )
                    if mongo_op == "$in":
                        filters[field] = {mongo_op: value.split(",")}
                    else:
                        filters.setdefault(field, {})[mongo_op] = value
                else:
                    filters[field] = value
    return filters


def parse_filter_json(filter_json: Optional[str]) -> Dict[str, Any]:
    """
    Parses a JSON string provided as the filter parameter.
    
    Example:
       '{"Sex": "male", "individual_id": {"gt": "ind0930"}}'
    """
    if not filter_json:
        return {}
    try:
        return json.loads(filter_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON in filter parameter") from e


def parse_deep_object_filters(filter_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a filter dictionary into a MongoDB filter.
    
    Supported operators (lowercase):
      - gt, gte, lt, lte, ne, in
      
    Example:
      { "age": {"gt": "30"}, "Sex": "male" }
    becomes:
      { "age": {"$gt": "30"}, "Sex": "male" }
    """
    filters = {}
    op_map = {
        "gt": "$gt",
        "gte": "$gte",
        "lt": "$lt",
        "lte": "$lte",
        "ne": "$ne",
        "in": "$in",
    }
    for field, value in filter_obj.items():
        if isinstance(value, dict):
            sub_filter = {}
            for op, v in value.items():
                if op in op_map:
                    if op == "in" and isinstance(v, str):
                        sub_filter[op_map[op]] = v.split(",")
                    else:
                        sub_filter[op_map[op]] = v
            filters[field] = sub_filter
        else:
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
    base_url: str,
    page: int,
    page_size: int,
    total: int,
    query_params: Optional[Dict[str, Any]] = None,
    execution_time: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Returns a metadata dictionary following JSON:API conventions.
    
    Contains:
      - total: total number of documents.
      - total_pages: total number of pages.
      - page: current page number.
      - page_size: number of items per page.
      - links: URLs to prev/next pages (if applicable). The links include
               any extra query parameters (e.g. filter and sort) provided.
      - execution_time_ms: (optional) Execution time in milliseconds.
    """
    meta = {"total": total, "page": page, "page_size": page_size}
    # Calculate total pages (using ceiling division)
    total_pages = (total + page_size - 1) // page_size
    meta["total_pages"] = total_pages

    links = {}
    query_params = query_params or {}

    if page > 1:
        prev_query = query_params.copy()
        prev_query.update({"page": page - 1, "page_size": page_size})
        links["prev"] = f"{base_url}?{urllib.parse.urlencode(prev_query)}"
    if page * page_size < total:
        next_query = query_params.copy()
        next_query.update({"page": page + 1, "page_size": page_size})
        links["next"] = f"{base_url}?{urllib.parse.urlencode(next_query)}"
    meta["links"] = links

    if execution_time is not None:
        meta["execution_time_ms"] = round(execution_time * 1000, 2)
    return meta
