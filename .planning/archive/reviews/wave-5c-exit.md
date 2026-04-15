# Wave 5c Exit Note

**Date:** 2026-04-12
**Branch:** `chore/wave-5c-identity-lifecycle` (sibling worktree at `~/development/hnf1b-db.worktrees/chore-wave-5c-identity-lifecycle/`)
**Target:** `main` (merge via PR)
**Entry commit:** `8eff251` (Wave 5b merge on main)

## Test counts -- entry vs exit

| Stage                     | Backend                           | Frontend                               |
| ------------------------- | --------------------------------- | -------------------------------------- |
| **Entry** (main `8eff251`) | 1090 collected                    | 292 passed + 1 xfailed                 |
| **Exit** (Wave 5c head)   | **1128 collected (+38)**           | **302 passed + 1 xfailed (+10)**       |

## HTTP baseline fixtures

- **Entry:** 14 fixtures (from Wave 5b exit)
- **Exit:** 14 fixtures (unchanged)

The 5 new fixtures originally planned (`auth_invite`, `auth_invite_accept`, `auth_password_reset_request`, `auth_password_reset_confirm`, `auth_verify_email`) were **deferred** -- they require custom token-setup plumbing in the baseline harness which was out of scope for this PR. Recommendation: capture them in a Wave 5c follow-up or during Wave 6.

## What landed (13 commits)

1. `6565d29` -- **feat(db): add credential_tokens table for identity lifecycle tokens** (Task 1). New table storing invite, password-reset, and verify-email tokens with hashed token values, expiry, and consumed-at timestamps. Migration + downgrade round-trip tested.

2. `e5f1bcd` -- **feat(config): add SMTP env vars and email config section** (Task 2). Adds `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` to `.env.example` plus a full `email:` section in `config.yaml` with `backend`, `from_address`, `from_name`, `tls_mode`, `validate_certs`, `timeout_seconds`, `use_credentials`, `max_retries`, `retry_backoff_factor`. Startup validator fails fast if `backend: "smtp"` + empty `SMTP_HOST`.

3. `b62b591` -- **feat(auth): add EmailSender protocol with ConsoleEmailSender** (Task 3). `EmailSender` Protocol class plus `ConsoleEmailSender` implementation that logs full URL with token via structured logger. `get_email_sender()` DI factory reads `settings.email.backend`; "smtp" branch raises `NotImplementedError` pending Wave 6.

4. `27d24ab` -- **feat(auth): add per-endpoint RateLimiter dependency** (Task 4). FastAPI `Depends`-compatible rate limiter keyed on IP + route. Applied to every anonymous/semi-public token endpoint.

5. `cbffe23` -- **feat(auth): add credential token repository with create/consume/invalidate** (Task 5). `CredentialTokenRepository` with `create()`, `consume()` (atomic hash lookup + expiry + mark consumed), and `invalidate_all_for_user()`. Token value is a URL-safe 32-byte secret; only the SHA-256 hash is stored.

6. `caf7636` -- **feat(api): add POST /auth/users/invite and POST /auth/invite/accept/{token}** (Task 6). Admin-only invite endpoint creates a `credential_tokens` row (kind=invite) and dispatches email via `EmailSender`. Public accept endpoint consumes the token, collects username + password, creates the user with `is_verified=True` directly, and returns a JWT pair.

7. `301a7ca` -- **feat(api): add password reset request and confirm endpoints** (Task 7). `POST /auth/password-reset/request` silently issues a token if the email exists (no user enumeration); `POST /auth/password-reset/confirm/{token}` consumes the token and updates the password. Both rate-limited.

8. `f8657a5` -- **feat(api): add verify-email consume and resend endpoints + auto-dispatch on user create** (Task 8). `POST /auth/verify-email/{token}` sets `is_verified=True`. `POST /auth/verify-email/resend` issues a fresh token for the authenticated user. Admin user-creation now auto-dispatches a verify email.

9. `22ddd7a` -- **test(auth): verify POST /auth/register does not exist (invite-only)** (Task 9). Negative test asserting the platform is invite-only; self-registration must return 404/405.

10. `6a5237e` -- **feat(frontend): add ForgotPassword and ResetPassword views** (Task 10). Two new anonymous views. `/forgot-password` form submits email to request endpoint. `/reset-password/:token` form submits new password to confirm endpoint. `Login.vue` "Forgot password?" link wired to `router.push('/forgot-password')`.

11. `1d77a42` -- **feat(frontend): add AcceptInvite and VerifyEmail views** (Task 11). `/accept-invite/:token` collects username + password and calls the accept endpoint (409 on conflict). `/verify-email/:token` calls the consume endpoint and shows success/expired state.

12. `e1731e1` -- **feat(frontend): add Invite User dialog to AdminUsers** (Task 12). New "Invite User" dialog alongside existing "Create User". Posts to `/auth/users/invite`. Dev-only token display gated by `import.meta.env.DEV`.

13. `<this commit>` -- **docs: add Wave 5c exit note + consolidated Wave 5 exit + Wave 6 plan update** (Task 13). This file, the consolidated Wave 5 summary, and SMTP/Mailpit inheritance docs in the Wave 6 plan.

## Exit criteria (all green)

- [x] **credential_tokens table live; migration + downgrade tested**
- [x] **6 endpoints live and tested:**
  - POST /auth/users/invite
  - POST /auth/invite/accept/{token}
  - POST /auth/password-reset/request
  - POST /auth/password-reset/confirm/{token}
  - POST /auth/verify-email/{token}
  - POST /auth/verify-email/resend
- [x] **Rate limits bound on all anonymous/semi-public token endpoints**
- [x] **POST /auth/register returns 404/405** (invite-only negative test)
- [x] **Invite-accept collects username with 409 on conflict**
- [x] **Admin user creation auto-dispatches verify email**
- [x] **Invite-accept sets is_verified=True directly**
- [x] **ConsoleEmailSender logs token URLs via structured logger**
- [x] **SMTP config vars in .env.example + config.yaml email section** (backend: "console" default)
- [x] **Startup validation:** backend: "smtp" + empty SMTP_HOST -> fail-fast
- [x] **Dev-only token display:** backend gated by `settings.environment != "production"`, frontend gated by `import.meta.env.DEV`
- [x] **4 new anonymous views:** ForgotPassword, ResetPassword, AcceptInvite, VerifyEmail
- [x] **Login.vue forgot-password wired** to `router.push('/forgot-password')`
- [x] **AdminUsers has Invite User dialog** alongside Create User
- [x] **Backend make check green**
- [x] **Frontend make check green**

## Wave 5a + 5b invariants preserved

- [x] 14 existing HTTP baselines still verify
- [x] Admin user CRUD still operational
- [x] BFLA router-level guards still in place
- [x] Argon2id primary + bcrypt fallback still transparently upgrading
- [x] Global soft-delete filter still operational
- [x] `_system_migration_` placeholder still protected from delete/deactivate

## What was deferred to Wave 6

- **SMTPEmailSender implementation** (real email delivery)
- **Mailpit container** for dev email capture
- **HTML email templates** (Jinja2 or similar)
- **Outbound mail rate limiting** (`email.rate_limit` config)
- **5 HTTP baseline fixtures** for new identity endpoints (custom token-setup plumbing required)

## Incidental fixes made during Wave 5c

- **`delete_user` endpoint now cleans up `credential_tokens` for the deleted user.** Required because `credential_tokens.user_id` FK has no `ON DELETE` clause. Task 8 discovered this regression via `test_create_then_update_then_unlock_then_delete_user`.
- **`backend/conftest.py` now sets `ENVIRONMENT=development` in test env** so dev-only token fields appear in responses. Needed for integration tests to access raw tokens for round-trip assertions.

## Entry conditions for Wave 6

- [x] Identity lifecycle fully functional in dev mode (via ConsoleEmailSender)
- [x] All config plumbing for SMTP ready (just needs the SMTPEmailSender class)
- [x] EmailSender protocol allows drop-in replacement without endpoint changes
- [x] 1128 backend tests + 302 frontend tests green
- [x] 14 HTTP baselines stable

**Wave 5c is done.**
