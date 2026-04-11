# Wave 5a Exit Note

**Date:** 2026-04-11
**Branch:** `chore/wave-5a-foundations` (sibling worktree at `~/development/hnf1b-db.worktrees/chore-wave-5a-foundations/`)
**Target:** `main` (merge via PR)
**Entry commit:** `c3ea38c` (Wave 5a plan commit on main)

## Test counts — entry vs exit

| Stage                    | Backend                                | Frontend                              |
| ------------------------ | -------------------------------------- | ------------------------------------- |
| **Entry** (main `c3ea38c`) | 978 passed + 9 skipped + 3 xfailed     | 267 passed + 1 xfailed (268 total)    |
| **Exit** (Wave 5a head)  | **998 passed + 10 skipped + 3 xfailed** | **269 passed + 1 xfailed (270 total)** |
| Delta                    | +20 passed, +1 skipped                 | +2 passed                             |

> **Plan vs reality on entry count:** The plan predicted a 907-test baseline. Actual baseline on `main` at commit `c3ea38c` was 978. The plan was written against an earlier main state and all downstream "expected ~N passed" predictions in the plan's verification steps were 71 higher than observed. The invariants that mattered — zero failing tests, matching `9 skipped` and `3 xfailed` — held throughout.

## HTTP baseline fixtures

- **Entry:** 8 Wave 4 fixtures (`admin_status`, `phenopackets_list`, `phenopackets_search`, `phenopackets_compare_variant_types`, `phenopackets_aggregate_summary`, `publications_list`, `reference_genes`, `search_autocomplete`)
- **Exit:** 9 fixtures (the 8 above, renamed dir + **1 new** `dev_login_as_admin.json`, tokens masked)
- `-k verify`: 9/9 pass

## What landed (15 commits)

1. `c93bd85` — **refactor(tests): rename http baseline fixtures dir to drop wave4 prefix.** Pure rename; zero logic changes; directory `wave4_http_baselines/` → `http_baselines/`; 8 fixtures relocated cleanly via `git mv`.

2. `3411179` — **feat(db): add is_fixture_user BOOLEAN column to users table.** Non-nullable, `server_default=FALSE`. Prereq for Wave 5 dev-mode Layer 3. Migration hand-written (autogenerate would have produced a spurious drop-table migration — see `env.py` drift note below).

3. `65d226b` — **refactor(db): FK-ify audit actor columns with system-migration placeholder.** Highest-risk commit in the PR (effort 4, risk 4). Converts `phenopackets.{created_by,updated_by,deleted_by}` and `phenopacket_audit.changed_by` from `String(100)` to `BigInt FK → users.id`. Migration seeds `_system_migration_` placeholder user, JOIN-populates FKs, falls back unmapped strings to the placeholder, adds FK constraints (`ON DELETE SET NULL`), drops old string columns. Downgrade reverses everything. Live DB round-trip verified against 864 phenopackets + 1728 audit rows. Updated call sites: `PhenopacketService.{create,update,soft_delete}` (`actor_id: Optional[int]`), `create_audit_entry` (`changed_by_id`), `PhenopacketRepository` (`_with_actor_eager_loads` helper via `selectinload`), `build_phenopacket_response` (renders username via relationship → API contract preserved), router, `list_audit_history` endpoint, Google-Sheets importer. 22 files changed, 841/134 insertions/deletions.

4. `9acfaa5` — **feat(backend): emit audit row on phenopacket CREATE.** Closes audit-on-create gap. `PhenopacketService.create()` now calls `create_audit_entry(action="CREATE")` inside the same transaction as the phenopacket INSERT.

5. `4cf7a6a` — **fix(backend): add optimistic-locking revision check to DELETE.** `PhenopacketDelete` gains optional `revision`; `soft_delete(expected_revision=...)` raises `ServiceConflict` on mismatch → router maps to 409. Backwards-compatible: omitting `revision` preserves blind-delete (frontend will adopt in Wave 5b).

6. `f9cb05d` — **feat(backend): add global soft-delete filter for Phenopacket entity.** SQLAlchemy `do_orm_execute` event listener attached to `Session` class applies `with_loader_criteria(Phenopacket, ...)` to every SELECT. Escape hatch: `execution_options(include_deleted=True)`. Scoped to `Phenopacket` only — other models unaffected. Manual per-method filters removed from `PhenopacketRepository`.

7. `1f496df` — **fix(frontend): sanitize v-html in About.vue and FAQ.vue.** 8 `v-html` sinks wrapped through existing `sanitize()` utility (About: 3, FAQ: 5). Double-wrap is defense-in-depth because `renderMarkdown`/`formatCitation` already call `sanitize()` internally. `frontend/tests/unit/utils/sanitize.spec.js` already existed from before Wave 5a (commit `5091011`) — no new test file created. Closes P1 #1 CRITICAL XSS finding from 2026-04-09 codebase review.

8. `1748ffb` — **feat(backend): add environment + enable_dev_auth config with refusal validator.** Dev-mode Layer 1. `Settings` now has `environment: Literal["development","staging","production"] = "production"` and `enable_dev_auth: bool = False` plus `model_validator(mode="after")` that raises `ValueError` (containing `"ENABLE_DEV_AUTH"`) if `enable_dev_auth=True` outside `environment=development`.

9. `7693275` — **feat(backend): add dev-only quick-login router with 5-layer gating.** Dev-mode Layer 2 + partial Layer 3. `backend/app/api/dev_endpoints.py` with module-level `assert`, `_require_loopback` dependency, `is_fixture_user` gate on the endpoint. Conditional mount in `main.py`. `dev_auth_client` conftest fixture, 4 tests, captured HTTP baseline `dev_login_as_admin.json` with token masking via `_VOLATILE_KEYS`.

10. `888f8cd` — **feat(backend): add dev fixture user seed script + Makefile target.** Dev-mode Layer 3 completion. `backend/scripts/seed_dev_users.py` seeds dev-admin/dev-curator/dev-viewer with `is_fixture_user=True`. Refuses outside `ENVIRONMENT=development`. `make dev-seed-users` target added to backend + root Makefiles.

11. `f3581c5` — **feat(frontend): add DevQuickLogin component with build-time DCE gating.** Dev-mode Layer 4. `DevQuickLogin.vue` component + dynamic import in `Login.vue` via `shallowRef(null)` + `if (import.meta.env.DEV)` + `defineAsyncComponent`. `devLoginAs` action on `authStore.js` with `if (!import.meta.env.DEV) return` as first statement. Vite/Rollup DCE verified clean on production build: `grep -rE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/` returns empty.

12. `5375aa5` — **docs(frontend): correct stale DCE comment in devLoginAs.** Hygiene fix — the Layer 4 comment in `authStore.js` referenced `/api/v2/dev/login-as/` but the actual template literal is `/dev/login-as/` (apiClient's baseURL already includes `/api/v2/`). Updated so a security auditor grepping the production bundle for the commented literal finds the right string.

13. `249692d` — **ci: add Wave 5a Layer 5 grep jobs + prod compose ENVIRONMENT pin + README.** Dev-mode Layer 5. Three grep jobs added to `.github/workflows/ci.yml` frontend job: (1) bundle leak check, (2) `ENABLE_DEV_AUTH` not truthy in prod compose, (3) `ENVIRONMENT=production` pinned. Plan's `docker-compose.prod.yml` path was stale — actual prod compose file is `docker/docker-compose.npm.yml` (Nginx Proxy Manager overlay); adapted accordingly. `ENVIRONMENT: production` added to that file. `README.md` created at repo root (the repo had none) with Quick Start + dev-mode section.

14. `e69899d` — **style(tests): add docstrings to satisfy ruff D103/D209.** Late-discovered lint cleanup. Tasks 5 and 8 added new test files but ran only `uv run pytest`, not full `make check` (which includes `uv run ruff check .`). Six pydocstyle findings (5× D103 + 1× D209) accumulated silently. Fixed by adding terse docstrings to 5 test functions and reflowing one multi-line docstring closing quote.

15. `<this commit>` — **docs(refactor): wave 5a exit note.** This file.

## Exit criteria (all green)

- [x] **Every phenopacket CREATE emits an audit row** — `test_phenopackets_audit_on_create.py` (2 tests) pass
- [x] **DELETE returns 409 on stale revision** — `test_phenopackets_delete_revision.py` (3 tests) pass
- [x] **Audit actor columns are nullable BigInt FK → users.id** — `test_audit_actor_fk.py` (3 tests) pass; downgrade round-trip verified against live dev DB (864 phenopackets, 1728 audit rows) twice
- [x] **Global soft-delete filter in place** — `test_soft_delete_global_filter.py` (2 tests) pass; audit history endpoint still sees deleted rows via `execution_options(include_deleted=True)`
- [x] **v-html XSS closed** — All 8 sinks in About.vue + FAQ.vue wrapped through `sanitize()`; `sanitize.spec.js` contract covers XSS payloads
- [x] **Dev-mode 5 layers operational**
  - Layer 1: `test_config_refuses_dev_auth_in_prod.py` (4 tests) pass
  - Layer 2: `test_dev_endpoints.py` module-level assert + loopback guard (4 tests) pass
  - Layer 3: `is_fixture_user` DB column + seed script; `test_seed_dev_users.py` refusal test passes
  - Layer 4: production build grep for `dev-admin|DevQuickLogin|dev/login-as` returns CLEAN
  - Layer 5: CI grep jobs wired in `.github/workflows/ci.yml` (bundle + compose env + compose enable_dev_auth)
- [x] **HTTP baseline directory renamed** — 8 existing fixtures relocated + 1 new `dev_login_as_admin.json` with token masking. 9/9 verify tests pass.
- [x] **Backend tests green** — 998 passed, 10 skipped, 3 xfailed
- [x] **Backend ruff green** — `uv run ruff check .` returns "All checks passed!"
- [x] **Backend mypy green** — `Success: no issues found in 151 source files`
- [x] **Frontend tests green** — 269 passed + 1 xfailed (270 total)
- [x] **Frontend lint under baseline** — 13 warnings, 0 errors (baseline was ≤23)
- [x] **Frontend format check green** — `prettier --check` on committed state reports "All matched files use Prettier code style"
- [x] **Alembic round-trip verified** — `downgrade -2` restores `created_by` string columns + drops `is_fixture_user`; `upgrade head` restores both cleanly

## Commit-budget accounting

- **Scope doc cap (§7 R7):** 14 commits
- **Actual:** 15 commits (+1 over the guidance)
- **Overflow rationale:** Commit 14 (`e69899d`) is a late-discovered cross-cutting ruff cleanup, not new scope. Commit 12 (`5375aa5`) is a Task 11 hygiene follow-up that should have been folded into the Task 11 commit but can't be because of the no-amend rule. Neither adds new functionality; both improve hygiene/accuracy. No PR split is indicated.

## Surprises & follow-up items for Wave 5b

All of the following were flagged by code reviewers during Wave 5a and deferred as non-blocking. They should be swept up in a targeted Wave 5b cleanup commit.

### Pre-existing tech debt discovered (not introduced by Wave 5a)

1. **`backend/alembic/env.py` imports only 5 phenopackets models, not 20+.** `alembic revision --autogenerate` produces a massive spurious migration with `DROP TABLE` operations for every unimported model (users, genes, transcripts, variant_annotations, publication_metadata, etc.). Both Wave 5a migrations (`3411179` is_fixture_user and `65d226b` fk_audit) had to be written by hand. Fix: import every SQLAlchemy model in `env.py` (or use a `Base.metadata` discovery pattern) so autogenerate produces clean diffs. **Blocker for any future schema work that relies on autogenerate.**

2. **`variant_query_builder.py` raw SQL CTEs bypass the global soft-delete filter.** Two CTEs at lines ~363 and ~435 query `phenopackets` directly without `AND p.deleted_at IS NULL`. Commit `f9cb05d` protects ORM-executed queries only. The `/api/v2/phenopackets/aggregate/all_variants` endpoint currently leaks variant counts from soft-deleted phenopackets. Fix: add `AND p.deleted_at IS NULL` to both CTEs. Low severity (deleted rows are rare in practice), but should be closed because commit `f9cb05d` gave the impression the soft-delete leak risk was closed globally — it isn't.

### Wave 5a implementation gaps (cross-cutting, non-blocking)

3. **`create_audit_entry` has `assert audit_row is not None, ...` that isn't caught by the service's `except` chain.** If the `RETURNING` fetch returns None (e.g., driver quirk, test double), `AssertionError` propagates raw through `create()`, `update()`, and `soft_delete()` instead of being mapped to `ServiceDatabaseError`. Pre-existing since before Wave 5a for UPDATE/DELETE paths; Task 4 added a third call site with the same gap. Fix: replace the `assert` with `raise ValueError(...)` in `audit.py` and add a `ValueError` handler in the service try/except chain.

4. **`_refuse_dev_auth_in_prod` validator does not emit `logger.critical`.** The sibling validators `validate_jwt_secret` and `validate_admin_password` both emit a critical log before raising so ops teams can alert on startup refusal. The new validator only raises. Fix: add `logger.critical(...)` call before the `raise ValueError`.

5. **`_register_soft_delete_filter()` is not idempotent.** If `database.py` is ever reloaded (e.g., `importlib.reload`), the listener is registered twice because the inner function is a new closure each call and SQLAlchemy can't deduplicate. Current behavior is correct (Python caches `sys.modules`), but fragile. Fix: extract the inner function to module scope + add a module-level boolean sentinel guard.

6. **`dev_auth_client` test fixture permanently mounts the dev router on the shared `app`.** The fixture guards against double-mount but never unmounts. Test ordering can affect which routes are registered. No current test asserts the dev route is absent in non-dev mode, so this is currently low-risk. Fix: snapshot `app.router.routes` before the yield and restore in `finally`, or construct a separate test `FastAPI()` instance instead of mutating the shared one.

7. **`dev_endpoints.py` module docstring has internal layer-numbering inconsistency.** The 5-item docstring list and the plan's 5-layer numbering use different schemes (docstring item 5 = loopback; plan Layer 5 = CI grep). Fix: rewrite the docstring as prose or explicitly cross-reference the plan's layer numbers.

8. **Pre-existing stray reference to `wave4_http_baselines` in `backend/app/api/admin/endpoints.py:12`.** A docstring in production code points to the old baseline path that no longer exists. Fix: update the docstring to reference `http_baselines`.

9. **Frontend Layer 4 test assertion is weak.** `DevQuickLogin.spec.js` asserts `expect(authStore.devLoginAs).toHaveBeenCalled()` rather than `toHaveBeenCalledWith('dev-admin')`. A bug that swapped the username argument would still pass. Fix: strengthen to `toHaveBeenCalledWith('dev-admin')`.

10. **Task test files from Tasks 5 and 8 were not ruff-checked at commit time.** The ruff D103/D209 findings that `e69899d` cleaned up should have been caught by each task's own `make check`. Root cause: implementers ran `uv run pytest tests/<file>.py` but not the full `make check` target. Fix: make `make check` a hard precondition for every commit in Wave 5b (e.g., enforce via a branch-protection rule or a pre-commit hook) to prevent silent lint drift.

### Worktree hygiene note

The worktree started with four pre-existing unstaged frontend files modified (`AppBar.vue`, `About.vue`, `PageVariant.vue`, `SearchResults.vue`). All were small formatting deltas present when the worktree was created. None are from Wave 5a work; all were left untouched across all 15 commits. `git status --short` on the exit state still shows them as ` M` (unstaged). Intentional — they are out of Wave 5a scope and should be committed separately (or reverted) on main.

## What was deferred

Nothing from the original 13-task plan. All 13 tasks landed + the 2 hygiene commits (11-followup and ruff fix) described above.

## Entry conditions for Wave 5b

- [x] Every phenopacket CRUD operation leaves an FK'd audit row (CREATE, UPDATE, DELETE all tested)
- [x] `/api/v2/dev/login-as/<username>` works locally — faster iteration for Wave 5b admin-user UI development
- [x] Global soft-delete filter in place — Wave 5b's admin user UI can't accidentally show soft-deleted phenopacket references (via ORM; raw-SQL path in variant_query_builder still needs attention — see follow-up #2)
- [x] v-html XSS closed — one less CRITICAL finding
- [x] HTTP surface locked in by 9 baseline fixtures — any Wave 5b refactor that drifts responses fails `-k verify`
- [x] All backend tests green (998 passing)
- [x] Frontend lint at 13 warnings (down from 23 baseline — new DevQuickLogin adds no net new warnings)

**Wave 5a is done.**
