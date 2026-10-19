"""Tests for login rate limiting and client IP extraction hardening."""

from typing import Optional

import pytest
from httpx import AsyncClient

from app.core.cache import cache
from app.middleware.rate_limiter import get_client_ip


class MockRequest:
    """Mock FastAPI Request for testing."""

    def __init__(
        self,
        client_host: str = "127.0.0.1",
        forwarded_for: Optional[str] = None,
        real_ip: Optional[str] = None,
    ):
        """Initialize mock request with client host and optional headers."""
        self.client = type("obj", (object,), {"host": client_host})
        self.headers = {}
        if forwarded_for:
            self.headers["X-Forwarded-For"] = forwarded_for
        if real_ip:
            self.headers["X-Real-IP"] = real_ip


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure in-memory cache fallback and clear between tests."""
    cache.use_fallback_only()
    cache.clear_fallback()
    yield
    cache.clear_fallback()


def test_get_client_ip_real_ip_precedence():
    """X-Real-IP takes precedence over X-Forwarded-For to prevent header spoofing."""
    request = MockRequest(
        client_host="127.0.0.1",
        forwarded_for="attacker.spoofed.ip, 192.168.1.1",
        real_ip="203.0.113.195",
    )
    assert get_client_ip(request) == "203.0.113.195"


def test_get_client_ip_forwarded_for_last_hop():
    """X-Forwarded-For uses the last hop IP appended by the trusted reverse proxy."""
    request = MockRequest(
        client_host="127.0.0.1",
        forwarded_for="attacker.spoofed.ip, 198.51.100.22",
    )
    assert get_client_ip(request) == "198.51.100.22"


@pytest.mark.asyncio
async def test_login_endpoint_rate_limited(async_client: AsyncClient, test_user):
    """POST /auth/login is rate-limited to 10 requests per 60 seconds."""
    payload = {"username": test_user.username, "password": "WrongPassword!"}

    # Make 10 failed login requests (within limit)
    for _ in range(10):
        resp = await async_client.post("/api/v2/auth/login", json=payload)
        # Should be 401 (invalid credentials) or 423 (locked), but NOT 429
        assert resp.status_code != 429

    # 11th request must be rate-limited with 429 Too Many Requests
    resp = await async_client.post("/api/v2/auth/login", json=payload)
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.text
