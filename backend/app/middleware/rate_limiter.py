"""Rate limiting middleware for variant search endpoint.

Implements in-memory rate limiting to prevent API abuse. For production
deployments, consider using Redis for distributed rate limiting.

Rate Limit: 10 requests per 60 seconds per IP address.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# In-memory rate limiter storage
# Format: {client_ip: [timestamp1, timestamp2, ...]}
REQUEST_COUNTS: Dict[str, List[datetime]] = defaultdict(list)

# Rate limit configuration
RATE_LIMIT = 10  # Maximum requests
RATE_WINDOW = 60  # Time window in seconds


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


def check_rate_limit(request: Request) -> None:
    """Check if client has exceeded rate limit.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded

    Rate Limit:
        - 10 requests per 60 seconds per IP address
        - Sliding window implementation
        - Old requests automatically cleaned up

    Note:
        For production with multiple backend instances, use Redis:
            from redis import Redis
            redis = Redis(host='localhost', port=6379)
            key = f"rate_limit:{client_ip}"
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, RATE_WINDOW)
            if count > RATE_LIMIT:
                raise HTTPException(status_code=429, ...)
    """
    client_ip = get_client_ip(request)
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_WINDOW)

    # Clean up old requests outside the time window
    REQUEST_COUNTS[client_ip] = [
        req_time for req_time in REQUEST_COUNTS[client_ip]
        if req_time > window_start
    ]

    # Check if rate limit exceeded
    current_count = len(REQUEST_COUNTS[client_ip])
    if current_count >= RATE_LIMIT:
        logger.warning(
            f"Rate limit exceeded for IP {client_ip}: "
            f"{current_count} requests in {RATE_WINDOW}s (limit: {RATE_LIMIT})"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": (
                    f"Maximum {RATE_LIMIT} requests per "
                    f"{RATE_WINDOW} seconds allowed"
                ),
                "retry_after": RATE_WINDOW,
                "current_count": current_count,
            }
        )

    # Record this request
    REQUEST_COUNTS[client_ip].append(now)
    logger.debug(
        f"Rate limit check passed for IP {client_ip}: "
        f"{current_count + 1}/{RATE_LIMIT} requests in {RATE_WINDOW}s"
    )


def reset_rate_limits() -> None:
    """Reset all rate limit counters.

    Useful for testing or administrative purposes.
    In production, this would clear the Redis cache.
    """
    REQUEST_COUNTS.clear()
    logger.info("All rate limit counters reset")


def get_rate_limit_status(request: Request) -> Dict[str, int]:
    """Get current rate limit status for a client.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with rate limit status:
            - requests_made: Number of requests in current window
            - requests_remaining: Number of requests remaining
            - window_seconds: Time window in seconds
            - limit: Maximum requests allowed
    """
    client_ip = get_client_ip(request)
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_WINDOW)

    # Clean up old requests
    REQUEST_COUNTS[client_ip] = [
        req_time for req_time in REQUEST_COUNTS[client_ip]
        if req_time > window_start
    ]

    requests_made = len(REQUEST_COUNTS[client_ip])
    requests_remaining = max(0, RATE_LIMIT - requests_made)

    return {
        "requests_made": requests_made,
        "requests_remaining": requests_remaining,
        "window_seconds": RATE_WINDOW,
        "limit": RATE_LIMIT,
    }
