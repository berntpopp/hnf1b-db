# app/utils.py
"""Utility functions for FastAPI endpoints with PostgreSQL support."""

import json
import urllib.parse
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request


def parse_filter_json(filter_json: Optional[str]) -> Dict[str, Any]:
    """Parses a JSON string provided as the filter parameter.

    Example:
       '{"sex": "male", "individual_id": {"gt": "ind0930"}}'
    """
    if not filter_json:
        return {}
    try:
        return json.loads(filter_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400, detail="Invalid JSON in filter parameter"
        ) from e


def parse_deep_object_filters(filter_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a filter dictionary into a format suitable for repository queries.

    Supported operators (lowercase):
      - gt, gte, lt, lte, ne, in, eq

    Example:
      { "age": {"gt": "30"}, "sex": "male" }
    becomes:
      { "age": {"gt": "30"}, "sex": "male" }

    Note: The actual SQL filtering is handled by the repository layer.
    """
    filters = {}
    supported_operators = ["gt", "gte", "lt", "lte", "ne", "in", "eq"]

    for field, value in filter_obj.items():
        if isinstance(value, dict):
            # Handle operator-based filters
            sub_filter = {}
            for op, v in value.items():
                if op in supported_operators:
                    if op == "in" and isinstance(v, str):
                        sub_filter[op] = v.split(",")
                    else:
                        sub_filter[op] = v
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Unsupported filter operator: {op}"
                    )
            filters[field] = sub_filter
        else:
            # Simple equality filter
            filters[field] = value

    return filters


def build_repository_filters(
    filter_obj: Dict[str, Any], field_mapping: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Convert API filter format to repository filter format.

    Args:
        filter_obj: Parsed filter dictionary
        field_mapping: Optional mapping of API field names to model field names

    Returns:
        Dictionary suitable for repository filtering
    """
    filters = {}
    field_mapping = field_mapping or {}

    for field, value in filter_obj.items():
        # Map API field names to model field names if needed
        model_field = field_mapping.get(field, field)

        if isinstance(value, dict):
            # Handle complex filters (operators)
            # For now, we'll extract simple equality for the repositories
            # More complex filtering logic can be added to repositories as needed
            if "eq" in value:
                filters[model_field] = value["eq"]
            elif len(value) == 1:
                # Single operator - for simplicity, use the value directly
                # Repository layer can handle more complex logic
                op, val = next(iter(value.items()))
                if op == "in":
                    # Handle 'in' operator by checking the first value for now
                    # Full 'in' support would need repository enhancements
                    filters[model_field] = val[0] if val else None
                else:
                    filters[model_field] = val
        else:
            filters[model_field] = value

    return filters


def build_search_fields(
    search_term: str,
    default_fields: List[str],
    field_mapping: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Build list of search fields, mapping API fields to model fields.

    Args:
        search_term: The search term
        default_fields: Default fields to search in
        field_mapping: Optional mapping of API field names to model field names

    Returns:
        List of model field names to search
    """
    field_mapping = field_mapping or {}
    return [field_mapping.get(field, field) for field in default_fields]


def build_pagination_meta(
    base_url: str,
    page: int,
    page_size: int,
    total: int,
    query_params: Optional[Dict[str, Any]] = None,
    execution_time: Optional[float] = None,
) -> Dict[str, Any]:
    """Returns a metadata dictionary following JSON:API conventions.

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


def build_base_url(request: Request) -> str:
    """Extract base URL from request (without query parameters).

    Args:
        request: FastAPI request object

    Returns:
        Base URL string
    """
    return str(request.url).split("?")[0]


def model_to_dict(
    model_instance, exclude_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Convert SQLAlchemy model instance to dictionary for JSON serialization.

    Args:
        model_instance: SQLAlchemy model instance
        exclude_fields: Fields to exclude from the dictionary

    Returns:
        Dictionary representation of the model
    """
    exclude_fields = exclude_fields or []

    result = {}
    for column in model_instance.__table__.columns:
        field_name = column.name
        if field_name not in exclude_fields:
            value = getattr(model_instance, field_name)
            # Handle UUID and datetime serialization
            if hasattr(value, "__str__"):
                result[field_name] = str(value) if value else None
            else:
                result[field_name] = value

    return result


def apply_field_mapping(
    data: Dict[str, Any], field_mapping: Dict[str, str], reverse: bool = False
) -> Dict[str, Any]:
    """Apply field name mapping to data dictionary.

    Args:
        data: Data dictionary
        field_mapping: Mapping from source to target field names
        reverse: If True, reverse the mapping direction

    Returns:
        Dictionary with mapped field names
    """
    if reverse:
        # Reverse the mapping
        mapping = {v: k for k, v in field_mapping.items()}
    else:
        mapping = field_mapping

    result = {}
    for key, value in data.items():
        new_key = mapping.get(key, key)
        result[new_key] = value

    return result


# Field mappings for maintaining API compatibility
INDIVIDUAL_FIELD_MAPPING = {
    "Sex": "sex",
    "individual_DOI": "individual_doi",
    "DupCheck": "dup_check",
    "IndividualIdentifier": "individual_identifier",
    "Problematic": "problematic",
}

PUBLICATION_FIELD_MAPPING = {
    "PMID": "pmid",
    "DOI": "doi",
    "PDF": "pdf",
}

VARIANT_FIELD_MAPPING = {
    "reported": "reported_entries",
}


# Temporary stub functions for backward compatibility during migration
def parse_filters(query_params):
    """Temporary stub function for backward compatibility."""
    return {}


def parse_sort(sort_param):
    """Temporary stub function for backward compatibility."""
    if not sort_param:
        return None
    if sort_param.startswith("-"):
        return (sort_param[1:], -1)  # Descending
    return (sort_param, 1)  # Ascending
