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


class _NonSerializableDetail:
    """Arbitrary non-JSON-native type to exercise the defensive coercion."""

    def __str__(self) -> str:
        """Return a stable string the test can assert on."""
        return "coerced via __str__"


@pytest.fixture
def app():
    """Build a minimal FastAPI app with the shared exception handlers."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=404, detail="Not found")

    @test_app.get("/http-dict-detail")
    async def http_dict_detail():
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "current_revision": 5},
        )

    @test_app.get("/http-custom-detail")
    async def http_custom_detail():
        raise HTTPException(
            status_code=418,
            detail=_NonSerializableDetail(),  # type: ignore[arg-type]
        )

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


def test_http_exception_dict_detail_round_trips(app):
    """HTTPException with a dict detail preserves structure, not stringified."""
    client = TestClient(app)
    response = client.get("/http-dict-detail")
    assert response.status_code == 409
    body = response.json()
    assert isinstance(body["detail"], dict)
    assert body["detail"]["error"] == "conflict"
    assert body["detail"]["current_revision"] == 5
    assert body["error_code"] == "http_409"


def test_http_exception_non_serializable_detail_coerced(app):
    """Non-JSON-native detail values are coerced to str for safe serialization."""
    client = TestClient(app)
    response = client.get("/http-custom-detail")
    assert response.status_code == 418
    body = response.json()
    assert body["detail"] == "coerced via __str__"
    assert body["error_code"] == "http_418"


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
