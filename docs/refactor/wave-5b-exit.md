# Wave 5b Exit Note

**Date:** 2026-04-12
**Branch:** `chore/wave-5b-user-management` (sibling worktree at `~/development/hnf1b-db.worktrees/chore-wave-5b-user-management/`)
**Target:** `main` (merge via PR)
**Entry commit:** `eb7d0c7` (Wave 5b plan commit on main)

## Test counts -- entry vs exit

| Stage                     | Backend                                 | Frontend                               |
| ------------------------- | --------------------------------------- | -------------------------------------- |
| **Entry** (main `eb7d0c7`) | 1063 passed + 11 skipped + 3 xfailed    | 288 passed + 1 xfailed (289 total)     |
| **Exit** (Wave 5b head)   | **1072 passed + 15 skipped + 3 xfailed** | **292 passed + 1 xfailed (293 total)** |
| Delta                     | +9 passed, +4 skipped                   | +4 passed                              |

## HTTP baseline fixtures

- **Entry:** 10 fixtures (8 Wave 4 originals + `dev_login_as_admin` + `auth_users_unlock`)
- **Exit:** 14 fixtures (the 10 above + **4 new**: `auth_users_list`, `auth_users_create`, `auth_users_update`, `auth_users_delete`; `last_login` added to `_VOLATILE_KEYS` for stable normalization)
- `-k verify`: 14/14 pass

## What landed (15 commits: 14 prior + this commit)

1. `0e72c61` -- **style(backend,frontend): apply ruff format + prettier drift cleanup.** Precursor commit. Auto-formatted files that had drifted from the canonical ruff/prettier style since Wave 5a merged. No logic changes.

2. `ca8c4dd` -- **chore(ci): enforce make check hygiene via pre-commit hook + CI gate.** Adds a pre-commit hook that runs `make check` in both backend and frontend. Closes Wave 5a follow-up #10 (lint drift prevention).

3. `dc71031` -- **fix(db): import all ORM models in alembic env.py + filter raw-SQL tables.** Closes Wave 5a follow-up #1 (alembic autogenerate producing spurious DROP TABLE migrations). All SQLAlchemy models now imported in `env.py`; raw-SQL-only tables excluded via `include_name`.

4. `752de85` -- **fix(backend): plug soft-delete leak in variant_query_builder raw-SQL CTEs.** Closes Wave 5a follow-up #2. Adds `AND p.deleted_at IS NULL` to variant query builder CTEs that bypassed the global ORM soft-delete filter.

5. `e6b97f8` -- **fix(backend): raise ValueError from audit.py instead of assert + handle in service.** Closes Wave 5a follow-up #3. Replaces bare `assert` in `create_audit_entry` with `ValueError` and adds handler in the service try/except chain.

6. `9c5f691` -- **docs(backend): update stale wave4_http_baselines reference in admin endpoints.** Closes Wave 5a follow-up #8. Docstring in `admin/endpoints.py` now points to the correct `http_baselines` directory.

7. `65f159f` -- **feat(api): add PATCH /auth/users/{id}/unlock endpoint + baseline.** Wave 5b Task 6. Admin-only endpoint to clear `failed_login_attempts` and `locked_until`. HTTP baseline captured. 3 tests (success, non-admin 403, user-not-found 404).

8. `0b4cda7` -- **refactor(api): split UserUpdate into UserUpdateAdmin + UserUpdatePublic (BOPLA).** Wave 5b Task 7. Prevents non-admin callers from escalating their own role via the public `/auth/change-password` path. Both schemas tested.

9. `32a5985` -- **test(auth): add explicit BFLA authorization matrix for admin routes.** Wave 5b Task 8. Parametrized test matrix asserts every `/auth/users/*` and `/admin/*` route denies viewer and curator tokens with 403.

10. `bfa4937` -- **refactor(auth): apply router-level BFLA guards on /auth/users + /admin.** Wave 5b Task 9. Moves `require_admin` from per-endpoint `Depends()` to `APIRouter(dependencies=...)` on both `users_router` and `admin_router`.

11. `147007a` -- **refactor(auth): remove per-endpoint require_admin guards now covered at router level.** Wave 5b Task 10. Removes now-redundant per-endpoint `Depends(require_admin)` calls.

12. `6a101dc` -- **refactor(auth): migrate passlib to pwdlib with verify-and-rehash.** Wave 5b Task 11. Replaces `passlib[bcrypt]` with `pwdlib[argon2,bcrypt]`. Login transparently rehashes legacy bcrypt to Argon2id.

13. `d941713` -- **refactor(frontend): split api/index.js into transport + session + domain modules.** Wave 5b Task 12. Monolithic `api/index.js` split into `transport.js`, `session.js`, and 11 domain modules under `api/domain/`.

14. `6690cd7` -- **refactor(frontend): extract useSyncTask composable from AdminDashboard.vue.** Wave 5b Task 13. Polling logic extracted to `composables/useSyncTask.js`; AdminDashboard drops from ~350 to ~250 LOC.

15. `<this commit>` -- **feat(frontend): admin user management UI + _system_migration_ guard + exit note.** Wave 5b Task 14. Backend `_system_migration_` guards on delete + deactivate, 5 new user-management tests, 4 new HTTP baselines. Frontend `AdminUsers.vue` view with role/active filters, create/edit dialogs, unlock, delete confirmation. `AdminUsersCard.vue` on dashboard. Client-side `_system_migration_` filter. Route at `/admin/users` with `requiresAuth + requiresAdmin`.

## Exit criteria (all green)

- [x] **`_system_migration_` protected from delete** -- `test_delete_system_migration_user_forbidden` passes (400)
- [x] **`_system_migration_` protected from deactivation** -- `test_deactivate_system_migration_user_forbidden` passes (400)
- [x] **Self-delete prevented** -- `test_cannot_self_delete` passes (400)
- [x] **Full CRUD round-trip** -- `test_create_then_update_then_unlock_then_delete_user` passes
- [x] **Role filter on list** -- `test_list_users_supports_role_filter` passes
- [x] **14 HTTP baselines verified** -- `pytest -k verify` shows 14/14 pass
- [x] **`/admin/users` route guarded** -- `requiresAuth: true, requiresAdmin: true` in router
- [x] **`_system_migration_` hidden from UI** -- `AdminUsers.spec.js` asserts placeholder absent from rendered list
- [x] **AdminUsersCard mounted on AdminDashboard** -- visible in template + import
- [x] **No resend-invite button** -- scope doc S4.2 explicit; not shipped, not hidden, not disabled, not stubbed
- [x] **Backend tests green** -- 1072 passed, 15 skipped, 3 xfailed
- [x] **Backend ruff green** -- `uv run ruff check .` returns "All checks passed!"
- [x] **Backend mypy green** -- no issues found
- [x] **Frontend tests green** -- 292 passed + 1 xfailed (293 total)
- [x] **Frontend lint** -- 0 errors, 13 warnings (matches Wave 5a exit baseline)
- [x] **Frontend build** -- `npm run build` succeeds
- [x] **Pre-commit hooks** -- all hooks pass

## Wave 5a invariants preserved

- [x] Audit FK columns still nullable BigInt FK to users.id
- [x] Global soft-delete filter still operational (ORM path)
- [x] variant_query_builder raw-SQL CTEs include `deleted_at IS NULL` (Wave 5b fix)
- [x] Dev-mode 5 layers still operational (Layer 4 DCE verified by build)
- [x] 10 pre-existing HTTP baselines still verify cleanly
- [x] v-html XSS sanitization intact in About.vue + FAQ.vue

## What was deferred

- **Resend-invite button** -- scope doc S4.2: "not shipped, not hidden, not disabled, not stubbed". Wave 5c ships it fresh along with the `/auth/invite` endpoint.
- **Email verification flow** -- requires SMTP integration; Wave 5c scope.
- **Password strength meter** -- nice-to-have; not in Wave 5b scope.
- **User activity log in admin UI** -- audit_log table exists but no frontend view yet.

## Entry conditions for Wave 5c

- [x] Admin user CRUD fully operational at `/admin/users`
- [x] `_system_migration_` placeholder protected from accidental admin operations
- [x] Argon2id is the default password hash; legacy bcrypt transparently rehashes on login
- [x] BFLA guards at router level on all admin routes
- [x] 14 HTTP surface baselines lock the API contract
- [x] Pre-commit hook enforces `make check` on every commit
- [x] All backend tests green (1072 passing)
- [x] Frontend lint at 13 warnings, 0 errors

**Wave 5b is done.**
