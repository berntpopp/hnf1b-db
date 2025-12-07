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
    """Check if a materialized view exists and has data.

    Args:
        db: Database session
        view_name: Name of the materialized view

    Returns:
        True if view exists and has data, False otherwise
    """
    if not settings.materialized_views.enabled:
        return False

    try:
        result = await db.execute(
            text(f"SELECT 1 FROM {view_name} LIMIT 1")  # noqa: S608
        )
        return result.fetchone() is not None
    except Exception:
        logger.debug(f"Materialized view {view_name} not available, using live query")
        return False
