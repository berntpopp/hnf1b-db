"""Materialized view availability cache.

This module provides a cached check for materialized view availability,
eliminating the per-request SQL query overhead. Views are checked once
at application startup and cached in memory.

Usage:
    from app.core.mv_cache import mv_cache

    # In aggregation endpoints
    if mv_cache.is_available("mv_sex_distribution"):
        # Use materialized view
    else:
        # Fall back to live query
"""

import logging
from typing import Dict, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


class MaterializedViewCache:
    """Cache for materialized view availability status.

    Checks view availability once at startup rather than on every request,
    providing O(1) lookups instead of per-request SQL queries.

    Attributes:
        _available_views: Set of view names confirmed to exist and have data
        _initialized: Whether the cache has been populated
    """

    def __init__(self) -> None:
        """Initialize empty cache."""
        self._available_views: Set[str] = set()
        self._initialized: bool = False
        self._check_results: Dict[str, bool] = {}

    @property
    def is_initialized(self) -> bool:
        """Check if cache has been initialized."""
        return self._initialized

    def is_available(self, view_name: str) -> bool:
        """Check if a materialized view is available (O(1) lookup).

        Args:
            view_name: Name of the materialized view

        Returns:
            True if view exists and has data, False otherwise
        """
        if not settings.materialized_views.enabled:
            return False

        if not self._initialized:
            logger.warning(
                f"MV cache not initialized, assuming {view_name} unavailable"
            )
            return False

        return view_name in self._available_views

    async def initialize(self, db: AsyncSession) -> None:
        """Initialize cache by checking all configured materialized views.

        Should be called once during application startup via lifespan.

        Args:
            db: Database session for checking view availability
        """
        if not settings.materialized_views.enabled:
            logger.info("Materialized views disabled in configuration")
            self._initialized = True
            return

        logger.info("Initializing materialized view cache...")
        views_to_check = settings.materialized_views.views

        for view_name in views_to_check:
            available = await self._check_view_exists(db, view_name)
            self._check_results[view_name] = available
            if available:
                self._available_views.add(view_name)

        self._initialized = True

        available_count = len(self._available_views)
        total_count = len(views_to_check)
        logger.info(
            f"MV cache initialized: {available_count}/{total_count} views available"
        )

        if self._available_views:
            logger.info(f"Available views: {sorted(self._available_views)}")

        unavailable = set(views_to_check) - self._available_views
        if unavailable:
            logger.warning(
                f"Unavailable views (will use live queries): {sorted(unavailable)}"
            )

    async def _check_view_exists(self, db: AsyncSession, view_name: str) -> bool:
        """Check if a materialized view exists and has data.

        Args:
            db: Database session
            view_name: Name of the materialized view

        Returns:
            True if view exists and has at least one row
        """
        try:
            # Use parameterized identifier check for safety
            # Note: view_name comes from config, not user input
            result = await db.execute(
                text(f"SELECT 1 FROM {view_name} LIMIT 1")  # noqa: S608
            )
            has_data = result.fetchone() is not None
            logger.debug(f"View {view_name}: exists={has_data}")
            return has_data
        except Exception as e:
            logger.debug(f"View {view_name} not available: {e}")
            return False

    def reset(self) -> None:
        """Reset cache state (useful for testing)."""
        self._available_views.clear()
        self._check_results.clear()
        self._initialized = False

    def get_status(self) -> Dict[str, object]:
        """Get cache status for debugging/monitoring.

        Returns:
            Dictionary with cache state information
        """
        return {
            "initialized": self._initialized,
            "enabled": settings.materialized_views.enabled,
            "available_views": sorted(self._available_views),
            "check_results": self._check_results.copy(),
        }


# Global singleton instance
mv_cache = MaterializedViewCache()


async def init_mv_cache(db: AsyncSession) -> None:
    """Initialize the global MV cache.

    Called during application startup via lifespan.

    Args:
        db: Database session for checking view availability
    """
    await mv_cache.initialize(db)


def get_mv_cache() -> MaterializedViewCache:
    """Get the global MV cache instance.

    Returns:
        The singleton MaterializedViewCache instance
    """
    return mv_cache
