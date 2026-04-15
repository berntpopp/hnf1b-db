# Auth Hardening Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the release-safe auth transport migration to HttpOnly refresh cookies, in-memory access tokens, CSRF protection, and JTI-backed server-side refresh invalidation.

**Architecture:** The work proceeds in four slices: backend persistence and token claims, backend endpoint/cookie/CSRF contract, frontend auth transport migration, and verification cleanup. The release-safe shape preserves bearer access tokens for request authorization while moving refresh capability into server-controlled cookie and session metadata.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL, Pydantic 2, Vue 3, Pinia, Axios, Vitest, Playwright, pytest, uv, npm.

---

## Status

This plan is active.

Merged in PR `#256`:

- [x] Task 1 foundations: refresh-session persistence primitives
- [x] Task 2 foundations: refresh-token session-version claims
- [x] Task 3 foundations: cookie and CSRF helpers

Still open:

- [ ] endpoint contract flip for login, refresh, and logout
- [ ] password-event invalidation rewiring
- [ ] frontend in-memory-token and cookie-refresh migration
- [ ] legacy raw refresh-path removal
- [ ] full targeted verification reruns

## Spec

Primary spec:

- `.planning/specs/2026-04-15-auth-hardening-phase-2-design.md`

Source-of-truth release driver:

- `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`

## File Map

### Backend

- Modify: `backend/app/api/auth_endpoints.py`
- Modify: `backend/app/auth/tokens.py`
- Modify: `backend/app/auth/dependencies.py`
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/models/user.py`
- Create: `backend/app/models/refresh_session.py`
- Create: `backend/app/repositories/refresh_session_repository.py`
- Create or modify: focused auth helper/service file for cookies and CSRF under `backend/app/auth/`
- Create: Alembic migration under `backend/alembic/versions/`
- Modify: targeted backend tests under `backend/tests/`

### Frontend

- Modify: `frontend/src/stores/authStore.js`
- Modify: `frontend/src/api/session.js`
- Modify: `frontend/src/api/transport.js`
- Modify: `frontend/src/api/domain/auth.js`
- Modify or create: targeted frontend auth transport tests

## Execution Order

1. Flip backend login, refresh, and logout to the cookie-backed contract.
2. Wire password-change, password-reset, and deactivate invalidation onto session-version and refresh-session revocation.
3. Migrate frontend auth state to in-memory access tokens and cookie refresh bootstrap.
4. Remove legacy raw refresh-token dependencies and fixtures.
5. Rerun backend, frontend, and manual release verification slices.

## Verification Slices

### Backend auth/session slice

- `cd backend && uv run pytest tests/test_auth.py tests/test_auth_tokens.py tests/test_auth_password_reset.py tests/test_dev_endpoints.py tests/test_auth_csrf.py tests/test_auth_refresh_sessions.py -v`

Focus:

- login cookie contract
- refresh rotation
- CSRF rejection
- logout invalidation
- password reset/change invalidation
- inactive/locked refresh denial

### Frontend auth transport slice

- `cd frontend && npx vitest run tests/unit/stores/authStore.spec.js tests/unit/api/transport.spec.js tests/unit/components/auth/DevQuickLogin.spec.js`

Focus:

- no refresh persistence
- refresh-on-bootstrap
- refresh queue behavior
- logout cleanup
- CSRF header injection

### Release-critical mixed slice

- targeted backend auth tests
- targeted frontend auth tests
- one manual browser check for login, reload, and logout against the dev stack

## Task 1: Add Refresh Session Persistence

Status: complete in PR `#256`

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/app/models/refresh_session.py`
- Create: `backend/app/repositories/refresh_session_repository.py`
- Create: `backend/alembic/versions/20260415_0005_add_refresh_sessions.py`
- Test: `backend/tests/test_auth_refresh_sessions.py`

- [x] Add a per-user session-version field to `User` so "revoke all refresh capability" does not depend on deleting individual rows.
- [x] Add a refresh-session model keyed by refresh-token JTI with fields for `user_id`, `token_jti`, `token_sha256` or equivalent hashed identifier, `session_version`, `expires_at`, `revoked_at`, and `rotated_from_jti`.
- [x] Write an Alembic migration that creates the refresh-session table, adds the user session-version field, and leaves the legacy `users.refresh_token` path in place only for transitional compatibility.
- [x] Add repository helpers for create, lookup by JTI, revoke current session, revoke a rotated chain/family, and revoke all sessions for a user by session-version bump.
- [x] Add backend tests proving a session row can be created, rotated, revoked, and rejected after a session-version bump.

## Task 2: Revise Token Claims And Auth Schemas

Status: partially complete in PR `#256`

**Files:**
- Modify: `backend/app/auth/tokens.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_auth_tokens.py`

- [x] Update refresh-token creation to include JTI and user session-version claims that match the persisted refresh-session row.
- [x] Keep access tokens bearer-based and short-lived; do not move access auth into cookies in this phase.
- [x] Replace the current `Token` response shape so login/refresh return `access_token`, `token_type`, and `expires_in` without requiring `refresh_token`.
- [ ] Remove or deprecate `RefreshTokenRequest` for browser refresh flow and update tests to assert the new response contract at the endpoint layer.
- [ ] Add tests that reject refresh JWTs with wrong type, wrong session version, or missing backing session row through the live refresh path.

## Task 3: Add Cookie And CSRF Helpers

Status: helper layer complete in PR `#256`

**Files:**
- Create: `backend/app/auth/session_cookies.py`
- Modify: `backend/app/auth/dependencies.py`
- Modify: `backend/app/api/auth_endpoints.py`
- Test: `backend/tests/test_auth_csrf.py`

- [x] Add one backend helper responsible for setting and clearing the refresh cookie and CSRF cookie with config-driven attributes.
- [x] Add one backend CSRF validation dependency/helper that compares the readable CSRF cookie with the `X-CSRF-Token` request header.
- [ ] Apply that CSRF rule to `POST /api/v2/auth/refresh`, `POST /api/v2/auth/logout`, and the shared mutation rule chosen for cookie-authenticated unsafe methods.
- [x] Make cookie settings explicit in config usage so production `Secure` and SameSite behavior are not hard-coded ad hoc in the router.
- [x] Add backend tests for missing header, mismatched cookie/header, and successful validation.

## Task 4: Rebuild Login, Refresh, And Logout Around Cookies

Status: next execution slice

**Files:**
- Modify: `backend/app/api/auth_endpoints.py`
- Modify: `backend/app/repositories/user_repository.py`
- Test: `backend/tests/test_auth_login.py`
- Test: `backend/tests/test_auth_refresh.py`
- Test: `backend/tests/test_auth_logout.py`

- [ ] Change login so successful authentication creates a refresh-session row, sets refresh and CSRF cookies, and returns only the access-token payload.
- [ ] Change refresh so it reads the refresh JWT from the cookie, validates CSRF, validates the refresh-session row and user state, rotates the session, resets cookies, and returns a new access token.
- [ ] Change logout so it can revoke the current refresh session and clear cookies even when the access token is expired or absent, as long as the request carries the valid refresh cookie plus CSRF token.
- [ ] Preserve `_assert_user_can_receive_tokens()` as the gate on every token issuance path, including refresh and any dev-only token issuance path that remains relevant.
- [ ] Add regression tests for inactive refresh denial, locked refresh denial, login cookie contract, refresh rotation, cookie clearing on logout, and suspicious refresh reuse rejection.

## Task 5: Make Password Events Revoke Refresh Capability

**Files:**
- Modify: `backend/app/api/auth_endpoints.py`
- Modify: `backend/app/repositories/user_repository.py`
- Test: `backend/tests/test_auth_password_change.py`
- Test: `backend/tests/test_auth_password_reset.py`

- [ ] Replace direct `update_refresh_token(user, "")` invalidation with a user session-version bump plus refresh-session revocation.
- [ ] Apply the same invalidation rule to password change and password reset confirmation.
- [ ] Ensure admin-driven deactivate flows also revoke future refresh capability by the same model if those flows already mutate account status in the release hardening scope.
- [ ] Add tests proving a refresh cookie minted before password change or reset can no longer mint a new access token afterward.

## Task 6: Remove Frontend Refresh Persistence

**Files:**
- Modify: `frontend/src/api/session.js`
- Modify: `frontend/src/stores/authStore.js`
- Test: `frontend/tests/**/*auth*.spec.js`

- [ ] Replace the current session helper with in-memory access-token storage only; remove refresh-token getters, setters, and storage writes.
- [ ] Keep legacy localStorage purge behavior only as cleanup for older clients; do not introduce new browser persistence for auth tokens.
- [ ] Remove `refreshToken` store state and any code that expects login/refresh responses to include a refresh token.
- [ ] Change auth initialization to attempt one refresh bootstrap before calling `/auth/me`.
- [ ] Add frontend tests that fail if refresh token persistence or sessionStorage refresh reads are reintroduced.

## Task 7: Update Axios Transport For Cookie Refresh And CSRF

**Files:**
- Modify: `frontend/src/api/transport.js`
- Modify: `frontend/src/api/domain/auth.js`
- Modify: `frontend/src/stores/authStore.js`
- Test: `frontend/tests/**/*transport*.spec.js`

- [ ] Configure auth refresh requests to use `withCredentials` so the browser sends the refresh cookie.
- [ ] Preserve the existing single-flight refresh queue so concurrent `401` responses still collapse into one refresh attempt.
- [ ] Inject `X-CSRF-Token` on refresh, logout, and authenticated mutation requests using the readable CSRF cookie.
- [ ] Ensure refresh failures clear only in-memory access state and route the user back to login without retry loops.
- [ ] Add tests for queued request replay after refresh, refresh failure logout behavior, and CSRF header injection on unsafe methods.

## Task 8: Remove Legacy Raw Refresh Paths

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: backend and frontend auth tests

- [ ] Stop reading `users.refresh_token` anywhere in live auth code.
- [ ] Remove the raw refresh token from API responses and fixtures that still assert it for non-dev browser paths.
- [ ] Keep or remove the legacy database column based on migration appetite, but the implementation must no longer depend on it for runtime auth decisions.
- [ ] Update docs/comments/tests so the cookie-based contract is the only supported browser flow.

## Task 9: Run Targeted Verification And Manual Release Slice

**Files:**
- Modify: `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md` only if verification commands need to be updated after implementation

- [ ] Run the targeted backend auth/session slice after the backend changes land.
- [ ] Run the targeted frontend auth transport slice after the frontend changes land.
- [ ] Run one end-to-end manual browser check: login, reload, access protected route, logout, then verify reload does not re-authenticate.
- [ ] Capture any cookie/CORS/SameSite issues explicitly rather than treating them as environment noise.
- [ ] Only call the phase complete when fresh runs show the new auth contract and invalidation model are stable.

## Verification Already Landed

Backend foundations already verified locally before merge with these slices:

- `cd backend && uv run pytest tests/test_auth_refresh_sessions.py -v`
- `cd backend && uv run pytest tests/test_auth_tokens.py tests/test_auth_bopla_schemas.py tests/test_auth.py tests/test_dev_endpoints.py -q`
- `cd backend && uv run pytest tests/test_auth_csrf.py -q`
- `cd backend && uv run pytest tests/test_alembic_env_autogenerate.py::test_env_py_imports_all_orm_models tests/test_auth_csrf.py -q`

PR `#256` also passed GitHub Actions for:

- `test`
- `frontend`
- `pre-commit hygiene gate`
- `E2E tests (Playwright)`

## Sequencing Notes

- Tasks 4 and 5 are the immediate backend continuation and should land behind passing backend auth tests before frontend integration.
- Tasks 6 and 7 can overlap once the backend cookie and response contract is stable.
- Task 8 should not start until both backend and frontend slices are green against the new contract.
- Task 9 is the release gate for this phase, not an optional cleanup step.
