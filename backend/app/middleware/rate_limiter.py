"""Rate limiting middleware using Redis for distributed rate limiting.

Implements sliding window rate limiting to prevent API abuse.
Uses Redis for distributed rate limiting across multiple backend instances.
Falls back to in-memory rate limiting if Redis is unavailable.

Configuration is loaded from config.yaml via app.core.config.
"""

import logging
from typing import Dict

from fastapi import HTTPException, Request

from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Checks X-Forwarded-For header first (for proxied requests),
    then falls back to direct client IP.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header (for requests behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    # Default if no client info available
    return "unknown"


async def check_rate_limit(request: Request) -> None:
    """Check if client has exceeded rate limit using Redis.

    Uses sliding window rate limiting with atomic Redis operations.
    Falls back to in-memory rate limiting if Redis is unavailable.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded

    Configuration:
        Loaded from config.yaml:
        - rate_limiting.api.requests_per_second: Max requests per window
        - rate_limiting.api.window_seconds: Time window in seconds
    """
    client_ip = get_client_ip(request)
    key = f"rate_limit:{client_ip}"

    # Get rate limit configuration from YAML config
    limit = settings.rate_limiting.api.requests_per_second
    window = settings.rate_limiting.api.window_seconds

    # Increment counter atomically (Redis INCR is atomic)
    count = await cache.incr(key, ttl=window)

    if count > limit:
        logger.warning(
            f"Rate limit exceeded for IP {client_ip}: "
            f"{count}/{limit} requests in {window}s"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Maximum {limit} requests per {window} seconds allowed",
                "retry_after": window,
                "current_count": count,
            },
            headers={"Retry-After": str(window)},
        )

    logger.debug(
        f"Rate limit check passed for IP {client_ip}: "
        f"{count}/{limit} requests in {window}s"
    )


async def reset_rate_limits() -> None:
    """Reset all rate limit counters.

    Clears all rate limit keys from Redis.
    Useful for testing or administrative purposes.
    """
    deleted = await cache.clear_pattern("rate_limit:*")
    logger.info(f"Reset {deleted} rate limit counters")


def get_rate_limit_status(request: Request) -> Dict[str, int]:
    """Get current rate limit status for a client (sync version for headers).

    Note: This is a synchronous function for use in response headers.
    For actual rate limiting, use check_rate_limit() which is async.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with rate limit info for response headers
    """
    limit = settings.rate_limiting.api.requests_per_second
    window = settings.rate_limiting.api.window_seconds

    return {
        "X-RateLimit-Limit": limit,
        "X-RateLimit-Window": window,
    }
