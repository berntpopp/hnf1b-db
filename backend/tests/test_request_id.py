"""Tests for the RequestIdMiddleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.request_id import RequestIdMiddleware


@pytest.fixture
def client():
    """Build a minimal FastAPI app mounted with RequestIdMiddleware + one route."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    async def ping(request: Request):
        """Echo the request_id attached to request.state (or None)."""
        return {"request_id": getattr(request.state, "request_id", None)}

    return TestClient(app)


def test_generates_request_id_when_absent(client):
    """Without an X-Request-ID header, the middleware generates one and attaches it to state."""
    response = client.get("/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] is not None
    assert len(data["request_id"]) > 0


def test_echoes_request_id_in_response_header(client):
    """The generated request_id is echoed in the X-Request-ID response header."""
    response = client.get("/ping")
    assert "x-request-id" in response.headers
    data = response.json()
    assert response.headers["x-request-id"] == data["request_id"]


def test_respects_incoming_request_id_header(client):
    """A client-supplied X-Request-ID is honoured as-is (not overwritten)."""
    response = client.get("/ping", headers={"X-Request-ID": "client-supplied-123"})
    data = response.json()
    assert data["request_id"] == "client-supplied-123"
    assert response.headers["x-request-id"] == "client-supplied-123"
