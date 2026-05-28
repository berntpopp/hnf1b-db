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
#
# https://cdn.jsdelivr.net is allowed in script-src/style-src because the
# Swagger UI (/api/v2/docs) and ReDoc (/api/v2/redoc) pages FastAPI serves
# load their JS/CSS bundles from that CDN. Without it the docs page renders
# blank (the swagger-ui div never hydrates). The favicon is served from
# https://fastapi.tiangolo.com and is already covered by img-src https:.
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://rest.ensembl.org https://eutils.ncbi.nlm.nih.gov "
    "https://hpo.jax.org https://www.ebi.ac.uk; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# Docs UI + OpenAPI spec must never be cached. They carry no Cache-Control
# otherwise, so a browser can heuristically cache a stale or broken version
# (e.g. one rendered while a deploy changed the CSP, or fetched during a
# container restart) and keep serving it — surfacing as Swagger's
# "Failed to fetch /api/v2/openapi.json". no-store forces a fresh fetch.
NO_STORE_PATHS = frozenset(
    {"/api/v2/docs", "/api/v2/redoc", "/api/v2/openapi.json"}
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
        if request.url.path in NO_STORE_PATHS:
            response.headers["Cache-Control"] = "no-store"
        return response
