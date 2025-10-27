"""Tests for rate limiting middleware.

This module tests the rate limiting functionality to prevent API abuse.
"""

import time
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException, Request

from app.middleware.rate_limiter import (
    RATE_LIMIT,
    RATE_WINDOW,
    REQUEST_COUNTS,
    check_rate_limit,
    get_client_ip,
    get_rate_limit_status,
    reset_rate_limits,
)


# Mock Request class for testing
class MockRequest:
    """Mock FastAPI Request for testing."""

    def __init__(self, client_host: str = "127.0.0.1", forwarded_for: str = None):
        self.client = type('obj', (object,), {'host': client_host})
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
        request = MockRequest(
            client_host="127.0.0.1",
            forwarded_for="203.0.113.42"
        )
        assert get_client_ip(request) == "203.0.113.42"

    def test_forwarded_for_multiple_ips(self):
        """Test X-Forwarded-For with multiple IPs (takes first)."""
        request = MockRequest(
            client_host="127.0.0.1",
            forwarded_for="203.0.113.42, 198.51.100.17, 192.0.2.1"
        )
        assert get_client_ip(request) == "203.0.113.42"


class TestRateLimiting:
    """Test rate limiting functionality."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_within_rate_limit(self):
        """Test that requests within limit pass."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 9 requests (below limit of 10)
        for i in range(9):
            check_rate_limit(request)  # Should not raise

    def test_exactly_at_rate_limit(self):
        """Test that 10th request (at limit) still passes."""
        request = MockRequest(client_host="192.168.1.100")

        # Make exactly 10 requests (at limit)
        for i in range(10):
            check_rate_limit(request)  # Should not raise

    def test_exceed_rate_limit(self):
        """Test that 11th request (exceeds limit) raises 429."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 10 requests (at limit)
        for i in range(10):
            check_rate_limit(request)

        # 11th request should raise HTTPException with status 429
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(request)

        assert exc.value.status_code == 429
        assert "Rate limit exceeded" in exc.value.detail["error"]
        assert exc.value.detail["retry_after"] == RATE_WINDOW

    def test_rate_limit_per_ip(self):
        """Test that rate limits are tracked per IP address."""
        request1 = MockRequest(client_host="192.168.1.100")
        request2 = MockRequest(client_host="192.168.1.101")

        # First IP makes 10 requests (at limit)
        for i in range(10):
            check_rate_limit(request1)

        # Second IP should still have full quota
        for i in range(10):
            check_rate_limit(request2)  # Should not raise

        # First IP should be blocked
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(request1)
        assert exc.value.status_code == 429

    def test_rate_limit_sliding_window(self):
        """Test that rate limit uses sliding window (old requests expire)."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 10 requests
        for i in range(10):
            check_rate_limit(request)

        # Manually set first request to be outside window
        client_ip = get_client_ip(request)
        old_time = datetime.now() - timedelta(seconds=RATE_WINDOW + 1)
        REQUEST_COUNTS[client_ip][0] = old_time

        # Now should be able to make another request (oldest expired)
        check_rate_limit(request)  # Should not raise

    def test_reset_rate_limits(self):
        """Test that reset clears all rate limit counters."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 10 requests (at limit)
        for i in range(10):
            check_rate_limit(request)

        # Reset counters
        reset_rate_limits()

        # Should be able to make requests again
        for i in range(10):
            check_rate_limit(request)  # Should not raise


class TestRateLimitStatus:
    """Test rate limit status query."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_status_no_requests(self):
        """Test status when no requests made."""
        request = MockRequest(client_host="192.168.1.100")
        status = get_rate_limit_status(request)

        assert status["requests_made"] == 0
        assert status["requests_remaining"] == RATE_LIMIT
        assert status["limit"] == RATE_LIMIT
        assert status["window_seconds"] == RATE_WINDOW

    def test_status_after_requests(self):
        """Test status after making some requests."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 5 requests
        for i in range(5):
            check_rate_limit(request)

        status = get_rate_limit_status(request)
        assert status["requests_made"] == 5
        assert status["requests_remaining"] == 5

    def test_status_at_limit(self):
        """Test status when at rate limit."""
        request = MockRequest(client_host="192.168.1.100")

        # Make 10 requests (at limit)
        for i in range(10):
            check_rate_limit(request)

        status = get_rate_limit_status(request)
        assert status["requests_made"] == 10
        assert status["requests_remaining"] == 0


class TestRateLimitErrorDetails:
    """Test rate limit error response details."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_error_contains_retry_after(self):
        """Test that error includes retry_after header."""
        request = MockRequest(client_host="192.168.1.100")

        # Exceed limit
        for i in range(10):
            check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(request)

        assert "retry_after" in exc.value.detail
        assert exc.value.detail["retry_after"] == RATE_WINDOW

    def test_error_contains_current_count(self):
        """Test that error includes current request count."""
        request = MockRequest(client_host="192.168.1.100")

        # Exceed limit
        for i in range(10):
            check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(request)

        assert "current_count" in exc.value.detail
        assert exc.value.detail["current_count"] == 10

    def test_error_message_helpful(self):
        """Test that error message is user-friendly."""
        request = MockRequest(client_host="192.168.1.100")

        # Exceed limit
        for i in range(10):
            check_rate_limit(request)

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(request)

        detail = exc.value.detail
        assert "Rate limit exceeded" in detail["error"]
        assert f"{RATE_LIMIT} requests" in detail["message"]
        assert f"{RATE_WINDOW} seconds" in detail["message"]
