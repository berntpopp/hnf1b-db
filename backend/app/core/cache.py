# app/core/cache.py
"""Redis-based caching service for distributed, persistent caching.

This module provides a unified caching interface that:
- Uses Redis for distributed caching (production)
- Falls back to in-memory cache if Redis is unavailable (development)
- Supports JSON serialization with automatic encoding/decoding
- Provides TTL (time-to-live) for cache expiration
- Includes rate limiting support via atomic counters

Usage:
    from app.core.cache import cache

    # Initialize on app startup
    await cache.connect()

    # Basic operations
    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")

    # JSON operations
    await cache.set_json("user:123", {"name": "John"}, ttl=3600)
    user = await cache.get_json("user:123")

    # Rate limiting
    count = await cache.incr("rate:192.168.1.1", ttl=1)
    if count > 5:
        raise RateLimitExceeded()

    # Close on app shutdown
    await cache.close()
"""

import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Simple in-memory cache with TTL support for fallback when Redis is unavailable.

    Uses OrderedDict for LRU eviction when size limit is reached.
    Thread-safe for single-process async applications.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize in-memory cache.

        Args:
            max_size: Maximum number of items to store
        """
        self._cache: OrderedDict[str, tuple[Any, Optional[datetime]]] = OrderedDict()
        self._max_size = max_size
        self._counters: dict[str, tuple[int, Optional[datetime]]] = {}

    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]

        # Check expiration
        if expires_at and datetime.now() > expires_at:
            del self._cache[key]
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None

        # LRU eviction if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def incr(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment counter with optional TTL (for rate limiting)."""
        now = datetime.now()

        if key in self._counters:
            count, existing_expires = self._counters[key]
            if existing_expires and now > existing_expires:
                # Expired, reset counter
                count = 0

            count += 1
            new_expires = now + timedelta(seconds=ttl) if ttl else None
            self._counters[key] = (count, new_expires)
            return count
        else:
            new_expires = now + timedelta(seconds=ttl) if ttl else None
            self._counters[key] = (1, new_expires)
            return 1

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._counters.clear()

    def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern (simple glob support).

        Supports simple patterns ending with '*' (e.g., "rate_limit:*").

        Args:
            pattern: Glob pattern (e.g., "rate_limit:*")

        Returns:
            Number of keys deleted
        """
        import fnmatch

        deleted = 0

        # Clear matching keys from cache
        keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._cache[key]
            deleted += 1

        # Clear matching keys from counters
        counter_keys_to_delete = [
            k for k in self._counters.keys() if fnmatch.fnmatch(k, pattern)
        ]
        for key in counter_keys_to_delete:
            del self._counters[key]
            deleted += 1

        return deleted


class CacheService:
    """Redis-based cache with JSON serialization and automatic fallback.

    Features:
    - Async Redis connection with connection pooling
    - Automatic fallback to in-memory cache if Redis is unavailable
    - JSON serialization for complex objects
    - TTL support for cache expiration
    - Rate limiting support via atomic INCR
    - Graceful error handling with logging
    """

    def __init__(self):
        """Initialize cache service (not connected yet)."""
        self._redis: Optional[aioredis.Redis] = None
        self._fallback = InMemoryCache()
        self._connected = False
        self._redis_url: Optional[str] = None

    async def connect(self, redis_url: Optional[str] = None) -> None:
        """Initialize Redis connection with fallback.

        Args:
            redis_url: Redis connection URL (default: from settings)
        """
        # Import here to avoid circular imports
        from app.core.config import settings

        self._redis_url = redis_url or settings.REDIS_URL

        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"Redis connected: {self._redis_url.split('@')[-1]}")
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(
                f"Redis unavailable ({e}), using in-memory fallback. "
                "This is fine for development but not recommended for production."
            )
            self._redis = None
            self._connected = False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()  # type: ignore[attr-defined]
            self._redis = None
            self._connected = False
            logger.info("Redis connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected and self._redis is not None

    async def get(self, key: str) -> Optional[str]:
        """Get string value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if self._redis:
            try:
                return await self._redis.get(key)
            except RedisError as e:
                logger.warning(f"Redis get error for {key}: {e}")
                return self._fallback.get(key)
        return self._fallback.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set string value with optional TTL.

        Args:
            key: Cache key
            value: String value to cache
            ttl: Time-to-live in seconds (None = no expiration)

        Returns:
            True if successful
        """
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ttl)
                return True
            except RedisError as e:
                logger.warning(f"Redis set error for {key}: {e}")
                return self._fallback.set(key, value, ttl)
        return self._fallback.set(key, value, ttl)

    async def get_json(self, key: str) -> Optional[dict[str, Any]]:
        """Get JSON value from cache.

        Args:
            key: Cache key

        Returns:
            Deserialized dict or None if not found
        """
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error for {key}: {e}")
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set JSON value with optional TTL.

        Args:
            key: Cache key
            value: Dict to serialize and cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            logger.warning(f"JSON encode error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except RedisError as e:
                logger.warning(f"Redis delete error for {key}: {e}")
                return self._fallback.delete(key)
        return self._fallback.delete(key)

    async def incr(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment counter with optional TTL (for rate limiting).

        Args:
            key: Counter key
            ttl: Time-to-live in seconds (for sliding window)

        Returns:
            New counter value
        """
        if self._redis:
            try:
                count = await self._redis.incr(key)
                if count == 1 and ttl:
                    await self._redis.expire(key, ttl)
                return int(count)
            except RedisError as e:
                logger.warning(f"Redis incr error for {key}: {e}")
                return self._fallback.incr(key, ttl)
        return self._fallback.incr(key, ttl)

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        if self._redis:
            try:
                return bool(await self._redis.exists(key))
            except RedisError as e:
                logger.warning(f"Redis exists error for {key}: {e}")
                return self._fallback.get(key) is not None
        return self._fallback.get(key) is not None

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Uses Redis SCAN for efficient pattern matching.
        Falls back to in-memory pattern matching if Redis is unavailable.

        Args:
            pattern: Glob pattern (e.g., "vep:*", "rate_limit:*")

        Returns:
            Number of keys deleted
        """
        if self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                return len(keys)
            except RedisError as e:
                logger.warning(f"Redis clear_pattern error for {pattern}: {e}")
                return self._fallback.clear_pattern(pattern)
        return self._fallback.clear_pattern(pattern)


# Global cache instance
cache = CacheService()


async def init_cache() -> None:
    """Initialize cache on application startup."""
    await cache.connect()


async def close_cache() -> None:
    """Close cache on application shutdown."""
    await cache.close()
