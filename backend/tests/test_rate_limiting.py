"""Tests for rate limiting middleware.

This module tests the rate limiting functionality using Redis (with in-memory fallback).
Tests the async rate limiting with distributed counter support.
"""

from typing import Optional

import pytest
from fastapi import HTTPException

from app.core.cache import cache
from app.core.config import settings
from app.middleware.rate_limiter import (
    check_rate_limit,
    get_client_ip,
    get_rate_limit_status,
    reset_rate_limits,
)

# Get rate limit values from config
RATE_LIMIT = settings.rate_limiting.api.requests_per_second
RATE_WINDOW = settings.rate_limiting.api.window_seconds


# Mock Request class for testing
class MockRequest:
    """Mock FastAPI Request for testing."""

    def __init__(
        self, client_host: str = "127.0.0.1", forwarded_for: Optional[str] = None
    ):
        """Initialize mock request with client host and optional forwarded headers."""
        self.client = type("obj", (object,), {"host": client_host})
        self.headers = {}
        if forwarded_for:
            self.headers["X-Forwarded-For"] = forwarded_for


class TestGetClientIP:
    """Test client IP extraction from request."""

    def test_direct_client_ip(self):
        """Test extraction of direct client IP."""
        request = MockRequest(client_host="192.168.1.100")
        assert get_client_ip(request) == "192.168.1.100"

    def test_forwarded_for_single_ip(self):
        """Test X-Forwarded-For with single IP."""
        request = MockRequest(client_host="127.0.0.1", forwarded_for="203.0.113.42")
        assert get_client_ip(request) == "203.0.113.42"

    def test_forwarded_for_multiple_ips(self):
        """Test X-Forwarded-For with multiple IPs (takes first)."""
        request = MockRequest(
            client_host="127.0.0.1",
            forwarded_for="203.0.113.42, 198.51.100.17, 192.0.2.1",
        )
        assert get_client_ip(request) == "203.0.113.42"

    def test_no_client_info(self):
        """Test fallback when no client info available."""
        request = MockRequest(client_host="127.0.0.1")
        request.client = None
        assert get_client_ip(request) == "unknown"


@pytest.fixture
def reset_cache():
    """Fixture to reset rate limits before each test.

    Uses in-memory fallback mode to avoid Redis connection issues in CI.
    This is a synchronous fixture that uses the use_fallback_only() method
    to prevent async event loop conflicts.
    """
    # Force in-memory mode to avoid Redis connection in tests
    cache.use_fallback_only()
    yield
    # Clear cache after test
    cache.clear_fallback()


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting functionality (async with Redis/in-memory fallback)."""

    async def test_within_rate_limit(self, reset_cache):
        """Test that requests within limit pass."""
        request = MockRequest(client_host="192.168.1.100")

        # Make requests below limit
        for i in range(RATE_LIMIT - 1):
            await check_rate_limit(request)  # Should not raise

    async def test_exactly_at_rate_limit(self, reset_cache):
        """Test that request at limit still passes."""
        request = MockRequest(client_host="192.168.1.101")

        # Make exactly RATE_LIMIT requests
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)  # Should not raise

    async def test_exceed_rate_limit(self, reset_cache):
        """Test that exceeding limit raises 429."""
        request = MockRequest(client_host="192.168.1.102")

        # Make RATE_LIMIT requests (at limit)
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        # Next request should raise HTTPException with status 429
        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request)

        assert exc.value.status_code == 429
        assert "Rate limit exceeded" in exc.value.detail["error"]
        assert exc.value.detail["retry_after"] == RATE_WINDOW

    async def test_rate_limit_per_ip(self, reset_cache):
        """Test that rate limits are tracked per IP address."""
        request1 = MockRequest(client_host="192.168.1.103")
        request2 = MockRequest(client_host="192.168.1.104")

        # First IP makes RATE_LIMIT requests (at limit)
        for i in range(RATE_LIMIT):
            await check_rate_limit(request1)

        # Second IP should still have full quota
        for i in range(RATE_LIMIT):
            await check_rate_limit(request2)  # Should not raise

        # First IP should be blocked
        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request1)
        assert exc.value.status_code == 429

    async def test_reset_rate_limits(self, reset_cache):
        """Test that reset clears all rate limit counters."""
        request = MockRequest(client_host="192.168.1.105")

        # Make RATE_LIMIT requests (at limit)
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        # Reset counters
        await reset_rate_limits()

        # Should be able to make requests again
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)  # Should not raise


class TestRateLimitStatus:
    """Test rate limit status query (synchronous helper)."""

    def test_status_returns_config_values(self):
        """Test status returns configured rate limit values."""
        request = MockRequest(client_host="192.168.1.200")
        status = get_rate_limit_status(request)

        assert status["X-RateLimit-Limit"] == RATE_LIMIT
        assert status["X-RateLimit-Window"] == RATE_WINDOW


@pytest.mark.asyncio
class TestRateLimitErrorDetails:
    """Test rate limit error response details."""

    async def test_error_contains_retry_after(self, reset_cache):
        """Test that error includes retry_after header."""
        request = MockRequest(client_host="192.168.1.110")

        # Exceed limit
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request)

        assert "retry_after" in exc.value.detail
        assert exc.value.detail["retry_after"] == RATE_WINDOW

    async def test_error_contains_current_count(self, reset_cache):
        """Test that error includes current request count."""
        request = MockRequest(client_host="192.168.1.111")

        # Exceed limit
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request)

        assert "current_count" in exc.value.detail
        # Count should be > RATE_LIMIT (the one that triggered the error)
        assert exc.value.detail["current_count"] > RATE_LIMIT

    async def test_error_message_helpful(self, reset_cache):
        """Test that error message is user-friendly."""
        request = MockRequest(client_host="192.168.1.112")

        # Exceed limit
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request)

        detail = exc.value.detail
        assert "Rate limit exceeded" in detail["error"]
        assert f"{RATE_LIMIT} requests" in detail["message"]
        assert f"{RATE_WINDOW} seconds" in detail["message"]

    async def test_retry_after_header_set(self, reset_cache):
        """Test that Retry-After header is set on 429 response."""
        request = MockRequest(client_host="192.168.1.113")

        # Exceed limit
        for i in range(RATE_LIMIT):
            await check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            await check_rate_limit(request)

        # Check headers dict exists and contains Retry-After
        assert exc.value.headers is not None
        assert "Retry-After" in exc.value.headers
        assert exc.value.headers["Retry-After"] == str(RATE_WINDOW)
