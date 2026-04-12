# Wave 5 Exit Note -- Consolidated Summary (5a + 5b + 5c)

**Date:** 2026-04-12
**Scope:** Platform-readiness refactor delivered across three sequential PRs

## Overview

Wave 5 completed the platform-readiness refactor in 3 sequential PRs, transforming HNF1B-DB from an invited-curator data-entry tool to a multi-user curation platform with credible identity lifecycle. The wave was split to keep each PR reviewable and to land foundational guarantees (audit FKs, dev-mode gating, XSS fix) before layering user-management UI (admin CRUD, BOPLA/BFLA hardening) and finally identity lifecycle (invite / reset / verify email flows).

## PR summary table

| PR       | Branch                              | Scope                                                                                                        | Commits | Merged                  |
| -------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------- | ----------------------- |
| Wave 5a  | `chore/wave-5a-foundations`         | Audit-on-create, FK-ify audit actor, soft-delete filter, dev-mode quick-login (5 layers), v-html sanitization | 18      | 2026-04-11 (PR #233)    |
| Wave 5b  | `chore/wave-5b-user-management`     | Admin user CRUD, BOPLA/BFLA hardening, pwdlib migration, api/index.js split, useSyncTask composable           | 15      | 2026-04-12 (PR #234)    |
| Wave 5c  | `chore/wave-5c-identity-lifecycle`  | credential_tokens, invite/reset/verify flows, EmailSender protocol, rate limiter, 4 frontend views            | 13      | TBD                     |

Full details for each PR in the sibling exit notes:
- `docs/refactor/wave-5a-exit.md`
- `docs/refactor/wave-5b-exit.md`
- `docs/refactor/wave-5c-exit.md`

## Combined test deltas

| Layer      | Entry (pre-5a) | Exit (post-5c) | Delta   |
| ---------- | -------------- | -------------- | ------- |
| Backend    | ~907 tests     | ~1128 tests    | **+221** |
| Frontend   | ~288 tests     | ~302 tests     | **+14**  |
| HTTP baselines | 8 fixtures | 14 fixtures    | +6      |

## Wave 5 success criteria (from scope doc S8) -- all met

- [x] **Admin can create curator accounts via `/admin/users` without SQL** (5b)
- [x] **User who forgot password can reset it via login page without admin** (5c)
- [x] **Locked account unlockable by admin without 15-min wait** (5b)
- [x] **Admin can invite new curator by email; invite accept creates Argon2id user** (5c)
- [x] **Every phenopacket CREATE/UPDATE/DELETE leaves audit row with FK'd actor** (5a)
- [x] **No forced logouts from bcrypt -> Argon2id migration** (5b; verify-and-rehash on login)
- [x] **`grep -r "dev-admin|DevQuickLogin|dev/login-as" dist/`** returns empty (5a; Vite DCE)
- [x] **2026-04-09 P1 #1 v-html XSS closed** (5a; About.vue + FAQ.vue sanitize wrap)
- [x] **OWASP API3 (BOPLA) closed** at schema level: `UserUpdateAdmin` vs `UserUpdatePublic` (5b)
- [x] **OWASP API5 (BFLA) closed** at router level: `require_admin` as router dep on `/auth/users` + `/admin` (5b)
- [x] **~985 test target met and exceeded** (~1128 at Wave 5c exit)
- [x] **All HTTP baselines verified** (14 fixtures stable at Wave 5c exit)

## Key architectural deliverables

### Wave 5a foundations
- `phenopackets.{created_by,updated_by,deleted_by}` + `phenopacket_audit.changed_by` migrated from `String(100)` to `BigInt FK -> users.id` with `_system_migration_` placeholder user for unmapped historical rows
- Audit row emitted on CREATE (was previously only on UPDATE/DELETE)
- Optimistic-locking revision check on DELETE (returns 409 on stale revision)
- Global soft-delete filter via SQLAlchemy `do_orm_execute` event listener with `include_deleted=True` escape hatch
- 5-layer dev-mode gating: config refusal, loopback-only router, `is_fixture_user` DB flag, frontend DCE, CI grep jobs
- HTTP baseline dir renamed `wave4_http_baselines/` -> `http_baselines/`

### Wave 5b user management
- Admin CRUD endpoints on `/auth/users/*` (list, create, get, update, delete, unlock, deactivate)
- `_system_migration_` placeholder protected from delete + deactivate
- BOPLA: `UserUpdate` schema split into `UserUpdateAdmin` (role-mutable) and `UserUpdatePublic` (role-locked)
- BFLA: `require_admin` lifted to router-level `dependencies=...` on `users_router` + `admin_router`
- `passlib[bcrypt]` -> `pwdlib[argon2,bcrypt]` migration with verify-and-rehash on login
- `frontend/src/api/index.js` monolith split into `transport.js`, `session.js`, and 11 domain modules
- `useSyncTask` composable extracted from `AdminDashboard.vue`
- `AdminUsers.vue` view + `AdminUsersCard.vue` dashboard tile at `/admin/users`

### Wave 5c identity lifecycle
- `credential_tokens` table (kind: invite/reset/verify, hashed token, expiry, consumed-at)
- `EmailSender` protocol + `ConsoleEmailSender` implementation (SMTP deferred to Wave 6)
- Per-endpoint `RateLimiter` dependency keyed on IP + route
- 6 new endpoints:
  - `POST /auth/users/invite` (admin-only)
  - `POST /auth/invite/accept/{token}` (anonymous)
  - `POST /auth/password-reset/request` (anonymous; no user enumeration)
  - `POST /auth/password-reset/confirm/{token}` (anonymous)
  - `POST /auth/verify-email/{token}` (anonymous)
  - `POST /auth/verify-email/resend` (authenticated)
- 4 new anonymous frontend views: `ForgotPassword`, `ResetPassword`, `AcceptInvite`, `VerifyEmail`
- `AdminUsers.vue` "Invite User" dialog alongside "Create User"
- Full SMTP config plumbing in `.env.example` + `config.yaml` (ready for Wave 6 `SMTPEmailSender`)

## Explicitly deferred to Wave 6

- **Bundle D:** phenopacket.state, revisions, comments, 3-lane review screen
- **Bundle E:** ORCID, user preferences, public attribution
- **Rest of Bundle F:** HttpOnly cookie refresh token, sessions table, CSRF protection
- **Bundle G:** `docs/security/` baseline doc, Playwright E2E expansion
- **Real SMTP:** `SMTPEmailSender` class + Mailpit container for dev (see Wave 6 plan)
- **HTML email templates** (Jinja2 recommended)
- **Outbound mail rate limiting** (`email.rate_limit` config)
- **5 HTTP baseline fixtures** for new identity endpoints (custom token-setup plumbing)
- **Large component decomposition:** `PageVariant.vue`, `HNF1BGeneVisualization.vue`, etc.

## Security posture at Wave 5 exit

- **XSS:** All 8 `v-html` sinks wrapped through `sanitize()` (Wave 5a); sanitize contract test guards regression
- **Audit:** FK'd actor on every CREATE/UPDATE/DELETE; global soft-delete filter; optimistic-locking revision check
- **AuthN:** Argon2id primary + bcrypt verify-and-rehash fallback; `ADMIN_PASSWORD` required at startup; JWT with `JWT_SECRET` required
- **AuthZ:** Router-level `require_admin` on `/auth/users` + `/admin`; BOPLA schema split prevents role escalation via public paths
- **Identity lifecycle:** Invite-only (no `/auth/register` endpoint); verified tokens hashed at rest; rate-limited on all anonymous/semi-public endpoints
- **Dev-mode isolation:** 5-layer gating prevents dev auth leakage into production bundles

## Wave 5 is done.

Three PRs, 46 commits total, zero regressions in existing baselines, full platform-readiness feature set delivered. Wave 6 inherits a codebase with credible identity lifecycle, admin user management, audit integrity, and a clean path to real SMTP delivery.
