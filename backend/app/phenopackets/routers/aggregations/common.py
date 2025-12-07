"""Common imports and utilities for aggregation endpoints.

This module provides shared dependencies used across all aggregation
sub-modules to reduce code duplication and ensure consistency.
"""

import logging
from typing import Any, Dict, List

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
]


async def check_materialized_view_exists(
    db: AsyncSession, view_name: str
) -> bool:
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
