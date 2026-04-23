# Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining backend release blockers by making auth/session transport and runtime dependencies fail closed, improving readiness signaling, and cleaning up async/transactional safety gaps.

**Architecture:** Keep request-scoped async SQLAlchemy and existing auth/session architecture. Tighten startup validation, make runtime dependency contracts explicit, replace blocking request-path I/O, and reduce partial-commit risk in credential flows. Prefer targeted changes over broad refactors.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2.0 async, Redis, requests/httpx or thread-offloaded fallback, pytest.

---

## Task 1: Enforce production email and cookie security at startup

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_core_config.py`
- Modify or Create: `backend/tests/test_config_refuses_dev_auth_in_prod.py` or adjacent config test file

- [ ] Add a model validator in `backend/app/core/config.py` that raises when:
  - `environment == "production"` and `yaml.email.backend == "console"`
  - `environment in {"staging", "production"}` and `AUTH_COOKIE_SECURE is False`

- [ ] Keep the existing `_refuse_dev_auth_in_prod()` behavior unchanged.

- [ ] Add config tests covering:
  - production + console email -> `ValidationError`
  - production + insecure auth cookies -> `ValidationError`
  - development + console email -> allowed
  - development + insecure auth cookies -> allowed

- [ ] Run:

```bash
cd backend && uv run pytest tests/test_core_config.py -v
```

- [ ] Commit:

```bash
git add backend/app/core/config.py backend/tests/test_core_config.py
git commit -m "fix(config): fail closed for prod email and cookie settings"
```

## Task 2: Make Redis production contract explicit

**Files:**
- Modify: `backend/app/core/cache.py`
- Modify: `backend/app/core/config.py`
- Modify or Create: `backend/tests/test_config.py`
- Create: `backend/tests/test_cache_contract.py`

- [ ] Add one explicit config flag or environment rule for Redis fallback. Preferred behavior:
  - `development`: fallback allowed
  - `staging` / `production`: fallback disallowed, startup fails if Redis is unavailable

- [ ] Update `CacheService.connect()` so production-like environments do not silently continue on in-memory fallback.

- [ ] Add tests covering:
  - development Redis failure -> fallback enabled
  - production Redis failure -> startup/config path raises

- [ ] Run:

```bash
cd backend && uv run pytest tests/test_cache_contract.py tests/test_config.py -v
```

- [ ] Commit:

```bash
git add backend/app/core/cache.py backend/app/core/config.py backend/tests/test_cache_contract.py backend/tests/test_config.py
git commit -m "fix(runtime): require redis for production safety"
```

## Task 3: Replace hard-coded `/health` with dependency-aware checks

**Files:**
- Modify: `backend/app/main.py`
- Modify or Create: `backend/tests/test_http_surface_baseline.py`
- Create: `backend/tests/test_health_endpoint.py`

- [ ] Split health semantics into:
  - lightweight liveness endpoint that proves process/responding
  - readiness endpoint or richer `/health` response that checks DB and Redis/cache availability

- [ ] Keep backward compatibility if possible by preserving `/health`, but change payload/status semantics to reflect dependency state.

- [ ] Verify Docker/probe assumptions before changing route names:
  - `backend/Dockerfile.prod`
  - `frontend/nginx.conf`
  - `frontend/nginx/nginx.prod.conf`

- [ ] Add tests covering:
  - healthy dependencies -> `200`
  - failed dependency state -> non-ready response and machine-readable payload

- [ ] Run:

```bash
cd backend && uv run pytest tests/test_health_endpoint.py tests/test_http_surface_baseline.py -v
```

- [ ] Commit:

```bash
git add backend/app/main.py backend/tests/test_health_endpoint.py backend/tests/test_http_surface_baseline.py backend/Dockerfile.prod frontend/nginx.conf frontend/nginx/nginx.prod.conf
git commit -m "feat(health): add dependency-aware readiness checks"
```

## Task 4: Remove blocking sync ontology HTTP from async request paths

**Files:**
- Modify: `backend/app/hpo_proxy.py`
- Modify: `backend/app/services/ontology_service.py`
- Modify: `backend/tests/test_ontology_service.py`
- Create: `backend/tests/test_hpo_proxy_validate.py`

- [ ] Choose the smallest safe implementation:
  - preferred: introduce async HTTP client usage for request-path API fallback
  - acceptable: isolate blocking ontology API fetches behind `asyncio.to_thread()` from the async route path if a full async rewrite is too invasive for this pass

- [ ] Preserve existing local-cache and file-cache behavior.

- [ ] Ensure the `validate_terms` route no longer directly performs blocking synchronous network I/O on the event loop.

- [ ] Add tests for:
  - local hit path
  - API fallback path with mocking
  - route behavior under mocked slow fetch

- [ ] Run:

```bash
cd backend && uv run pytest tests/test_ontology_service.py tests/test_hpo_proxy_validate.py -v
```

- [ ] Commit:

```bash
git add backend/app/hpo_proxy.py backend/app/services/ontology_service.py backend/tests/test_ontology_service.py backend/tests/test_hpo_proxy_validate.py
git commit -m "fix(ontology): remove blocking io from async request path"
```

## Task 5: Tighten transaction ownership in credential flows

**Files:**
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/auth/credential_tokens.py`
- Modify: `backend/app/api/auth_endpoints.py`
- Create: `backend/tests/test_auth_transaction_boundaries.py`

- [ ] Remove internal commits from repository/service methods that are used in multi-step auth flows where endpoint-level atomicity matters.

- [ ] Update callers in `auth_endpoints.py` to own the transaction boundary explicitly.

- [ ] Focus on these flows first:
  - invite create / accept
  - password reset request / confirm
  - verify-email resend / confirm

- [ ] Add tests that simulate failure after one step and assert the overall state does not partially persist in a security-sensitive way.

- [ ] Run:

```bash
cd backend && uv run pytest tests/test_auth_password_reset.py tests/test_auth_email_verify.py tests/test_auth_invite.py tests/test_auth_transaction_boundaries.py -v
```

- [ ] Commit:

```bash
git add backend/app/repositories/user_repository.py backend/app/auth/credential_tokens.py backend/app/api/auth_endpoints.py backend/tests/test_auth_transaction_boundaries.py backend/tests/test_auth_password_reset.py backend/tests/test_auth_email_verify.py backend/tests/test_auth_invite.py
git commit -m "refactor(auth): centralize transaction ownership in credential flows"
```

## Task 6: Lane verification

**Files:**
- No code changes required unless fixes are needed

- [ ] Run the backend lane verification bundle:

```bash
cd backend && uv run pytest \
  tests/test_core_config.py \
  tests/test_auth_csrf.py \
  tests/test_email_sender.py \
  tests/test_auth_password_reset.py \
  tests/test_auth_refresh_sessions.py \
  tests/test_dev_endpoints.py \
  tests/test_security_headers.py \
  tests/test_ontology_service.py \
  tests/test_health_endpoint.py \
  tests/test_auth_transaction_boundaries.py -v
```

- [ ] If any test fails, fix before marking the lane complete.

- [ ] Commit any final lane-only follow-up:

```bash
git add backend
git commit -m "test(backend): finalize hardening verification"
```

