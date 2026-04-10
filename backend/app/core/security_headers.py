"""Security headers middleware.

Adds standard defensive HTTP headers to every response. Works with
FastAPI's built-in middleware mechanism via add_middleware.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# CSP is intentionally permissive for now because the frontend uses
# inline scripts and connects to multiple origins. Tighten this in a
# future hardening pass (out of Wave 2 scope).
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://rest.ensembl.org https://eutils.ncbi.nlm.nih.gov "
    "https://hpo.jax.org https://www.ebi.ac.uk; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Attach security headers to the outgoing response."""
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = DEFAULT_CSP
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        return response
