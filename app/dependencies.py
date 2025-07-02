# File: app/dependencies.py
from fastapi import Query
from typing import Dict, Any, Optional


def parse_filter(
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated list of filters to apply. "
            "Format: field:value,field2:value2"
        ),
    )
) -> Dict[str, Any]:
    """
    Parses a filter query string into a dictionary.
    For example, if filter is "Sex:male,AgeReported:30",
    returns: {"Sex": "male", "AgeReported": "30"}
    """
    filters = {}
    if filter:
        parts = filter.split(",")
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                filters[key.strip()] = value.strip()
    return filters
