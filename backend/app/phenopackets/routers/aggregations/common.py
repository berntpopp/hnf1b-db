"""Common imports and utilities for aggregation endpoints.

This module provides shared dependencies used across all aggregation
sub-modules to reduce code duplication and ensure consistency.
"""

import logging
from typing import Any, Dict, List, Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.mv_cache import mv_cache
from app.database import get_db
from app.phenopackets.models import (
    AggregationResult,
    Phenopacket,
)

logger = logging.getLogger(__name__)

# Re-export commonly used dependencies
__all__ = [
    # Logging
    "logger",
    # FastAPI
    "APIRouter",
    "Depends",
    "Query",
    # SQLAlchemy
    "AsyncSession",
    "func",
    "select",
    "text",
    # App modules
    "settings",
    "get_db",
    "AggregationResult",
    "Phenopacket",
    # Type hints
    "Any",
    "Dict",
    "List",
    # Shared helpers
    "check_materialized_view_exists",
    "calculate_percentages",
]


async def check_materialized_view_exists(db: AsyncSession, view_name: str) -> bool:
    """Check if a materialized view is available (O(1) cached lookup).

    This function now uses the startup-initialized MV cache instead of
    per-request SQL queries. The db parameter is kept for backward
    compatibility but is no longer used.

    Args:
        db: Database session (unused, kept for backward compatibility)
        view_name: Name of the materialized view

    Returns:
        True if view exists and has data, False otherwise
    """
    return mv_cache.is_available(view_name)


def calculate_percentages(
    rows: Sequence[Any],
    total: int,
    count_key: str = "count",
) -> List[Dict[str, Any]]:
    """Add a ``percentage`` field to each row based on ``(count / total) * 100``.

    Accepts either plain dict rows or SQLAlchemy row objects with a
    ``._mapping`` attribute. Any other row shape raises ``TypeError`` so the
    caller notices — we do NOT fall back to silently hoovering attributes
    via ``dir()``.

    Returns a **new** list of new dicts — the input rows are never mutated.

    Args:
        rows: Sequence of query result rows (dict or SQLAlchemy Row).
        total: Denominator for percentage calculation. If 0, percentage is 0.
        count_key: Field name holding the count (default ``"count"``).

    Returns:
        List of new dicts with every original field plus ``percentage``.

    Raises:
        TypeError: If any row is neither a dict nor exposes ``._mapping``.
    """
    result: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            data = dict(row._mapping)
        elif isinstance(row, dict):
            data = dict(row)
        else:
            raise TypeError(
                f"calculate_percentages expects dict or SQLAlchemy Row, "
                f"got {type(row).__name__}"
            )

        count_value = int(data.get(count_key, 0))
        data["percentage"] = (count_value / total * 100) if total > 0 else 0
        result.append(data)
    return result
