"""Materialized view refresh utilities.

Provides functions for refreshing the global_search_index MV
and scheduling refreshes based on staleness.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker

logger = logging.getLogger(__name__)

# In-memory timestamp of last refresh (per-process) and pending trailing refresh task
_last_refresh_time: datetime | None = None
_pending_refresh_task: asyncio.Task[None] | None = None


async def _delayed_refresh(delay_seconds: float) -> None:
    """Wait for the cooldown window to expire, then execute a trailing MV refresh."""
    global _pending_refresh_task
    try:
        await asyncio.sleep(max(0.01, delay_seconds))
        await refresh_global_search_index()
    except asyncio.CancelledError:
        return
    finally:
        _pending_refresh_task = None


def _ensure_trailing_refresh(delay_seconds: float) -> None:
    """Schedule a single trailing refresh task if one is not already active."""
    global _pending_refresh_task
    if _pending_refresh_task is not None and not _pending_refresh_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
        _pending_refresh_task = loop.create_task(_delayed_refresh(delay_seconds))
    except RuntimeError:
        pass


async def refresh_global_search_index(
    db: AsyncSession | None = None,
    concurrently: bool = True,
) -> None:
    """Refresh the global search and aggregation materialized views.

    Args:
        db: Database session (if None, creates one via async_session_maker)
        concurrently: If True, uses CONCURRENTLY (doesn't block reads
                     but requires unique index on MV)
    """
    global _last_refresh_time, _pending_refresh_task

    if _pending_refresh_task is not None and not _pending_refresh_task.done():
        current = asyncio.current_task()
        if _pending_refresh_task is not current:
            _pending_refresh_task.cancel()
            _pending_refresh_task = None

    if db is None:
        async with async_session_maker() as session:
            await refresh_global_search_index(session, concurrently=concurrently)
            return

    keyword = "CONCURRENTLY" if concurrently else ""
    try:
        refresh_sql = f"REFRESH MATERIALIZED VIEW {keyword} global_search_index"
        await db.execute(text(refresh_sql))
        try:
            await db.execute(text("SELECT refresh_all_aggregation_views()"))
        except SQLAlchemyError as err:
            logger.warning("Could not refresh aggregation materialized views: %s", err)
        await db.commit()
        _last_refresh_time = datetime.now(timezone.utc)
        logger.info("Refreshed global_search_index and aggregation materialized views")
    except SQLAlchemyError as e:
        logger.error(f"Failed to refresh global_search_index: {e}")
        # Don't raise - refresh failure shouldn't break the main operation
        await db.rollback()


async def schedule_refresh_if_stale(
    db: AsyncSession | None = None,
    max_age_seconds: int = 60,
) -> bool:
    """Refresh MV if older than max_age_seconds, or schedule a trailing refresh.

    Uses in-memory timestamp for fast checking. Falls back to
    PostgreSQL pg_stat_user_tables if no timestamp available.

    Args:
        db: Database session (if None, creates one via async_session_maker)
        max_age_seconds: Maximum age in seconds before refresh

    Returns:
        True if immediate refresh was performed, False if throttled
        (with trailing refresh scheduled)
    """
    global _last_refresh_time

    if db is None:
        async with async_session_maker() as session:
            return await schedule_refresh_if_stale(
                session, max_age_seconds=max_age_seconds
            )

    # Fast path: check in-memory timestamp
    if _last_refresh_time:
        age = (datetime.now(timezone.utc) - _last_refresh_time).total_seconds()
        if age < max_age_seconds:
            _ensure_trailing_refresh(max_age_seconds - age)
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
            age_secs = float(row.age_seconds)
            if age_secs < max_age_seconds:
                age_delta = timedelta(seconds=age_secs)
                _last_refresh_time = datetime.now(timezone.utc) - age_delta
                _ensure_trailing_refresh(max_age_seconds - age_secs)
                return False
    except SQLAlchemyError as e:
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
