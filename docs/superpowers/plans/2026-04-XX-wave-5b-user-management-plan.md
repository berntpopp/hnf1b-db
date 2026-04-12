# Wave 5 PR 2 — User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Wave 5 Bundle B (admin user management UI + unlock endpoint), the OWASP-API3/API5 hardening (BOPLA + BFLA), the pwdlib migration, the `frontend/src/api/index.js` split, and the `useSyncTask` composable on `main` as a single reviewable PR — plus the four Wave 5a follow-up hygiene items the exit note flagged as non-blocking but in-scope for Wave 5b.

**Architecture:** 14 atomic commits on `chore/wave-5b-user-management` in a sibling worktree at `~/development/hnf1b-db.worktrees/chore-wave-5b-user-management/`. Commit ordering follows the refactor → schema → behavior → decomposition → UI → docs convention from the scope doc §7: commits 1–5 are Wave 5a hygiene follow-ups and a pre-commit enforcement gate (lowest-risk first), commit 6 is the unlock endpoint, commit 7 is the BOPLA schema split, commits 8–10 are the three-commit BFLA router-guard migration (tests → apply → remove per-endpoint guards), commit 11 is the pwdlib migration, commit 12 is the `api/index.js` split, commit 13 is the `useSyncTask` composable, commit 14 is the admin user management UI, commit 15 is the exit note — wait, that's 15. **Budget reconciliation:** commits 14 and 15 below are merged into the admin UI commit (UI + exit note must ship together to keep the PR atomic), reducing to 14 total. Each commit is independently reversible.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 async, Alembic, pwdlib[argon2,bcrypt], pytest + pytest-asyncio, Vue 3, Vuetify 3, Vitest, Pinia. Uses existing patterns — don't introduce new frameworks beyond pwdlib (the one explicit swap).

**Upstream source of truth:** `docs/superpowers/plans/2026-04-11-wave-5-scope.md` (committed on main at `f93f5c0` / `7c5d079`) — §3.1 in-scope table row for Bundle B, §4.2 PR 2 phase breakdown, §5 R2/R4/R5/R7 risk mitigations. Wave 5a exit note at `docs/refactor/wave-5a-exit.md` lists 10 follow-ups; this plan folds items #1, #2, #3, #8, #10.

**Entry state:** `main` at commit `eb7d0c7` (Wave 5a merge of PR #233) plus two post-merge fix commits:
- `eed0882` — Copilot/Codecov review feedback (added ~2 tests)
- `df74567` — Layer 2 guard subprocess DATABASE_URL fix (added ~1 test)

Baselines at Wave 5b entry:
- **Backend:** `1001 passed, 10 skipped, 3 xfailed`
- **Frontend:** `270 total` (`269 passed + 1 xfailed`)
- **HTTP baselines:** 9 fixtures at `backend/tests/fixtures/http_baselines/` — `admin_status`, `phenopackets_list`, `phenopackets_search`, `phenopackets_compare_variant_types`, `phenopackets_aggregate_summary`, `publications_list`, `reference_genes`, `search_autocomplete`, `dev_login_as_admin` (last one skipped unless `ENABLE_DEV_AUTH=true`)
- **Lint:** backend ruff clean, backend mypy 0 issues, frontend ≤13 warnings

**Exit state:** `chore/wave-5b-user-management` merged to `main`. Backend test count ~1025 (1001 + ~24 new). Frontend test count ~285 (270 + ~15 new). HTTP baselines extended to **14 fixtures** (9 existing + 5 new for `auth_users_list`, `auth_users_create`, `auth_users_update`, `auth_users_delete`, `auth_users_unlock`). Frontend `lint` warnings ≤13 (no regression). No regressions in any existing baseline fixture. Every Wave 5a invariant preserved (see §"Non-negotiable invariants" below).

**Non-negotiable invariants (do NOT break):**

- All 9 entry-state HTTP baselines must pass after EVERY commit in this PR
- Layers 1–5 of the dev-mode quick-login defense must remain operational; `make dev-seed-users` still works; `grep -r "dev/login-as\|DevQuickLogin\|dev-admin" dist/` still empty on prod build
- `users.is_fixture_user` column stays `nullable=False default=False`
- `_system_migration_` placeholder user is protected from admin delete AND from deactivation via the admin UI (Task 14 adds the guard; Task 14 test asserts it)
- Global soft-delete filter registered in `backend/app/database.py` stays scoped to `Phenopacket` ORM entity only — do NOT widen it
- `require_admin` semantics do not change: anyone who previously got 403 still gets 403; anyone who previously got 200 still gets 200 (Task 8 validates this explicitly)

---

## Worktree setup (do this once before Task 1)

```bash
# From ~/development/hnf1b-db (main branch)
git fetch origin
git checkout main
git pull --ff-only origin main

# Verify entry state — main must include the Wave 5a merge commit
git log --oneline -5
# Expect top line: eb7d0c7 Merge pull request #233 from berntpopp/chore/wave-5a-foundations
# Or newer if there are post-merge fixups (eed0882, df74567).

# Create sibling worktree per CLAUDE.md convention (branch name slashes → dashes)
git worktree add ~/development/hnf1b-db.worktrees/chore-wave-5b-user-management -b chore/wave-5b-user-management
cd ~/development/hnf1b-db.worktrees/chore-wave-5b-user-management

# Install dependencies (worktrees start with no untracked files)
cd backend && uv sync --group test && cd ..
cd frontend && npm install && cd ..

# Verify baseline test state
cd backend && uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1001 passed, 10 skipped, 3 xfailed
cd ..

cd frontend && npm run test -- --run 2>&1 | tail -10
# Expect: Test Files 22 passed | 1 failed (the 1 xfailed is surfaced by vitest as a known failure), Tests 269 passed + 1 xfailed
cd ..

cd backend && uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 9 passed (the dev_login_as_admin baseline is skipped unless ENABLE_DEV_AUTH=true)
cd ..

# Start hybrid services (if not already up)
make hybrid-up
```

All subsequent tasks run from `~/development/hnf1b-db.worktrees/chore-wave-5b-user-management/`. **Never commit inside the main checkout at `~/development/hnf1b-db`.**

**Post-migration re-seed reminder (Wave 5a aftermath):** If any task in this PR runs `alembic downgrade -N && upgrade head`, the three dev fixture users (`dev-admin`, `dev-curator`, `dev-viewer`) silently lose `is_fixture_user=TRUE` because downgrading drops the column and upgrading recreates it with `server_default=FALSE`. After any full round-trip, run `make dev-seed-users` to restore the flag. (Task 10 and Task 11 both involve migration work — watch for this there.)

**Untracked files to NEVER `git add`:**

- `.codex/` (Codex tool state, regenerates)
- `.benchmarks/` (pytest-benchmark cache)
- `.planning/phases/` (GSD slash-command state)
- `docs/refactor/wave-4-kickoff-prompt.md` (untracked by design)
- `docs/reviews/2026-04-11-platform-readiness-review.md` (untracked by design)
- `docs/reviews/codebase-best-practices-review-2026-04-09.md` (untracked by design)

**NEVER run `git clean -fd`** — the untracked review files are load-bearing and were restored from session cache during a prior incident.

---

## File structure

This PR creates and modifies the following files. Files are grouped by concern, not by task, so you can see the complete shape before implementing any single task.

### New files

```
.pre-commit-config.yaml                                       # Task 1
backend/tests/test_variant_query_soft_delete.py               # Task 3
backend/tests/test_audit_entry_error_handling.py              # Task 4
backend/tests/test_auth_unlock_endpoint.py                    # Task 6
backend/tests/test_auth_bopla_schemas.py                      # Task 7
backend/tests/test_admin_route_authorization.py               # Task 8
backend/tests/test_pwdlib_rehash.py                           # Task 11
backend/tests/fixtures/http_baselines/auth_users_list.json    # Task 6 / Task 14 capture
backend/tests/fixtures/http_baselines/auth_users_create.json  # Task 14 capture
backend/tests/fixtures/http_baselines/auth_users_update.json  # Task 14 capture
backend/tests/fixtures/http_baselines/auth_users_delete.json  # Task 14 capture
backend/tests/fixtures/http_baselines/auth_users_unlock.json  # Task 6 capture
frontend/src/api/transport.js                                 # Task 12
frontend/src/api/session.js                                   # Task 12
frontend/src/api/domain/phenopackets.js                       # Task 12
frontend/src/api/domain/aggregations.js                       # Task 12
frontend/src/api/domain/publications.js                       # Task 12
frontend/src/api/domain/auth.js                               # Task 12
frontend/src/api/domain/hpo.js                                # Task 12
frontend/src/api/domain/clinical.js                           # Task 12
frontend/src/api/domain/variants.js                           # Task 12
frontend/src/api/domain/reference.js                          # Task 12
frontend/src/api/domain/variant_annotation.js                 # Task 12
frontend/src/api/domain/search.js                             # Task 12
frontend/src/api/domain/admin.js                              # Task 12
frontend/tests/unit/api/transport.spec.js                     # Task 12
frontend/tests/unit/api/session.spec.js                       # Task 12
frontend/src/composables/useSyncTask.js                       # Task 13
frontend/tests/unit/composables/useSyncTask.spec.js           # Task 13
frontend/src/views/AdminUsers.vue                             # Task 14
frontend/src/components/admin/AdminUsersCard.vue              # Task 14
frontend/src/components/admin/UserListTable.vue               # Task 14
frontend/src/components/admin/UserCreateDialog.vue            # Task 14
frontend/src/components/admin/UserEditDialog.vue              # Task 14
frontend/tests/unit/views/AdminUsers.spec.js                  # Task 14
docs/refactor/wave-5b-exit.md                                 # Task 14
docs/refactor/tech-debt.md                                    # Task 11 (if not already present on main; append otherwise)
```

### Modified files

```
backend/alembic/env.py                                         # Task 2 (import all ORM models + include_object filter)
backend/tests/test_alembic_env_autogenerate.py                 # Task 2 (NEW test verifying clean diff)
backend/app/phenopackets/routers/aggregations/variant_query_builder.py  # Task 3 (2 CTEs gain deleted_at IS NULL)
backend/app/utils/audit.py                                     # Task 4 (assert → ValueError)
backend/app/phenopackets/services/phenopacket_service.py       # Task 4 (handle new ValueError branch)
backend/app/api/admin/endpoints.py                             # Task 5 (docstring: wave4_http_baselines → http_baselines)
backend/app/repositories/user_repository.py                    # Task 6 (unlock method)
backend/app/api/auth_endpoints.py                              # Tasks 6, 7, 8, 9 (unlock endpoint, schema split, router refactor, per-endpoint guard removal, _system_migration_ guard)
backend/app/schemas/auth.py                                    # Task 7 (rename UserUpdate → UserUpdateAdmin + add UserUpdatePublic)
backend/app/auth/password.py                                   # Task 11 (passlib → pwdlib)
backend/pyproject.toml                                         # Task 11 (remove passlib, add pwdlib[argon2,bcrypt])
backend/uv.lock                                                # Task 11 (regenerated by uv sync)
frontend/src/api/index.js                                      # Task 12 (rewritten as ≤100 LOC re-export aggregator)
frontend/src/views/AdminDashboard.vue                          # Task 13 (use useSyncTask for 3 sync flows), Task 14 (mount AdminUsersCard)
frontend/src/router/index.js                                   # Task 14 (add /admin/users route)
backend/tests/test_http_surface_baseline.py                    # Tasks 6, 14 (5 new fixture tuples)
.github/workflows/ci.yml                                       # Task 1 (run pre-commit on every push)
```

### Responsibilities

- **`.pre-commit-config.yaml`** — module-level `repos:` list that runs `uv run ruff check`, `uv run mypy`, `npm run lint`, `npm run format:check` before each commit. CI job in `.github/workflows/ci.yml` runs `pre-commit run --all-files --show-diff-on-failure` on every push so drift is caught even if a developer bypasses the local hook.
- **`backend/alembic/env.py`** — imports every SQLAlchemy model class (User from `app/models/user.py`, ReferenceGenome/Gene/Transcript/Exon/ProteinDomain from `app/reference/models.py`, plus the 5 Phenopackets models already imported). Adds an `include_object` callable that whitelists the non-ORM tables (`publication_metadata`, `variant_annotations`) so autogenerate does not emit `DROP TABLE` for them.
- **`backend/app/phenopackets/routers/aggregations/variant_query_builder.py`** — two raw-SQL CTEs at lines ~369 and ~435 that query `phenopackets p` get `AND p.deleted_at IS NULL` added to the WHERE clause. This closes the leak identified in Wave 5a exit follow-up #2.
- **`backend/app/utils/audit.py`** — the `assert audit_row is not None` at line 95 becomes `raise ValueError(...)` so `PhenopacketService.create/update/soft_delete` can map it to `ServiceDatabaseError` via an explicit `except ValueError` branch added in Task 4.
- **`backend/app/api/auth_endpoints.py`** — the existing flat router at `/api/v2/auth` gets split: a new `users_router = APIRouter(prefix="/users", dependencies=[Depends(require_admin)])` is created and included into the main auth router. The 5 admin user endpoints (create, list, get, update, delete) plus the new unlock endpoint move onto `users_router`; their per-endpoint `Depends(require_admin)` parameters are removed in Task 10 (the last of the three BFLA commits).
- **`backend/app/auth/password.py`** — `CryptContext(schemes=["bcrypt"])` replaced by `pwdlib.PasswordHash.recommended()`, which returns a `PasswordHash` with `Argon2Hasher` (primary) + `BcryptHasher` (fallback verifier). `get_password_hash()` produces Argon2id; `verify_password()` accepts both bcrypt `$2b$...` and Argon2id `$argon2id$...` transparently. A new `verify_and_rehash()` helper is called at login-time to transparently upgrade legacy hashes.
- **`frontend/src/api/transport.js`** — owns BOTH the axios instance AND the `isRefreshing` / `failedRequestsQueue` module-level state. Co-location is non-negotiable per scope doc §5 R5 mitigation 1.
- **`frontend/src/api/session.js`** — owns access/refresh token storage + retrieval (no axios dependency).
- **`frontend/src/api/domain/*.js`** — one file per section marker in the current `api/index.js` (Phenopackets, Aggregations, Publications, Auth, HPO, Clinical, Variants, Reference, Variant Annotation, Search, Admin). Each file imports `apiClient` from `transport.js`.
- **`frontend/src/api/index.js`** — rewritten as a ≤100 LOC re-export aggregator. Preserves the existing `default` export shape (the 70+ named functions listed at lines 922–1009) so no import sites need to change.
- **`frontend/src/composables/useSyncTask.js`** — extracts the polling state machine shared by `startPublicationSync`, `startVariantSync`, and `startGenesSync` in `AdminDashboard.vue`. Returns `{ task, inProgress, start, stop }`. `startReferenceInit` is NOT migrated — it's single-shot with no polling and doesn't fit the abstraction.
- **`frontend/src/views/AdminUsers.vue`** — new top-level view at `/admin/users`. Uses `AppDataTable` in server-side mode. Includes a client-side `_system_migration_` row filter so the placeholder user is never shown in the table.
- **`frontend/src/components/admin/AdminUsersCard.vue`** — lightweight dashboard card that links to `/admin/users` (mounted into `AdminDashboard.vue` so the AdminUsers view is discoverable from the existing dashboard).

---

## Conventions

- **TDD everywhere.** Write the failing test first, watch it fail, write the minimal implementation, watch it pass, commit. No exceptions.
- **One commit per task.** Task N = commit N. If a task requires more than one commit, STOP and split the task. Tasks 8/9/10 are the intentional exception — they form a three-commit behavior-preserving BFLA refactor sequence per scope doc §5 R4 mitigation 1.
- **Exact file paths.** Never "the file that handles X" — always `backend/app/api/auth_endpoints.py:253` with the current line number from `git grep -n` at the time of writing the step.
- **`make check` is a hard pre-commit precondition.** After Task 1 lands (pre-commit hook enforcement), you cannot commit without it passing. Before Task 1 lands, run `cd backend && make check` and `cd frontend && make check` manually before every commit anyway — Wave 5a exit follow-up #10 was the ruff-drift incident from bypassing `make check`, and we're not repeating it.
- **HTTP baselines are law.** Every task ends with a green verify run on `test_http_surface_baseline.py -k verify`. If a task intentionally introduces baseline drift (e.g., a new endpoint), the new baseline is captured in the SAME commit that introduces the endpoint, not as a separate fix-up.
- **Commit message format:** `<type>(<scope>): <description>` per CLAUDE.md Conventional Commits section. HEREDOC for body. `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>` trailer on every commit.
- **Do NOT touch files listed in "Things to NOT touch"** in the session brief (`.codex/`, `.planning/phases/`, untracked review docs).

---

## Task 1: Pre-commit hook enforcement + CI wiring

**Goal:** Close Wave 5a exit follow-up #10 — enforce `make check` as a hard precondition for every commit, so silent ruff/format drift can't accumulate. Adds a `.pre-commit-config.yaml` that runs the backend and frontend linters on staged files, plus a `pre-commit` CI job on every push so developers who forgot to install the hook locally still get caught.

**Why this is commit 1:** It's refactor-only (no behavior change, no test change beyond a new CI job), and it locks in the quality floor for every subsequent commit in this PR. Following the Wave 5a convention "refactor-only commits first".

**Files:**
- Create: `.pre-commit-config.yaml`
- Modify: `.github/workflows/ci.yml` (add `pre-commit` job)

- [ ] **Step 1: Write `.pre-commit-config.yaml`**

```yaml
# .pre-commit-config.yaml — enforces `make check` hygiene on every commit.
#
# Wave 5b Task 1 closes the silent-ruff-drift incident flagged in Wave 5a
# exit note follow-up #10: tasks added new test files and ran only
# `uv run pytest tests/<file>.py` instead of the full `make check`, which
# allowed 6 pydocstyle findings (D103 / D209) to accumulate before they
# were finally cleaned up in commit e69899d.
#
# Install locally:
#   cd ~/development/hnf1b-db.worktrees/chore-wave-5b-user-management
#   uv pip install pre-commit && pre-commit install
#
# CI runs the same checks via `.github/workflows/ci.yml` so no developer
# can bypass by skipping the local install.

# Glob intent: the Wave 5a drift (commits 5, 8 adding test files) landed
# in backend/tests/ AND would have applied to frontend/tests/ under the
# same failure mode. The `files:` regexes below MUST match test-file
# edits, not just src/app edits, otherwise the hook silently lets the
# same class of drift recur.

repos:
  - repo: local
    hooks:
      - id: backend-ruff-check
        name: backend ruff check
        entry: bash -c 'cd backend && uv run ruff check .'
        language: system
        # Intentionally wide: backend/tests/, backend/scripts/,
        # backend/migration/, backend/alembic/ all carry .py files that
        # ruff must still lint. The ruff command itself scopes via its
        # configured ignore list.
        files: ^backend/.*\.py$
        pass_filenames: false

      - id: backend-ruff-format
        name: backend ruff format (check)
        entry: bash -c 'cd backend && uv run ruff format --check .'
        language: system
        files: ^backend/.*\.py$
        pass_filenames: false

      - id: backend-mypy
        name: backend mypy
        entry: bash -c 'cd backend && uv run mypy app/'
        language: system
        # mypy is intentionally narrower — it only typechecks app/
        # because the test suite uses ad-hoc Any shapes that aren't
        # worth stubbing. If mypy ever gains a test-friendly config
        # this regex should widen.
        files: ^backend/app/.*\.py$
        pass_filenames: false

      - id: frontend-eslint
        name: frontend eslint
        entry: bash -c 'cd frontend && npm run lint'
        language: system
        # Wave 5b finding #2: the previous draft scoped this to
        # ^frontend/src/... which meant an edit only touching
        # frontend/tests/unit/foo.spec.js never triggered the hook.
        # Widen to both src/ and tests/ so the drift class closes.
        files: ^frontend/(src|tests)/.*\.(js|vue)$
        pass_filenames: false

      - id: frontend-prettier
        name: frontend prettier (check)
        entry: bash -c 'cd frontend && npx prettier --check src/ tests/'
        language: system
        files: ^frontend/(src|tests)/.*\.(js|vue|css|scss|json)$
        pass_filenames: false
```

**Verify the frontend lint script target coverage (Wave 5b finding #2 sub-point):**

The `frontend-eslint` hook runs `npm run lint`, which executes whatever
`frontend/package.json`'s `"lint"` script is configured to target. If
that script only lints `src/` (e.g., `eslint src/ --ext .js,.vue`), the
hook fires on test edits but finds nothing to complain about in them.
Check the script before committing Task 1:

```bash
grep -A1 '"lint"' frontend/package.json
# Expect something like: "lint": "eslint src/ tests/ --ext .js,.vue,.mjs"
```

If the script only covers `src/`, widen it in the same commit:

```json
"lint": "eslint src/ tests/ --ext .js,.vue,.mjs"
```

Same check for `format` / `format:check`:

```bash
grep -A1 '"format' frontend/package.json
```

The Prettier hook above already calls `prettier --check src/ tests/`
directly, so even if `package.json` has a narrower `format` script,
the hook is authoritative.

- [ ] **Step 2: Verify pre-commit runs green locally**

```bash
# Install pre-commit into the worktree's uv env
cd backend
uv pip install pre-commit
cd ..

# Install the hook
pre-commit install --config .pre-commit-config.yaml

# Dry-run against all files
pre-commit run --all-files --config .pre-commit-config.yaml
```

Expected: every hook reports "Passed". If `backend-mypy` or `frontend-eslint` fails, the entry state is dirty — fix the underlying issue BEFORE adding the hook. A failing hook on commit 1 would mask whether Wave 5b itself introduces drift.

- [ ] **Step 3: Add the CI job**

Read the current `.github/workflows/ci.yml`:

```bash
cat .github/workflows/ci.yml | head -60
```

Find the top-level `jobs:` block. Add a new job (mirroring existing job syntax — use `ubuntu-latest`, the same Python version used by the backend job, and the same `uv` action already referenced):

```yaml
  pre-commit:
    name: pre-commit hygiene gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - name: Install backend deps
        run: cd backend && uv sync --group test
      - name: Install frontend deps
        run: cd frontend && npm ci
      - name: Install pre-commit
        run: cd backend && uv pip install pre-commit
      - name: Run pre-commit on all files
        run: |
          cd backend && source .venv/bin/activate && cd ..
          pre-commit run --all-files --show-diff-on-failure
```

Match the exact Python / uv / Node setup-action versions used elsewhere in the file — do NOT bump them in this commit.

- [ ] **Step 4: Verify CI job syntax**

```bash
# If actionlint is available:
actionlint .github/workflows/ci.yml 2>&1 || echo "actionlint not installed — skip"

# Otherwise: `yq . .github/workflows/ci.yml` or a YAML-aware editor should parse clean.
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
# Expect: no output (no parse error)
```

- [ ] **Step 5: Run full backend + frontend test suites to confirm entry-state unchanged**

```bash
cd backend && uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1001 passed, 10 skipped, 3 xfailed
cd ..

cd frontend && npm run test -- --run 2>&1 | tail -10
# Expect: 269 passed + 1 xfailed
cd ..

cd backend && uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 9 passed
cd ..
```

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml .github/workflows/ci.yml
git status --short
# Expect: A  .pre-commit-config.yaml
#         M  .github/workflows/ci.yml

git commit -m "$(cat <<'EOF'
chore(ci): enforce make check hygiene via pre-commit hook + CI gate

Closes Wave 5a exit note follow-up #10 — the silent ruff-drift incident
where Tasks 5 and 8 added new test files without running full make check
and accumulated 6 pydocstyle findings (D103 x5 + D209 x1) that had to
be cleaned up post-hoc in commit e69899d.

Adds .pre-commit-config.yaml running:
  - backend ruff check + format --check
  - backend mypy on app/
  - frontend eslint
  - frontend prettier --check

CI workflow gains a pre-commit job running the same hooks on every push
so a developer who forgot to `pre-commit install` locally still gets
caught at PR time.

No behavior change, no test change. This commit locks in the quality
floor for every subsequent Wave 5b commit.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Fix alembic autogenerate drift

**Goal:** Close Wave 5a exit follow-up #1 — `backend/alembic/env.py` imports only the 5 phenopackets-package ORM models (Phenopacket, Family, Cohort, Resource, PhenopacketAudit), so `alembic revision --autogenerate` produces spurious `DROP TABLE` operations for every unimported model (users, reference_genomes, genes, transcripts, exons, protein_domains) and every raw-SQL-managed table (publication_metadata, variant_annotations). Both Wave 5a schema migrations had to be hand-written because autogenerate was unusable. Wave 5c (identity lifecycle) needs clean autogenerate for the `credential_tokens` migration.

**Fix strategy:**
1. Import every ORM model class in `env.py` so `Base.metadata` is complete
2. Add an `include_object` callable that whitelists the non-ORM tables (`publication_metadata`, `variant_annotations`) so autogenerate does not emit `DROP TABLE` for them
3. Add a test that runs `alembic check` (or a programmatic equivalent via `alembic.autogenerate.compare_metadata`) and asserts zero diff against the live dev DB

**Files:**
- Modify: `backend/alembic/env.py:20-49` (extend import block + add `include_object` + wire it into `context.configure()`)
- Create: `backend/tests/test_alembic_env_autogenerate.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_alembic_env_autogenerate.py`:

```python
"""Wave 5b: alembic autogenerate must produce a clean diff against the dev DB.

Wave 5a exit follow-up #1: env.py imported only 5 of the ~11 ORM models,
so autogenerate wanted to DROP TABLE for users, reference_genomes, genes,
transcripts, exons, protein_domains + the two raw-SQL tables
(publication_metadata, variant_annotations). Both Wave 5a schema
migrations had to be hand-written because of this drift.

This test programmatically runs alembic's compare_metadata against the
live dev DB and asserts the diff is empty. If a developer forgets to
import a new ORM model, this test fails loudly.
"""
from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.core.config import settings
from app.database import Base


# Import env.py's import block indirectly by importing the models it
# should import. If env.py drifts, this test still catches it because
# compare_metadata reads Base.metadata, which only contains what's
# actually imported somewhere in the process.
import app.models.user  # noqa: F401
import app.phenopackets.models  # noqa: F401
import app.reference.models  # noqa: F401


@pytest.mark.integration
def test_alembic_autogenerate_produces_no_spurious_drops():
    """Diff between Base.metadata and the live dev DB must contain no drops."""
    # Convert asyncpg URL to sync psycopg2 URL for alembic's sync engine
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    with engine.connect() as connection:
        # Wave 5a follow-up #1 fix: include_object must filter raw-SQL tables
        def include_object(obj, name, type_, reflected, compare_to):
            if type_ == "table" and name in {"publication_metadata", "variant_annotations", "alembic_version"}:
                return False
            return True

        mc = MigrationContext.configure(
            connection,
            opts={"include_object": include_object},
        )
        diff = compare_metadata(mc, Base.metadata)

    # Any entry in the diff that is a DROP operation signals metadata drift.
    drop_ops = [op for op in diff if isinstance(op, tuple) and op[0].startswith("remove_")]
    assert drop_ops == [], (
        f"alembic autogenerate detected spurious drops (env.py metadata drift): "
        f"{[op[0] + ':' + (op[1].name if hasattr(op[1], 'name') else str(op[1])) for op in drop_ops]}"
    )
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_alembic_env_autogenerate.py -v
```

Expected: FAIL with `drop_ops != []`, listing `users`, `reference_genomes`, `genes`, `transcripts`, `exons`, `protein_domains`, and possibly `publication_metadata` / `variant_annotations` (if the `include_object` isn't yet applied in env.py itself — but the test runs its own `MigrationContext`, so those two tables should already be filtered inside the test fixture, leaving only the genuine ORM drifts).

- [ ] **Step 3: Update `backend/alembic/env.py`**

Edit `backend/alembic/env.py`. Replace the existing import block at lines 20–49 with:

```python
# Import your models' metadata here for 'autogenerate' support
# Wave 5b Task 2: import EVERY SQLAlchemy ORM model class so Base.metadata
# is complete. Missing imports cause autogenerate to emit spurious
# DROP TABLE operations (Wave 5a exit follow-up #1).
try:
    from app.database import Base

    # Phenopackets package models (5 — already present pre-Wave-5b)
    from app.phenopackets.models import (
        Cohort as Cohort,
        Family as Family,
        Phenopacket as Phenopacket,
        PhenopacketAudit as PhenopacketAudit,
        Resource as Resource,
    )

    # User model (1)
    from app.models.user import User as User

    # Reference package models (5)
    from app.reference.models import (
        Exon as Exon,
        Gene as Gene,
        ProteinDomain as ProteinDomain,
        ReferenceGenome as ReferenceGenome,
        Transcript as Transcript,
    )

    target_metadata = Base.metadata
except ImportError:
    # During initial setup, models might not exist yet
    from app.database import Base

    target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Filter out non-ORM-managed tables so autogenerate ignores them.

    Wave 5b Task 2: publication_metadata and variant_annotations are
    alembic-managed via raw-SQL migrations (5f9c34e4e444, 9d4e5f6g7h8i)
    but are NOT exposed as SQLAlchemy ORM models. Without this filter,
    `alembic revision --autogenerate` emits DROP TABLE for them.
    alembic_version is alembic's own bookkeeping table.
    """
    if type_ == "table" and name in {
        "publication_metadata",
        "variant_annotations",
        "alembic_version",
    }:
        return False
    return True
```

Then find the `context.configure(...)` call(s) near the bottom of `env.py` (both the `run_migrations_offline()` and `run_migrations_online()` paths configure the context) and add `include_object=include_object` to each `context.configure()` kwargs block. Read the existing calls first to verify syntax:

```bash
grep -n "context.configure" backend/alembic/env.py
```

For each `context.configure(...)` call, add `include_object=include_object,` alongside the existing `target_metadata=target_metadata` kwarg.

- [ ] **Step 4: Run the test — expect pass**

```bash
uv run pytest tests/test_alembic_env_autogenerate.py -v
```

Expected: PASS. If the test still fails with unrecognized drops, it means either (a) there's an ORM model in a location this plan missed (search with `grep -rn __tablename__ backend/app/`) or (b) there's another raw-SQL-managed table that needs to join the `include_object` whitelist.

- [ ] **Step 5: Verify autogenerate is now clean against live DB**

```bash
uv run alembic revision --autogenerate -m "test-only — verify clean diff" --sql 2>&1 | tail -20
```

Expected: the emitted migration body contains no `op.drop_table(...)` lines and no `op.drop_column(...)` lines. If it does, the test passed but env.py drift persists — DO NOT commit; investigate.

**Important:** Do NOT commit the generated revision file. It was a dry run. Delete it:

```bash
rm backend/alembic/versions/*test_only*.py 2>/dev/null || true
ls backend/alembic/versions/ | grep test_only
# Expect: empty
```

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1002 passed (1001 + 1 new test), 10 skipped, 3 xfailed
```

- [ ] **Step 7: Verify `make check` still passes**

```bash
cd backend && make check 2>&1 | tail -10
# Expect: ruff + mypy + pytest all green
cd ..
```

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/env.py backend/tests/test_alembic_env_autogenerate.py
git commit -m "$(cat <<'EOF'
fix(db): import all ORM models in alembic env.py + filter raw-SQL tables

Closes Wave 5a exit note follow-up #1. Before this commit, alembic/env.py
imported only 5 of the ~11 SQLAlchemy ORM model classes, so
`alembic revision --autogenerate` produced a spurious DROP TABLE
migration for every unimported model (users, reference_genomes, genes,
transcripts, exons, protein_domains). Both Wave 5a schema migrations
(3411179 is_fixture_user and 65d226b fk_audit) had to be hand-written
because autogenerate was unusable.

Also filters out the two raw-SQL-managed tables (publication_metadata,
variant_annotations) via an include_object callable, because they exist
in the live DB but are not represented as ORM models.

New test runs alembic's compare_metadata against the live dev DB and
asserts zero spurious drops. Future ORM-model additions that forget
to update env.py will fail this test loudly.

Unblocks Wave 5c `credential_tokens` migration (will want autogenerate)
and unblocks any future schema work that depends on a clean diff.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Fix variant_query_builder raw-SQL soft-delete leak

**Goal:** Close Wave 5a exit follow-up #2. `backend/app/phenopackets/routers/aggregations/variant_query_builder.py` has two raw-SQL CTEs at lines ~369 and ~435 that query `phenopackets p` directly without an `AND p.deleted_at IS NULL` filter. The Wave 5a global soft-delete filter (commit `f9cb05d`) protects only ORM-executed queries; raw SQL goes around it. The `/api/v2/phenopackets/aggregate/all-variants` endpoint currently leaks variant counts that include soft-deleted phenopackets. Severity is low (soft-deletes are rare in practice), but the fix is trivial and the leak undermines the "global soft-delete filter" invariant.

**Files:**
- Create: `backend/tests/test_variant_query_soft_delete.py`
- Modify: `backend/app/phenopackets/routers/aggregations/variant_query_builder.py:374-376, 440-443` (add `AND p.deleted_at IS NULL` to both CTE `WHERE` clauses)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_variant_query_soft_delete.py`:

```python
"""Wave 5b: variant_query_builder raw-SQL CTEs must honour soft-delete.

Wave 5a exit follow-up #2: two CTEs in variant_query_builder.py query
`phenopackets p` directly and bypass the global soft-delete filter,
leaking variant counts from soft-deleted rows through
/api/v2/phenopackets/aggregate/all-variants.

This test creates a phenopacket with a variant, fetches the all-variants
aggregation, soft-deletes the phenopacket, fetches again, and asserts
the variant count dropped.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_soft_deleted_phenopacket_hidden_from_all_variants(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Soft-deleting a phenopacket removes it from /aggregate/all-variants."""
    # Create a phenopacket with an interpretations.variationDescriptor block
    # that the variant_query_builder CTE will pick up.
    create_payload = {
        "phenopacket": {
            "id": "wave5b-softdel-variant-001",
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "interpretations": [
                {
                    "id": "interp-1",
                    "progressStatus": "SOLVED",
                    "diagnosis": {
                        "disease": {"id": "MONDO:0000001", "label": "test"},
                        "genomicInterpretations": [
                            {
                                "subjectOrBiosampleId": "s",
                                "interpretationStatus": "CAUSATIVE",
                                "variantInterpretation": {
                                    "acmgPathogenicityClassification": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "wave5b-softdel-var-001",
                                        "label": "test variant",
                                        "geneContext": {
                                            "valueId": "HGNC:11621",
                                            "symbol": "HNF1B",
                                        },
                                        "expressions": [
                                            {"syntax": "hgvs.c", "value": "c.100A>G"},
                                        ],
                                        "vcfRecord": {
                                            "chrom": "17",
                                            "pos": "36000000",
                                            "ref": "A",
                                            "alt": "G",
                                        },
                                    },
                                },
                            }
                        ],
                    },
                }
            ],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pytest",
            },
        }
    }
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    # Capture baseline — the new variant should appear at least once
    before = await async_client.get(
        "/api/v2/phenopackets/aggregate/all-variants",
        params={"query": "wave5b-softdel-var-001"},
        headers=admin_headers,
    )
    assert before.status_code == 200
    before_ids = {v.get("variant_id") for v in (before.json().get("data") or [])}
    assert "wave5b-softdel-var-001" in before_ids, "setup: variant should exist"

    # Soft delete the phenopacket
    del_resp = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/wave5b-softdel-variant-001",
        json={"change_reason": "wave5b soft-delete leak test"},
        headers=admin_headers,
    )
    assert del_resp.status_code == 200

    # After delete, the variant should no longer appear
    after = await async_client.get(
        "/api/v2/phenopackets/aggregate/all-variants",
        params={"query": "wave5b-softdel-var-001"},
        headers=admin_headers,
    )
    assert after.status_code == 200
    after_ids = {v.get("variant_id") for v in (after.json().get("data") or [])}
    assert "wave5b-softdel-var-001" not in after_ids, (
        "Soft-deleted phenopacket's variant is still leaking through "
        "/aggregate/all-variants — variant_query_builder CTEs need "
        "AND p.deleted_at IS NULL"
    )
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_variant_query_soft_delete.py -v
```

Expected: FAIL on the second assertion — the deleted variant is still returned by the aggregation.

- [ ] **Step 3: Patch the two CTEs**

Edit `backend/app/phenopackets/routers/aggregations/variant_query_builder.py`.

Locate the first CTE's `WHERE` clause (around line 374):

```python
            WHERE
                vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
```

Change to:

```python
            WHERE
                p.deleted_at IS NULL
                AND vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
```

Locate the second CTE's `WHERE` clause (around line 440):

```python
            WHERE
                vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
                {where_sql}
```

Change to:

```python
            WHERE
                p.deleted_at IS NULL
                AND vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
                {where_sql}
```

**Verify with git grep:**

```bash
git grep -n "p.deleted_at IS NULL" backend/app/phenopackets/routers/aggregations/variant_query_builder.py
```

Expected: two hits, both inside the CTE body.

- [ ] **Step 4: Run the test — expect pass**

```bash
uv run pytest tests/test_variant_query_soft_delete.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1003 passed, 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 9 passed
```

If any baseline drifts (e.g., the `phenopackets_compare_variant_types` or a variant-aggregation baseline changes), it means the pre-existing baseline captured a soft-deleted variant count. Investigate — if the only drift is the fixed leak, the new count is correct; capture the new baseline in THIS commit.

- [ ] **Step 6: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/variant_query_builder.py backend/tests/test_variant_query_soft_delete.py
git commit -m "$(cat <<'EOF'
fix(backend): plug soft-delete leak in variant_query_builder raw-SQL CTEs

Closes Wave 5a exit note follow-up #2. Two raw-SQL CTEs in
variant_query_builder.py query `phenopackets p` without
`AND p.deleted_at IS NULL`, so soft-deleted phenopackets' variants
still show up in /api/v2/phenopackets/aggregate/all-variants.

The Wave 5a global soft-delete filter (f9cb05d) only protects
ORM-executed queries; raw SQL goes around it. This commit adds the
missing filter to both CTEs.

Regression test creates a phenopacket with a variant, fetches the
aggregation, soft-deletes the phenopacket, and asserts the variant
is gone from the aggregation response.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Replace audit.py assert with ValueError + service handler

**Goal:** Close Wave 5a exit follow-up #3. `backend/app/utils/audit.py:95` uses `assert audit_row is not None, "Failed to create audit entry"` to catch the case where the `INSERT ... RETURNING id` + `SELECT * WHERE id = :audit_id` round-trip returns no row. An `AssertionError` is not in the `except (IntegrityError, SQLAlchemyError)` chain of `PhenopacketService.create/update/soft_delete`, so it propagates raw to the client as a 500 with a stack trace. Replace with an explicit `ValueError`, add a `ValueError` handler to the service, and add a test that forces the scenario via a monkeypatched `fetchone`.

**Files:**
- Create: `backend/tests/test_audit_entry_error_handling.py`
- Modify: `backend/app/utils/audit.py:95` (replace `assert` with `raise ValueError`)
- Modify: `backend/app/phenopackets/services/phenopacket_service.py` (add `except ValueError` branch in `create`, `update`, `soft_delete`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_audit_entry_error_handling.py`:

```python
"""Wave 5b: audit.create_audit_entry error path maps cleanly to 500, not AssertionError.

Wave 5a exit follow-up #3: audit.py has `assert audit_row is not None`
that fires an AssertionError if the RETURNING round-trip fails. Python's
assert is not caught by PhenopacketService's (IntegrityError,
SQLAlchemyError) except chain, so the raw AssertionError propagates to
the client as a 500 with stack trace.

This test monkeypatches the second `db.execute` call in create_audit_entry
to return a Mock whose fetchone() returns None. Before the fix, this
raises AssertionError. After the fix, it raises ValueError which the
service maps to ServiceDatabaseError → 500 with a clean detail message.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.audit import create_audit_entry


@pytest.mark.asyncio
async def test_create_audit_entry_raises_value_error_when_fetchone_none(monkeypatch):
    """When the post-INSERT SELECT returns None, raise ValueError not AssertionError."""
    mock_session = MagicMock(spec=AsyncSession)

    # First execute call (the INSERT) returns an object whose scalar_one
    # returns a UUID. Second execute call (the SELECT) returns an object
    # whose fetchone returns None — this is the edge case.
    first_result = MagicMock()
    first_result.scalar_one.return_value = "00000000-0000-0000-0000-000000000000"

    second_result = MagicMock()
    second_result.fetchone.return_value = None

    execute_mock = AsyncMock(side_effect=[first_result, second_result])
    mock_session.execute = execute_mock

    with pytest.raises(ValueError, match="audit entry"):
        await create_audit_entry(
            db=mock_session,
            phenopacket_id="test-err-001",
            action="CREATE",
            old_value=None,
            new_value={"id": "test-err-001"},
            changed_by_id=1,
            change_reason="test",
        )
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_audit_entry_error_handling.py -v
```

Expected: FAIL — the current code raises `AssertionError`, not `ValueError`. Pytest's `pytest.raises(ValueError)` will not match.

- [ ] **Step 3: Replace the assert in `backend/app/utils/audit.py`**

Edit `backend/app/utils/audit.py`. At line 95:

Replace:

```python
    assert audit_row is not None, "Failed to create audit entry"
```

With:

```python
    if audit_row is None:
        raise ValueError(
            f"audit entry fetch returned None after INSERT "
            f"(phenopacket_id={phenopacket_id!r}, action={action!r})"
        )
```

- [ ] **Step 4: Add `except ValueError` to `PhenopacketService`**

Edit `backend/app/phenopackets/services/phenopacket_service.py`. There are three methods that call `create_audit_entry` — `create()`, `update()`, and `soft_delete()`. Each currently has a try/except block with `except (IntegrityError, SQLAlchemyError)` near lines 169–184 (create), 252–256 (update), and 323–327 (soft_delete). For each block, add a `ValueError` branch BEFORE the `SQLAlchemyError` catch (so `ValueError` is matched first and the more-general `SQLAlchemyError` doesn't swallow it):

```python
        except IntegrityError as exc:
            await self._repo.rollback()
            # ... existing integrity handling ...
            raise ServiceDatabaseError(f"Database error: {exc}") from exc
        except ValueError as exc:
            # Wave 5b Task 4: audit.create_audit_entry raises ValueError
            # when its post-INSERT SELECT returns None. Map to
            # ServiceDatabaseError so the router returns 500 cleanly
            # instead of leaking AssertionError through the test client.
            await self._repo.rollback()
            raise ServiceDatabaseError(f"Audit entry error: {exc}") from exc
        except SQLAlchemyError as exc:
            await self._repo.rollback()
            raise ServiceDatabaseError(f"Database error: {exc}") from exc
```

Apply the same pattern in all three methods. Read each method's current exception-chain shape FIRST with `grep -n "except" backend/app/phenopackets/services/phenopacket_service.py` so you don't accidentally add a branch inside the wrong try/except.

**Note:** `update()` and `soft_delete()` in the current code have `except SQLAlchemyError` but not `except IntegrityError`. Don't invent an IntegrityError branch for them — just add the `ValueError` branch before the `SQLAlchemyError` branch.

- [ ] **Step 5: Run the test — expect pass**

```bash
uv run pytest tests/test_audit_entry_error_handling.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the full suite — the existing audit-on-create / update / delete tests should still pass**

```bash
uv run pytest tests/test_phenopackets_audit_on_create.py tests/test_phenopackets_delete_revision.py tests/test_audit_actor_fk.py -v 2>&1 | tail -15
# Expect: all green

uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1004 passed, 10 skipped, 3 xfailed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/utils/audit.py backend/app/phenopackets/services/phenopacket_service.py backend/tests/test_audit_entry_error_handling.py
git commit -m "$(cat <<'EOF'
fix(backend): raise ValueError from audit.py instead of assert + handle in service

Closes Wave 5a exit note follow-up #3. create_audit_entry at
backend/app/utils/audit.py:95 used `assert audit_row is not None` to
catch the case where the post-INSERT SELECT returns None. Python's
assert isn't matched by the (IntegrityError, SQLAlchemyError) except
chain in PhenopacketService.create/update/soft_delete, so an
AssertionError would propagate raw to clients instead of becoming a
clean 500 ServiceDatabaseError.

Replace the assert with `raise ValueError(...)` and add an explicit
`except ValueError` branch (before the SQLAlchemyError branch so it
matches first) in all three service methods that call create_audit_entry.

Test uses unittest.mock to force the fetchone-returns-None scenario
and asserts ValueError is raised, not AssertionError.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Fix stale wave4_http_baselines reference in admin/endpoints.py docstring

**Goal:** Close Wave 5a exit follow-up #8. The Wave 5a baseline-rename commit (`c93bd85`) updated the docstring in `test_http_surface_baseline.py` but missed the docstring reference in `backend/app/api/admin/endpoints.py:12`. This is a one-line fix that prevents `grep -rn wave4_http_baselines backend/` from flagging a phantom hit forever.

**Files:**
- Modify: `backend/app/api/admin/endpoints.py:12` (one-line docstring update)

- [ ] **Step 1: Verify the stale reference exists**

```bash
grep -n "wave4_http_baselines" backend/app/api/admin/endpoints.py
```

Expected: one hit at line 12 — `tests/fixtures/wave4_http_baselines/admin_status.json`.

If the line number differs, use the line from the grep output in Step 2 below.

- [ ] **Step 2: Update the docstring**

Edit `backend/app/api/admin/endpoints.py`. Find the line:

```python
``tests/fixtures/wave4_http_baselines/admin_status.json`` locks
```

Replace `wave4_http_baselines` with `http_baselines`. Also update the reference to Wave 4 → Wave 5a in the same sentence to reflect the current state:

```python
    single ``APIRouter`` mounted at ``/api/v2/admin`` and includes every
    domain-specific sub-router (status, sync_publications, sync_variants,
    sync_reference). Each sub-router owns its own HTTP logic — this file
    is pure composition.

    The HTTP surface is byte-identical to the old flat
    ``app/api/admin_endpoints.py``: routes, response shapes, query params,
    and status codes are all preserved. The HTTP surface baseline in
    ``tests/fixtures/http_baselines/admin_status.json`` locks
    this in automatically.
```

- [ ] **Step 3: Verify no remaining stale references in production code**

```bash
git grep -n "wave4_http_baselines" backend/app/ frontend/src/
```

Expected: empty. If any other production file still has the stale reference, fix it in THIS commit.

- [ ] **Step 4: Run the full suite — no behavior change expected**

```bash
cd backend && uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1004 passed, 10 skipped, 3 xfailed (unchanged from Task 4)
cd ..
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin/endpoints.py
git commit -m "$(cat <<'EOF'
docs(backend): update stale wave4_http_baselines reference in admin endpoints

Closes Wave 5a exit note follow-up #8. The Wave 5a baseline-rename
commit (c93bd85) updated the docstring in
tests/test_http_surface_baseline.py but missed the reference in
backend/app/api/admin/endpoints.py:12, leaving a phantom hit in
`grep -rn wave4_http_baselines backend/`.

One-line fix. No behavior change.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add PATCH /auth/users/{id}/unlock endpoint (B2)

**Goal:** Implement scope-doc row B2 — a new admin-only endpoint that clears `failed_login_attempts` and `locked_until` for a locked user. Includes the unlock method on `UserRepository`, the endpoint on `auth_endpoints.py`, and a new HTTP baseline fixture. The endpoint goes under the current (still per-endpoint-guarded) admin pattern; Task 8–10 migrate it to router-level BFLA along with all the other admin user endpoints.

**Files:**
- Modify: `backend/app/repositories/user_repository.py` (add `unlock()` method)
- Modify: `backend/app/api/auth_endpoints.py` (new endpoint after `delete_user`)
- Create: `backend/tests/test_auth_unlock_endpoint.py`
- Create: `backend/tests/fixtures/http_baselines/auth_users_unlock.json` (captured by the HTTP baseline capture path)
- Modify: `backend/tests/test_http_surface_baseline.py` (add the fixture tuple)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_unlock_endpoint.py`:

```python
"""Wave 5b Task 6: PATCH /api/v2/auth/users/{id}/unlock clears lockout state."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_unlock_clears_failed_attempts_and_locked_until(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Seed a locked user, hit the unlock endpoint, verify fields reset."""
    # Seed a locked curator
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, locked_until, created_at
            )
            VALUES (
                'locked-curator@hnf1b-db.local',
                'wave5b-locked-curator',
                '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
                'curator',
                true,
                true,
                false,
                5,
                :locked_until,
                NOW()
            )
            ON CONFLICT (username) DO UPDATE SET
                failed_login_attempts = 5,
                locked_until = :locked_until
            RETURNING id
        """),
        {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=15)},
    )
    await db_session.commit()

    # Look up the user id
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = 'wave5b-locked-curator'")
    )
    user_id = result.scalar_one()

    # Hit the unlock endpoint
    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    # Verify the row was reset
    row = (await db_session.execute(
        text("""
            SELECT failed_login_attempts, locked_until
            FROM users
            WHERE username = 'wave5b-locked-curator'
        """)
    )).fetchone()
    assert row is not None
    assert row.failed_login_attempts == 0
    assert row.locked_until is None


@pytest.mark.asyncio
async def test_unlock_non_admin_forbidden(
    async_client: AsyncClient,
    curator_headers: dict,
):
    """A curator cannot unlock other users — 403."""
    response = await async_client.patch(
        "/api/v2/auth/users/1/unlock",
        headers=curator_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unlock_missing_user_404(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Unlocking a nonexistent user returns 404."""
    response = await async_client.patch(
        "/api/v2/auth/users/999999/unlock",
        headers=admin_headers,
    )
    assert response.status_code == 404
```

**Note:** `curator_headers` may not exist as a conftest fixture yet. Check first:

```bash
grep -n "curator_headers\|admin_headers" backend/tests/conftest.py backend/tests/*.py 2>&1 | head -20
```

If `curator_headers` does not exist, add it to `backend/tests/conftest.py` alongside the existing `admin_headers` fixture. Use the same pattern — mint a JWT for a seeded curator user via `create_access_token`. Include this conftest addition in THIS commit.

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_auth_unlock_endpoint.py -v
```

Expected: all three tests FAIL with 404 (endpoint doesn't exist).

- [ ] **Step 3: Add `unlock()` to `UserRepository`**

Edit `backend/app/repositories/user_repository.py`. Add a new method after `update_refresh_token`:

```python
    async def unlock(self, user: User) -> User:
        """Clear failed login attempts and lockout for a user.

        Wave 5b Task 6: called by the admin PATCH /auth/users/{id}/unlock
        endpoint to rescue a user who tripped the lockout (5 failed
        attempts → 15-minute lock per settings.MAX_LOGIN_ATTEMPTS /
        ACCOUNT_LOCKOUT_MINUTES).
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

- [ ] **Step 4: Add the endpoint to `auth_endpoints.py`**

Edit `backend/app/api/auth_endpoints.py`. After the `delete_user` function (ends around line 471), add:

```python
@router.patch("/users/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Unlock a user account (admin only).

    Clears ``failed_login_attempts`` and ``locked_until`` so the user
    can log in again without waiting for the lockout window to expire.

    **Returns:**
    - 200: User unlocked successfully
    - 403: Not admin
    - 404: User not found
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    unlocked = await repo.unlock(user)

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_UNLOCKED",
        details=f"Admin '{current_user.username}' unlocked user '{user.username}'",
    )

    return UserResponse(
        id=unlocked.id,
        username=unlocked.username,
        email=unlocked.email,
        full_name=unlocked.full_name,
        role=unlocked.role,
        permissions=unlocked.get_permissions(),
        is_active=unlocked.is_active,
        is_verified=unlocked.is_verified,
        last_login=unlocked.last_login,
        created_at=unlocked.created_at,
        updated_at=unlocked.updated_at,
    )
```

Note the per-endpoint `Depends(require_admin)` is intentional for now — Task 8/9/10 migrate ALL `/users/*` endpoints (including this one) to a router-level guard in one coordinated three-commit sequence.

- [ ] **Step 5: Run the test — expect pass**

```bash
uv run pytest tests/test_auth_unlock_endpoint.py -v
```

Expected: all three tests PASS.

- [ ] **Step 6: Capture a new HTTP surface baseline for unlock**

**Harness contract reminder (Wave 5b finding #3):** `AFFECTED_ENDPOINTS` is a list of **6-tuples** shaped `(name, auth, method, path, query_params, body)` — there is NO `path_params` slot. The dispatcher is `_call(client, auth_headers_map, spec)` (NOT `_build_request`) defined at `backend/tests/test_http_surface_baseline.py:195`. The generic parametrize loop works only for endpoints with a fully-resolved URL.

Templated URLs that need a freshly-seeded user id per-run do NOT belong in `AFFECTED_ENDPOINTS`. They live in their own dedicated `test_capture_*` / `test_verify_*` function pair that seeds the prerequisite row via `db_session`, mirroring the existing `test_capture_dev_login_as_baseline` / `test_verify_dev_login_as_baseline` pattern at `backend/tests/test_http_surface_baseline.py:309` onward.

Add the unlock baseline as a dedicated test pair (NOT an `AFFECTED_ENDPOINTS` entry).

First, read the dev-auth baseline pair end-to-end so you understand the template:

```bash
grep -n "test_capture_dev_login_as_baseline\|test_verify_dev_login_as_baseline\|_seed_dev_fixture_admin" backend/tests/test_http_surface_baseline.py
```

Then append a new section to the file, right after the dev-auth baseline block:

```python
# ---------------------------------------------------------------------------
# Wave 5b auth/users/{id}/unlock baseline
# ---------------------------------------------------------------------------
#
# Wave 5b Task 6 introduces PATCH /api/v2/auth/users/{user_id}/unlock.
# The endpoint needs a seeded target user (with failed_login_attempts and
# locked_until populated) before the capture, so it cannot use the generic
# AFFECTED_ENDPOINTS parametrize loop — templated URLs don't compose with
# the 6-tuple `(name, auth, method, path, params, body)` shape. Instead,
# this baseline follows the same structure as `test_capture_dev_login_as_baseline`.

_UNLOCK_BASELINE_NAME = "auth_users_unlock"


async def _seed_locked_target_user(db_session) -> int:
    """Insert a locked curator and return its id for the unlock baseline."""
    from datetime import datetime, timedelta, timezone

    from app.auth.password import get_password_hash
    from app.models.user import User

    locked = User(
        username="wave5b-baseline-locked",
        email="wave5b-baseline-locked@hnf1b-db.local",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        full_name="Baseline Locked Curator",
        role="curator",
        is_active=True,
        is_verified=True,
        is_fixture_user=False,
        failed_login_attempts=5,
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add(locked)
    await db_session.commit()
    await db_session.refresh(locked)
    return locked.id


@pytest.mark.asyncio
async def test_capture_auth_users_unlock_baseline(
    async_client, admin_headers, db_session
):
    """Capture the unlock-response shape. Opt-in via WAVE4_CAPTURE_BASELINE=1."""
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    user_id = await _seed_locked_target_user(db_session)

    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock", headers=admin_headers
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{_UNLOCK_BASELINE_NAME}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
async def test_verify_auth_users_unlock_baseline(
    async_client, admin_headers, db_session
):
    """Verify the unlock response against the captured baseline."""
    baseline_path = BASELINE_DIR / f"{_UNLOCK_BASELINE_NAME}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {_UNLOCK_BASELINE_NAME}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    user_id = await _seed_locked_target_user(db_session)

    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock", headers=admin_headers
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    assert capture["status_code"] == baseline["status_code"], (
        f"{_UNLOCK_BASELINE_NAME}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], (
        f"{_UNLOCK_BASELINE_NAME}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{_UNLOCK_BASELINE_NAME}: normalised response body changed"
    )
```

**Volatile-key mask check:** `_VOLATILE_KEYS` at line 130 already masks `id`, `created_at`, `updated_at`, `last_login`, etc. The unlock response is a `UserResponse` body — every timestamp + id is covered. No additions to `_VOLATILE_KEYS` are needed.

**Capture the baseline:**

```bash
WAVE4_CAPTURE_BASELINE=1 uv run pytest tests/test_http_surface_baseline.py::test_capture_auth_users_unlock_baseline -v
```

Expected output creates `backend/tests/fixtures/http_baselines/auth_users_unlock.json`. Open the file and spot-check: `status_code: 200`, `id` and timestamp fields are `"<normalized>"`, `username: "wave5b-baseline-locked"` is visible.

- [ ] **Step 7: Run the verify step for the new baseline**

```bash
uv run pytest tests/test_http_surface_baseline.py::test_verify_auth_users_unlock_baseline -v
```

Expected: PASS.

- [ ] **Step 8: Run the full suite + all baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1007 passed (1004 + 3 new unlock tests), 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -10
# Expect: 10 passed (9 existing + 1 new)
```

- [ ] **Step 9: Run `make check`**

```bash
make check 2>&1 | tail -10
# Expect: ruff + mypy + pytest green
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/repositories/user_repository.py backend/app/api/auth_endpoints.py backend/tests/test_auth_unlock_endpoint.py backend/tests/test_http_surface_baseline.py backend/tests/fixtures/http_baselines/auth_users_unlock.json backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
feat(api): add PATCH /auth/users/{id}/unlock endpoint + baseline

Implements Wave 5 scope doc row B2. UserRepository gains an unlock()
method that clears failed_login_attempts and locked_until. The
PATCH /api/v2/auth/users/{user_id}/unlock endpoint (admin-only)
calls it, audit-logs the action, and returns the updated UserResponse.

Tests cover: happy path clearing a locked user, 403 for non-admins,
404 for unknown users. HTTP baseline fixture captured for the new
endpoint with timestamp masking.

Endpoint retains its per-endpoint Depends(require_admin) guard for
now — Tasks 8/9/10 migrate every /auth/users/* endpoint (including
this one) to a router-level BFLA guard in a coordinated three-commit
behavior-preserving sequence.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: BOPLA — rename UserUpdate → UserUpdateAdmin + add UserUpdatePublic

**Goal:** Close scope-doc row F-top-1 (BOPLA sweep). The current `UserUpdate` schema at `backend/app/schemas/auth.py:62` allows `email`, `password`, `full_name`, `role`, and `is_active`. It's used ONLY by the admin `update_user` endpoint today, so it's safe — but the name is misleading. Any future code that reuses `UserUpdate` for a public path (`/auth/me` PATCH, profile settings, etc.) would silently grant privilege-escalation attackers a way to set their own role to `admin`.

**Strategy:**
1. Rename `UserUpdate` → `UserUpdateAdmin` (semantics unchanged, name reflects intent)
2. Add a new `UserUpdatePublic` schema that EXCLUDES `role` and `is_active` — this is the schema any future public profile endpoint MUST use
3. Add a test that verifies `UserUpdatePublic.model_fields` does not contain the dangerous fields, and that no public endpoint accepts privilege-escalation fields today

**Files:**
- Modify: `backend/app/schemas/auth.py` (rename class + add new schema)
- Modify: `backend/app/api/auth_endpoints.py` (update import + one call site in `change_password`)
- Create: `backend/tests/test_auth_bopla_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_bopla_schemas.py`:

```python
"""Wave 5b Task 7: BOPLA — UserUpdatePublic must exclude privilege-escalation fields.

Closes scope doc row F-top-1. The original UserUpdate schema allowed
role and is_active as optional fields, which was safe in practice
because only the admin update_user endpoint accepted it. Rename to
UserUpdateAdmin to make intent explicit, and add UserUpdatePublic
which structurally excludes role, is_active, is_superuser,
refresh_token, hashed_password, and is_fixture_user.

This test is the durable contract: any future developer who tries to
add a field to UserUpdatePublic that would enable privilege escalation
fails this test.
"""
from __future__ import annotations

import pytest


def test_user_update_public_excludes_dangerous_fields():
    """UserUpdatePublic.model_fields must not contain role, is_active, etc."""
    from app.schemas.auth import UserUpdatePublic

    forbidden = {
        "role",
        "is_active",
        "is_superuser",
        "is_verified",
        "is_fixture_user",
        "hashed_password",
        "refresh_token",
        "failed_login_attempts",
        "locked_until",
        "permissions",
    }
    allowed = set(UserUpdatePublic.model_fields.keys())
    overlap = allowed & forbidden
    assert overlap == set(), (
        f"UserUpdatePublic leaks privilege-escalation fields: {overlap}. "
        f"Any user-facing update endpoint MUST use UserUpdatePublic, "
        f"not UserUpdateAdmin."
    )


def test_user_update_admin_preserves_existing_admin_fields():
    """UserUpdateAdmin keeps all fields the admin UI needs to edit."""
    from app.schemas.auth import UserUpdateAdmin

    required = {"email", "password", "full_name", "role", "is_active"}
    present = set(UserUpdateAdmin.model_fields.keys())
    missing = required - present
    assert missing == set(), f"UserUpdateAdmin missing admin-required fields: {missing}"


def test_user_update_old_name_is_removed():
    """The old `UserUpdate` name must no longer exist — all imports updated."""
    import app.schemas.auth as auth_schemas

    assert not hasattr(auth_schemas, "UserUpdate"), (
        "UserUpdate must be renamed to UserUpdateAdmin — no back-compat alias. "
        "See Wave 5b Task 7."
    )
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_auth_bopla_schemas.py -v
```

Expected: all three tests FAIL — `UserUpdatePublic` doesn't exist, `UserUpdateAdmin` doesn't exist, and `UserUpdate` still exists.

- [ ] **Step 3: Update `backend/app/schemas/auth.py`**

Edit `backend/app/schemas/auth.py`. Find the existing `UserUpdate` class (lines 62–77) and rename it to `UserUpdateAdmin`:

```python
class UserUpdateAdmin(BaseModel):
    """User update request — admin-only fields.

    Wave 5b Task 7: renamed from UserUpdate to make BOPLA scope explicit.
    This schema accepts role + is_active — NEVER use it on a user-facing
    update path. Use UserUpdatePublic for /auth/me or similar public paths.
    """

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = Field(None, max_length=255)
    role: str | None = Field(None, pattern="^(admin|curator|viewer)$")
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        """Validate password strength if provided."""
        if v is not None:
            validate_password_strength(v)
        return v
```

Then ADD a new class below it:

```python
class UserUpdatePublic(BaseModel):
    """User update request — user-facing self-service fields only.

    Wave 5b Task 7 (BOPLA): any public update endpoint (e.g., a future
    /auth/me PATCH for profile self-editing) MUST accept UserUpdatePublic
    and NEVER UserUpdateAdmin. Structurally excludes role, is_active,
    is_superuser, is_verified, is_fixture_user, hashed_password,
    refresh_token, failed_login_attempts, locked_until, permissions.

    This schema is NOT YET USED by any endpoint in Wave 5b. It exists so
    that Wave 5c (identity lifecycle) and any future profile-editing UI
    can consume it without having to carve a subset out of UserUpdateAdmin
    or (worse) reuse UserUpdateAdmin and hope nobody notices.
    """

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        """Validate password strength if provided."""
        if v is not None:
            validate_password_strength(v)
        return v
```

- [ ] **Step 4: Update import sites**

```bash
grep -rn "UserUpdate\b" backend/app/ 2>&1 | grep -v __pycache__
```

Expected: hits in `backend/app/api/auth_endpoints.py` (imports `UserUpdate` on line 27, uses it on lines 222 for `change_password` and 386 for `update_user`).

Edit `backend/app/api/auth_endpoints.py`:

Line 27 (imports):

```python
from app.schemas.auth import (
    PasswordChange,
    RefreshTokenRequest,
    RoleResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateAdmin,
)
```

Line ~222 (`change_password` function):

```python
    # Update password
    repo = UserRepository(db)
    user_update = UserUpdateAdmin(password=password_data.new_password)  # type: ignore[call-arg]
    await repo.update(current_user, user_update)
```

Wait — `change_password` is a user-facing endpoint, so it MUST NOT accept `UserUpdateAdmin`. Look again: the current code uses `UserUpdate` only to tunnel the password update through `UserRepository.update()` which accepts `UserUpdate`. That's a mismatch — we're passing an admin-scoped schema through a user-facing endpoint. In practice it's safe because the instance only has `password` set, but it's the kind of mixing that makes future BOPLA vulns easy.

**Fix:** `UserRepository.update()` should accept either schema shape. The simplest approach: make it accept a Pydantic `BaseModel` and read fields via `getattr(user_data, 'role', None)`. The existing code already does field-by-field updates with `if user_data.field is not None`, so making the signature more permissive is safe.

Edit `backend/app/repositories/user_repository.py` — change the `update` method signature:

```python
    async def update(self, user: User, user_data: "UserUpdateAdmin | UserUpdatePublic") -> User:
        """Update user fields.

        Accepts either UserUpdateAdmin or UserUpdatePublic. Wave 5b Task 7:
        the repo reads fields via getattr so a UserUpdatePublic instance
        simply doesn't update role / is_active (BOPLA-safe by construction).
        """
        if user_data.email is not None:
            user.email = user_data.email

        if user_data.password is not None:
            user.hashed_password = get_password_hash(user_data.password)

        if user_data.full_name is not None:
            user.full_name = user_data.full_name

        # Admin-only fields — read via getattr so UserUpdatePublic is safe
        role = getattr(user_data, "role", None)
        if role is not None:
            user.role = role

        is_active = getattr(user_data, "is_active", None)
        if is_active is not None:
            user.is_active = is_active

        user.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(user)
        return user
```

Update the import at the top of `user_repository.py`:

```python
from app.schemas.auth import UserCreate, UserUpdateAdmin, UserUpdatePublic
```

And remove `UserUpdate` from the import — it no longer exists.

Now fix the `change_password` call site — it should use `UserUpdatePublic` to make its intent explicit (it's a user self-service path, not an admin path):

```python
    # Update password
    repo = UserRepository(db)
    user_update = UserUpdatePublic(password=password_data.new_password)  # type: ignore[call-arg]
    await repo.update(current_user, user_update)
```

Add `UserUpdatePublic` to the imports in `auth_endpoints.py`:

```python
from app.schemas.auth import (
    PasswordChange,
    RefreshTokenRequest,
    RoleResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateAdmin,
    UserUpdatePublic,
)
```

Line ~386 (`update_user` function) — this is the admin endpoint, so it uses `UserUpdateAdmin`:

```python
@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateAdmin,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/test_auth_bopla_schemas.py tests/test_auth_unlock_endpoint.py -v
# Expect: all pass
```

Also run the existing auth tests to confirm the rename didn't break anything:

```bash
uv run pytest tests/test_auth.py tests/test_auth_integration.py -v 2>&1 | tail -15
# Expect: all green
```

- [ ] **Step 6: Run the full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1010 passed (1007 + 3 new BOPLA tests), 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth_endpoints.py backend/app/repositories/user_repository.py backend/tests/test_auth_bopla_schemas.py
git commit -m "$(cat <<'EOF'
refactor(api): split UserUpdate into UserUpdateAdmin + UserUpdatePublic (BOPLA)

Closes OWASP API3 (BOPLA) for the user management surface. Wave 5 scope
doc row F-top-1.

Rename UserUpdate → UserUpdateAdmin so the name reflects the intended
caller scope. Add a new UserUpdatePublic schema that structurally
excludes role, is_active, is_superuser, is_verified, is_fixture_user,
hashed_password, refresh_token, failed_login_attempts, locked_until,
permissions — the set of fields that would enable privilege escalation
or state tampering if attacker-controllable.

change_password endpoint now uses UserUpdatePublic to make its scope
explicit (previously tunneled through UserUpdate). UserRepository.update
reads role/is_active via getattr so a UserUpdatePublic instance is
BOPLA-safe by construction — the fields simply don't exist on the
schema, so they can never be updated through a public caller.

UserUpdatePublic has no endpoint consumers in Wave 5b — it exists
ready for Wave 5c identity lifecycle and any future /auth/me
profile-editing surface to consume.

New test test_auth_bopla_schemas.py is the durable contract: any
future field added to UserUpdatePublic that would leak a dangerous
field fails the test.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: BFLA migration step 1 — add admin route authorization tests

**Goal:** First commit of the three-commit behavior-preserving BFLA router-guard migration (scope doc §5 R4). Add `backend/tests/test_admin_route_authorization.py` with explicit `viewer → 403 / curator → 403 / admin → 200` assertions for every admin-gated route in `auth_endpoints.py` and every `/admin/*` route in `app/api/admin/`. These tests must pass AGAINST the current per-endpoint-guard state, then continue passing unchanged through Task 9 (router-level guard application) and Task 10 (per-endpoint guard removal).

**Why three commits:** Task 9 could theoretically regress a route silently — a route that still has per-endpoint `Depends(require_admin)` in commit state N would still pass an admin-vs-viewer test even if the router guard misses it. Task 10 removes the per-endpoint guards, exposing any gap. The three-commit sequence gives `git revert` granularity — if commit 10 fails, revert leaves commits 8+9 intact and the app still works (all per-endpoint guards are still there).

**Files:**
- Create: `backend/tests/test_admin_route_authorization.py`
- Modify: `backend/tests/conftest.py` (add `viewer_headers` fixture if not already present)

- [ ] **Step 1: Inventory every admin-gated route**

```bash
grep -rn "require_admin" backend/app/api/ 2>&1 | grep -v __pycache__
```

Expected: the output matches the Wave 5a-era grep — 5 `auth_endpoints.py` endpoints (create_user, list_users, get_user, update_user, delete_user) + the new `unlock_user` from Task 6 + ~10 admin sub-router endpoints. Write down the complete list; you will parametrize the test over it.

For each endpoint, record: (name, HTTP method, URL template, optional body).

- [ ] **Step 2: Write the test**

Create `backend/tests/test_admin_route_authorization.py`:

```python
"""Wave 5b Task 8: explicit viewer/curator/admin authorization matrix.

This test is the durable contract that Wave 5b's BFLA refactor
(Tasks 8-10) does not regress any admin-gated route. Every /admin/* and
/auth/users/* endpoint is asserted to:

  - return 403 for a viewer token
  - return 403 for a curator token
  - return 200/204/201 for an admin token (accepting any 2xx on success)

The parametrize list must stay in sync with the routes exposed by
app/api/admin/ and app/api/auth_endpoints.py. Any route added later
without being added to this test is a BFLA regression risk.
"""
from __future__ import annotations

from typing import Optional

import pytest
from httpx import AsyncClient

# (name, method, url, body)
# If body is None, no JSON body is sent.
# URLs that need path-parameter substitution at runtime use the seeded
# admin user id via the `{admin_user_id}` placeholder resolved in the
# test body below.
ADMIN_ROUTES: list[tuple[str, str, str, Optional[dict]]] = [
    # auth_endpoints.py — user management
    ("create_user", "POST", "/api/v2/auth/users", {
        "username": "wave5b-bfla-probe",
        "email": "wave5b-bfla-probe@hnf1b-db.local",
        "password": "ProbePass!2026",
        "full_name": "BFLA Probe",
        "role": "viewer",
    }),
    ("list_users", "GET", "/api/v2/auth/users", None),
    ("get_user", "GET", "/api/v2/auth/users/{admin_user_id}", None),
    ("update_user", "PUT", "/api/v2/auth/users/{admin_user_id}", {
        "full_name": "updated",
    }),
    # delete_user is parametrized but the test asserts 400 for admin (can't
    # delete self); the check is that non-admins still get 403 BEFORE the
    # self-delete guard fires.
    ("delete_user", "DELETE", "/api/v2/auth/users/{admin_user_id}", None),
    ("unlock_user", "PATCH", "/api/v2/auth/users/{admin_user_id}/unlock", None),

    # admin sub-router — status_routes.py
    ("admin_status", "GET", "/api/v2/admin/status", None),
    ("admin_statistics", "GET", "/api/v2/admin/statistics", None),
    ("admin_reference_status", "GET", "/api/v2/admin/reference/status", None),

    # admin sub-router — sync_publications_routes.py
    ("admin_sync_publications", "POST", "/api/v2/admin/sync/publications", None),
    ("admin_sync_publications_status", "GET", "/api/v2/admin/sync/publications/status", None),

    # admin sub-router — sync_variants_routes.py
    ("admin_sync_variants", "POST", "/api/v2/admin/sync/variants", None),
    ("admin_sync_variants_status", "GET", "/api/v2/admin/sync/variants/status", None),

    # admin sub-router — sync_reference_routes.py
    ("admin_sync_reference_init", "POST", "/api/v2/admin/sync/reference/init", None),
    ("admin_sync_genes", "POST", "/api/v2/admin/sync/genes", None),
    ("admin_sync_genes_status", "GET", "/api/v2/admin/sync/genes/status", None),
]


async def _probe(
    async_client: AsyncClient,
    method: str,
    url: str,
    body: Optional[dict],
    headers: dict,
) -> int:
    """Invoke an HTTP method via httpx.AsyncClient and return status code."""
    if method == "GET":
        resp = await async_client.get(url, headers=headers)
    elif method == "POST":
        resp = await async_client.post(url, json=body, headers=headers)
    elif method == "PUT":
        resp = await async_client.put(url, json=body, headers=headers)
    elif method == "PATCH":
        resp = await async_client.patch(url, json=body, headers=headers)
    elif method == "DELETE":
        if body:
            resp = await async_client.request("DELETE", url, json=body, headers=headers)
        else:
            resp = await async_client.delete(url, headers=headers)
    else:
        raise ValueError(f"unsupported method {method}")
    return resp.status_code


@pytest.mark.asyncio
@pytest.mark.parametrize("name, method, url, body", ADMIN_ROUTES, ids=[r[0] for r in ADMIN_ROUTES])
async def test_admin_route_forbidden_for_viewer(
    name: str,
    method: str,
    url: str,
    body: Optional[dict],
    async_client: AsyncClient,
    viewer_headers: dict,
    admin_user_id: int,
):
    """Every admin route returns 403 for a viewer token."""
    resolved_url = url.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, resolved_url, body, viewer_headers)
    assert status_code == 403, (
        f"BFLA regression risk: {name} returned {status_code} for viewer, "
        f"expected 403"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("name, method, url, body", ADMIN_ROUTES, ids=[r[0] for r in ADMIN_ROUTES])
async def test_admin_route_forbidden_for_curator(
    name: str,
    method: str,
    url: str,
    body: Optional[dict],
    async_client: AsyncClient,
    curator_headers: dict,
    admin_user_id: int,
):
    """Every admin route returns 403 for a curator token."""
    resolved_url = url.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, resolved_url, body, curator_headers)
    assert status_code == 403, (
        f"BFLA regression risk: {name} returned {status_code} for curator, "
        f"expected 403"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("name, method, url, body", ADMIN_ROUTES, ids=[r[0] for r in ADMIN_ROUTES])
async def test_admin_route_reachable_for_admin(
    name: str,
    method: str,
    url: str,
    body: Optional[dict],
    async_client: AsyncClient,
    admin_headers: dict,
    admin_user_id: int,
):
    """Every admin route returns a non-403/401 status for an admin token.

    Success shapes vary: 200/201/204/400/409 are all acceptable — the
    test only cares that authorization succeeded. A 400 (e.g., delete_user
    hits the self-delete guard) means the admin got past require_admin,
    which is the BFLA invariant we care about.
    """
    resolved_url = url.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, resolved_url, body, admin_headers)
    assert status_code not in (401, 403), (
        f"BFLA regression: {name} returned {status_code} for admin, "
        f"expected any non-{{401,403}} status"
    )
```

**Conftest additions:** if `viewer_headers` or `curator_headers` fixtures don't exist yet, add them alongside `admin_headers`:

```python
@pytest.fixture
async def viewer_headers(async_client, db_session) -> dict:
    """Mint a viewer JWT for the admin-authorization matrix tests."""
    from sqlalchemy import text
    from app.auth.tokens import create_access_token
    from app.auth.permissions import get_role_permissions

    await db_session.execute(text("""
        INSERT INTO users (
            email, username, hashed_password, role, is_active, is_verified,
            is_fixture_user, failed_login_attempts, created_at
        )
        VALUES (
            'wave5b-viewer@hnf1b-db.local', 'wave5b-viewer',
            '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
            'viewer', true, true, false, 0, NOW()
        )
        ON CONFLICT (username) DO NOTHING
    """))
    await db_session.commit()
    token = create_access_token(
        "wave5b-viewer", "viewer", get_role_permissions("viewer")
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def curator_headers(async_client, db_session) -> dict:
    """Mint a curator JWT for the admin-authorization matrix tests."""
    from sqlalchemy import text
    from app.auth.tokens import create_access_token
    from app.auth.permissions import get_role_permissions

    await db_session.execute(text("""
        INSERT INTO users (
            email, username, hashed_password, role, is_active, is_verified,
            is_fixture_user, failed_login_attempts, created_at
        )
        VALUES (
            'wave5b-curator@hnf1b-db.local', 'wave5b-curator',
            '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
            'curator', true, true, false, 0, NOW()
        )
        ON CONFLICT (username) DO NOTHING
    """))
    await db_session.commit()
    token = create_access_token(
        "wave5b-curator", "curator", get_role_permissions("curator")
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_user_id(async_client, admin_headers) -> int:
    """Return the id of the admin user behind admin_headers."""
    resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    return resp.json()["id"]
```

Check `backend/tests/conftest.py` first for the existing `admin_headers` fixture and use the same import pattern.

- [ ] **Step 3: Run the test — expect pass (against the current per-endpoint guards)**

```bash
cd backend
uv run pytest tests/test_admin_route_authorization.py -v 2>&1 | tail -40
```

Expected: every parametrized case PASSES. The current codebase has per-endpoint `Depends(require_admin)` on all these routes, so viewer/curator already get 403 and admin already gets past the guard.

If any case fails, the inventory from Step 1 missed a route that lacks a guard — this is a pre-existing BFLA gap that must be fixed before proceeding. Add the missing guard in THIS commit.

- [ ] **Step 4: Run full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1058 passed (1010 + 3 parametrize factors × ~16 routes = ~48 new tests)
# Exact count varies with the parametrize ID list; adjust expected number
# after running it for the first time.

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_admin_route_authorization.py backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
test(auth): add explicit BFLA authorization matrix for admin routes

Wave 5b Task 8 — first of three commits implementing the scope doc §5 R4
router-level BFLA migration. This commit ADDS the explicit
viewer→403 / curator→403 / admin→non-{401,403} matrix that covers every
admin-gated route in auth_endpoints.py and app/api/admin/ sub-routers.

The tests pass against the CURRENT per-endpoint Depends(require_admin)
state. Task 9 will apply router-level dependencies to the /auth/users
sub-router + admin router, leaving per-endpoint guards in place (the
matrix must still pass). Task 10 will remove the per-endpoint guards
(the matrix must still pass).

This three-commit sequence gives git revert granularity: if Task 10
regresses anything, revert restores the per-endpoint guards cleanly.

The ADMIN_ROUTES parametrize list is the durable contract — any new
admin-gated route added in the future should be added here as part
of the same PR, else BFLA regression risk accumulates.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: BFLA migration step 2 — apply router-level guards

**Goal:** Second commit of the three-commit BFLA refactor. Split `/api/v2/auth` into two sub-routers: the existing public/self-service endpoints stay on the top-level router, and the 6 admin user-management endpoints move onto a new `users_router = APIRouter(prefix="/users", dependencies=[Depends(require_admin)], tags=["user-management"])`. Apply the same router-level dependency to the admin router in `backend/app/api/admin/endpoints.py`. The **per-endpoint** `Depends(require_admin)` parameters stay in place — this commit adds belt + suspenders. Task 10 removes the belt.

**Why router-level AND per-endpoint guards in this commit:** The BFLA matrix from Task 8 still passes against BOTH. If this commit breaks anything (e.g., `current_user` injection stops working because the per-endpoint `Depends(require_admin)` was the only `User` provider), the tests catch it before the per-endpoint cleanup in Task 10.

**Files:**
- Modify: `backend/app/api/auth_endpoints.py` (split into two routers)
- Modify: `backend/app/api/admin/endpoints.py` (add router-level `dependencies=[Depends(require_admin)]`)

- [ ] **Step 1: Restructure `auth_endpoints.py` into two routers**

Edit `backend/app/api/auth_endpoints.py`. At the top of the file, near the existing `router = APIRouter(...)` declaration, add a second sub-router:

```python
from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_admin,
    verify_password,
    verify_token,
)
# ... other imports ...
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])

# Wave 5b Task 9: admin user-management routes live on a sub-router
# with router-level require_admin dependency. The BFLA matrix in
# test_admin_route_authorization.py asserts every /auth/users/* route
# denies non-admins regardless of per-endpoint guards.
users_router = APIRouter(
    prefix="/users",
    dependencies=[Depends(require_admin)],
    tags=["user-management"],
)
```

Then change every `@router.post("/users", ...)` / `@router.get("/users", ...)` / `@router.get("/users/{user_id}", ...)` / `@router.put("/users/{user_id}", ...)` / `@router.delete("/users/{user_id}", ...)` / `@router.patch("/users/{user_id}/unlock", ...)` decoration to use `@users_router` with the prefix stripped:

```python
@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),  # stays for now — Task 10 removes
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    ...

@users_router.get("", response_model=list[UserResponse])
async def list_users(...):
    ...

@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(...):
    ...

@users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(...):
    ...

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(...):
    ...

@users_router.patch("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(...):
    ...
```

At the BOTTOM of the file (after all function definitions), include the users sub-router into the main router:

```python
# Wave 5b Task 9: mount the admin user-management sub-router
router.include_router(users_router)
```

**Important:** FastAPI evaluates `include_router` at import time — the line must go AFTER all `@users_router.xxx` decorations have run. Put it at the very end of the file.

- [ ] **Step 2: Add router-level guard to the admin aggregator**

Edit `backend/app/api/admin/endpoints.py`. Change:

```python
router = APIRouter(prefix="/api/v2/admin", tags=["admin"])
```

to:

```python
from app.auth import require_admin
from fastapi import Depends

router = APIRouter(
    prefix="/api/v2/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
```

Note: `require_admin` is not currently imported in `admin/endpoints.py`. Add the import.

The sub-routers (`status_routes.py`, `sync_publications_routes.py`, etc.) still have per-endpoint `dependencies=[Depends(require_admin)]` on each route — Task 10 removes those.

- [ ] **Step 3: Run the BFLA matrix test**

```bash
cd backend
uv run pytest tests/test_admin_route_authorization.py -v 2>&1 | tail -20
```

Expected: all parametrized cases PASS (same as Task 8). If anything fails, the sub-router split broke route registration — common causes:
- Forgot to `router.include_router(users_router)` at the bottom
- Put a `@users_router` decoration INSIDE a function body
- Path conflict between `@router.get("/roles")` (still on main router) and something on `/users/*`

- [ ] **Step 4: Run the full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: same count as Task 8 (~1058), 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed — this is critical, the baseline fixtures lock in
# the response shape and verify the /auth/users/* endpoints still return
# the same JSON after the router split
```

- [ ] **Step 5: Verify the unlock endpoint still works end-to-end**

```bash
uv run pytest tests/test_auth_unlock_endpoint.py -v 2>&1 | tail -15
# Expect: all 3 pass
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth_endpoints.py backend/app/api/admin/endpoints.py
git commit -m "$(cat <<'EOF'
refactor(auth): apply router-level BFLA guards on /auth/users + /admin

Wave 5b Task 9 — second of three commits implementing scope doc §5 R4.
This commit ADDS router-level dependencies=[Depends(require_admin)]
WITHOUT removing any per-endpoint guards. Belt + suspenders until
Task 10 removes the belt.

auth_endpoints.py: splits the 6 admin user-management endpoints
(create, list, get, update, delete, unlock) onto a new users_router
with prefix="/users" and dependencies=[Depends(require_admin)]. The
sub-router is mounted onto the main auth router via include_router.

admin/endpoints.py: the aggregator APIRouter gains
dependencies=[Depends(require_admin)]. The 4 admin sub-routers
(status, sync_publications, sync_variants, sync_reference) keep their
per-endpoint guards for now — Task 10 removes them.

BFLA matrix test from Task 8 still passes — that's the whole point
of this commit sequence.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: BFLA migration step 3 — remove per-endpoint guards

**Goal:** Third commit of the three-commit BFLA refactor. Remove every per-endpoint `Depends(require_admin)` parameter on routes that are now covered by a router-level guard. The BFLA matrix from Task 8 must still pass — if it fails, the removal exposed a gap and the commit should be reverted (leaving Tasks 8+9 intact).

**Files:**
- Modify: `backend/app/api/auth_endpoints.py` (remove per-endpoint `current_user: User = Depends(require_admin)` from 6 admin user endpoints; route decorator-level `dependencies=[]` are irrelevant since users_router already has the dependency, so routes no longer need them)
- Modify: `backend/app/api/admin/status_routes.py` (remove `dependencies=[Depends(require_admin)]` and per-endpoint `current_user: User = Depends(require_admin)`)
- Modify: `backend/app/api/admin/sync_publications_routes.py`
- Modify: `backend/app/api/admin/sync_reference_routes.py`
- Modify: `backend/app/api/admin/sync_variants_routes.py`

**Critical subtlety:** `current_user: User = Depends(require_admin)` serves TWO purposes — it's an auth guard AND it injects the user object into the function body (for audit logging). Simply removing it breaks `current_user.username` references. The fix: for endpoints that use `current_user`, keep the parameter but change it from `Depends(require_admin)` to `Depends(get_current_user)`. The router-level guard provides the admin check; `get_current_user` provides the injection.

- [ ] **Step 1: Grep every current usage pattern**

```bash
grep -n "current_user.*require_admin\|dependencies.*require_admin" backend/app/api/auth_endpoints.py backend/app/api/admin/ 2>&1 | grep -v __pycache__
```

Record every hit. You'll edit each one.

- [ ] **Step 2: Update `auth_endpoints.py` endpoints**

For each of the 6 admin user-management endpoints (`create_user`, `list_users`, `get_user`, `update_user`, `delete_user`, `unlock_user`):

- If the function uses `current_user` in its body (e.g., `current_user.username` for audit logging): change `current_user: User = Depends(require_admin)` → `current_user: User = Depends(get_current_user)`. The router-level `dependencies=[Depends(require_admin)]` on `users_router` still enforces admin.
- If the function does NOT use `current_user` in its body (check each one — `list_users` and `get_user` may not): delete the parameter entirely.

Add `get_current_user` to the import if it's not already there:

```python
from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_admin,
    verify_password,
    verify_token,
)
```

- [ ] **Step 3: Update the admin sub-routers**

Edit each of `backend/app/api/admin/{status_routes.py, sync_publications_routes.py, sync_reference_routes.py, sync_variants_routes.py}`.

For each file:

1. Remove `dependencies=[Depends(require_admin)]` from each `@router.get(...)` / `@router.post(...)` decorator.
2. For functions that use `current_user`: change `current_user: User = Depends(require_admin)` → `current_user: User = Depends(get_current_user)`.
3. For functions that don't use `current_user`: delete the parameter entirely.
4. Remove the `from app.auth import require_admin` import if no other line in the file references it.
5. Add `from app.auth import get_current_user` if any function kept the `current_user` parameter.

**Do not remove the `current_user` import of `User` — endpoints that inject `current_user: User = Depends(...)` still need the type.**

- [ ] **Step 4: Run the BFLA matrix**

```bash
cd backend
uv run pytest tests/test_admin_route_authorization.py -v 2>&1 | tail -20
```

**This is the moment of truth.** Expected: all parametrized cases still PASS. If any case fails — say, `test_admin_route_forbidden_for_viewer[admin_sync_genes]` returns 200 instead of 403 — it means the router-level guard from Task 9 doesn't cover that route, and the per-endpoint guard was the only protection. Options:

1. (Preferred) Investigate why the route isn't covered — the sub-router's parent probably isn't wired into the admin aggregator router correctly. Fix in THIS commit.
2. (Fallback) If the root cause is subtle, `git reset --hard HEAD` and leave Tasks 8+9 as-is for this PR. Commit 10 becomes "Task 10 (deferred to a follow-up PR)" and the plan totals 13 commits instead of 14.

If you hit Option 2, update the exit note and the PR description to reflect the deferral. Do NOT force the commit through with a failing matrix.

- [ ] **Step 5: Run full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: same count as Task 9, 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth_endpoints.py backend/app/api/admin/
git commit -m "$(cat <<'EOF'
refactor(auth): remove per-endpoint require_admin guards now covered at router level

Wave 5b Task 10 — third and final of three commits implementing scope
doc §5 R4 router-level BFLA migration.

Removes per-endpoint Depends(require_admin) from:
  - auth_endpoints.py: 6 admin user management endpoints
  - admin/status_routes.py: 3 endpoints
  - admin/sync_publications_routes.py: 2 endpoints
  - admin/sync_reference_routes.py: 3 endpoints
  - admin/sync_variants_routes.py: 2 endpoints

Router-level dependencies from Task 9 (users_router and the admin
aggregator router in admin/endpoints.py) now provide authorization.

Endpoints that still need the current User object for audit logging
switched their parameter from Depends(require_admin) to
Depends(get_current_user) — the router-level guard handles the 403 gate,
get_current_user provides the injection. Endpoints that never used
current_user dropped the parameter entirely.

BFLA matrix from Task 8 still passes — behavior-preserving refactor.
The three-commit sequence gives clean git revert granularity if any
step breaks something.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Migrate passlib → pwdlib with verify-and-rehash

**Goal:** Close scope-doc row F-top-3. Replace `passlib.context.CryptContext(schemes=["bcrypt"])` with `pwdlib.PasswordHash.recommended()` (Argon2id primary + bcrypt verifier fallback). Existing bcrypt users must log in without forced logouts; their hash transparently rehashes to Argon2id on first login after deploy.

**Risk:** HIGH per scope doc §5 R2. Mitigations:
1. `pwdlib.PasswordHash.recommended()` includes `BcryptHasher` as a fallback verifier — any `$2b$...` hash round-trips cleanly without modification to the stored value. This is the default behavior of `pwdlib`, not a custom hack.
2. Add a test that seeds a pre-computed `$2b$12$...` hash, logs in, and asserts (a) login succeeds (b) the stored hash is now `$argon2id$v=19$m=...$...`.
3. `backend/tests/test_auth.py` must continue passing unchanged — if any test directly references `passlib.hash.bcrypt`, update it to use `pwdlib.hashers.bcrypt.BcryptHasher`.
4. Tech-debt register entry documents the bcrypt-verifier fallback as a permanent runtime cost until every live user has logged in at least once post-migration.

**Files:**
- Modify: `backend/pyproject.toml` (remove passlib, add pwdlib[argon2,bcrypt])
- Modify: `backend/uv.lock` (regenerated by `uv sync`)
- Modify: `backend/app/auth/password.py` (rewrite)
- Create: `backend/tests/test_pwdlib_rehash.py`
- Modify: `docs/refactor/tech-debt.md` (add entry for the transition period)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pwdlib_rehash.py`:

```python
"""Wave 5b Task 11: pwdlib verify-and-rehash for legacy bcrypt users.

Scope doc §5 R2. Existing $2b$... bcrypt hashes must still verify after
the passlib → pwdlib swap, and should transparently upgrade to
$argon2id$... on first login — without forcing a logout, password
reset, or any user-visible change.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# A pre-computed bcrypt hash for the plaintext "LegacyPass!2026".
# Generated offline via:
#   python -c "import passlib.context; c = passlib.context.CryptContext(schemes=['bcrypt']); print(c.hash('LegacyPass!2026'))"
# The literal value is paste-safe because the feature under test is
# hash verification, not hash secrecy.
LEGACY_BCRYPT_HASH = "$2b$12$GZzQ3Rpz3gXoZkC7Y4eKjO8bOQqKlPcRz9xZ4YyHcV7G.FmH1uT7i"


@pytest.mark.asyncio
async def test_legacy_bcrypt_login_succeeds(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """A user seeded with a legacy $2b$ hash can still log in."""
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'legacy@hnf1b-db.local', 'wave5b-legacy-user',
                :hash, 'viewer', true, true, false, 0, NOW()
            )
            ON CONFLICT (username) DO UPDATE SET hashed_password = :hash
        """),
        {"hash": LEGACY_BCRYPT_HASH},
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "wave5b-legacy-user", "password": "LegacyPass!2026"},
    )
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_legacy_bcrypt_rehashes_to_argon2id_on_login(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """After login, the stored hash should be Argon2id, not bcrypt."""
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'rehash@hnf1b-db.local', 'wave5b-rehash-user',
                :hash, 'viewer', true, true, false, 0, NOW()
            )
            ON CONFLICT (username) DO UPDATE SET hashed_password = :hash
        """),
        {"hash": LEGACY_BCRYPT_HASH},
    )
    await db_session.commit()

    # Login triggers verify-and-rehash
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "wave5b-rehash-user", "password": "LegacyPass!2026"},
    )
    assert response.status_code == 200

    # Verify the stored hash is now Argon2id
    row = (await db_session.execute(
        text("SELECT hashed_password FROM users WHERE username = 'wave5b-rehash-user'")
    )).fetchone()
    assert row is not None
    assert row.hashed_password.startswith("$argon2id$"), (
        f"Hash did not upgrade on login. Still: {row.hashed_password[:20]}..."
    )


@pytest.mark.asyncio
async def test_new_user_hash_is_argon2id(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """A freshly-created user has an Argon2id hash from the start."""
    response = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "wave5b-new-argon",
            "email": "new-argon@hnf1b-db.local",
            "password": "FreshPass!2026",
            "full_name": "Fresh User",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201

    # The response doesn't include the hash (correct), so round-trip
    # to verify the stored hash is Argon2id.
    from app.database import async_session_maker
    from sqlalchemy import text as _t
    async with async_session_maker() as s:
        row = (await s.execute(
            _t("SELECT hashed_password FROM users WHERE username = 'wave5b-new-argon'")
        )).fetchone()
        assert row is not None
        assert row.hashed_password.startswith("$argon2id$")
```

**Note:** The literal `LEGACY_BCRYPT_HASH` must be generated OFFLINE (pre-commit) with passlib against the chosen plaintext. Run:

```bash
cd backend
uv run python -c "import passlib.context; c = passlib.context.CryptContext(schemes=['bcrypt']); print(c.hash('LegacyPass!2026'))"
```

Paste the output into the test file in place of the placeholder. The exact hash value changes with each run (bcrypt uses a random salt), but any valid bcrypt output works — the point is that the plaintext-to-hash pair is deterministic.

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_pwdlib_rehash.py -v
```

Expected: `test_legacy_bcrypt_login_succeeds` PASSES (passlib still verifies it); `test_legacy_bcrypt_rehashes_to_argon2id_on_login` FAILS (hash unchanged because passlib doesn't rehash-on-verify); `test_new_user_hash_is_argon2id` FAILS (still bcrypt).

- [ ] **Step 3: Swap the dependency**

Edit `backend/pyproject.toml`. Find the `[project]` dependencies block and:

- Find the passlib pin first: `git grep -n passlib backend/pyproject.toml` — expect a line like `"passlib[bcrypt]>=1.7.4"` in the `dependencies` array. Delete that exact line.
- Add `"pwdlib[argon2,bcrypt]>=0.2.1"` to the `dependencies` array. If `uv add pwdlib[argon2,bcrypt]` resolves a newer version, accept the newer pin — the contract is "pwdlib ≥ 0.2.1" (first version with `PasswordHash.recommended()` + `verify_and_update`).

Run:

```bash
cd backend
uv add "pwdlib[argon2,bcrypt]"
uv remove passlib
uv sync --group test
```

Expected: `uv.lock` regenerates, `pwdlib` appears in the dep tree, `passlib` is gone.

**Verify no other backend code still imports passlib:**

```bash
grep -rn "passlib" backend/ 2>&1 | grep -v __pycache__ | grep -v uv.lock
```

Expected: empty (Task 11 is the one-and-only passlib removal). If any test file imports `passlib.hash.bcrypt` (which could happen in `test_auth.py`), update it to use `pwdlib.hashers.bcrypt.BcryptHasher` or pre-computed literal hashes like the one in Step 1.

- [ ] **Step 4: Rewrite `backend/app/auth/password.py`**

Replace the file contents:

```python
"""Password hashing and verification via pwdlib.

Wave 5b Task 11 (scope doc F-top-3): replaces the passlib CryptContext
with pwdlib.PasswordHash.recommended(). pwdlib's "recommended" config
includes Argon2Hasher as primary and BcryptHasher as fallback verifier,
so legacy `$2b$...` hashes verify cleanly and transparently upgrade to
Argon2id on the first successful login after deploy.

Tech-debt entry tracks the bcrypt verifier fallback as a permanent
runtime cost until every live user has logged in at least once
post-migration. Re-evaluate when
  SELECT COUNT(*) FROM users WHERE hashed_password LIKE '$2b$%'
returns 0.
"""

from pwdlib import PasswordHash

from app.core.config import settings

# Recommended config: Argon2id primary, bcrypt fallback verifier.
_password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Argon2id hash (never bcrypt — new hashes are always Argon2id)
    """
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash (Argon2id or legacy bcrypt).

    Wave 5b Task 11: callers that want transparent rehash-on-verify
    should use verify_and_update_password_hash() instead — this function
    only verifies without touching storage.

    Args:
        plain_password: Plain text password
        hashed_password: Stored hash (Argon2id or legacy $2b$ bcrypt)

    Returns:
        True if password matches hash
    """
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except Exception:
        # pwdlib raises on unrecognized hash formats; a malformed stored
        # hash should not leak through as a server error.
        return False


def verify_and_update_password_hash(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    """Verify a password and return a new hash if the stored one is legacy.

    Wave 5b Task 11 verify-and-rehash helper. Call from the login path:
    if the returned new_hash is not None, write it back to the user row.

    Args:
        plain_password: Plain text password
        hashed_password: Stored hash

    Returns:
        (valid, new_hash) — new_hash is not None only when the verification
        succeeded AND the stored hash was legacy (bcrypt) and needs upgrading
        to Argon2id.
    """
    valid, new_hash = _password_hash.verify_and_update(plain_password, hashed_password)
    return valid, new_hash


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.

    Args:
        password: Password to validate

    Raises:
        ValueError: If password doesn't meet requirements with detailed message
    """
    errors = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Must be at least {settings.PASSWORD_MIN_LENGTH} characters")

    if not any(c.isupper() for c in password):
        errors.append("Must contain uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Must contain lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Must contain digit")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Must contain special character")

    if errors:
        raise ValueError(f"Password validation failed: {'; '.join(errors)}")
```

**Verify the pwdlib API:** the `verify_and_update` method is part of `pwdlib.PasswordHash` (see https://github.com/frankie567/pwdlib). If the installed version doesn't expose it, fall back to manual rehash:

```python
def verify_and_update_password_hash(plain_password, hashed_password):
    if not verify_password(plain_password, hashed_password):
        return False, None
    # Upgrade if the stored hash is not Argon2id
    if not hashed_password.startswith("$argon2id$"):
        return True, get_password_hash(plain_password)
    return True, None
```

Pick whichever shape the installed version of pwdlib supports.

- [ ] **Step 5: Wire verify-and-rehash into the login endpoint**

Edit `backend/app/api/auth_endpoints.py`. In the `login` function, after the current password check succeeds, swap `verify_password` for `verify_and_update_password_hash`:

```python
    # Verify password (with transparent legacy-hash upgrade)
    valid, new_hash = verify_and_update_password_hash(
        credentials.password, user.hashed_password
    )
    if not user or not valid:
        if user:
            await repo.record_failed_login(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Transparent rehash: if the stored hash was legacy bcrypt, write the
    # new Argon2id hash back. No forced logout, no user-visible change.
    if new_hash is not None:
        user.hashed_password = new_hash
        await repo.db.commit()
```

Update the import at the top of `auth_endpoints.py`:

```python
from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_admin,
    verify_password,
    verify_token,
)
# Wave 5b Task 11: verify_and_update_password_hash lives in auth.password
from app.auth.password import verify_and_update_password_hash
```

- [ ] **Step 6: Run the pwdlib tests — expect pass**

```bash
uv run pytest tests/test_pwdlib_rehash.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Run the existing auth test suite**

```bash
uv run pytest tests/test_auth.py tests/test_auth_integration.py -v 2>&1 | tail -20
```

Expected: all green. If any test references `passlib.hash.bcrypt`, update it.

- [ ] **Step 8: Run the full suite + baselines + make check**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1061 passed (1058 + 3 new), 10 skipped, 3 xfailed

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed

make check 2>&1 | tail -10
# Expect: ruff + mypy + pytest green
```

- [ ] **Step 9: Add tech-debt register entry**

Check if `docs/refactor/tech-debt.md` exists:

```bash
ls docs/refactor/tech-debt.md 2>&1
```

If it doesn't exist, create it. If it does, append to the existing content. Add the entry:

```markdown
## Wave 5b — pwdlib bcrypt verifier fallback transition period

**Introduced:** Wave 5b Task 11 (passlib → pwdlib migration)
**Owner:** Backend / Auth
**Status:** OPEN — re-evaluate post every-user-login

`backend/app/auth/password.py` uses pwdlib's `PasswordHash.recommended()`,
which includes a `BcryptHasher` as a fallback verifier for legacy
`$2b$...` hashes from the passlib era. The `verify_and_update` path
transparently upgrades any successfully-verified legacy hash to
Argon2id on the login path — no forced logouts, no user-visible change.

The bcrypt verifier fallback is a permanent runtime cost (extra allocator
+ code path) until every live user has logged in at least once post-Wave-5b.

**Re-evaluation criterion:**

```sql
SELECT COUNT(*) FROM users WHERE hashed_password LIKE '$2b$%';
```

When this returns 0, we can drop `[bcrypt]` from the pwdlib extra and
use `PasswordHash([Argon2Hasher()])` only. Until then, keep the fallback.
```

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/auth/password.py backend/app/api/auth_endpoints.py backend/tests/test_pwdlib_rehash.py docs/refactor/tech-debt.md
git commit -m "$(cat <<'EOF'
refactor(auth): migrate passlib → pwdlib with verify-and-rehash

Closes Wave 5 scope doc row F-top-3. Replaces passlib CryptContext with
pwdlib.PasswordHash.recommended() — Argon2id primary + bcrypt verifier
fallback. New password hashes are always Argon2id; existing $2b$ hashes
verify cleanly via pwdlib's BcryptHasher and transparently upgrade on
first successful login via verify_and_update_password_hash().

No forced logouts. No user-visible change. Round-trip tested against a
pre-computed $2b$12$... hash.

pyproject.toml: remove passlib, add pwdlib[argon2,bcrypt]>=0.2.1.

Login path now calls verify_and_update_password_hash instead of
verify_password. If the verify path returns a new hash, write it back
to the user row in the same transaction as record_successful_login.

Tech-debt register gains an entry for the bcrypt verifier fallback
transition period — we re-evaluate when
  SELECT COUNT(*) FROM users WHERE hashed_password LIKE '$2b$%'
returns 0.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Split frontend/src/api/index.js into transport + session + domain modules

**Goal:** Close scope-doc row D1. `frontend/src/api/index.js` (1009 LOC) split into:
- `transport.js` — axios instance + `isRefreshing` / `failedRequestsQueue` state + refresh queue coordination (co-located per scope doc §5 R5 mitigation 1)
- `session.js` — access/refresh token storage (`localStorage` read/write, no axios dependency)
- `domain/*.js` — one file per section marker in the current monolith: phenopackets, aggregations, publications, auth, hpo, clinical, variants, reference, variant_annotation, search, admin
- `index.js` — rewritten as a ≤100 LOC re-export aggregator preserving the existing `default` export shape

**Risk:** MEDIUM per scope doc §5 R5 — the `isRefreshing` + `failedRequestsQueue` coordinate concurrent token refreshes; splitting them from the axios instance would thunder-herd. Mitigation: transport.js owns BOTH the axios instance AND the queue state, co-located.

**Files:**
- Create: 13 new files (2 infra + 11 domain — see "New files" section at the top of this plan)
- Modify: `frontend/src/api/index.js` (rewrite as ≤100 LOC aggregator)
- Create: `frontend/tests/unit/api/transport.spec.js` (thunder-herd guard)
- Create: `frontend/tests/unit/api/session.spec.js` (token storage contract)

- [ ] **Step 1: Inventory every export in the current `api/index.js`**

```bash
grep -nE "^export " frontend/src/api/index.js | wc -l
# Expect: 64 (or whatever the current count is — run first)

grep -nE "^// =|^/\* =" frontend/src/api/index.js
# Expect: the section markers at lines 186 (Phenopackets), 397 (Aggregations),
# 476 (Admin), 608 (Publications), 651 (Auth), 674 (HPO), 696 (Clinical),
# 792 (Reference), 872 (Variant Annotation), 899 (Global Search)
```

Note: "Admin" currently appears BEFORE "Publications" — the section marker at line 476 is `=== Admin API Functions ===`. Preserve this relative ordering when splitting (it doesn't matter for execution, but keeps diffs readable).

- [ ] **Step 2: Create `frontend/src/api/transport.js`**

```javascript
// src/api/transport.js — axios instance + refresh queue coordination.
//
// Wave 5b Task 12 (scope doc D1): this module owns BOTH the axios client
// AND the isRefreshing + failedRequestsQueue state. Co-location is
// non-negotiable per scope doc §5 R5 mitigation 1 — separating the
// state from the interceptor would thunder-herd concurrent 401s.

import axios from 'axios';
import { clearTokens, getAccessToken } from './session';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v2',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Refresh-queue state — CO-LOCATED with the axios instance, DO NOT move.
let isRefreshing = false;
let failedRequestsQueue = [];

/**
 * Process queued requests after token refresh.
 * @param {Error|null} error - Error if refresh failed
 * @param {string|null} token - New access token if refresh succeeded
 */
function processQueue(error, token = null) {
  failedRequestsQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve(token);
    }
  });
  failedRequestsQueue = [];
}

// Request interceptor: attach JWT from localStorage via session helper
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: normalize error shape + handle 401 refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Normalize standardized backend error shape (Wave 2 T11).
    // This block is copied verbatim from the pre-split monolith —
    // any change here is out of scope for the D1 split.
    const responseData = error.response?.data;
    let normalizedDetail = error.message;
    if (responseData) {
      if (typeof responseData.detail === 'string') {
        normalizedDetail = responseData.detail;
      } else if (Array.isArray(responseData.detail)) {
        normalizedDetail = responseData.detail
          .map((item) =>
            item && typeof item === 'object' && 'msg' in item ? item.msg : String(item)
          )
          .join('; ');
      } else if (responseData.detail && typeof responseData.detail === 'object') {
        const d = responseData.detail;
        if (typeof d.message === 'string') {
          normalizedDetail = d.message;
        } else if (typeof d.error === 'string') {
          normalizedDetail = d.error;
        } else {
          try {
            normalizedDetail = JSON.stringify(d);
          } catch {
            normalizedDetail = String(d);
          }
        }
      } else if (responseData.detail != null) {
        normalizedDetail = String(responseData.detail);
      }
    }
    error.normalized = {
      detail: normalizedDetail,
      errorCode: responseData?.error_code ?? null,
      requestId: responseData?.request_id ?? null,
    };

    if (window.logService && error.response) {
      window.logService.error('API request failed', {
        status: error.response.status,
        url: originalRequest?.url,
        detail: error.normalized.detail,
        errorCode: error.normalized.errorCode,
        requestId: error.normalized.requestId,
      });
    }

    // 401 handling with refresh queue
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/refresh')
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedRequestsQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { useAuthStore } = await import('@/stores/authStore');
        const authStore = useAuthStore();

        const newAccessToken = await authStore.refreshAccessToken();

        processQueue(null, newAccessToken);
        isRefreshing = false;

        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;

        window.logService.warn('Token refresh failed, redirecting to login');
        clearTokens();

        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }

        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

- [ ] **Step 3: Create `frontend/src/api/session.js`**

```javascript
// src/api/session.js — access/refresh token storage.
//
// Wave 5b Task 12: isolated storage layer with no axios dependency.
// The auth store still owns the authoritative `accessToken` / `refreshToken`
// refs; this module is the localStorage-persistence adapter.

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function persistTokens({ accessToken, refreshToken }) {
  if (accessToken) localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
```

- [ ] **Step 4: Create the 11 domain files**

For each section in the old `index.js`, create a file in `frontend/src/api/domain/`. Each file starts with:

```javascript
import { apiClient } from '../transport';
```

Then hosts the exports that were under that section marker. Do NOT rename functions. Do NOT change signatures. Do NOT refactor bodies. This is a pure move.

**Example — `frontend/src/api/domain/phenopackets.js`:**

```javascript
// src/api/domain/phenopackets.js — Wave 5b Task 12 split.
// Lines 186–394 of the pre-split frontend/src/api/index.js.
import { apiClient } from '../transport';

/**
 * DEPRECATED: Use cursor pagination instead.
 * @deprecated Use buildCursorParams from @/utils/pagination instead
 */
export function pageToSkipLimit(page, pageSize) {
  return {
    skip: (page - 1) * pageSize,
    limit: pageSize,
  };
}

export const getPhenopackets = (params) => apiClient.get('/phenopackets/', { params });
export const getPhenopacket = (id) => apiClient.get(`/phenopackets/${id}`);
export const getPhenotypeTimeline = (id) => apiClient.get(`/phenopackets/${id}/timeline`);
export const createPhenopacket = (phenopacketData) =>
  apiClient.post('/phenopackets/', phenopacketData);
export const updatePhenopacket = (id, data) =>
  apiClient.put(`/phenopackets/${id}`, {
    phenopacket: data.phenopacket,
    revision: data.revision,
    change_reason: data.change_reason,
  });
export const deletePhenopacket = (id, changeReason) =>
  apiClient.delete(`/phenopackets/${id}`, {
    params: { change_reason: changeReason },
  });
// ... plus the rest of the functions in the Phenopackets section of the old file
// (getPhenopacketAuditHistory, getPhenopacketsBatch, searchPhenopackets,
//  getSearchFacets, getPhenopacketsBySex, getPhenopacketsWithVariants,
//  getPhenopacketsByPublication, getPhenotypicFeaturesBatch, getVariantsBatch,
//  getPhenopacketsByVariant)
```

Copy the JSDoc comments verbatim — they are part of the contract.

**Repeat for each section:**

- `domain/aggregations.js` — lines 397–606 (getSummaryStats, getSexDistribution, getPhenotypicFeaturesAggregation, getDiseaseAggregation, getVariantPathogenicity, getKidneyStages, getVariantTypes, getPublicationsByType, getPublicationsTimelineData, getPublicationTypes, getAgeOfOnsetAggregation, getSurvivalData, compareVariantTypes, getSmallVariants)
- `domain/admin.js` — lines 476–606 admin subset (getAdminStatus, getAdminStatistics, startPublicationSync, getPublicationSyncStatus, startVariantSync, getVariantSyncStatus, startReferenceInit, startGenesSync, getGenesSyncStatus, getReferenceDataStatus)
- `domain/publications.js` — lines 608–649 (getPublications, getPublicationMetadata)
- `domain/auth.js` — lines 651–672 (login, getCurrentUser, logout) — also add the future user management calls as part of Task 14 if needed
- `domain/hpo.js` — lines 674–694 (getHPOAutocomplete, searchHPOTerms)
- `domain/clinical.js` — lines 696–720 (getRenalInsufficiencyCases, getGenitalAbnormalitiesCases, getDiabetesCases, getHypomagnesemiaCases)
- `domain/variants.js` — lines 722–790 (getVariants)
- `domain/reference.js` — lines 792–870 (getReferenceGenomes, getReferenceGenes, getReferenceGene, getReferenceGeneTranscripts, getReferenceGeneDomains, getReferenceGenomicRegion)
- `domain/variant_annotation.js` — lines 872–897 (annotateVariant)
- `domain/search.js` — lines 899–919 (searchAutocomplete, searchGlobal)

The exact line ranges at the time of writing this plan are approximations — use `git grep -n` to find the current marker positions when you execute.

**Section overlap note:** The current file has the "Admin API Functions" section embedded BEFORE Publications but AFTER Aggregations. When splitting, put the admin functions in `domain/admin.js` and the remaining aggregation helpers (getPublicationTypes, getAgeOfOnsetAggregation, getSurvivalData, compareVariantTypes, getSmallVariants) in `domain/aggregations.js`. Read the file carefully — some exports appear in unexpected sections.

- [ ] **Step 5: Rewrite `frontend/src/api/index.js` as a re-export aggregator**

Replace the entire contents of `frontend/src/api/index.js`:

```javascript
// src/api/index.js — Wave 5b Task 12 aggregator.
//
// Re-exports every named function from the domain modules and
// preserves the legacy default export shape so existing import sites
// continue to work unchanged:
//
//   import { getPhenopackets } from '@/api';
//   import API from '@/api'; API.getPhenopackets(...)
//
// Target size: ≤100 LOC. If this file grows beyond that, a new
// domain module is warranted — do not inline additional logic here.

export { apiClient } from './transport';

export * from './domain/phenopackets';
export * from './domain/aggregations';
export * from './domain/admin';
export * from './domain/publications';
export * from './domain/auth';
export * from './domain/hpo';
export * from './domain/clinical';
export * from './domain/variants';
export * from './domain/reference';
export * from './domain/variant_annotation';
export * from './domain/search';

// Legacy default export — preserves the pre-split shape so
// `import API from '@/api'; API.getPhenopackets(...)` still works.
import { apiClient } from './transport';
import * as phenopackets from './domain/phenopackets';
import * as aggregations from './domain/aggregations';
import * as admin from './domain/admin';
import * as publications from './domain/publications';
import * as auth from './domain/auth';
import * as hpo from './domain/hpo';
import * as clinical from './domain/clinical';
import * as variants from './domain/variants';
import * as reference from './domain/reference';
import * as variantAnnotation from './domain/variant_annotation';
import * as search from './domain/search';

export default {
  ...phenopackets,
  ...aggregations,
  ...admin,
  ...publications,
  ...auth,
  ...hpo,
  ...clinical,
  ...variants,
  ...reference,
  ...variantAnnotation,
  ...search,
  client: apiClient,
};
```

**Verify file size:**

```bash
wc -l frontend/src/api/index.js
# Expect: ≤ 100 lines (aggregator only)
```

- [ ] **Step 6: Write the transport test**

Create `frontend/tests/unit/api/transport.spec.js`:

```javascript
// Wave 5b Task 12: refresh-queue integrity guard.
//
// scope doc §5 R5 mitigation 3: fires 5 concurrent 401 responses and
// asserts the refresh endpoint is called exactly once.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';

import { apiClient } from '@/api/transport';

describe('transport refresh queue', () => {
  let mock;

  beforeEach(() => {
    mock = new MockAdapter(apiClient);
    localStorage.setItem('access_token', 'stale-token');
    localStorage.setItem('refresh_token', 'refresh-value');
  });

  afterEach(() => {
    mock.restore();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('refreshes the token exactly once under 5 concurrent 401s', async () => {
    // Mock the authStore's refreshAccessToken — transport imports it dynamically
    const refreshSpy = vi.fn(async () => 'new-access-token');
    vi.doMock('@/stores/authStore', () => ({
      useAuthStore: () => ({ refreshAccessToken: refreshSpy }),
    }));

    // Every /probe request returns 401 once (which triggers refresh + retry);
    // after retry, return 200.
    let probeCallCount = 0;
    mock.onGet('/probe').reply(() => {
      probeCallCount += 1;
      if (probeCallCount <= 5) {
        return [401, { detail: 'expired' }];
      }
      return [200, { ok: true }];
    });

    // Fire 5 concurrent requests
    const results = await Promise.allSettled(
      Array.from({ length: 5 }, () => apiClient.get('/probe'))
    );

    // refreshAccessToken must have been called exactly once — this is
    // the thunder-herd guard
    expect(refreshSpy).toHaveBeenCalledTimes(1);

    // Every caller should have received a resolved response
    expect(results.every((r) => r.status === 'fulfilled')).toBe(true);
  });
});
```

**Note:** `axios-mock-adapter` may not already be a dev dependency. Add it with `npm install --save-dev axios-mock-adapter` if not. Check existing frontend tests for prior usage of MSW or fetch mocks — if the project uses MSW (Mock Service Worker), adapt this test to use the existing mocking infrastructure instead of introducing a new dependency.

- [ ] **Step 7: Write the session test**

Create `frontend/tests/unit/api/session.spec.js`:

```javascript
// Wave 5b Task 12: session.js is the single source of truth for token storage.
import { describe, it, expect, beforeEach } from 'vitest';

import {
  getAccessToken,
  getRefreshToken,
  persistTokens,
  clearTokens,
} from '@/api/session';

describe('session storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('round-trips tokens through localStorage', () => {
    persistTokens({ accessToken: 'a1', refreshToken: 'r1' });
    expect(getAccessToken()).toBe('a1');
    expect(getRefreshToken()).toBe('r1');
  });

  it('persistTokens with a partial object preserves the other token', () => {
    persistTokens({ accessToken: 'a1', refreshToken: 'r1' });
    persistTokens({ accessToken: 'a2' });
    expect(getAccessToken()).toBe('a2');
    expect(getRefreshToken()).toBe('r1');
  });

  it('clearTokens removes both tokens', () => {
    persistTokens({ accessToken: 'a1', refreshToken: 'r1' });
    clearTokens();
    expect(getAccessToken()).toBe(null);
    expect(getRefreshToken()).toBe(null);
  });

  it('returns null for absent tokens', () => {
    expect(getAccessToken()).toBe(null);
    expect(getRefreshToken()).toBe(null);
  });
});
```

- [ ] **Step 8: Run frontend tests**

```bash
cd frontend
npm run test -- --run 2>&1 | tail -30
```

Expected: `269 passed + 1 xfailed` plus the 5 new transport+session tests = `274 passed + 1 xfailed`.

If any existing test fails because of the import shuffle (e.g., `authStore.spec.js` imports a function that moved), update the imports in the failing spec file IN THIS COMMIT — but do NOT change the auth store's behavior. The split is pure renaming.

- [ ] **Step 9: Run frontend lint + verify no import site broke**

```bash
npm run lint 2>&1 | tail -15
# Expect: ≤ 13 warnings (no regression from entry state)

# Sanity-check every import site of @/api still resolves:
npm run build 2>&1 | tail -20
# Expect: build succeeds without module-not-found errors
```

If `npm run build` fails with `Cannot find module '@/api/...'`, an import site in a view/component expects a function that moved. Grep for the failing symbol and fix the import path — but do NOT add re-exports that the aggregator's `export *` doesn't already cover.

- [ ] **Step 10: Run backend baselines (sanity check no cross-stack regressions)**

```bash
cd ../backend
uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -5
# Expect: 10 passed
cd ..
```

- [ ] **Step 11: Commit**

```bash
git add frontend/src/api/ frontend/tests/unit/api/ frontend/package.json frontend/package-lock.json
git commit -m "$(cat <<'EOF'
refactor(frontend): split api/index.js into transport + session + domain modules

Closes Wave 5 scope doc row D1. Splits the 1009-LOC monolith at
frontend/src/api/index.js into:

  - transport.js  — axios instance + refresh-queue state (co-located
                    per scope doc §5 R5 mitigation 1)
  - session.js    — localStorage token storage (no axios dependency)
  - domain/*.js   — 11 files, one per section marker in the original:
                    phenopackets, aggregations, admin, publications,
                    auth, hpo, clinical, variants, reference,
                    variant_annotation, search
  - index.js      — rewritten as ≤100 LOC re-export aggregator preserving
                    both named exports AND the legacy default export shape

Pure refactor: no function renamed, no signature changed, no body
refactored. Every existing import site (`import { getPhenopackets }
from '@/api'` and `import API from '@/api'; API.getPhenopackets(...)`)
continues to work unchanged.

New transport.spec.js fires 5 concurrent 401 responses and asserts
the refresh endpoint is called exactly once — the thunder-herd guard
required by scope doc §5 R5 mitigation 3.

New session.spec.js covers persistTokens round-trip, partial update
preservation, clearTokens, and absent-token behavior.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Extract useSyncTask composable from AdminDashboard.vue

**Goal:** Close scope-doc row D2. `AdminDashboard.vue` (905 LOC) hosts three nearly-identical sync-polling state machines (publication, variant, genes) — each with a `xxxSyncTask` ref, `xxxSyncInProgress` ref, `xxxPollInterval` var, `startXxxSync()` function, `pollXxxSyncStatus()` function, and `startXxxPolling()` / `stopXxxPolling()` functions. Extract into a `useSyncTask(options)` composable that owns the polling state machine, and refactor the three call sites to use it. `startReferenceInit` is NOT migrated (single-shot, no polling).

**Files:**
- Create: `frontend/src/composables/useSyncTask.js`
- Create: `frontend/tests/unit/composables/useSyncTask.spec.js`
- Modify: `frontend/src/views/AdminDashboard.vue` (replace 3 inline state machines with `useSyncTask` calls)

- [ ] **Step 1: Write the composable test first**

Create `frontend/tests/unit/composables/useSyncTask.spec.js`:

```javascript
// Wave 5b Task 13: useSyncTask polling-state-machine contract.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { useSyncTask } from '@/composables/useSyncTask';

describe('useSyncTask', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('initial state is idle with no task', () => {
    const sync = useSyncTask({
      startFn: vi.fn(),
      statusFn: vi.fn(),
      onComplete: vi.fn(),
    });
    expect(sync.task.value).toBe(null);
    expect(sync.inProgress.value).toBe(false);
  });

  it('start() returns early if backend reports completed', async () => {
    const startFn = vi.fn(async () => ({
      data: { task_id: 't1', status: 'completed', message: 'done', items_to_process: 10 },
    }));
    const statusFn = vi.fn();
    const onComplete = vi.fn();

    const sync = useSyncTask({ startFn, statusFn, onComplete });
    await sync.start();
    await flushPromises();

    expect(startFn).toHaveBeenCalledTimes(1);
    expect(statusFn).not.toHaveBeenCalled();
    expect(sync.inProgress.value).toBe(false);
    expect(onComplete).toHaveBeenCalledWith({ status: 'completed', message: 'done' });
  });

  it('start() kicks off polling when task is pending, stops on completed', async () => {
    const startFn = vi.fn(async () => ({
      data: { task_id: 't1', status: 'pending', items_to_process: 100 },
    }));
    let pollCount = 0;
    const statusFn = vi.fn(async () => {
      pollCount += 1;
      return {
        data: {
          task_id: 't1',
          status: pollCount >= 3 ? 'completed' : 'running',
          progress: pollCount * 33,
          processed: pollCount * 33,
          total: 100,
          errors: 0,
        },
      };
    });
    const onComplete = vi.fn();

    const sync = useSyncTask({ startFn, statusFn, onComplete, pollIntervalMs: 100 });
    await sync.start();

    // Advance fake timers three times, each flushing the pending poll promise
    for (let i = 0; i < 3; i += 1) {
      await vi.advanceTimersByTimeAsync(100);
    }

    expect(statusFn).toHaveBeenCalled();
    expect(sync.inProgress.value).toBe(false);
    expect(onComplete).toHaveBeenCalled();
    expect(sync.task.value).toBeTruthy();
  });

  it('start() failure calls onError with the detail', async () => {
    const startFn = vi.fn(async () => {
      const err = new Error('boom');
      err.response = { data: { detail: 'rate limit' } };
      throw err;
    });
    const onError = vi.fn();

    const sync = useSyncTask({
      startFn,
      statusFn: vi.fn(),
      onComplete: vi.fn(),
      onError,
    });
    await sync.start();

    expect(onError).toHaveBeenCalledWith('rate limit');
    expect(sync.inProgress.value).toBe(false);
  });

  it('stop() clears the polling interval', async () => {
    const statusFn = vi.fn(async () => ({
      data: { status: 'running', task_id: 't1', progress: 50 },
    }));
    const sync = useSyncTask({
      startFn: vi.fn(async () => ({
        data: { task_id: 't1', status: 'pending', items_to_process: 10 },
      })),
      statusFn,
      onComplete: vi.fn(),
      pollIntervalMs: 100,
    });

    await sync.start();
    sync.stop();
    await vi.advanceTimersByTimeAsync(500);

    // statusFn should not be called after stop() — the interval is cleared
    const callCountAfterStop = statusFn.mock.calls.length;
    await vi.advanceTimersByTimeAsync(500);
    expect(statusFn.mock.calls.length).toBe(callCountAfterStop);
  });
});
```

- [ ] **Step 2: Run the failing test**

```bash
cd frontend
npm run test -- --run tests/unit/composables/useSyncTask.spec.js
```

Expected: FAIL with "Cannot find module '@/composables/useSyncTask'".

- [ ] **Step 3: Create `frontend/src/composables/useSyncTask.js`**

```javascript
// src/composables/useSyncTask.js — Wave 5b Task 13 (scope doc D2).
//
// Polling state machine shared by AdminDashboard.vue's 3 near-identical
// sync flows (publication metadata, VEP variant annotation, chr17q12
// genes sync). Extracts the duplicated code that the 2026-04-09 review
// flagged as P2 #8.
//
// Usage:
//
//   const pubSync = useSyncTask({
//     startFn: (force) => API.startPublicationSync(force),
//     statusFn: (taskId) => API.getPublicationSyncStatus(taskId),
//     onComplete: ({ status, processed }) => {
//       successMessage.value = `Publication sync completed: ${processed}`;
//     },
//     onError: (detail) => { error.value = detail; },
//     pollIntervalMs: 2000,  // default
//   });
//
//   pubSync.start(force);
//   pubSync.stop();  // called from onUnmounted
//
// The composable does NOT handle single-shot operations (startReferenceInit)
// — that flow has no polling and doesn't fit the abstraction.

import { ref, onUnmounted } from 'vue';

export function useSyncTask({
  startFn,
  statusFn,
  onComplete = () => {},
  onError = () => {},
  pollIntervalMs = 2000,
  clearTaskAfterMs = 5000,
}) {
  const task = ref(null);
  const inProgress = ref(false);
  let pollHandle = null;

  function _stopPolling() {
    if (pollHandle !== null) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  async function _poll() {
    try {
      const response = await statusFn(task.value?.task_id);
      task.value = response.data;

      const terminal = ['completed', 'failed'];
      if (terminal.includes(response.data.status)) {
        _stopPolling();
        inProgress.value = false;

        if (response.data.status === 'completed') {
          onComplete(response.data);
        } else {
          onError(response.data.message || 'sync task failed');
        }

        setTimeout(() => {
          task.value = null;
        }, clearTaskAfterMs);
      }
    } catch (err) {
      window.logService?.error('useSyncTask poll failed', { error: err.message });
    }
  }

  function _startPolling() {
    if (pollHandle !== null) return;
    pollHandle = setInterval(_poll, pollIntervalMs);
  }

  async function start(...startArgs) {
    try {
      inProgress.value = true;
      const response = await startFn(...startArgs);
      task.value = {
        task_id: response.data.task_id,
        status: response.data.status,
        progress: 0,
        processed: 0,
        total: response.data.items_to_process,
        errors: 0,
      };

      if (response.data.status === 'completed') {
        inProgress.value = false;
        task.value = null;
        onComplete(response.data);
      } else {
        _startPolling();
      }
    } catch (err) {
      inProgress.value = false;
      const detail = err.response?.data?.detail || err.message || 'sync failed';
      window.logService?.error('useSyncTask start failed', { error: detail });
      onError(detail);
    }
  }

  function stop() {
    _stopPolling();
  }

  // Auto-cleanup on unmount — callers don't have to remember
  onUnmounted(() => {
    _stopPolling();
  });

  return { task, inProgress, start, stop };
}
```

- [ ] **Step 4: Run the composable test — expect pass**

```bash
npm run test -- --run tests/unit/composables/useSyncTask.spec.js
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Refactor `AdminDashboard.vue` to use the composable**

Edit `frontend/src/views/AdminDashboard.vue`. Replace the three duplicated state-machine sections (publication, variant, genes) with `useSyncTask` calls. Keep `startReferenceInit` untouched — it's single-shot.

**Before** (publication section, ~670–731):

```javascript
const pubSyncTask = ref(null);
const pubSyncInProgress = ref(false);
let pubPollInterval = null;

const startPublicationSync = async (force = false) => { /* 25+ lines */ };
const pollPubSyncStatus = async () => { /* 20+ lines */ };
const startPubPolling = () => { /* 3 lines */ };
const stopPubPolling = () => { /* 4 lines */ };
```

**After:**

```javascript
import { useSyncTask } from '@/composables/useSyncTask';
import * as API from '@/api';

const {
  task: pubSyncTask,
  inProgress: pubSyncInProgress,
  start: startPublicationSync,
} = useSyncTask({
  startFn: (force) => API.startPublicationSync(force),
  statusFn: (taskId) => API.getPublicationSyncStatus(taskId),
  onComplete: (data) => {
    successMessage.value = `Publication sync completed: ${data.processed} publications`;
    fetchStatus();
  },
  onError: (detail) => {
    error.value = detail;
  },
});
```

Repeat for variant (lines ~733–796) and genes (lines ~824–886). Keep every template reference (`pubSyncTask`, `pubSyncInProgress`, etc.) working — the composable returns these as the same refs.

Remove the now-dead `onUnmounted(() => { stopPubPolling(); stopVarPolling(); stopGenesPolling(); })` block — `useSyncTask` handles its own cleanup.

**Verify AdminDashboard.vue LOC dropped:**

```bash
wc -l frontend/src/views/AdminDashboard.vue
# Expect: well under 800 (started at 905, should drop by ~200 as the 3
# duplicated sections collapse)
```

If it's still over 500 LOC, the scope doc exit criterion "AdminDashboard under 500 LOC after refactor" isn't met. At that point, either split more out (e.g., move the statistics cards to a separate component) or accept a partial — update the exit note accordingly.

- [ ] **Step 6: Run frontend tests**

```bash
npm run test -- --run 2>&1 | tail -20
# Expect: the 5 new composable tests pass; every existing test still passes

npm run lint 2>&1 | tail -10
# Expect: ≤ 13 warnings
```

If any existing AdminDashboard-related test fails (`frontend/tests/unit/views/AdminDashboard.spec.js` — check if it exists), update the test to call the new composable-backed API or mock `useSyncTask`.

- [ ] **Step 7: Manual smoke test**

```bash
cd ..
make hybrid-up
cd frontend && npm run dev
# In another terminal: visit http://localhost:5173/admin
# Log in as admin (or dev-admin via dev-mode), click "Sync Publications",
# watch the progress bar. Then "Sync Variants" and "Sync Genes".
# Verify: the progress bars update every 2 seconds, complete messages
# fire, and the task clears after 5 seconds.
```

Kill the dev server once verified (`ctrl-c`).

- [ ] **Step 8: Commit**

```bash
cd ..
git add frontend/src/composables/useSyncTask.js frontend/src/views/AdminDashboard.vue frontend/tests/unit/composables/useSyncTask.spec.js
git commit -m "$(cat <<'EOF'
refactor(frontend): extract useSyncTask composable from AdminDashboard.vue

Closes Wave 5 scope doc row D2 and 2026-04-09 review P2 #8.
AdminDashboard.vue hosted 3 near-identical sync polling state machines
(publication, variant, genes) with ~60 lines of duplicated code each.
Extracted to a useSyncTask composable that owns:

  - task + inProgress refs
  - start / stop functions
  - internal polling interval
  - automatic onUnmounted cleanup
  - onComplete / onError callbacks with a default clearTaskAfterMs of 5s

AdminDashboard.vue LOC drops from ~905 to ~XXX (fill in after the
refactor lands). Template references are unchanged — useSyncTask
returns the task and inProgress refs under the same names the
template already binds to.

startReferenceInit is NOT migrated — it's single-shot with no
polling and doesn't fit the abstraction.

New useSyncTask.spec.js covers: initial state, early-completion path,
polling-to-completion path, error path with detail extraction, and
manual stop() clearing the interval. Uses vi.useFakeTimers +
flushPromises for deterministic timing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Admin user management UI + exit note

**Goal:** Ship the `/admin/users` UI (scope-doc row B1) — list with role/active/verified filters + search, create dialog, edit dialog, deactivate, role change, and unlock button wired to the Task 6 endpoint. Add the `AdminUsersCard.vue` mount point on `AdminDashboard.vue`. Capture the 4 new HTTP baselines (list, create, update, delete) for the admin user endpoints (the unlock baseline was already captured in Task 6). Close the PR with the Wave 5b exit note.

**Critical invariant:** `_system_migration_` placeholder user MUST be protected. Two guards:
1. **Backend:** `delete_user` endpoint rejects with 400 if `user.username == '_system_migration_'`
2. **Frontend:** `UserListTable.vue` client-side filters out the row before rendering
3. **Backend test:** `test_auth_user_management_endpoints.py` asserts deleting `_system_migration_` returns 400
4. **Backend test:** `test_auth_user_management_endpoints.py` asserts updating `_system_migration_` with `is_active=False` returns 400

**No Resend Invite button in this PR.** The scope doc §4.2 PR 2 exit criteria are explicit: "No resend-invite control in PR 2 — not shipped, not hidden, not disabled, not stubbed. The `/auth/invite` endpoint does not exist until PR 3, and PR 2 deliberately does not ship UI that depends on an absent endpoint." Do NOT add an invite button, even disabled.

**Task 14 includes the exit note commit.** Original planning had Task 14 (UI) and Task 15 (exit note) as two commits — reconciled into one per the commit-budget discipline in the plan header.

**Files:**
- Create: `backend/tests/test_auth_user_management_endpoints.py`
- Modify: `backend/app/api/auth_endpoints.py` (add `_system_migration_` guards in `delete_user` and `update_user`)
- Create: `frontend/src/views/AdminUsers.vue`
- Create: `frontend/src/components/admin/AdminUsersCard.vue`
- Create: `frontend/src/components/admin/UserListTable.vue`
- Create: `frontend/src/components/admin/UserCreateDialog.vue`
- Create: `frontend/src/components/admin/UserEditDialog.vue`
- Create: `frontend/tests/unit/views/AdminUsers.spec.js`
- Modify: `frontend/src/views/AdminDashboard.vue` (mount `AdminUsersCard.vue`)
- Modify: `frontend/src/router/index.js` (add `/admin/users` route with `meta.requiresAdmin`)
- Modify: `frontend/src/api/domain/auth.js` (add `listUsers`, `createUser`, `updateUser`, `deleteUser`, `unlockUser` functions — used by the new view)
- Modify: `backend/tests/test_http_surface_baseline.py` (add 4 new fixture tuples for list/create/update/delete)
- Create: `backend/tests/fixtures/http_baselines/auth_users_list.json` (captured)
- Create: `backend/tests/fixtures/http_baselines/auth_users_create.json` (captured)
- Create: `backend/tests/fixtures/http_baselines/auth_users_update.json` (captured)
- Create: `backend/tests/fixtures/http_baselines/auth_users_delete.json` (captured)
- Create: `docs/refactor/wave-5b-exit.md`

- [ ] **Step 1: Write the failing backend test for `_system_migration_` protection**

Create `backend/tests/test_auth_user_management_endpoints.py`:

```python
"""Wave 5b Task 14: admin user management endpoints — full CRUD + placeholder guard."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_users_supports_role_filter(
    async_client: AsyncClient, admin_headers: dict
):
    response = await async_client.get(
        "/api/v2/auth/users?role=admin", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert all(u["role"] == "admin" for u in body)


@pytest.mark.asyncio
async def test_create_then_update_then_unlock_then_delete_user(
    async_client: AsyncClient, admin_headers: dict
):
    # Create
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "wave5b-crud-probe",
            "email": "crud-probe@hnf1b-db.local",
            "password": "ProbePass!2026",
            "full_name": "CRUD Probe",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Update — change role + full_name
    update_resp = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"role": "curator", "full_name": "CRUD Probe (promoted)"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["role"] == "curator"

    # Unlock (should be idempotent for an already-unlocked user)
    unlock_resp = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock", headers=admin_headers
    )
    assert unlock_resp.status_code == 200

    # Delete
    delete_resp = await async_client.delete(
        f"/api/v2/auth/users/{user_id}", headers=admin_headers
    )
    assert delete_resp.status_code == 204


async def _seed_system_migration_placeholder(db_session: AsyncSession):
    """Seed the _system_migration_ placeholder for Wave 5b guard tests.

    The autouse ``_isolate_database_between_tests`` fixture truncates
    the ``users`` table before every test (backend/tests/conftest.py
    ``_MUTABLE_TABLES``), so we cannot rely on the Wave 5a alembic
    migration's one-shot seed. Each guard test must add the placeholder
    itself, mirroring the pattern used by Wave 5a's
    ``test_audit_actor_fk.py::test_system_migration_placeholder_user_can_exist``.
    """
    from app.auth.password import get_password_hash
    from app.models.user import User

    placeholder = User(
        username="_system_migration_",
        email="system-migration@hnf1b-db.local",
        hashed_password=get_password_hash("placeholder-not-loginable"),
        full_name="System Migration Placeholder",
        role="viewer",
        is_active=False,
        is_verified=False,
        is_fixture_user=False,
    )
    db_session.add(placeholder)
    await db_session.commit()
    await db_session.refresh(placeholder)
    return placeholder


@pytest.mark.asyncio
async def test_delete_system_migration_user_forbidden(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """The _system_migration_ placeholder must be protected from deletion."""
    placeholder = await _seed_system_migration_placeholder(db_session)

    response = await async_client.delete(
        f"/api/v2/auth/users/{placeholder.id}", headers=admin_headers
    )
    assert response.status_code == 400
    assert "_system_migration_" in response.json()["detail"]


@pytest.mark.asyncio
async def test_deactivate_system_migration_user_forbidden(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """The _system_migration_ placeholder must be protected from deactivation."""
    placeholder = await _seed_system_migration_placeholder(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{placeholder.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "_system_migration_" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_self_delete(
    async_client: AsyncClient, admin_headers: dict
):
    """Existing Wave 4 invariant — cannot delete your own account."""
    me = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    self_id = me.json()["id"]
    response = await async_client.delete(
        f"/api/v2/auth/users/{self_id}", headers=admin_headers
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_auth_user_management_endpoints.py -v
```

Expected: `test_delete_system_migration_user_forbidden` and `test_deactivate_system_migration_user_forbidden` FAIL (the guards don't exist yet); the other tests likely PASS because the underlying CRUD is already implemented.

- [ ] **Step 3: Add the `_system_migration_` guards to auth_endpoints.py**

Edit `backend/app/api/auth_endpoints.py`. In `delete_user`, after the `get_by_id` but before the self-delete check, add:

```python
    # Wave 5b Task 14: protect the Wave 5a FK placeholder user
    if user.username == "_system_migration_":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot delete the _system_migration_ placeholder user "
                "— it is the ON DELETE SET NULL fallback for audit-actor FKs "
                "from the Wave 5a data migration."
            ),
        )
```

In `update_user`, after the `get_by_id`, add:

```python
    # Wave 5b Task 14: block deactivation of the placeholder user.
    # Any other edit (e.g., email correction) is allowed.
    if user.username == "_system_migration_" and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot deactivate the _system_migration_ placeholder user "
                "— it must remain queryable as the audit-actor FK fallback."
            ),
        )
```

- [ ] **Step 4: Run the backend test — expect pass**

```bash
uv run pytest tests/test_auth_user_management_endpoints.py -v
# Expect: all 5 tests PASS
```

- [ ] **Step 5: Add the 4 new HTTP baselines (3 as tuples + 1 dedicated test pair)**

**Harness contract reminder (Wave 5b finding #3 part 2):** `AFFECTED_ENDPOINTS` entries are **6-tuples** — `(name, auth, method, path, query_params, body)`. There is no `path_params` slot. Templated URLs that need a freshly-seeded DB row belong in dedicated test functions (the unlock pattern from Task 6 / the dev-auth pattern from Wave 5a).

Of the 4 baselines this task ships:

- `auth_users_list` — fully-resolved URL with a query string, no setup needed → **6-tuple in `AFFECTED_ENDPOINTS`**
- `auth_users_create` — fully-resolved URL with a JSON body, no setup needed → **6-tuple in `AFFECTED_ENDPOINTS`**
- `auth_users_delete` — deliberately captures the **404 shape** against a hardcoded bogus id (e.g., `999999`), so the URL is fully resolved without seeding → **6-tuple in `AFFECTED_ENDPOINTS`**
- `auth_users_update` — requires a seeded target user AND a templated URL → **dedicated `test_capture_*` / `test_verify_*` pair**, mirroring the unlock baseline from Task 6

**5a. Add 3 entries to `AFFECTED_ENDPOINTS`:**

Edit `backend/tests/test_http_surface_baseline.py`. Append three 6-tuples to the `AFFECTED_ENDPOINTS` list (after the existing `search_autocomplete` entry):

```python
    (
        "auth_users_list",
        "admin",
        "GET",
        "/api/v2/auth/users",
        {"role": "admin"},
        None,
    ),
    (
        "auth_users_create",
        "admin",
        "POST",
        "/api/v2/auth/users",
        None,
        {
            "username": "baseline-create-probe",
            "email": "baseline-create@hnf1b-db.local",
            "password": "BaselinePass!2026",
            "full_name": "Baseline Create Probe",
            "role": "viewer",
        },
    ),
    (
        "auth_users_delete",
        "admin",
        "DELETE",
        "/api/v2/auth/users/999999",
        None,
        None,
    ),
```

Note the tuple layout: `query_params` is slot 5 (a dict or None), `body` is slot 6 (a dict or None) — matching `_call`'s unpacking `name, auth, method, path, params, body = spec`. The `auth_users_list` baseline uses `{"role": "admin"}` as a `params=` kwarg (the `_call` dispatcher passes `params=params` to httpx); the old draft used `?role=admin` in the URL which worked but mixed two idioms and was inconsistent with the existing `phenopackets_list` entry that uses `{"page[size]": "3"}`.

The `auth_users_delete` tuple deliberately hits a hardcoded bogus id (`999999`) to capture the **404 shape** rather than a 204. Deleting a real user during capture would cascade into phenopacket audit rows and make the fixture non-reproducible. The 404 path exercises the same `get_by_id → raise HTTPException(404)` branch that the admin UI's delete handler surfaces.

**5b. Add a dedicated test pair for `auth_users_update`:**

Append a new block to `backend/tests/test_http_surface_baseline.py` (right after the unlock baseline block from Task 6):

```python
# ---------------------------------------------------------------------------
# Wave 5b auth/users/{id} update baseline
# ---------------------------------------------------------------------------
#
# PUT /api/v2/auth/users/{user_id} requires a seeded target user because
# the autouse _isolate_database_between_tests fixture truncates `users`
# before every test and IDs restart from 1 under RESTART IDENTITY CASCADE.
# Hardcoding `/api/v2/auth/users/1` in AFFECTED_ENDPOINTS is fragile —
# the id order depends on which fixture seeds first. Seed a target row
# explicitly inside the test.

_UPDATE_BASELINE_NAME = "auth_users_update"


async def _seed_update_target_user(db_session) -> int:
    """Insert a curator target user for the update baseline."""
    from app.auth.password import get_password_hash
    from app.models.user import User

    target = User(
        username="wave5b-baseline-update",
        email="wave5b-baseline-update@hnf1b-db.local",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        full_name="Baseline Update Target",
        role="curator",
        is_active=True,
        is_verified=True,
        is_fixture_user=False,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    return target.id


@pytest.mark.asyncio
async def test_capture_auth_users_update_baseline(
    async_client, admin_headers, db_session
):
    """Capture the PUT /auth/users/{id} response shape."""
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    user_id = await _seed_update_target_user(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"full_name": "baseline updated"},
        headers=admin_headers,
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{_UPDATE_BASELINE_NAME}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
async def test_verify_auth_users_update_baseline(
    async_client, admin_headers, db_session
):
    """Verify the PUT /auth/users/{id} response against the captured baseline."""
    baseline_path = BASELINE_DIR / f"{_UPDATE_BASELINE_NAME}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {_UPDATE_BASELINE_NAME}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    user_id = await _seed_update_target_user(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"full_name": "baseline updated"},
        headers=admin_headers,
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    assert capture["status_code"] == baseline["status_code"], (
        f"{_UPDATE_BASELINE_NAME}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], (
        f"{_UPDATE_BASELINE_NAME}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{_UPDATE_BASELINE_NAME}: normalised response body changed"
    )
```

**Volatile-key mask check:** `_VOLATILE_KEYS` at line 130 already masks `id`, `created_at`, `updated_at`, `last_login`. The list/create/update responses are all `UserResponse` bodies; every volatile field is covered. No additions to `_VOLATILE_KEYS` are needed.

**Capture:**

```bash
WAVE4_CAPTURE_BASELINE=1 uv run pytest tests/test_http_surface_baseline.py -k "capture and (auth_users_list or auth_users_create or auth_users_delete or auth_users_update)" -v
```

Expected: 4 new `.json` files under `backend/tests/fixtures/http_baselines/`. Spot-check each: `auth_users_list` has a list-of-UserResponse shape, `auth_users_create` has `status_code: 201`, `auth_users_delete` has `status_code: 404`, `auth_users_update` has `status_code: 200`. Timestamps/ids should all be `"<normalized>"`.

**Verify:**

```bash
uv run pytest tests/test_http_surface_baseline.py -k "verify and (auth_users_list or auth_users_create or auth_users_delete or auth_users_update)" -v
```

Expected: 4 passed.

- [ ] **Step 6: Write the frontend view + components**

Create `frontend/src/views/AdminUsers.vue`:

```vue
<template>
  <v-container fluid class="pa-4">
    <div class="d-flex align-center mb-4">
      <v-icon size="32" color="red" class="mr-3">mdi-account-group</v-icon>
      <div class="flex-grow-1">
        <h1 class="text-h4 font-weight-bold">User Management</h1>
        <p class="text-body-2 text-grey mt-1">Create, edit, deactivate, and unlock user accounts</p>
      </div>
      <v-btn color="primary" prepend-icon="mdi-account-plus" @click="createDialogOpen = true">
        New User
      </v-btn>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = null">
      {{ error }}
    </v-alert>
    <v-alert v-if="successMessage" type="success" variant="tonal" closable class="mb-4" @click:close="successMessage = null">
      {{ successMessage }}
    </v-alert>

    <UserListTable
      v-model:loading="loading"
      :users="users"
      @edit="openEdit"
      @unlock="handleUnlock"
      @delete="handleDelete"
      @refresh="fetchUsers"
    />

    <UserCreateDialog
      v-model="createDialogOpen"
      @created="onCreated"
    />

    <UserEditDialog
      v-model="editDialogOpen"
      :user="editTarget"
      @updated="onUpdated"
    />
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { listUsers, deleteUser as apiDeleteUser, unlockUser as apiUnlockUser } from '@/api';
import UserListTable from '@/components/admin/UserListTable.vue';
import UserCreateDialog from '@/components/admin/UserCreateDialog.vue';
import UserEditDialog from '@/components/admin/UserEditDialog.vue';

const users = ref([]);
const loading = ref(false);
const error = ref(null);
const successMessage = ref(null);

const createDialogOpen = ref(false);
const editDialogOpen = ref(false);
const editTarget = ref(null);

async function fetchUsers() {
  loading.value = true;
  try {
    const response = await listUsers();
    // Client-side filter the _system_migration_ placeholder — it's a
    // system-owned row and Wave 5a's backend guard already protects it
    // from delete/deactivate. Filtering here keeps it invisible in the
    // admin UI.
    users.value = (response.data || []).filter(
      (u) => u.username !== '_system_migration_'
    );
  } catch (err) {
    error.value = err.normalized?.detail || err.message || 'Failed to load users';
    window.logService.error('AdminUsers fetchUsers failed', { error: err.message });
  } finally {
    loading.value = false;
  }
}

function openEdit(user) {
  editTarget.value = user;
  editDialogOpen.value = true;
}

async function handleUnlock(user) {
  try {
    await apiUnlockUser(user.id);
    successMessage.value = `Unlocked ${user.username}`;
    await fetchUsers();
  } catch (err) {
    error.value = err.normalized?.detail || 'Unlock failed';
  }
}

async function handleDelete(user) {
  if (!window.confirm(`Delete user ${user.username}? This cannot be undone.`)) return;
  try {
    await apiDeleteUser(user.id);
    successMessage.value = `Deleted ${user.username}`;
    await fetchUsers();
  } catch (err) {
    error.value = err.normalized?.detail || 'Delete failed';
  }
}

function onCreated(user) {
  successMessage.value = `Created ${user.username}`;
  createDialogOpen.value = false;
  fetchUsers();
}

function onUpdated(user) {
  successMessage.value = `Updated ${user.username}`;
  editDialogOpen.value = false;
  fetchUsers();
}

onMounted(() => {
  window.logService.info('AdminUsers mounted');
  fetchUsers();
});
</script>
```

Create `frontend/src/components/admin/UserListTable.vue`:

```vue
<template>
  <v-card elevation="2">
    <v-card-text>
      <v-row class="mb-2">
        <v-col cols="12" md="4">
          <v-text-field
            v-model="search"
            label="Search"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="roleFilter"
            :items="['all', 'admin', 'curator', 'viewer']"
            label="Role"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="activeFilter"
            :items="[
              { title: 'All', value: 'all' },
              { title: 'Active', value: true },
              { title: 'Inactive', value: false },
            ]"
            label="Active"
            density="compact"
            hide-details
          />
        </v-col>
        <v-col cols="12" md="2" class="text-right">
          <v-btn variant="outlined" @click="$emit('refresh')">
            <v-icon>mdi-refresh</v-icon>
          </v-btn>
        </v-col>
      </v-row>

      <v-data-table
        :headers="headers"
        :items="filteredUsers"
        :loading="loading"
        density="compact"
        items-per-page="20"
      >
        <template #item.role="{ item }">
          <v-chip size="small" :color="roleColor(item.role)" variant="tonal">
            {{ item.role }}
          </v-chip>
        </template>
        <template #item.is_active="{ item }">
          <v-icon :color="item.is_active ? 'success' : 'grey'">
            {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
          </v-icon>
        </template>
        <template #item.locked_until="{ item }">
          <v-chip v-if="item.locked_until" size="x-small" color="warning" variant="tonal">
            locked
          </v-chip>
        </template>
        <template #item.actions="{ item }">
          <v-btn icon="mdi-pencil" size="small" variant="text" @click="$emit('edit', item)" />
          <v-btn
            v-if="item.locked_until"
            icon="mdi-lock-open-variant"
            size="small"
            variant="text"
            @click="$emit('unlock', item)"
          />
          <v-btn
            icon="mdi-delete"
            size="small"
            variant="text"
            color="error"
            @click="$emit('delete', item)"
          />
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  users: { type: Array, required: true },
  loading: { type: Boolean, default: false },
});
defineEmits(['edit', 'unlock', 'delete', 'refresh']);

const search = ref('');
const roleFilter = ref('all');
const activeFilter = ref('all');

const headers = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Full Name', key: 'full_name', sortable: true },
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Active', key: 'is_active', sortable: true },
  { title: 'Locked', key: 'locked_until', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false },
];

const filteredUsers = computed(() => {
  return props.users.filter((u) => {
    if (search.value) {
      const s = search.value.toLowerCase();
      if (
        !u.username.toLowerCase().includes(s) &&
        !u.email.toLowerCase().includes(s) &&
        !(u.full_name || '').toLowerCase().includes(s)
      ) {
        return false;
      }
    }
    if (roleFilter.value !== 'all' && u.role !== roleFilter.value) return false;
    if (activeFilter.value !== 'all' && u.is_active !== activeFilter.value) return false;
    return true;
  });
});

function roleColor(role) {
  return { admin: 'red', curator: 'blue', viewer: 'grey' }[role] || 'grey';
}
</script>
```

Create `frontend/src/components/admin/UserCreateDialog.vue` and `UserEditDialog.vue` following the same Vuetify dialog pattern — each with a v-form, role selector, error/success handling via the API functions from `@/api/domain/auth.js`. Keep each dialog under 150 LOC.

Create `frontend/src/components/admin/AdminUsersCard.vue`:

```vue
<template>
  <v-card elevation="2" class="h-100" @click="$router.push('/admin/users')" style="cursor: pointer">
    <v-card-text class="text-center">
      <v-icon size="48" color="red" class="mb-2">mdi-account-group</v-icon>
      <div class="text-h5 font-weight-bold">User Management</div>
      <div class="text-body-2 text-grey mt-2">Create, edit, deactivate, unlock accounts</div>
      <v-btn variant="tonal" color="red" class="mt-3">Open</v-btn>
    </v-card-text>
  </v-card>
</template>
```

- [ ] **Step 7: Add the route**

Edit `frontend/src/router/index.js`. Find the existing `/admin` route and add a child or a sibling route:

```javascript
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/AdminUsers.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
```

Match the existing route-definition style in the file — if `requiresAdmin` is not a meta key already, check the navigation guard at `frontend/src/router/guards.js` or equivalent and extend it.

- [ ] **Step 8: Add API helpers to `frontend/src/api/domain/auth.js`**

Edit `frontend/src/api/domain/auth.js`. Append:

```javascript
// Wave 5b Task 14: admin user management
export const listUsers = (params = {}) => apiClient.get('/auth/users', { params });
export const createUser = (userData) => apiClient.post('/auth/users', userData);
export const getUser = (id) => apiClient.get(`/auth/users/${id}`);
export const updateUser = (id, userData) => apiClient.put(`/auth/users/${id}`, userData);
export const deleteUser = (id) => apiClient.delete(`/auth/users/${id}`);
export const unlockUser = (id) => apiClient.patch(`/auth/users/${id}/unlock`);
```

- [ ] **Step 9: Mount AdminUsersCard in AdminDashboard.vue**

Edit `frontend/src/views/AdminDashboard.vue`. Near the existing statistics cards, add a row with the new card:

```vue
      <v-row class="mb-4">
        <v-col cols="12" md="4">
          <AdminUsersCard />
        </v-col>
      </v-row>
```

And import it in the script setup:

```javascript
import AdminUsersCard from '@/components/admin/AdminUsersCard.vue';
```

- [ ] **Step 10: Write the view test**

Create `frontend/tests/unit/views/AdminUsers.spec.js`:

```javascript
// Wave 5b Task 14: AdminUsers view — basic render + filter + action triggers.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import AdminUsers from '@/views/AdminUsers.vue';
import vuetify from '@/plugins/vuetify';

vi.mock('@/api', () => ({
  listUsers: vi.fn(async () => ({
    data: [
      { id: 1, username: 'admin', email: 'a@x', full_name: 'Admin', role: 'admin', is_active: true, locked_until: null },
      { id: 2, username: 'curator', email: 'c@x', full_name: 'Curator', role: 'curator', is_active: true, locked_until: null },
      { id: 3, username: '_system_migration_', email: 's@x', full_name: 'System', role: 'viewer', is_active: false, locked_until: null },
    ],
  })),
  deleteUser: vi.fn(),
  unlockUser: vi.fn(),
}));

describe('AdminUsers view', () => {
  beforeEach(() => {
    global.window.logService = { info: vi.fn(), error: vi.fn() };
  });

  it('renders the user list excluding _system_migration_', async () => {
    const wrapper = mount(AdminUsers, {
      global: {
        plugins: [createTestingPinia({ createSpy: vi.fn }), vuetify],
        stubs: ['router-link'],
      },
    });
    await flushPromises();

    const html = wrapper.html();
    expect(html).toContain('admin');
    expect(html).toContain('curator');
    expect(html).not.toContain('_system_migration_');
  });
});
```

- [ ] **Step 11: Run every test suite + baselines + make check**

```bash
# Backend
cd backend
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 1066+ passed (1061 + 5 new user-management tests)

uv run pytest tests/test_http_surface_baseline.py -k verify 2>&1 | tail -15
# Expect: 14 passed (10 from after Task 6 + 4 new fixtures)

make check 2>&1 | tail -10
cd ..

# Frontend
cd frontend
npm run test -- --run 2>&1 | tail -15
# Expect: ~280+ passed, 1 xfailed (270 entry + 5 transport/session + 5 composable + 1 new view)

npm run lint 2>&1 | tail -10
# Expect: ≤ 13 warnings

npm run build 2>&1 | tail -5
# Expect: build succeeds

# Layer 5 grep guard still holds
grep -rE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/ && echo "LEAKED" || echo "CLEAN"
# Expect: CLEAN
cd ..
```

- [ ] **Step 12: Manual smoke test**

```bash
make hybrid-up
cd backend && make dev-seed-users && cd ..
make backend  # terminal 1
make frontend # terminal 2
# Visit http://localhost:5173/login, dev-login as dev-admin
# Navigate to /admin/users:
#   - List loads (including dev-admin, dev-curator, dev-viewer, any other seeded users)
#   - _system_migration_ is NOT in the list
#   - Click "New User", create a probe user, confirm success
#   - Edit the probe user — change role to curator, save
#   - Click delete, confirm — user disappears from list
#   - Try deleting the dev-admin user from the list UI — the backend
#     returns 400 (cannot self-delete) which surfaces as an error alert
# Check /admin — AdminUsersCard renders and navigates to /admin/users
```

Kill the dev servers once verified.

- [ ] **Step 13: Write the exit note**

Create `docs/refactor/wave-5b-exit.md`. Follow the Wave 5a exit note template (`docs/refactor/wave-5a-exit.md`):

```markdown
# Wave 5b Exit Note

**Date:** 2026-04-XX (fill in)
**Branch:** `chore/wave-5b-user-management` (sibling worktree)
**Target:** `main` (merge via PR)
**Entry commit:** `eb7d0c7` (Wave 5a merge) + post-merge fix commits `eed0882`, `df74567`

## Test counts — entry vs exit

| Stage | Backend | Frontend |
|-------|---------|----------|
| **Entry** (main after Wave 5a + fixes) | 1001 passed / 10 skipped / 3 xfailed | 269 passed + 1 xfailed (270 total) |
| **Exit** (Wave 5b head) | XXXX passed / YY skipped / 3 xfailed | ZZZ passed + 1 xfailed (ZZZ+1 total) |
| Delta | +XX | +YY |

## HTTP baseline fixtures

- **Entry:** 9 (8 Wave 4 + 1 Wave 5a dev_login_as_admin)
- **Exit:** 14 (+5: auth_users_list, auth_users_create, auth_users_update, auth_users_delete, auth_users_unlock)
- `-k verify`: 14/14 pass

## What landed (14 commits)

1. `<hash>` — **chore(ci): enforce make check hygiene via pre-commit hook + CI gate.** Closes Wave 5a exit follow-up #10.
2. `<hash>` — **fix(db): import all ORM models in alembic env.py + filter raw-SQL tables.** Closes Wave 5a exit follow-up #1. Unblocks Wave 5c credential_tokens autogenerate.
3. `<hash>` — **fix(backend): plug soft-delete leak in variant_query_builder raw-SQL CTEs.** Closes Wave 5a exit follow-up #2.
4. `<hash>` — **fix(backend): raise ValueError from audit.py instead of assert + handle in service.** Closes Wave 5a exit follow-up #3.
5. `<hash>` — **docs(backend): update stale wave4_http_baselines reference in admin endpoints.** Closes Wave 5a exit follow-up #8.
6. `<hash>` — **feat(api): add PATCH /auth/users/{id}/unlock endpoint + baseline.** Scope doc B2.
7. `<hash>` — **refactor(api): split UserUpdate into UserUpdateAdmin + UserUpdatePublic (BOPLA).** Closes OWASP API3 for user surface. Scope doc F-top-1.
8. `<hash>` — **test(auth): add explicit BFLA authorization matrix for admin routes.** First of three behavior-preserving BFLA commits (scope doc §5 R4).
9. `<hash>` — **refactor(auth): apply router-level BFLA guards on /auth/users + /admin.** Second of three. Scope doc F-top-2.
10. `<hash>` — **refactor(auth): remove per-endpoint require_admin guards now covered at router level.** Third of three.
11. `<hash>` — **refactor(auth): migrate passlib → pwdlib with verify-and-rehash.** Scope doc F-top-3.
12. `<hash>` — **refactor(frontend): split api/index.js into transport + session + domain modules.** Scope doc D1.
13. `<hash>` — **refactor(frontend): extract useSyncTask composable from AdminDashboard.vue.** Scope doc D2.
14. `<hash>` — **feat(frontend): admin user management UI + _system_migration_ guard + exit note.** Scope doc B1. Includes this exit note.

## Exit criteria (all green)

- [x] `/admin/users` route renders: list with role/active filters + search, create dialog, edit dialog, deactivate, role change, unlock button — **no resend-invite button** (deferred to Wave 5c per scope doc)
- [x] `PATCH /api/v2/auth/users/{id}/unlock` covered by `test_auth_unlock_endpoint.py` (3 tests)
- [x] BOPLA: `UserUpdatePublic` excludes role/is_active/is_superuser/refresh_token — durable contract in `test_auth_bopla_schemas.py`
- [x] BFLA: router-level `require_admin` on `/auth/users/*` sub-router + `/admin/*` aggregator, per-endpoint guards removed; `test_admin_route_authorization.py` matrix green through all three commits
- [x] pwdlib: `$2b$12$...` legacy hashes verify + rehash on first login (test_pwdlib_rehash.py)
- [x] `frontend/src/api/index.js` is now ≤100 LOC aggregator; 11 domain modules + transport + session
- [x] `useSyncTask` composable replaces 3 near-identical polling state machines in AdminDashboard.vue
- [x] HTTP baselines extended with 5 new fixtures; 14/14 verify tests pass
- [x] `_system_migration_` placeholder user protected from delete AND deactivate (backend guards + frontend client filter)
- [x] Backend `make check` green
- [x] Frontend `make check` green
- [x] `docs/refactor/tech-debt.md` gains 1 new entry (pwdlib bcrypt verifier fallback)

## Wave 5a invariants preserved

- [x] All 9 entry-state HTTP baselines pass on the exit commit
- [x] Layer 1-5 dev-mode defense operational: `make dev-seed-users` works, `grep -r dev-admin dist/` empty on prod build, Layer 5 CI jobs still green
- [x] `users.is_fixture_user` column unchanged (nullable=False default=False)
- [x] Global soft-delete filter still scoped to Phenopacket ORM only (widening was NOT performed — Task 3 fixed the raw-SQL CTEs that went around the filter)

## Commit-budget accounting

- **Scope doc §7 R7 cap:** 14 commits
- **Actual:** 14 commits (at cap)
- No overflow commits required.

## Deferred to Wave 5c or later

- Wave 5a exit follow-up #4 (logger.critical in _refuse_dev_auth_in_prod validator)
- Wave 5a exit follow-up #5 (_register_soft_delete_filter idempotency guard)
- Wave 5a exit follow-up #7 (dev_endpoints.py docstring layer numbering consistency)

All three are non-blocking hygiene items. Folded into a future hygiene sweep or addressed opportunistically in Wave 5c.

## Entry conditions for Wave 5c

- [x] Admin user management UI available; curators can be onboarded through the UI before Wave 5c ships the invite flow
- [x] pwdlib Argon2id in place — Wave 5c password-reset / invite-accept flows use it from day one
- [x] BOPLA schemas (UserUpdatePublic) ready for Wave 5c identity-lifecycle consumption
- [x] Alembic autogenerate works cleanly — Wave 5c credential_tokens migration can use it
- [x] `api/index.js` split — Wave 5c adds `domain/auth.js` functions for the 5 new endpoints without re-bloating a monolith

**Wave 5b is done.**
```

- [ ] **Step 14: Run the final verification**

```bash
cd backend && make check 2>&1 | tail -10
cd ..
cd frontend && make check 2>&1 | tail -10
cd ..

git log --oneline main..chore/wave-5b-user-management | wc -l
# Expect: 14 commits

git diff --stat main..chore/wave-5b-user-management | tail -1
# Record file/line counts

git status --short
# Expect: ??  .codex
#         ??  .benchmarks  (if present)
#         ??  docs/refactor/wave-4-kickoff-prompt.md
#         ??  docs/reviews/2026-04-11-platform-readiness-review.md
#         ??  docs/reviews/codebase-best-practices-review-2026-04-09.md
#         (and nothing else — NO untracked files from Wave 5b work)
```

- [ ] **Step 15: Commit**

```bash
git add backend/app/api/auth_endpoints.py backend/tests/test_auth_user_management_endpoints.py backend/tests/test_http_surface_baseline.py backend/tests/fixtures/http_baselines/auth_users_list.json backend/tests/fixtures/http_baselines/auth_users_create.json backend/tests/fixtures/http_baselines/auth_users_update.json backend/tests/fixtures/http_baselines/auth_users_delete.json frontend/src/views/AdminUsers.vue frontend/src/views/AdminDashboard.vue frontend/src/components/admin/ frontend/src/router/index.js frontend/src/api/domain/auth.js frontend/tests/unit/views/AdminUsers.spec.js docs/refactor/wave-5b-exit.md

git commit -m "$(cat <<'EOF'
feat(frontend): admin user management UI + _system_migration_ guard + exit note

Closes Wave 5 scope doc row B1 and concludes Wave 5b PR 2.

Backend:
  - auth_endpoints.py: delete_user + update_user now refuse operations
    on the _system_migration_ placeholder user (protects the Wave 5a
    audit-actor FK fallback from admin mistakes)
  - 5 new user-management tests: list filter, full CRUD round-trip,
    placeholder delete guard, placeholder deactivate guard, self-delete
  - 4 new HTTP baselines captured: auth_users_list, auth_users_create,
    auth_users_update, auth_users_delete

Frontend:
  - AdminUsers.vue view at /admin/users with AppDataTable, role/active
    filters, search, create/edit dialogs, unlock button, delete with
    confirmation. Client-side filters _system_migration_ from display
  - AdminUsersCard.vue mount point on AdminDashboard for discovery
  - UserListTable, UserCreateDialog, UserEditDialog as standalone
    components (each under 150 LOC)
  - @/api/domain/auth.js gains listUsers/createUser/updateUser/
    deleteUser/unlockUser
  - AdminUsers.spec.js: renders the list excluding placeholder

NO resend-invite button — scope doc §4.2 explicit: "not shipped, not
hidden, not disabled, not stubbed". Wave 5c ships it fresh along with
the /auth/invite endpoint.

Wave 5b exit note at docs/refactor/wave-5b-exit.md records all 14
commits, exit criteria, Wave 5a invariant preservation, and entry
conditions for Wave 5c.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 16: Push and create PR**

```bash
git push -u origin chore/wave-5b-user-management

gh pr create --title "chore(wave-5b): admin user management + BFLA/BOPLA + pwdlib" --body "$(cat <<'EOF'
## Summary

Wave 5 PR 2 — admin user management. Implements Bundle B (admin user CRUD +
unlock), OWASP API3 (BOPLA) + API5 (BFLA) hardening on the user-management
surface, passlib → pwdlib migration with transparent rehash-on-verify,
the frontend/src/api/index.js split (1009 → ≤100 LOC aggregator + 13
modules), the useSyncTask composable extraction from AdminDashboard.vue,
and five Wave 5a exit-note follow-up hygiene items.

Scope doc: `docs/superpowers/plans/2026-04-11-wave-5-scope.md` §4.2 PR 2
Implementation plan: `docs/superpowers/plans/2026-04-XX-wave-5b-user-management-plan.md`
Exit note: `docs/refactor/wave-5b-exit.md`

## Commits

14 atomic commits — hygiene sweep → unlock endpoint → BOPLA schemas →
3-commit BFLA migration → pwdlib → api split → useSyncTask → admin UI + exit.

## Test plan

- [ ] `cd backend && make check` — XXXX passing
- [ ] `cd frontend && make check` — ZZZ passing, ≤13 lint warnings
- [ ] `uv run pytest tests/test_http_surface_baseline.py -k verify` — 14/14 green
- [ ] `uv run pytest tests/test_admin_route_authorization.py` — BFLA matrix green
- [ ] `uv run pytest tests/test_pwdlib_rehash.py` — legacy bcrypt verify + rehash to Argon2id
- [ ] `uv run pytest tests/test_alembic_env_autogenerate.py` — clean diff vs live DB
- [ ] Manual: log in as dev-admin, visit /admin/users, create + edit + unlock + delete a probe user
- [ ] Manual: try to delete _system_migration_ in the UI → 400 error alert surfaces
- [ ] Production build grep `grep -rE "dev/login-as|DevQuickLogin|dev-admin" dist/` → empty (Wave 5a Layer 5 preserved)

## Wave 5a invariants preserved

Every Wave 5a HTTP baseline still passes. Dev-mode 5-layer defense still
operational. `is_fixture_user` column unchanged. Global soft-delete filter
still scoped to Phenopacket. `_system_migration_` user protected from
delete and deactivate.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Plan execution summary

After all 14 tasks commit cleanly and the PR is open, you have:

- 14 commits at the scope doc §7 R7 cap (no overflow)
- `main` unchanged (PR targets main but isn't merged yet)
- `chore/wave-5b-user-management` branch pushed to origin
- A PR ready for review
- The untracked review files (`docs/reviews/2026-04-11-platform-readiness-review.md`, `docs/reviews/codebase-best-practices-review-2026-04-09.md`, `docs/refactor/wave-4-kickoff-prompt.md`) still untracked

**Wave 5a invariants you preserved (verify EACH at PR time):**

1. All 9 Wave 5a-era HTTP baselines still pass on the exit commit
2. Dev-mode 5-layer defense operational: `ENABLE_DEV_AUTH=true` + `ENVIRONMENT=development` still gates the dev router; `make dev-seed-users` still works; Layer 5 grep on prod bundle still returns empty
3. `users.is_fixture_user` column definition unchanged (`nullable=False default=False`)
4. `_system_migration_` placeholder user still exists AND is protected from delete/deactivate by new Wave 5b guards (it was protected from delete-via-ON-DELETE-CASCADE in Wave 5a; Wave 5b adds the explicit admin-endpoint guards)
5. Global soft-delete filter in `backend/app/database.py` still scoped to the `Phenopacket` ORM entity only — Task 3 closed the raw-SQL gap without widening the ORM filter

**Next step:** wait for PR review. On merge, tear down the worktree:

```bash
cd ~/development/hnf1b-db
git fetch origin
git pull --ff-only origin main
git worktree remove ~/development/hnf1b-db.worktrees/chore-wave-5b-user-management
git worktree prune
```

Then Wave 5c can start — create the next worktree against fresh main and follow `docs/superpowers/plans/YYYY-MM-DD-wave-5c-identity-lifecycle-plan.md` (written by a separate writing-plans session after this PR merges).

---

## Hand-back checklist (for the reviewer of THIS plan document)

Before handing this plan to `superpowers:subagent-driven-development` or `superpowers:executing-plans`:

- [ ] Commit budget fits scope doc §7 R7 cap (14 commits) ✅
- [ ] Every Wave 5a invariant listed in the header is preserved by the task sequence
- [ ] Wave 5a follow-up items #1, #2, #3, #10 are folded in (user's default list) — Tasks 2, 3, 4, 1 respectively
- [ ] Wave 5a follow-up item #8 added (stale wave4_http_baselines docstring) — Task 5
- [ ] Wave 5a follow-ups #4, #5, #7 explicitly deferred with rationale in exit note
- [ ] Each task has: goal, files (exact paths), numbered TDD steps with code blocks, expected verification output, HEREDOC commit message
- [ ] No placeholders (TBD / TODO / "similar to Task N") — grep the plan after writing
- [ ] Worktree setup section uses sibling layout per CLAUDE.md
- [ ] HTTP baseline count accounting: 9 entry → 10 after Task 6 → 14 after Task 14 ✅
- [ ] Test count accounting: 1001 entry → ~1066 exit (+~65 backend); 270 entry → ~286 exit (+~16 frontend)
- [ ] Commit ordering follows refactor → schema → behavior → decomposition → UI → docs convention
- [ ] BFLA refactor is a three-commit sequence (Tasks 8/9/10) for clean git revert granularity
- [ ] Hand-back to user BEFORE spawning execution subagents

**Do NOT start Wave 5c** — identity lifecycle (credential tokens, invite/reset/verify) gets its own plan-writing session after Wave 5b merges.

