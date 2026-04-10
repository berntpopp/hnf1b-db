"""Tests for the standardized error response format.

Every error response must have the shape:
    {"detail": str, "error_code": str, "request_id": str | None}
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import register_exception_handlers


class Sample(BaseModel):
    """Sample pydantic model used to trigger validation errors."""

    value: int = Field(..., gt=0)


@pytest.fixture
def app():
    """Build a minimal FastAPI app with the shared exception handlers."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=404, detail="Not found")

    @test_app.post("/validation-error")
    async def validation_error(body: Sample):
        return body

    @test_app.get("/uncaught-error")
    async def uncaught_error():
        raise RuntimeError("Something broke")

    return test_app


def test_http_exception_response_shape(app):
    """HTTPException responses include detail and error_code fields."""
    client = TestClient(app)
    response = client.get("/http-error")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] == "http_error" or "404" in body["error_code"]


def test_validation_error_response_shape(app):
    """Pydantic validation errors are returned with error_code=validation_error."""
    client = TestClient(app)
    response = client.post("/validation-error", json={"value": -1})
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] == "validation_error"


def test_uncaught_error_is_500_with_shape(app):
    """Uncaught exceptions produce a 500 with the standard error shape."""
    # raise_server_exceptions=False lets Starlette's exception handler run
    # and return a response instead of re-raising to the test client.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/uncaught-error")
    assert response.status_code == 500
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] in ("internal_error", "server_error")
