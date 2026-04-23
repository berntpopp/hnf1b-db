# ADR 0002: Cookie-backed refresh sessions with in-memory access token

**Status:** Accepted
**Date:** 2026-04-23
**Supersedes:** [ADR 0001: JWT Storage Location](0001-jwt-storage.md)

## Context

The live authentication flow no longer persists JWTs in browser storage.
Frontend code keeps the short-lived access token in memory only, while the
backend manages session continuity with a rotating refresh token cookie.

This design reduces the XSS exposure of bearer credentials while preserving a
browser-friendly refresh flow. It also requires explicit CSRF protection for
requests that rely on cookies for authentication state.

## Decision

The HNF1B application uses a split-token browser session model:

- The access token is short-lived and stored in frontend memory only.
- The refresh token is issued as a rotating `HttpOnly` cookie.
- The backend also issues a readable `csrf_token` cookie for browser clients.
- Unsafe cookie-auth requests must include the `X-CSRF-Token` header with the
  same value as the `csrf_token` cookie.
- Login and refresh responses rotate the cookie-backed session state and return
  a fresh access token for in-memory use.

## Consequences

- Browser JavaScript cannot read the refresh token directly.
- Reloads or expired access tokens require the standard refresh flow to mint a
  new in-memory access token from the cookie-backed refresh session.
- Frontend auth helpers must not persist access or refresh tokens to
  `localStorage` or `sessionStorage`.
- Cookie-auth endpoints must continue enforcing CSRF validation on unsafe
  methods.
- Documentation and onboarding material should describe the session model as
  "in-memory access token + `HttpOnly` refresh cookie + CSRF header/cookie".

## References

- [backend/app/api/auth_endpoints.py](../../backend/app/api/auth_endpoints.py) — login, refresh, and logout flow
- [backend/app/auth/session_cookies.py](../../backend/app/auth/session_cookies.py) — refresh and CSRF cookie settings
- [backend/app/auth/dependencies.py](../../backend/app/auth/dependencies.py) — CSRF validation dependency
- [frontend/src/api/session.js](../../frontend/src/api/session.js) — in-memory access token and CSRF cookie helper
- [frontend/src/api/transport.js](../../frontend/src/api/transport.js) — `Authorization` and `X-CSRF-Token` request handling
