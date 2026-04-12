"""Request ID middleware for log correlation.

Generates a UUID4 for each incoming request (or uses a client-supplied
X-Request-ID header if present), attaches it to request.state, and
echoes it back in the response headers.

Downstream consumers:
  - app.core.exceptions (uses request.state.request_id in error bodies)
  - app.main logging middleware (attaches to log records)
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request/response cycle.

    Reads a client-supplied ``X-Request-ID`` header if present;
    otherwise generates a fresh UUID4. The ID lives on
    ``request.state.request_id`` for downstream handlers and is
    echoed back in the response's ``X-Request-ID`` header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Run the request/response cycle with a request_id in state."""
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming_id or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
