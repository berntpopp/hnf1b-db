import json
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
    for key, value in query_params.items():
        if key.startswith("filter[") and key.endswith("]"):
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
                    }
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
    except Exception as e:
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
    base_url: str, page: int, page_size: int, total: int, execution_time: Optional[float] = None
) -> Dict[str, Any]:
    """
    Returns a metadata dictionary following JSON:API conventions.
    
    Contains:
      - total: total number of documents.
      - page: current page number.
      - page_size: number of items per page.
      - links: URLs to prev/next pages (if applicable).
      - execution_time_ms: (optional) Execution time in milliseconds.
    """
    meta = {"total": total, "page": page, "page_size": page_size}
    links = {}
    if page > 1:
        links["prev"] = f"{base_url}?page={page - 1}&page_size={page_size}"
    if page * page_size < total:
        links["next"] = f"{base_url}?page={page + 1}&page_size={page_size}"
    meta["links"] = links
    if execution_time is not None:
        meta["execution_time_ms"] = round(execution_time * 1000, 2)
    return meta
