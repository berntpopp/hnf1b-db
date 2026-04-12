"""Tests for per-endpoint RateLimiter dependency.

Verifies count-and-reject logic (Nth+1 returns 429 + Retry-After).
Does NOT verify exact window expiry timing — see design spec §6 for
the acknowledged Redis vs in-memory parity gap.
"""

from unittest.mock import MagicMock

import pytest

from app.auth.rate_limit import RateLimiter
from app.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear cache counters before each test."""
    cache.use_fallback_only()
    cache.clear_fallback()
    yield
    cache.clear_fallback()


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    """Requests within limit succeed (no exception)."""
    limiter = RateLimiter("test-allow", max_requests=3, window_seconds=3600)

    for _ in range(3):
        request = MagicMock()
        request.client.host = "127.0.0.1"
        await limiter(request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_rejects_over_limit():
    """Request exceeding limit gets 429 with Retry-After header."""
    from fastapi import HTTPException

    limiter = RateLimiter("test-reject", max_requests=2, window_seconds=3600)
    request = MagicMock()
    request.client.host = "127.0.0.1"

    # Use up the limit
    await limiter(request)
    await limiter(request)

    # Third request should fail
    with pytest.raises(HTTPException) as exc_info:
        await limiter(request)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limiter_keys_by_ip():
    """Different IPs have independent counters."""
    limiter = RateLimiter("test-ip", max_requests=1, window_seconds=3600)

    req1 = MagicMock()
    req1.client.host = "1.2.3.4"
    await limiter(req1)  # IP 1 uses its one request

    req2 = MagicMock()
    req2.client.host = "5.6.7.8"
    await limiter(req2)  # IP 2 should still succeed (different counter)
