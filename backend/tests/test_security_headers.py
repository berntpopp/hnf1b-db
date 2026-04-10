"""Tests for the security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def client():
    """Build a minimal FastAPI app with SecurityHeadersMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    async def ping():
        """Return a trivial JSON payload to exercise the middleware."""
        return {"ok": True}

    return TestClient(app)


def test_x_frame_options_present(client):
    """X-Frame-Options should be set to DENY on every response."""
    response = client.get("/ping")
    assert response.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_present(client):
    """X-Content-Type-Options should be set to nosniff on every response."""
    response = client.get("/ping")
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_present(client):
    """Referrer-Policy header should be present on every response."""
    response = client.get("/ping")
    assert "referrer-policy" in response.headers


def test_content_security_policy_present(client):
    """Content-Security-Policy header should be present on every response."""
    response = client.get("/ping")
    assert "content-security-policy" in response.headers


def test_permissions_policy_present(client):
    """Permissions-Policy header should be present on every response."""
    response = client.get("/ping")
    assert "permissions-policy" in response.headers
