# Auth Hardening Phase 2 Design

Date: 2026-04-15
Status: Active implementation spec

## Goal

Define the release-safe Phase 2 auth hardening design that replaces frontend refresh-token persistence with an HttpOnly cookie flow, keeps access tokens in memory only, adds explicit CSRF protection for cookie-authenticated requests, and replaces the current raw refresh-token-on-user-row model with server-side invalidation that survives password and account-state changes.

## Source Of Truth

This design is scoped directly from:

- `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`

It elaborates only the auth/session items already called out there:

- HttpOnly refresh cookie flow
- short-lived in-memory access token contract
- CSRF protection for refresh/logout/mutation routes
- server-side refresh invalidation semantics

## Execution Status

Merged foundation work from PR `#256` already covers the first backend slice:

- refresh-session persistence primitives
- refresh-token session-version claims
- cookie and CSRF helper foundations

Remaining work is the endpoint contract flip, password-event invalidation wiring, frontend transport migration, and full verification reruns.

## Why Phase 2 Exists

Current `main` still has the following release blockers in the auth path:

- frontend auth persists refresh material in browser-managed storage
- `POST /api/v2/auth/refresh` accepts a raw refresh JWT in the JSON body
- refresh rotation is enforced by comparing one raw token against `users.refresh_token`
- password reset and password change clear refresh capability, but the invalidation model is still single-token and row-local
- once refresh moves into cookies, the API surface needs CSRF protection rather than relying only on bearer-style semantics

Phase 2 exists to fix those issues without broadening into a full session-management platform.

## In Scope

- refresh token transport via secure HttpOnly cookie
- access token returned in response body and held in frontend memory only
- bootstrap session flow for page reloads using the refresh cookie
- CSRF token issuance and validation for cookie-authenticated refresh, logout, and state-changing API requests
- server-side refresh invalidation model based on refresh-session metadata rather than raw token storage
- invalidation on password change, password reset, admin deactivate, and lockout-sensitive issuance checks
- targeted backend and frontend regression coverage for the new contract

## Out Of Scope

- multi-device session management UI
- user-visible "list my sessions" or selective device revocation
- OAuth / third-party identity providers
- long-lived access tokens
- moving all authentication to cookies only
- unrelated admin/user-profile redesign

## Current Constraints From The Codebase

The existing implementation creates a valid migration path but also defines the hard constraints:

- backend login and refresh currently return `Token(access_token, refresh_token, token_type, expires_in)`
- `frontend/src/stores/authStore.js` still expects both tokens in the response body and writes them through `frontend/src/api/session.js`
- `frontend/src/api/transport.js` already has a refresh queue and request retry mechanism worth preserving
- `backend/app/models/user.py` still stores one raw `refresh_token` directly on `users`
- account-state checks already exist in `_assert_user_can_receive_tokens()` and should remain the gate for every token issuance path

The design should preserve those good seams while changing the contract behind them.

## Approaches Considered

### Option 1: Keep refresh JWT in frontend storage and harden around it

Pros:

- lowest implementation cost
- smallest frontend diff

Cons:

- fails the explicit release gate against frontend token persistence
- leaves refresh material exposed to XSS and browser storage leakage
- does not solve the transport problem the source-of-truth plan calls out

Recommendation: reject.

### Option 2: HttpOnly refresh cookie plus in-memory access token plus double-submit CSRF

Pros:

- directly satisfies the release gate
- preserves bearer access-token semantics for existing backend dependencies
- limits frontend churn to the auth store and transport layer
- keeps CSRF logic explicit and understandable

Cons:

- requires coordinated backend/frontend contract changes
- requires cookie and CORS configuration review

Recommendation: choose this option.

### Option 3: Full cookie-based auth for both access and refresh

Pros:

- fewer explicit bearer headers on the frontend
- one transport style

Cons:

- much larger backend dependency and authorization refactor
- higher CSRF surface area on all authenticated reads and writes
- unnecessary for this release-hardening phase

Recommendation: reject for this release.

## Proposed Design

### 1. Session Contract

The browser holds two pieces of auth state:

- access token: stored in memory only, never written to `localStorage` or `sessionStorage`
- CSRF token: readable client-side token stored in a non-HttpOnly cookie and mirrored into request headers when required

The browser does not hold refresh token material in JS-readable storage. The refresh token travels only via a secure HttpOnly cookie set by the backend.

### 2. Login Flow

`POST /api/v2/auth/login` remains a JSON request with username/password.

Successful login does all of the following:

- verifies credentials
- enforces `_assert_user_can_receive_tokens(user)`
- creates a short-lived access token
- creates a refresh session record server-side
- emits the refresh JWT in a `Set-Cookie` header for an HttpOnly refresh cookie
- emits a CSRF cookie for browser-readable use
- returns JSON containing the access token and expiry metadata only

The response body no longer includes `refresh_token`.

### 3. Refresh Flow

`POST /api/v2/auth/refresh` becomes a cookie-authenticated endpoint:

- request body is empty
- refresh JWT is read from the refresh cookie
- CSRF header is required and must match the CSRF cookie
- server verifies the refresh JWT type and JTI
- server loads the refresh session metadata and user
- server enforces account state before issuing new tokens
- server rotates the refresh session and refresh cookie
- server returns a new access token in JSON

If refresh verification fails because the session is revoked, expired, mismatched, or belongs to an inactive/locked user, the endpoint clears the refresh cookie and returns `401` or `423`/`403` according to the failure mode already used by issuance checks.

### 4. Bootstrap / Reload Flow

On a fresh page load:

- the frontend starts with no access token in memory
- auth initialization attempts a refresh call if the refresh cookie is present
- if refresh succeeds, the returned access token is stored in memory and `/auth/me` is fetched
- if refresh fails, auth state remains anonymous and the frontend should not loop

This replaces the current session-storage bootstrap behavior.

### 5. Logout Flow

`POST /api/v2/auth/logout` becomes valid in either of these cases:

- authenticated by bearer access token plus CSRF header
- authenticated by refresh cookie plus CSRF header when access token is expired or absent

Server-side logout:

- revokes the active refresh session if present
- clears refresh and CSRF cookies
- returns a success message even if the session was already absent

Frontend logout:

- attempts backend logout once
- clears the in-memory access token regardless of backend outcome
- does not try to clear any JS-held refresh token because none exists

### 6. CSRF Model

Phase 2 uses a double-submit CSRF pattern scoped to browser-cookie auth.

Mechanics:

- backend sets a readable CSRF cookie on login and refresh
- frontend reads that cookie and sends it as `X-CSRF-Token`
- backend compares cookie value against header value for protected routes

Protected routes:

- `POST /api/v2/auth/refresh`
- `POST /api/v2/auth/logout`
- all non-GET authenticated mutation routes under `/api/v2/` when the request is made with cookies enabled

This keeps the rule simple: unsafe methods require CSRF validation when cookie auth is in play.

Bearer-only API clients remain possible if they do not rely on the refresh cookie flow.

### 7. Refresh Invalidation Model

The current `users.refresh_token` string is replaced by refresh-session metadata.

Recommended model:

- new table for refresh sessions keyed by token JTI
- server stores only hashed refresh-token identifiers or enough metadata to avoid persisting raw token material
- each record includes user id, token JTI, session version, expires_at, revoked_at, rotated_from_jti, and optional user-agent/ip audit metadata

The refresh JWT includes:

- `sub`
- `jti`
- `type=refresh`
- `sv` or equivalent session-version claim
- expiry

Validation requires all of the following:

- JWT signature and expiry are valid
- refresh session row exists for that JTI
- row is not revoked
- row expiry is valid
- user exists
- JWT session version matches current user session version

This gives two invalidation layers:

- row-level revocation for logout and rotation
- user-level session-version bump for "revoke all refresh capability"

### 8. Invalidation Events

The following events must revoke existing refresh capability:

- password change: bump user session version and clear current cookie
- password reset confirmation: bump user session version and clear current cookie
- admin deactivation: bump user session version; user can no longer refresh even with an old cookie
- token-theft or rotation mismatch detection: revoke the current refresh-session family for that user and require re-login

Unlocking an account does not automatically recreate any refresh session. It only allows future login or refresh issuance once the user authenticates through a valid path again.

### 9. API Shape

New or revised response shapes:

- login response: `access_token`, `token_type`, `expires_in`
- refresh response: `access_token`, `token_type`, `expires_in`
- optional new bootstrap endpoint is not required; initialization can call `POST /auth/refresh`

Schema consequences:

- the current `Token` schema should no longer require `refresh_token`
- `RefreshTokenRequest` should be removed or deprecated from browser-facing use

