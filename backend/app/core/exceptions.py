"""Shared exception handlers for consistent API error response shape.

All error responses follow:
    {
        "detail": <error payload>,     # see below
        "error_code": str,              # machine-readable code
        "request_id": str | None,       # for log correlation (set by
                                        # request_id middleware in Wave 6)
    }

``detail`` is always present, but may be a plain string *or* a
JSON-serializable structured value (dict, list, number, bool, null)
depending on the originating exception. The http_exception_handler
preserves the original ``HTTPException.detail`` structure so that
endpoints raising e.g.
``HTTPException(status_code=409, detail={"error": ..., "current_revision": N})``
round-trip their structured payload to the client unchanged.
Non-JSON-native detail values are coerced to str as a defensive fallback.
"""

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _build_error_response(
    status_code: int,
    detail: Any,
    error_code: str,
    request: Request,
) -> JSONResponse:
    """Build a standardized error response body.

    `detail` may be a string (the common case) or a JSON-serializable
    dict/list. Structured details from endpoints like
    ``HTTPException(status_code=409, detail={"error": ..., "current_revision": N})``
    round-trip to the client unchanged so that existing clients and tests
    keyed on the structured shape continue to work.
    """
    request_id = getattr(request.state, "request_id", None)
    body: Dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=body)


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert HTTPException into the standardized shape.

    Preserves the original ``exc.detail`` structure: strings stay strings,
    dicts stay dicts, lists stay lists. Only unknown non-serializable
    detail values are coerced to ``str``.
    """
    assert isinstance(exc, HTTPException)
    error_code = f"http_{exc.status_code}"
    detail: Any = exc.detail
    # Coerce non-JSON-native types (Pydantic models, arbitrary objects)
    # so that JSONResponse encoding never fails.
    if not isinstance(detail, (str, dict, list, int, float, bool, type(None))):
        detail = str(detail)
    return _build_error_response(
        status_code=exc.status_code,
        detail=detail,
        error_code=error_code,
        request=request,
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Convert pydantic validation errors into the standardized shape."""
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errors
    )
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
        error_code="validation_error",
        request=request,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for uncaught exceptions.

    Logs the traceback and returns a safe 500 response without leaking
    stack details to the client.
    """
    logger.exception(
        "Uncaught exception in request %s %s", request.method, request.url.path
    )
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        error_code="internal_error",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all shared exception handlers on the given FastAPI app."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
