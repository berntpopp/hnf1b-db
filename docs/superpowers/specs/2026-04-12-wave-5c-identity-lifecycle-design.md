# Wave 5c Design — Identity Lifecycle

**Date:** 2026-04-12
**Predecessor:** Wave 5b (PR #234, merged 2026-04-12, commit `8eff251`)
**Scope doc:** `docs/superpowers/plans/2026-04-11-wave-5-scope.md` §4.3
**Items:** C1, C2, C3, C4, C5
**Commit budget:** ≤13
**Branch:** `chore/wave-5c-identity-lifecycle`

---

## 1. Goal

Ship credential-token-based identity flows (invite, password reset, email verification) so that:

- An admin can invite a new user by email; the invite-accept flow creates a user with Argon2id password hash and `is_verified=True`.
- A user who forgot their password can reset it via the login page without admin intervention.
- Email verification tokens work end-to-end.
- No self-registration exists — invite-only, verified by negative test.
- All config plumbing for real SMTP is in place (Wave 6 drops in `SMTPEmailSender` + Mailpit without touching endpoints).

---

## 2. Entry state

| Metric | Value |
|--------|-------|
| Main branch | `8eff251` (Wave 5b merged) |
| Backend tests | 1090 collected |
| Frontend tests | 292 passed + 1 xfailed |
| HTTP baselines | 14 fixtures |
| pwdlib + Argon2id | In place (Wave 5b Task 11) |
| `credential_tokens` model | Does not exist |
| Email infrastructure | Does not exist |
| `Login.vue` forgot-password | TODO stub at line 175 |

---

## 3. Database — `credential_tokens` table

### 3.1 Schema

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BigInt PK` | Auto-increment |
| `user_id` | `BigInt FK → users.id, nullable` | NULL for invite tokens (user doesn't exist yet) |
| `purpose` | `VARCHAR` + CHECK | `'reset'`, `'invite'`, `'verify'` |
| `token_sha256` | `VARCHAR(64)` | SHA-256 hex of raw token; unique index |
| `email` | `VARCHAR` | Bound at creation time |
| `expires_at` | `TIMESTAMPTZ` | Default: `created_at + 24h` |
| `used_at` | `TIMESTAMPTZ, nullable` | NULL = unused; non-NULL = consumed |
| `metadata` | `JSONB, nullable` | Purpose-specific data (e.g., `{"role": "curator"}` for invite tokens) |
| `created_at` | `TIMESTAMPTZ` | Server default `now()` |

### 3.2 Token lifecycle

- **Generation:** `secrets.token_urlsafe(32)` → URL-safe 43-char string.
- **Storage:** Only the SHA-256 hex hash is persisted. Raw token is sent to the user via email/logs and never stored.
- **Consumption:** `UPDATE ... SET used_at = now() WHERE token_sha256 = ? AND used_at IS NULL AND expires_at > now()` — atomic single-use + expiry check.
- **Invalidation:** When a new token is created for the same email + purpose, all prior unused tokens for that combination are invalidated (`used_at = now()`).
- **FK behavior:** No CASCADE delete on `user_id`. Tokens survive user edits; orphaned tokens expire naturally.

### 3.3 New files

- `backend/app/models/credential_token.py` — SQLAlchemy ORM model.
- `backend/app/auth/credential_tokens.py` — Repository: `create_token`, `verify_and_consume`, `invalidate_by_email_and_purpose`.

---

## 4. Email infrastructure

### 4.1 Config split

**`.env` (secrets, 4 vars):**

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `SMTP_HOST` | `str` | `""` | Empty = not configured, triggers console fallback |
| `SMTP_PORT` | `int` | `587` | IETF standard STARTTLS port (RFC 6409/8314) |
| `SMTP_USERNAME` | `str` | `""` | For SendGrid: literal `"apikey"`; for Mailgun: `"postmaster@domain"` |
| `SMTP_PASSWORD` | `str` | `""` | API key or password; never committed to VCS |

**`config.yaml` (behavioral, new `email` section):**

```yaml
email:
  backend: "console"              # "console" | "smtp"
  from_address: "noreply@hnf1b-db.org"
  from_name: "HNF1B Database"
  tls_mode: "starttls"            # "starttls" | "ssl" | "none"
  validate_certs: true
  timeout_seconds: 30
  use_credentials: true
  max_retries: 3
  retry_backoff_factor: 2.0
```

### 4.2 Startup validation

Extends existing `Settings` validators in `backend/app/core/config.py`:

- If `email.backend == "smtp"` and `SMTP_HOST` is empty → application exits at startup (same pattern as `JWT_SECRET`).
- If `email.backend == "smtp"` and `email.use_credentials == true` and `SMTP_USERNAME` or `SMTP_PASSWORD` is empty → application exits.
- If `email.tls_mode == "none"` → log critical warning.

### 4.3 EmailSender protocol

```python
# backend/app/auth/email.py

class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body_html: str) -> None: ...
```

**`ConsoleEmailSender`** — sole Wave 5c implementation. Writes to, subject, and full body (including token URL) to the structured logger via `logging.getLogger(__name__)`. No `aiosmtplib` dependency added.

**`get_email_sender()`** — FastAPI dependency. Reads `email.backend` from config:
- `"console"` → returns `ConsoleEmailSender`
- `"smtp"` → Wave 6 adds `SMTPEmailSender` branch here; zero endpoint changes needed.

### 4.4 Wave 6 handoff

The following are documented in the Wave 6 plan update but NOT shipped in Wave 5c:

- `SMTPEmailSender` using `aiosmtplib`
- Mailpit (`axllent/mailpit`) in `docker-compose.dev.yml` (ports 1025 SMTP / 8025 web UI, following sysndd pattern with `MP_SMTP_AUTH_ACCEPT_ANY=1`)
- Provider quick-reference (SendGrid, Mailgun, AWS SES, Gmail, local relay)
- Outbound mail rate limiting (`email.rate_limit.max_per_minute`, `max_per_hour`)
- Email templates with HTML rendering

---

## 5. Backend endpoints

### 5.1 Invite flow (admin-only, on `users_router`)

**`POST /api/v2/auth/invite`**

- Body: `{ email: str, role: str = "viewer" }`
- Creates `credential_token` with `purpose='invite'`, binds email at creation. Stores intended `role` in a new `metadata` JSONB column on the token row (e.g., `{"role": "curator"}`).
- Dispatches via `EmailSender`.
- Returns `201` with `{ email, role, expires_at }`.
- **Dev-only:** When `ENVIRONMENT != "production"`, response includes `{ token }` (raw token for frontend dev banner).
- Rate limit: inherits router-level admin guard.

**`POST /api/v2/auth/invite/accept/{token}`**

- Body: `{ password: str, full_name: str }`
- Verifies token: hash lookup + unused + not expired + `purpose='invite'`.
- Creates user: bound email + Argon2id hash + `is_verified=True` + role from invite.
- Returns `201` with `UserResponse`.
- Rate limit: `Depends(RateLimiter("invite-accept", 5, 3600))` — 5/h/IP.

### 5.2 Password reset flow (anonymous, on main `router`)

**`POST /api/v2/auth/password-reset/request`**

- Body: `{ email: str }`
- **Always returns `202`** — constant-time, no email enumeration (OWASP Forgot Password Cheat Sheet).
- If email exists: creates token with `purpose='reset'` + `user_id` set, dispatches via `EmailSender`.
- If email doesn't exist: no-op, still 202.
- **Dev-only:** When `ENVIRONMENT != "production"` and email exists, response includes `{ token }`.
- Rate limit: `Depends(RateLimiter("reset-request", 3, 3600))` — 3/h/IP. Account-level limit uses email as composite key: `rate:reset-request:{email}`.

**`POST /api/v2/auth/password-reset/confirm/{token}`**

- Body: `{ new_password: str }`
- Verifies token, updates user's password hash (Argon2id), invalidates all other reset tokens for that email.
- Returns `200` with `{ message: "Password reset successful" }`.
- Rate limit: `Depends(RateLimiter("reset-confirm", 5, 3600))` — 5/h/IP.

### 5.3 Email verification (anonymous, on main `router`)

**`POST /api/v2/auth/verify-email/{token}`**

- Verifies token with `purpose='verify'`.
- Sets `is_verified=True` on the user.
- Returns `200` with `{ message: "Email verified" }`.
- Rate limit: `Depends(RateLimiter("verify-email", 5, 3600))` — 5/h/IP.

### 5.4 Resend invite

Not a new endpoint. Reuses `POST /api/v2/auth/invite` with the same email. Old unused tokens for that email + purpose are automatically invalidated when a new token is created.

### 5.5 Invite-only (negative test)

`POST /api/v2/auth/register` does NOT exist. Verified by `test_register_endpoint_absent.py` expecting 404/405.

---

## 6. Rate limiter dependency

New file: `backend/app/auth/rate_limit.py`

```python
class RateLimiter:
    """FastAPI Depends() guard for per-endpoint rate limiting."""

    def __init__(self, key_prefix: str, max_requests: int, window_seconds: int): ...

    async def __call__(self, request: Request) -> None:
        """Raises HTTPException(429) with Retry-After header if limit exceeded."""
```

- Uses existing `cache.incr()` with TTL from `backend/app/core/cache.py`.
- Key format: `rate:{key_prefix}:{client_ip}`.
- Account-level variant: `rate:{key_prefix}:{email}` (for reset-request).
- Returns `Retry-After` header on 429.
- Does NOT modify the existing global rate limiter in `middleware/rate_limiter.py` — separate concern, separate module.

---

## 7. Frontend

### 7.1 New routes

| Route | View | Auth required | Notes |
|-------|------|:------------:|-------|
| `/forgot-password` | `ForgotPassword.vue` | No | Linked from Login.vue |
| `/reset-password/:token` | `ResetPassword.vue` | No | From email link |
| `/accept-invite/:token` | `AcceptInvite.vue` | No | From email link |
| `/verify-email/:token` | `VerifyEmail.vue` | No | From email link |

All four are anonymous routes — `requiresAuth: false`. Navigation guards must not redirect them to `/login`.

### 7.2 New views

**`ForgotPassword.vue`** (~80 LOC)
- Email input form + submit.
- On submit: `POST /auth/password-reset/request`.
- Always shows "If an account exists with that email, we've sent a reset link" (constant-time UX).
- **Dev-only banner:** `v-if="!isProduction"` shows the token URL from response. Gated by `import.meta.env.VITE_ENVIRONMENT !== 'production'`. Tree-shaken from production build.
- Link back to `/login`.

**`ResetPassword.vue`** (~90 LOC)
- Reads `:token` from route params.
- New password + confirm password form.
- On submit: `POST /auth/password-reset/confirm/{token}`.
- Success: redirect to `/login` with success toast.
- Error: expired/invalid token message with link to `/forgot-password`.

**`AcceptInvite.vue`** (~100 LOC)
- Reads `:token` from route params.
- Shows bound email (passed as query param in invite URL, e.g., `/accept-invite/{token}?email=user@example.com` — display only, not trusted for creation).
- Full name + password + confirm password form.
- On submit: `POST /auth/invite/accept/{token}`.
- Success: redirect to `/login` with "Account created" toast.

**`VerifyEmail.vue`** (~50 LOC)
- Reads `:token` from route params.
- Auto-consumes token on mount (no form).
- Shows success, error (expired/invalid), or already-used state.
- Link to `/login`.

### 7.3 Modified views

**`Login.vue`** — Replace `handleForgotPassword` TODO stub (line 175) with `router.push('/forgot-password')`.

**`AdminUsers.vue`** + **`UserListTable.vue`** — Add "Resend Invite" row action button. Icon: `mdi-email-fast`, tooltip: "Resend Invite". Calls `POST /api/v2/auth/invite` with user's email. Only visible for users where `is_verified === false`.

### 7.4 API additions

Extend `frontend/src/api/domain/auth.js`:

- `requestPasswordReset(email)` — POST `/auth/password-reset/request`
- `confirmPasswordReset(token, newPassword)` — POST `/auth/password-reset/confirm/{token}`
- `acceptInvite(token, password, fullName)` — POST `/auth/invite/accept/{token}`
- `verifyEmail(token)` — POST `/auth/verify-email/{token}`
- `sendInvite(email, role)` — POST `/auth/invite` (reused for resend)

### 7.5 Dev-only token display

Backend endpoints for reset-request and invite include the raw token in the response body **only when `ENVIRONMENT != "production"`**. The frontend reads this field and renders a dev-only `v-alert` banner with the clickable token URL. In production, the field is absent from the JSON response — not hidden by CSS, actually omitted from serialization.

---

## 8. Testing

### 8.1 New backend tests (~30 tests)

| Test file | What it covers | Est. |
|-----------|----------------|:----:|
| `test_credential_tokens.py` | Hash storage, single-use, expiry, purpose discrimination, invalidate-by-email | ~6 |
| `test_auth_invite.py` | Admin creates invite, email binding (wrong email → rejected), accept creates user with Argon2id + `is_verified=True`, expired/used rejected, caplog verifies ConsoleEmailSender | ~7 |
| `test_auth_password_reset.py` | Request always 202, confirm resets hash, old tokens invalidated, rate limit 3/h | ~6 |
| `test_auth_email_verify.py` | Sets `is_verified=True`, single-use, expired rejected | ~3 |
| `test_auth_rate_limits_wave5c.py` | All anonymous endpoints rate-limited, 429 + Retry-After header | ~4 |
| `test_register_endpoint_absent.py` | `POST /auth/register` → 404/405 | ~1 |
| `test_email_sender.py` | ConsoleEmailSender formats correctly, satisfies EmailSender protocol | ~3 |

### 8.2 New frontend tests (~12 tests)

| Test file | What it covers | Est. |
|-----------|----------------|:----:|
| `ForgotPassword.spec.js` | Render, form validation, 202 handling, dev-banner | ~3 |
| `ResetPassword.spec.js` | Render, token from route, form submit, error states | ~3 |
| `AcceptInvite.spec.js` | Render, token from route, form submit, success redirect | ~3 |
| `VerifyEmail.spec.js` | Auto-consume on mount, success/error states | ~2 |
| Extend `auth.spec.js` | 5 new API functions | ~1 |

### 8.3 HTTP baselines (5 new)

| Fixture | Endpoint |
|---------|----------|
| `auth_invite.json` | `POST /api/v2/auth/invite` |
| `auth_invite_accept.json` | `POST /api/v2/auth/invite/accept/{token}` |
| `auth_password_reset_request.json` | `POST /api/v2/auth/password-reset/request` |
| `auth_password_reset_confirm.json` | `POST /api/v2/auth/password-reset/confirm/{token}` |
| `auth_verify_email.json` | `POST /api/v2/auth/verify-email/{token}` |

### 8.4 Entry → exit targets

| Metric | Entry | Exit |
|--------|:-----:|:----:|
| Backend tests | 1090 | ~1120-1130 |
| Frontend tests | 292 | ~304 |
| HTTP baselines | 14 | 19 |
| Backend lint | 0 errors | 0 errors |
| Frontend lint | 13 warnings | ≤13 warnings |

---

## 9. Commit ordering

| # | Type | Description | Scope item |
|---|------|-------------|:----------:|
| 1 | schema | `credential_tokens` Alembic migration + ORM model + downgrade | C1 |
| 2 | infra | Email config: `.env` vars, `config.yaml` email section, Settings validators, `.env.example` | C2 prereq |
| 3 | infra | `EmailSender` protocol + `ConsoleEmailSender` + `get_email_sender` DI + `test_email_sender.py` | C2 prereq |
| 4 | infra | `RateLimiter` dependency class + `test_auth_rate_limits_wave5c.py` | C3 |
| 5 | infra | Credential token repository: create, verify-and-consume, invalidate + `test_credential_tokens.py` | C2 prereq |
| 6 | feat | Invite endpoints + `test_auth_invite.py` + baseline | C2 |
| 7 | feat | Password reset endpoints + `test_auth_password_reset.py` + baseline | C2 |
| 8 | feat | Verify email endpoint + `test_auth_email_verify.py` + baseline | C2 |
| 9 | test | `test_register_endpoint_absent.py` | C5 |
| 10 | feat | Frontend: `ForgotPassword.vue` + `ResetPassword.vue` + routes + API + Login.vue wiring + specs | C4 |
| 11 | feat | Frontend: `AcceptInvite.vue` + `VerifyEmail.vue` + routes + API + specs | C4 |
| 12 | feat | Frontend: Resend Invite button on AdminUsers + UserListTable | C4 |
| 13 | docs | Wave 5c exit note + Wave 5 consolidated exit note + Wave 6 plan update | — |

---

## 10. Exit criteria

- [ ] `credential_tokens` table live; migration + downgrade tested
- [ ] 5 endpoints live, tested, baselined
- [ ] Rate limits bound on all anonymous token endpoints (invite-accept, reset-request, reset-confirm, verify-email)
- [ ] `POST /auth/register` returns 404/405 (invite-only, negative test)
- [ ] `ConsoleEmailSender` logs token URLs via structured logger
- [ ] SMTP config vars in `.env.example` + `config.yaml` email section (`backend: "console"` default)
- [ ] Startup validation: `backend: "smtp"` + empty `SMTP_HOST` → fail-fast
- [ ] Frontend: 4 new views functional, dev-only token banner works in non-production
- [ ] `Login.vue` forgot-password TODO replaced with `router.push('/forgot-password')`
- [ ] AdminUsers resend-invite button wired for unverified users
- [ ] Backend `make check` green (~1120-1130 tests)
- [ ] Frontend `make check` green (~304 tests)
- [ ] 19 HTTP baselines verified
- [ ] `docs/refactor/wave-5c-exit.md` written
- [ ] `docs/refactor/wave-5-exit.md` consolidated summary written
- [ ] Wave 6 plan updated with Mailpit + SMTPEmailSender + provider reference findings

---

## 11. Risks

### R1 — Token timing attacks on verify-and-consume (LOW)

SHA-256 comparison uses Python's `==` which is not constant-time. However, since we compare hex strings derived from hashing (not raw secrets), the information leaked is about the hash, not the token. The token space (32 bytes) makes brute force infeasible regardless.

**Mitigation:** Use `hmac.compare_digest()` for the SHA-256 comparison anyway — zero cost, defense in depth.

### R2 — Dev-only token leaking to production (MEDIUM)

Raw token in response body when `ENVIRONMENT != "production"` could leak if environment is misconfigured.

**Mitigation 1:** Backend checks `settings.ENVIRONMENT` (same trusted config source as dev-quick-login).
**Mitigation 2:** Frontend uses `import.meta.env.VITE_ENVIRONMENT` for the `v-if` gate — tree-shaken from production build.
**Mitigation 3:** HTTP baseline tests run in test environment; production baselines would not include the token field.

### R3 — Rate limiter Redis dependency in tests (LOW)

Rate limiter uses `cache.incr()` which falls back to in-memory in tests.

**Mitigation:** Test rate limiting by calling the endpoint N+1 times and asserting the last call returns 429. In-memory fallback preserves this behavior.

---

## 12. Files touched

```
backend/app/models/credential_token.py                 (NEW)
backend/alembic/versions/<hex>_credential_tokens.py    (NEW)
backend/app/auth/credential_tokens.py                  (NEW — repository)
backend/app/auth/email.py                              (NEW — protocol + ConsoleEmailSender)
backend/app/auth/rate_limit.py                         (NEW — RateLimiter dependency)
backend/app/api/auth_endpoints.py                      (5 new endpoints)
backend/app/schemas/auth.py                            (request/response schemas)
backend/app/core/config.py                             (email config + SMTP env vars + validators)
backend/app/auth/__init__.py                           (re-export new modules)
backend/.env.example                                   (SMTP vars)
backend/config.yaml                                    (email section)
backend/tests/fixtures/http_baselines/                 (5 new fixtures)
backend/tests/test_credential_tokens.py                (NEW)
backend/tests/test_auth_invite.py                      (NEW)
backend/tests/test_auth_password_reset.py              (NEW)
backend/tests/test_auth_email_verify.py                (NEW)
backend/tests/test_auth_rate_limits_wave5c.py          (NEW)
backend/tests/test_register_endpoint_absent.py         (NEW)
backend/tests/test_email_sender.py                     (NEW)
frontend/src/views/ForgotPassword.vue                  (NEW)
frontend/src/views/ResetPassword.vue                   (NEW)
frontend/src/views/AcceptInvite.vue                    (NEW)
frontend/src/views/VerifyEmail.vue                     (NEW)
frontend/src/views/Login.vue                           (wire forgot-password link)
frontend/src/views/AdminUsers.vue                      (resend invite button)
frontend/src/components/admin/UserListTable.vue        (resend invite action)
frontend/src/api/domain/auth.js                        (5 new functions)
frontend/src/router/index.js                           (4 new routes)
frontend/tests/unit/views/ForgotPassword.spec.js       (NEW)
frontend/tests/unit/views/ResetPassword.spec.js        (NEW)
frontend/tests/unit/views/AcceptInvite.spec.js         (NEW)
frontend/tests/unit/views/VerifyEmail.spec.js          (NEW)
docs/refactor/wave-5c-exit.md                          (NEW)
docs/refactor/wave-5-exit.md                           (NEW)
docs/superpowers/plans/2026-04-10-wave-6-tooling-evolution.md  (updated)
```
