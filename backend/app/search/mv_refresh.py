"""Materialized view refresh utilities.

Provides functions for refreshing the global_search_index MV
and scheduling refreshes based on staleness.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# In-memory timestamp of last refresh (per-process)
_last_refresh_time: datetime | None = None


async def refresh_global_search_index(
    db: AsyncSession,
    concurrently: bool = True,
) -> None:
    """Refresh the global search materialized view.

    Args:
        db: Database session
        concurrently: If True, uses CONCURRENTLY (doesn't block reads
                     but requires unique index on MV)
    """
    global _last_refresh_time

    keyword = "CONCURRENTLY" if concurrently else ""
    try:
        refresh_sql = f"REFRESH MATERIALIZED VIEW {keyword} global_search_index"
        await db.execute(text(refresh_sql))
        await db.commit()
        _last_refresh_time = datetime.utcnow()
        logger.info("Refreshed global_search_index materialized view")
    except Exception as e:
        logger.error(f"Failed to refresh global_search_index: {e}")
        # Don't raise - refresh failure shouldn't break the main operation
        await db.rollback()


async def schedule_refresh_if_stale(
    db: AsyncSession,
    max_age_seconds: int = 60,
) -> bool:
    """Refresh MV if older than max_age_seconds.

    Uses in-memory timestamp for fast checking. Falls back to
    PostgreSQL pg_stat_user_tables if no timestamp available.

    Args:
        db: Database session
        max_age_seconds: Maximum age in seconds before refresh

    Returns:
        True if refresh was performed, False otherwise
    """
    global _last_refresh_time

    # Fast path: check in-memory timestamp
    if _last_refresh_time:
        age = (datetime.utcnow() - _last_refresh_time).total_seconds()
        if age < max_age_seconds:
            return False

    # Slow path: check PostgreSQL statistics
    try:
        age_sql = """
            SELECT EXTRACT(EPOCH FROM (
                NOW() - COALESCE(last_analyze, last_autoanalyze, '1970-01-01')
            )) as age_seconds
            FROM pg_stat_user_tables
            WHERE relname = 'global_search_index'
        """
        result = await db.execute(text(age_sql))
        row = result.fetchone()

        if row and row.age_seconds is not None:
            if row.age_seconds < max_age_seconds:
                age_delta = timedelta(seconds=row.age_seconds)
                _last_refresh_time = datetime.utcnow() - age_delta
                return False
    except Exception as e:
        logger.warning(f"Could not check MV age: {e}")

    # Refresh needed
    await refresh_global_search_index(db)
    return True


async def force_refresh(db: AsyncSession) -> None:
    """Force an immediate refresh of the MV.

    Use this after bulk data operations.
    """
    await refresh_global_search_index(db, concurrently=False)


class MVRefreshMiddleware:
    """Middleware-style class for triggering MV refresh after mutations.

    Usage:
        async with MVRefreshMiddleware(db) as mv:
            # Do mutations
            await create_phenopacket(...)
            mv.mark_dirty()
        # MV will be refreshed after context exits if marked dirty
    """

    def __init__(self, db: AsyncSession, max_age_seconds: int = 60) -> None:
        """Initialize middleware with database session and staleness threshold."""
        self.db = db
        self.max_age_seconds = max_age_seconds
        self._dirty = False

    async def __aenter__(self) -> "MVRefreshMiddleware":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context, triggering refresh if dirty and no exception."""
        if self._dirty and exc_type is None:
            await schedule_refresh_if_stale(self.db, self.max_age_seconds)

    def mark_dirty(self) -> None:
        """Mark that data has changed and MV may need refresh."""
        self._dirty = True
