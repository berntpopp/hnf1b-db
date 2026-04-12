"""Per-endpoint rate limiting via FastAPI Depends().

Uses cache.incr() with TTL for counting. Redis provides fixed-window
semantics (TTL set on first increment). The in-memory fallback provides
sliding-window semantics (TTL resets on each increment). Tests verify
count-and-reject logic; exact window semantics require Redis.
"""

from fastapi import HTTPException, Request, status

from app.core.cache import cache


class RateLimiter:
    """FastAPI dependency for per-endpoint rate limiting.

    Usage:
        @router.post("/reset", dependencies=[Depends(RateLimiter("reset", 3, 3600))])
        async def request_reset(...): ...
    """

    def __init__(self, key_prefix: str, max_requests: int, window_seconds: int):
        """Initialize rate limiter.

        Args:
            key_prefix: Unique prefix for the cache key (e.g., "reset", "login").
            max_requests: Maximum number of requests allowed per window.
            window_seconds: Time window in seconds for the rate limit.
        """
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        """Check rate limit; raise 429 if exceeded."""
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{self.key_prefix}:{client_ip}"
        count = await cache.incr(key, ttl=self.window_seconds)

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded. "
                    f"Max {self.max_requests} requests per {self.window_seconds}s."
                ),
                headers={"Retry-After": str(self.window_seconds)},
            )
