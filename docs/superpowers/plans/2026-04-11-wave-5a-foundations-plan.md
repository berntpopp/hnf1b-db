# Wave 5 PR 1 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Wave 5 Bundle A foundations + the critical v-html XSS fix on `main` as a single reviewable PR, establishing the schema + behavior baseline every downstream Wave 5 PR depends on.

**Architecture:** 13 atomic commits on `chore/wave-5a-foundations` in a sibling worktree at `~/development/hnf1b-db.worktrees/chore-wave-5a-foundations/`. Commit ordering follows the refactor → schema → behavior → dev-mode layers → docs convention from the scope doc §7: commit 1 is a pure directory rename, commits 2–3 are Alembic schema migrations, commit 4 is the audit-on-create behavior fix, commits 5–6 are the DELETE revision check and soft-delete global filter, commit 7 is the v-html audit, commits 8–12 are the dev-mode quick-login 5-layer gating, commit 13 is the wave-5a exit note. Each commit is independently reversible.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest + pytest-asyncio, Vue 3, Vuetify 3, Vitest, DOMPurify. Uses existing patterns — don't introduce new frameworks.

**Upstream source of truth:** `docs/superpowers/plans/2026-04-11-wave-5-scope.md` (committed on main at `7c5d079`). Refer back to the scope doc for rationale, risk discussion, and exit criteria cross-checks.

**Entry state:** `main` at commit `7c5d079` (after scope doc fixes) — 907 backend tests passing, 9 skipped, 3 xfailed; frontend make check green with 23 pre-existing lint warnings; 8 HTTP baselines at `backend/tests/fixtures/wave4_http_baselines/`.

**Exit state:** `chore/wave-5a-foundations` merged to `main`. Backend test count ~937 (907 + ~30 new). Frontend lint warnings ≤ 23. HTTP baselines directory renamed to `http_baselines/` and one new fixture for `/api/v2/dev/login-as/{username}` (gated behind `ENABLE_DEV_AUTH=true`). No regressions in any existing baseline fixture.

---

## Worktree setup (do this once before Task 1)

```bash
# From ~/development/hnf1b-db (main branch)
git fetch origin
git pull --ff-only origin main

# Verify entry state
git log --oneline -3
# Expect: 7c5d079 docs(plans): resolve 3 Wave 5 scope-doc inconsistencies...
#         f93f5c0 docs(plans): add Wave 5 scope...
#         6c5d673 Merge pull request #232 ...

# Create sibling worktree per CLAUDE.md convention
git worktree add ~/development/hnf1b-db.worktrees/chore-wave-5a-foundations -b chore/wave-5a-foundations
cd ~/development/hnf1b-db.worktrees/chore-wave-5a-foundations

# Install dependencies (worktrees start with no untracked files)
cd backend && uv sync --group test && cd ..
cd frontend && npm install && cd ..

# Verify baseline test state
cd backend && uv run pytest -q --no-header 2>&1 | tail -5
# Expect: 907 passed, 9 skipped, 3 xfailed
cd ..
cd frontend && npm run test -- --run 2>&1 | tail -10
cd ..

# Start hybrid services (if not already up)
make hybrid-up
```

All subsequent tasks run from `~/development/hnf1b-db.worktrees/chore-wave-5a-foundations/`.

---

## File structure

This PR creates and modifies the following files. Files are grouped by concern, not by task, so you can see the complete shape before implementing any single task.

### New files

```
backend/app/api/dev_endpoints.py                                   # Task 9
backend/scripts/seed_dev_users.py                                  # Task 10
backend/alembic/versions/<hex>_add_is_fixture_user.py              # Task 2 (alembic revision generates hex)
backend/alembic/versions/<hex>_fk_audit_actor.py                   # Task 3 (alembic revision generates hex)
backend/tests/test_phenopackets_audit_on_create.py                 # Task 4
backend/tests/test_phenopackets_delete_revision.py                 # Task 5
backend/tests/test_audit_actor_fk.py                               # Task 3
backend/tests/test_soft_delete_global_filter.py                    # Task 6
backend/tests/test_dev_endpoints.py                                # Task 9
backend/tests/test_config_refuses_dev_auth_in_prod.py              # Task 8
backend/tests/test_seed_dev_users.py                               # Task 10
frontend/src/components/auth/DevQuickLogin.vue                     # Task 11
frontend/tests/unit/utils/sanitize.spec.js                         # Task 7
frontend/tests/unit/components/auth/DevQuickLogin.spec.js          # Task 11
docs/refactor/wave-5a-exit.md                                      # Task 13
```

### Renamed files

```
backend/tests/fixtures/wave4_http_baselines/  →  backend/tests/fixtures/http_baselines/   # Task 1
```

### Modified files

```
backend/app/phenopackets/models.py                         # Tasks 3, 4 (FK columns + audit create)
backend/app/phenopackets/services/phenopacket_service.py   # Tasks 3, 4, 5 (signature + audit-on-create + revision check)
backend/app/phenopackets/repositories/phenopacket_repository.py  # Tasks 3, 6 (JOIN + soft-delete filter)
backend/app/phenopackets/routers/crud.py                   # Tasks 4, 5 (pass current_user.id through)
backend/app/phenopackets/query_builders.py                 # Task 3 (response field lookups)
backend/app/utils/audit.py                                 # Task 3 (changed_by_id signature)
backend/app/models/user.py                                 # Task 2 (is_fixture_user column)
backend/app/database.py                                    # Task 6 (soft-delete query event listener)
backend/app/core/config.py                                 # Task 8 (environment + enable_dev_auth)
backend/app/main.py                                        # Task 9 (conditional dev router mount)
backend/Makefile                                           # Task 10 (dev-seed-users target)
Makefile                                                   # Task 10 (root dev-seed-users passthrough)
backend/tests/test_http_surface_baseline.py                # Task 1 (path constant rename)
backend/tests/conftest.py                                  # Task 9 (dev_auth_client fixture)
frontend/src/views/About.vue                               # Task 7 (sanitize v-html)
frontend/src/views/FAQ.vue                                 # Task 7 (sanitize v-html)
frontend/src/views/Login.vue                               # Task 11 (conditional DevQuickLogin import)
frontend/src/stores/authStore.js                           # Task 11 (devLoginAs action, DEV-gated)
.github/workflows/ci.yml                                   # Task 12 (3 Layer 5 grep jobs)
docker-compose.prod.yml                                    # Task 12 (ENVIRONMENT=production explicit)
README.md                                                  # Task 12 (dev-mode quick-login paragraph)
```

### Responsibilities

- **`dev_endpoints.py`** — dev-only `/api/v2/dev/login-as/{username}` endpoint, only mounted when `settings.enable_dev_auth and settings.environment == "development"`. Module-level `assert` crashes on accidental import in non-dev (Layer 2). Loopback-only `Depends` guard. No password verification for fixture users.
- **`seed_dev_users.py`** — standalone script that seeds three fixture users (`dev-admin`, `dev-curator`, `dev-viewer`). Refuses to run outside dev. Called from `make dev-seed-users`.
- **`DevQuickLogin.vue`** — dev-only component with three buttons (admin / curator / viewer). Rendered only when `import.meta.env.DEV` is true. Dynamically imported so Rollup DCE-eliminates it from prod builds.
- **`phenopacket_service.py`** — gains `actor_id: int` parameter in `create` / `update` / `soft_delete` (replacing `actor: str`), adds `create_audit_entry()` call to `create()`, adds `revision` check to `soft_delete()`.
- **`audit.py`** — `create_audit_entry()` takes `changed_by_id: int` instead of `changed_by: str`; internal SQL references the new FK column.
- **`database.py`** — gains a SQLAlchemy `do_orm_execute` event listener that transparently adds `Phenopacket.deleted_at.is_(None)` to SELECT statements unless `execution_options(include_deleted=True)` is passed.

---

## Conventions

- **TDD everywhere.** Write the failing test first, watch it fail, write the minimal implementation, watch it pass, commit. No exceptions.
- **One commit per task.** Task N = commit N. If a task requires more than one commit, STOP and split the task.
- **Exact file paths.** Never "the file that handles X" — always `backend/app/phenopackets/routers/crud.py:194`.
- **Verification commands must match.** If a step says `uv run pytest tests/test_foo.py::test_bar -v` and expected output is `PASSED`, and instead you see `FAILED`, you read the error before moving on. Do NOT proceed to the next step on red.
- **HTTP baselines are law.** Every task ends with a green verify run on `test_http_surface_baseline.py -k verify`. If baseline drift is intentional (e.g., response keys changed), capture the new baseline in the SAME commit that introduces the drift, not as a separate fix-up.
- **Commit message format:** `<type>(<scope>): <description>` per CLAUDE.md Conventional Commits section. Examples below in each task's commit step.
- **Always run the full `make check` on each affected stack before committing.** `cd backend && make check` for backend changes; `cd frontend && make check` for frontend changes; both for tasks that touch both.

---

## Task 1: Rename HTTP surface baseline fixtures directory

**Goal:** Move `backend/tests/fixtures/wave4_http_baselines/` to `backend/tests/fixtures/http_baselines/` (and update the path constant in the test file) so future waves don't need to cascade-rename. This is a pure refactor — zero logic changes, zero test behavior changes.

**Files:**
- Rename: `backend/tests/fixtures/wave4_http_baselines/` → `backend/tests/fixtures/http_baselines/`
- Modify: `backend/tests/test_http_surface_baseline.py:55` (`BASELINE_DIR` constant)

**Why this is commit 1:** It's the lowest-risk commit in the PR. Rename a directory, update one string literal, verify the 8 existing verify tests still pass. If this commit breaks anything, it's isolated.

- [ ] **Step 1: Rename the directory with `git mv`**

```bash
git mv backend/tests/fixtures/wave4_http_baselines backend/tests/fixtures/http_baselines
```

- [ ] **Step 2: Update the `BASELINE_DIR` constant**

Replace in `backend/tests/test_http_surface_baseline.py:55`:

```python
BASELINE_DIR = Path(__file__).parent / "fixtures" / "http_baselines"
```

- [ ] **Step 3: Update the module docstring reference**

The docstring at line 22 mentions `tests/fixtures/wave4_http_baselines/`. Update it to `tests/fixtures/http_baselines/`. Also update the ruff `WAVE4_CAPTURE_BASELINE` env var name reference in the docstring if you see it — keep the env var name itself as `WAVE4_CAPTURE_BASELINE` (do NOT rename the env var, that's a separate breaking change and not in scope).

- [ ] **Step 4: Run the full HTTP baseline verify suite**

```bash
cd backend
uv run pytest tests/test_http_surface_baseline.py -k verify -v
```

Expected output:

```
tests/test_http_surface_baseline.py::test_verify_http_baseline[admin_status] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[phenopackets_list] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[phenopackets_search] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[phenopackets_compare_variant_types] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[phenopackets_aggregate_summary] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[publications_list] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[reference_genes] PASSED
tests/test_http_surface_baseline.py::test_verify_http_baseline[search_autocomplete] PASSED
8 passed
```

If any baseline fails, the rename missed a reference. Stop and debug.

- [ ] **Step 5: Run full backend test suite to catch any stray reference**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
```

Expected: `907 passed, 9 skipped, 3 xfailed` (same as entry state).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/http_baselines backend/tests/test_http_surface_baseline.py
git status --short
# Expect: R  backend/tests/fixtures/wave4_http_baselines/admin_status.json -> backend/tests/fixtures/http_baselines/admin_status.json
#         (7 more R lines)
#         M  backend/tests/test_http_surface_baseline.py

git commit -m "$(cat <<'EOF'
refactor(tests): rename http baseline fixtures dir to drop wave4 prefix

Move backend/tests/fixtures/wave4_http_baselines/ to
backend/tests/fixtures/http_baselines/ and update the BASELINE_DIR
constant in test_http_surface_baseline.py. Pure rename — zero logic
changes. Future waves will extend this directory instead of cascading
the wave-prefix.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `is_fixture_user` BOOLEAN column to users table

**Goal:** Add a `is_fixture_user BOOLEAN NOT NULL DEFAULT FALSE` column to `users` so the dev-mode quick-login endpoint (Task 9) has a positive gate beyond just matching the username. This is Layer 3 of the dev-mode 5-layer defense: even if someone in prod happens to have `username='dev-admin'`, they can't be targeted by `/dev/login-as/dev-admin` because `is_fixture_user=False`.

**Files:**
- Modify: `backend/app/models/user.py:15-104`
- Create: `backend/alembic/versions/<hex>_add_is_fixture_user.py` (alembic-generated hex prefix)

**Why this is commit 2 (before FK-ify):** Simpler migration, lower risk, smaller diff, nothing downstream depends on it. Good "warm-up" schema commit.

- [ ] **Step 1: Add the `is_fixture_user` column to the User model**

Edit `backend/app/models/user.py` — inside the `User` class, after `is_verified` at line 57, add:

```python
    is_fixture_user: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=False,
        comment="True only for seeded dev-mode fixture users; must be FALSE in prod",
    )
```

The default=False and nullable=False are critical — they mean existing rows automatically get FALSE during the migration.

- [ ] **Step 2: Generate the Alembic migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add is_fixture_user to users"
```

Expected output:

```
Generating /home/.../backend/alembic/versions/<hex>_add_is_fixture_user_to_users.py ... done
```

Note the generated hex prefix — you'll see it in the filename.

- [ ] **Step 3: Review the generated migration**

Open the new file at `backend/alembic/versions/<hex>_add_is_fixture_user_to_users.py`. Alembic may generate something like:

```python
def upgrade() -> None:
    op.add_column('users', sa.Column('is_fixture_user', sa.Boolean(), nullable=False, server_default=sa.false(), comment='...'))

def downgrade() -> None:
    op.drop_column('users', 'is_fixture_user')
```

Verify:
- `nullable=False` is set (not `nullable=True`)
- `server_default=sa.false()` or equivalent is present (critical — without this, existing rows fail the NOT NULL constraint)
- `downgrade()` drops the column
- No other spurious changes (e.g., index renames from a model drift — if you see unrelated changes, revert the ORM-side `is_fixture_user` addition, re-run, and examine)

If `server_default` is missing, add it manually:

```python
op.add_column('users', sa.Column('is_fixture_user', sa.Boolean(), nullable=False, server_default=sa.false()))
```

- [ ] **Step 4: Run the migration upgrade**

```bash
uv run alembic upgrade head
```

Expected output includes:

```
INFO  [alembic.runtime.migration] Running upgrade <prev> -> <new>, add is_fixture_user to users
```

- [ ] **Step 5: Verify the column exists via psql**

```bash
PGPASSWORD=hnf1b_pass psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "\d users" | grep is_fixture_user
```

Expected output (one line):

```
 is_fixture_user     | boolean                     |           | not null | false
```

- [ ] **Step 6: Verify downgrade is reversible**

```bash
uv run alembic downgrade -1
PGPASSWORD=hnf1b_pass psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "\d users" | grep is_fixture_user
# Expect: empty (column no longer exists)

uv run alembic upgrade head
# Expect: upgrade runs again cleanly
```

- [ ] **Step 7: Run full backend test suite**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
```

Expected: `907 passed, 9 skipped, 3 xfailed` (migration is additive; no test changes yet).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/
git commit -m "$(cat <<'EOF'
feat(db): add is_fixture_user BOOLEAN column to users table

Prerequisite for the Wave 5 dev-mode quick-login 5-layer defense
(review §5.3 Layer 3): even if a real user in prod has username
'dev-admin', they can't be targeted by /dev/login-as/dev-admin because
is_fixture_user defaults to FALSE and the dev endpoint requires TRUE.

Non-nullable with server_default=FALSE so existing rows auto-migrate.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: FK-ify audit actor columns with `_system_migration_` placeholder

**Goal:** Convert `phenopackets.created_by`, `phenopackets.updated_by`, `phenopackets.deleted_by`, and `phenopacket_audit.changed_by` from `String(100)` to nullable `BigInt FK → users.id`. Preserve existing data by mapping distinct usernames to user rows (with `_system_migration_` placeholder for values that don't map, notably the `"hnf1b-db v1.0.0"` string from the initial import). Update the ORM model, repository, service, and audit utility to use the new FK columns.

**Files:**
- Create: `backend/alembic/versions/<hex>_fk_audit_actor.py`
- Create: `backend/tests/test_audit_actor_fk.py`
- Modify: `backend/app/phenopackets/models.py` (Phenopacket, PhenopacketAudit column definitions + Pydantic schemas)
- Modify: `backend/app/phenopackets/services/phenopacket_service.py` (signature: `actor_id: int`)
- Modify: `backend/app/phenopackets/repositories/phenopacket_repository.py` (JOIN on FK when rendering)
- Modify: `backend/app/phenopackets/routers/crud.py:210, :247, :283` (pass `current_user.id`)
- Modify: `backend/app/phenopackets/query_builders.py` (lookups in build_phenopacket_response)
- Modify: `backend/app/utils/audit.py` (signature: `changed_by_id: int`, SQL column rename)

**Scope warning:** This is the highest-risk task in PR 1 (effort 4, risk 4 in the scope doc). Read every listed file top-to-bottom before touching anything.

- [ ] **Step 1: Read the complete current state of every affected file**

Before making any change, read:

```bash
# backend
cat backend/app/phenopackets/models.py | head -200
cat backend/app/phenopackets/services/phenopacket_service.py
cat backend/app/phenopackets/repositories/phenopacket_repository.py
cat backend/app/phenopackets/routers/crud.py
cat backend/app/phenopackets/query_builders.py
cat backend/app/utils/audit.py
```

You need a mental model of which code paths set and read each `*_by` column before writing the migration.

- [ ] **Step 2: Write the failing test first**

Create `backend/tests/test_audit_actor_fk.py`:

```python
"""Tests that the FK-ified audit actor columns round-trip correctly.

After the Wave 5a FK-ify migration, phenopackets.created_by_id,
.updated_by_id, .deleted_by_id, and phenopacket_audit.changed_by_id
are nullable BigInt FKs to users.id. This test verifies:

1. A new phenopacket created by an authenticated user has
   created_by_id set to that user's id (not a string).
2. The API response layer can still render the username
   (looked up via JOIN).
3. Historical rows with unmapped usernames map to the
   '_system_migration_' placeholder user.
4. The downgrade migration restores the String columns.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_system_migration_placeholder_user_exists(db_session: AsyncSession):
    """The FK migration seeded a `_system_migration_` user with is_active=False."""
    result = await db_session.execute(
        text("SELECT id, is_active, is_fixture_user FROM users WHERE username = '_system_migration_'")
    )
    row = result.fetchone()
    assert row is not None, "placeholder user not seeded by migration"
    assert row.is_active is False, "placeholder user must be inactive"
    assert row.is_fixture_user is False, "placeholder is not a fixture user"


@pytest.mark.asyncio
async def test_new_phenopacket_has_fk_created_by_id(
    async_client: AsyncClient, admin_headers: dict
):
    """POST /phenopackets sets created_by_id to the authenticated user's id."""
    payload = {
        "phenopacket": {
            "id": "test-fk-audit-001",
            "subject": {"id": "subject-001", "sex": "MALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # The response should expose created_by as a username string
    # (looked up from the FK), not as an integer id.
    assert isinstance(body.get("created_by"), str)
    assert body["created_by"] == "admin"


@pytest.mark.asyncio
async def test_audit_row_has_fk_changed_by_id(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """PUT /phenopackets/{id} writes an audit row with changed_by_id populated."""
    # First create a phenopacket
    create_payload = {
        "phenopacket": {
            "id": "test-fk-audit-002",
            "subject": {"id": "subject-002", "sex": "FEMALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    # Then update it
    update_payload = {
        **create_payload,
        "revision": 1,
        "change_reason": "test",
    }
    await async_client.put(
        "/api/v2/phenopackets/test-fk-audit-002",
        json=update_payload,
        headers=admin_headers,
    )

    # Verify the audit row has a FK changed_by_id, not a string
    result = await db_session.execute(
        text("""
            SELECT a.changed_by_id, u.username
            FROM phenopacket_audit a
            JOIN users u ON u.id = a.changed_by_id
            WHERE a.phenopacket_id = 'test-fk-audit-002'
            ORDER BY a.changed_at DESC
            LIMIT 1
        """)
    )
    row = result.fetchone()
    assert row is not None
    assert row.changed_by_id is not None
    assert row.username == "admin"
```

- [ ] **Step 3: Run the failing test**

```bash
cd backend
uv run pytest tests/test_audit_actor_fk.py -v
```

Expected: 3 tests, all FAIL with errors like `column "_system_migration_" does not exist` or `column changed_by_id does not exist` — because the migration hasn't been created yet.

- [ ] **Step 4: Generate the Alembic migration stub**

```bash
uv run alembic revision -m "fk audit actor columns"
```

Note the generated hex prefix. Open the file at `backend/alembic/versions/<hex>_fk_audit_actor_columns.py`.

- [ ] **Step 5: Write the migration — upgrade() step**

Replace the generated empty `upgrade()` and `downgrade()` with:

```python
"""fk audit actor columns

Revision ID: <hex>
Revises: <prev>
Create Date: 2026-04-11 ...

Wave 5 PR 1: FK-ify the four audit-actor columns (phenopackets.created_by,
updated_by, deleted_by + phenopacket_audit.changed_by) from String(100)
to nullable BigInt FK -> users.id. Create a placeholder `_system_migration_`
user to hold migration-origin rows (notably the "hnf1b-db v1.0.0" string
from the initial Google Sheets import).

Upgrade:
  1. Insert `_system_migration_` user row (is_active=False, is_fixture_user=False)
  2. Add nullable *_by_id BIGINT columns alongside the existing String columns
  3. Populate new columns by JOIN on users.username
  4. Fallback unmapped rows to the `_system_migration_` user id
  5. Add FK constraints on the new columns
  6. Drop the original String columns

Downgrade reverses everything: re-add String columns, reverse-JOIN via
users.username, drop FK columns, delete placeholder user.
"""
from alembic import op
import sqlalchemy as sa

revision = '<hex>'
down_revision = '<prev>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: Seed the placeholder user
    # We hash a random password with bcrypt($2b$12$...) — this user will
    # never log in, but the hashed_password column is NOT NULL on users.
    # Use a $2b$ prefix so it's structurally a valid bcrypt hash; the
    # value itself doesn't matter.
    connection.execute(sa.text("""
        INSERT INTO users (
            email, username, hashed_password, full_name, role,
            is_active, is_verified, is_fixture_user,
            failed_login_attempts, created_at
        )
        VALUES (
            'system-migration@hnf1b-db.local',
            '_system_migration_',
            '$2b$12$placeholder.no.login.ever.attempted.$2b$12$placeholder.xx',
            'System Migration Placeholder',
            'viewer',
            false,
            false,
            false,
            0,
            NOW()
        )
        ON CONFLICT (username) DO NOTHING
    """))

    # Step 2: Add new FK columns (nullable, no constraint yet — constraint
    # added in step 5 after data is populated)
    op.add_column('phenopackets', sa.Column('created_by_id', sa.BigInteger(), nullable=True))
    op.add_column('phenopackets', sa.Column('updated_by_id', sa.BigInteger(), nullable=True))
    op.add_column('phenopackets', sa.Column('deleted_by_id', sa.BigInteger(), nullable=True))
    op.add_column('phenopacket_audit', sa.Column('changed_by_id', sa.BigInteger(), nullable=True))

    # Step 3: Populate new columns from old string columns via JOIN
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET created_by_id = u.id
        FROM users u
        WHERE phenopackets.created_by = u.username
    """))
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET updated_by_id = u.id
        FROM users u
        WHERE phenopackets.updated_by = u.username
    """))
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET deleted_by_id = u.id
        FROM users u
        WHERE phenopackets.deleted_by = u.username
    """))
    connection.execute(sa.text("""
        UPDATE phenopacket_audit
        SET changed_by_id = u.id
        FROM users u
        WHERE phenopacket_audit.changed_by = u.username
    """))

    # Step 4: Fallback unmapped rows to the _system_migration_ placeholder
    # (catches `"hnf1b-db v1.0.0"` and any other non-user strings)
    placeholder_id_query = sa.text(
        "SELECT id FROM users WHERE username = '_system_migration_'"
    )
    placeholder_id = connection.execute(placeholder_id_query).scalar_one()

    connection.execute(
        sa.text("""
            UPDATE phenopackets
            SET created_by_id = :pid
            WHERE created_by_id IS NULL AND created_by IS NOT NULL AND created_by <> ''
        """),
        {"pid": placeholder_id},
    )
    connection.execute(
        sa.text("""
            UPDATE phenopackets
            SET updated_by_id = :pid
            WHERE updated_by_id IS NULL AND updated_by IS NOT NULL AND updated_by <> ''
        """),
        {"pid": placeholder_id},
    )
    connection.execute(
        sa.text("""
            UPDATE phenopackets
            SET deleted_by_id = :pid
            WHERE deleted_by_id IS NULL AND deleted_by IS NOT NULL AND deleted_by <> ''
        """),
        {"pid": placeholder_id},
    )
    connection.execute(
        sa.text("""
            UPDATE phenopacket_audit
            SET changed_by_id = :pid
            WHERE changed_by_id IS NULL AND changed_by IS NOT NULL AND changed_by <> ''
        """),
        {"pid": placeholder_id},
    )

    # Step 5: Add FK constraints
    op.create_foreign_key(
        'fk_phenopackets_created_by_id_users',
        'phenopackets', 'users',
        ['created_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_phenopackets_updated_by_id_users',
        'phenopackets', 'users',
        ['updated_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_phenopackets_deleted_by_id_users',
        'phenopackets', 'users',
        ['deleted_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_phenopacket_audit_changed_by_id_users',
        'phenopacket_audit', 'users',
        ['changed_by_id'], ['id'], ondelete='SET NULL',
    )

    # Step 6: Drop the original String columns
    op.drop_column('phenopackets', 'created_by')
    op.drop_column('phenopackets', 'updated_by')
    op.drop_column('phenopackets', 'deleted_by')
    op.drop_column('phenopacket_audit', 'changed_by')


def downgrade() -> None:
    connection = op.get_bind()

    # Step 1: Re-add String(100) columns
    op.add_column('phenopackets', sa.Column('created_by', sa.String(100), nullable=True))
    op.add_column('phenopackets', sa.Column('updated_by', sa.String(100), nullable=True))
    op.add_column('phenopackets', sa.Column('deleted_by', sa.String(100), nullable=True))
    op.add_column('phenopacket_audit', sa.Column('changed_by', sa.String(100), nullable=True))

    # Step 2: Populate from reverse-JOIN
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET created_by = u.username
        FROM users u
        WHERE phenopackets.created_by_id = u.id
    """))
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET updated_by = u.username
        FROM users u
        WHERE phenopackets.updated_by_id = u.id
    """))
    connection.execute(sa.text("""
        UPDATE phenopackets
        SET deleted_by = u.username
        FROM users u
        WHERE phenopackets.deleted_by_id = u.id
    """))
    connection.execute(sa.text("""
        UPDATE phenopacket_audit
        SET changed_by = u.username
        FROM users u
        WHERE phenopacket_audit.changed_by_id = u.id
    """))

    # Step 3: Drop FK columns
    op.drop_constraint('fk_phenopackets_created_by_id_users', 'phenopackets', type_='foreignkey')
    op.drop_constraint('fk_phenopackets_updated_by_id_users', 'phenopackets', type_='foreignkey')
    op.drop_constraint('fk_phenopackets_deleted_by_id_users', 'phenopackets', type_='foreignkey')
    op.drop_constraint('fk_phenopacket_audit_changed_by_id_users', 'phenopacket_audit', type_='foreignkey')
    op.drop_column('phenopackets', 'created_by_id')
    op.drop_column('phenopackets', 'updated_by_id')
    op.drop_column('phenopackets', 'deleted_by_id')
    op.drop_column('phenopacket_audit', 'changed_by_id')

    # Step 4: Delete placeholder user
    connection.execute(sa.text(
        "DELETE FROM users WHERE username = '_system_migration_'"
    ))
```

- [ ] **Step 6: Update the ORM models**

Edit `backend/app/phenopackets/models.py`:

Replace lines 89-104 (Phenopacket actor columns):

```python
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")

    # Soft delete fields
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when record was soft-deleted (NULL if active)",
    )
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="FK to users.id who performed the soft delete",
    )
```

Add the required imports at the top of the file:

```python
from sqlalchemy import BigInteger, Computed, DateTime, ForeignKey, Integer, String, Text, func
```

Replace line 186 (`PhenopacketAudit.changed_by`):

```python
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

Also update the Pydantic schemas in the same file — find `PhenopacketCreate` and `PhenopacketResponse` (around line 344+) and update the `created_by` / `updated_by` fields from `Optional[str]` to either:

1. Remove them entirely from request schemas (they are overridden by the authenticated actor anyway — `phenopacket_service.py:148`), OR
2. Keep them as `Optional[str]` response-only fields that the service looks up from the FK

**Decision:** option 2. Keep `created_by: Optional[str]` and `updated_by: Optional[str]` in the **response** schema only (they render as usernames via the JOIN in `build_phenopacket_response`). Remove them from **request** schemas so BOPLA can't sneak in a bad actor value. Specifically:

- `PhenopacketCreate`: remove `created_by: Optional[str] = None` field
- `PhenopacketUpdate`: remove `updated_by: Optional[str] = None` field
- `PhenopacketDelete`: leave unchanged (change_reason only)
- `PhenopacketResponse`: keep `created_by: Optional[str]` / `updated_by: Optional[str]` — these are rendered from the JOIN

Audit the Pydantic schemas carefully — there may be more fields than you expect. Read lines 340-500 of `models.py` first.

- [ ] **Step 7: Update `create_audit_entry()` in `backend/app/utils/audit.py`**

Change the function signature and SQL:

```python
async def create_audit_entry(
    db: AsyncSession,
    phenopacket_id: str,
    action: str,
    old_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    changed_by_id: int,
    change_reason: str,
) -> PhenopacketAudit:
    """Create audit trail entry for phenopacket change.

    Wave 5 PR 1 update: changed_by_id is now a FK to users.id
    (int), not a username string.
    """
    valid_actions = {"CREATE", "UPDATE", "DELETE"}
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of {valid_actions}")

    change_patch = None
    if action == "UPDATE" and old_value and new_value:
        change_patch = generate_json_patch(old_value, new_value)

    change_summary = generate_change_summary(action, old_value, new_value)

    query = text("""
        INSERT INTO phenopacket_audit
        (id, phenopacket_id, action, old_value, new_value, changed_by_id,
         change_reason, change_patch, change_summary, changed_at)
        VALUES (gen_random_uuid(), :phenopacket_id, :action, :old_value,
                :new_value, :changed_by_id, :change_reason, :change_patch,
                :change_summary, :changed_at)
        RETURNING id
    """)

    result = await db.execute(
        query,
        {
            "phenopacket_id": phenopacket_id,
            "action": action,
            "old_value": json.dumps(old_value) if old_value else None,
            "new_value": json.dumps(new_value) if new_value else None,
            "changed_by_id": changed_by_id,
            "change_reason": change_reason,
            "change_patch": json.dumps(change_patch) if change_patch else None,
            "change_summary": change_summary,
            "changed_at": datetime.now(timezone.utc),
        },
    )

    audit_id = result.scalar_one()

    # Fetch and return the created audit entry (JOIN to resolve username for display)
    fetch_query = text("""
        SELECT a.*, u.username AS changed_by_username
        FROM phenopacket_audit a
        LEFT JOIN users u ON u.id = a.changed_by_id
        WHERE a.id = :audit_id
    """)
    audit_result = await db.execute(fetch_query, {"audit_id": audit_id})
    audit_row = audit_result.fetchone()

    assert audit_row is not None, "Failed to create audit entry"

    return PhenopacketAudit(
        id=audit_row.id,
        phenopacket_id=audit_row.phenopacket_id,
        action=audit_row.action,
        old_value=audit_row.old_value,
        new_value=audit_row.new_value,
        changed_by_id=audit_row.changed_by_id,
        changed_at=audit_row.changed_at,
        change_reason=audit_row.change_reason,
        change_patch=audit_row.change_patch,
        change_summary=audit_row.change_summary,
    )
```

- [ ] **Step 8: Update `PhenopacketService` method signatures**

Edit `backend/app/phenopackets/services/phenopacket_service.py`:

Change `actor: str` → `actor_id: int` in `create`, `update`, `soft_delete`.

Replace `existing.updated_by = payload.updated_by or actor` → `existing.updated_by_id = actor_id`.
Replace `created_by=payload.created_by or actor` → `created_by_id=actor_id`.
Replace `phenopacket.deleted_by = actor` → `phenopacket.deleted_by_id = actor_id`.

Update `create_audit_entry(...)` call sites — pass `changed_by_id=actor_id` instead of `changed_by=<string>`.

**Warning:** The `update()` method currently calls `create_audit_entry(..., changed_by=existing.updated_by, ...)`. After the rename, this becomes `changed_by_id=actor_id` — note that `actor_id` is the function parameter, not `existing.updated_by_id` (which would also work but is one hop removed).

Note: `PhenopacketService.create()` still does NOT call `create_audit_entry()` — that's deliberately left for Task 4. This task only updates the signature and FK columns.

- [ ] **Step 9: Update the router to pass `current_user.id`**

Edit `backend/app/phenopackets/routers/crud.py`:

Line 210: `service.create(phenopacket_data, actor=current_user.username)` → `service.create(phenopacket_data, actor_id=current_user.id)`
Line 247: `service.update(phenopacket_id, phenopacket_data, actor=current_user.username)` → `service.update(phenopacket_id, phenopacket_data, actor_id=current_user.id)`
Line 283: `service.soft_delete(phenopacket_id, delete_request.change_reason, actor=current_user.username)` → `service.soft_delete(phenopacket_id, delete_request.change_reason, actor_id=current_user.id)`

- [ ] **Step 10: Update `build_phenopacket_response` in `query_builders.py`**

The response layer needs to render `created_by` / `updated_by` as strings (usernames) for API consumers. Read `backend/app/phenopackets/query_builders.py` first to see how the response is currently built, then update the function to JOIN on users and include the usernames.

**Important:** The response must continue to return the keys `created_by` and `updated_by` as strings, not `created_by_id` / `updated_by_id` as integers — this preserves the HTTP baseline fixture. The rename is strictly internal (column rename + FK-ify); the API surface stays identical.

One clean way to do this: change `build_phenopacket_response` to accept a resolved username map as a second parameter, OR have the repository eager-load a `User` relationship on Phenopacket and let the response builder read `phenopacket.created_by_user.username`.

**Recommended approach:** Add a SQLAlchemy `relationship` on Phenopacket:

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.user import User  # only import if no circular

# Inside Phenopacket class:
created_by_user: Mapped[Optional["User"]] = relationship(
    "User", foreign_keys=[created_by_id], viewonly=True
)
updated_by_user: Mapped[Optional["User"]] = relationship(
    "User", foreign_keys=[updated_by_id], viewonly=True
)
deleted_by_user: Mapped[Optional["User"]] = relationship(
    "User", foreign_keys=[deleted_by_id], viewonly=True
)
```

Then `build_phenopacket_response` can read `pp.created_by_user.username if pp.created_by_user else None` and put it into the response dict under the key `created_by` — preserving the existing API contract.

Check `backend/app/phenopackets/query_builders.py` for the current response shape and update accordingly.

- [ ] **Step 11: Update `PhenopacketRepository.get_by_id` to eager-load relationships**

Edit `backend/app/phenopackets/repositories/phenopacket_repository.py`:

Wrap the SELECT with `.options(selectinload(Phenopacket.created_by_user), selectinload(Phenopacket.updated_by_user), selectinload(Phenopacket.deleted_by_user))` to prevent N+1 on render.

```python
from sqlalchemy.orm import selectinload

async def get_by_id(
    self, phenopacket_id: str, *, include_deleted: bool = False
) -> Optional[Phenopacket]:
    conditions = [Phenopacket.phenopacket_id == phenopacket_id]
    if not include_deleted:
        conditions.append(Phenopacket.deleted_at.is_(None))

    stmt = (
        select(Phenopacket)
        .where(and_(*conditions))
        .options(
            selectinload(Phenopacket.created_by_user),
            selectinload(Phenopacket.updated_by_user),
            selectinload(Phenopacket.deleted_by_user),
        )
    )
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()
```

Apply the same `.options()` to `base_list_query()`, `get_batch()`, and any other method that returns `Phenopacket` for rendering.

- [ ] **Step 12: Run the migration**

```bash
uv run alembic upgrade head
```

If this fails, most likely cause: an existing row has a `created_by` / `updated_by` / `deleted_by` value that wasn't caught by the placeholder fallback. Debug with:

```bash
PGPASSWORD=hnf1b_pass psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "
  SELECT DISTINCT created_by FROM phenopackets WHERE created_by IS NOT NULL;
  SELECT DISTINCT updated_by FROM phenopackets WHERE updated_by IS NOT NULL;
  SELECT DISTINCT deleted_by FROM phenopackets WHERE deleted_by IS NOT NULL;
  SELECT DISTINCT changed_by FROM phenopacket_audit WHERE changed_by IS NOT NULL;
"
```

- [ ] **Step 13: Run the FK audit tests**

```bash
uv run pytest tests/test_audit_actor_fk.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 14: Run the full test suite**

```bash
uv run pytest -q --no-header 2>&1 | tail -10
```

Expected: ~910 passed (907 baseline + 3 new), 9 skipped, 3 xfailed.

If any existing test fails with references to `created_by` / `updated_by` / `deleted_by` / `changed_by` strings, it means you missed a call site. Common spots:
- `backend/tests/test_phenopackets_crud.py`
- `backend/tests/test_auth_integration.py`
- `backend/migration/database/storage.py` (migration script — updates `created_by` directly)

The migration script at `backend/migration/database/storage.py:70-81` needs to resolve the actor username → user id (or use the placeholder) before INSERTing. Read that file and update accordingly.

- [ ] **Step 15: Run the HTTP baseline verify suite**

```bash
uv run pytest tests/test_http_surface_baseline.py -k verify -v
```

Expected: 8 PASS. If any baseline drifts (e.g., `created_by` is now rendered as `null` instead of `"admin"`), it means the response layer isn't resolving the FK. Go back to Step 10.

- [ ] **Step 16: Verify downgrade reversibility**

```bash
uv run alembic downgrade -1
# Expect: upgrade reversed; string columns restored
uv run pytest tests/test_audit_actor_fk.py::test_system_migration_placeholder_user_exists -v
# Expect: FAIL (placeholder user deleted on downgrade)

uv run alembic upgrade head
# Expect: upgrade re-runs cleanly
uv run pytest tests/test_audit_actor_fk.py -v
# Expect: all 3 pass
```

- [ ] **Step 17: Commit**

```bash
git add -A backend/app/phenopackets backend/app/utils/audit.py backend/app/models backend/alembic/versions backend/tests/test_audit_actor_fk.py backend/migration/database/storage.py
git status --short
# Review carefully — expect ~8-10 modified files + 2 new files

git commit -m "$(cat <<'EOF'
refactor(db): FK-ify audit actor columns with system-migration placeholder

Convert phenopackets.(created_by|updated_by|deleted_by) and
phenopacket_audit.changed_by from String(100) to nullable BigInt FK ->
users.id. Preserves existing data via:

1. One-shot seed of a '_system_migration_' placeholder user
   (is_active=False, is_fixture_user=False, role=viewer)
2. Data migration JOINing existing string values against users.username
3. Fallback mapping of unmapped strings (notably "hnf1b-db v1.0.0"
   from the initial import) to the placeholder
4. FK constraints with ON DELETE SET NULL

Updated call sites:
- PhenopacketService.create/update/soft_delete now take actor_id: int
- create_audit_entry() takes changed_by_id: int, raw SQL updated
- PhenopacketRepository eager-loads {created,updated,deleted}_by_user
  relationships via selectinload to prevent N+1 on response render
- build_phenopacket_response() looks up username via the relationship
  to preserve the existing API contract (response still uses string
  usernames under keys created_by/updated_by/deleted_by)
- Router passes current_user.id instead of current_user.username

API contract unchanged — HTTP baselines pass. Downgrade tested reversible.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Emit audit row on phenopacket CREATE

**Goal:** Close the audit-on-create gap (scope doc §R1, platform review §2.2). `PhenopacketService.create()` currently adds the row and commits but never calls `create_audit_entry()`. Every other action (UPDATE, DELETE) writes an audit row. This task makes CREATE consistent.

**Files:**
- Create: `backend/tests/test_phenopackets_audit_on_create.py`
- Modify: `backend/app/phenopackets/services/phenopacket_service.py` (inject `create_audit_entry` call in `create()`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phenopackets_audit_on_create.py`:

```python
"""Wave 5a: phenopacket CREATE must emit an audit row.

Before this fix, only UPDATE and DELETE wrote audit rows; CREATE
silently skipped it, so the audit history endpoint never had an
'initial import' row for any phenopacket created through the API.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_phenopacket_emits_audit_row(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """POST /phenopackets writes a CREATE audit row with the patch structure."""
    payload = {
        "phenopacket": {
            "id": "audit-on-create-001",
            "subject": {"id": "subject-aoc-001", "sex": "MALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": "All"}}
            ],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=admin_headers
    )
    assert response.status_code == 200, response.text

    # There should be exactly ONE audit row for this phenopacket, with action=CREATE
    result = await db_session.execute(
        text("""
            SELECT action, new_value, change_summary, changed_by_id
            FROM phenopacket_audit
            WHERE phenopacket_id = 'audit-on-create-001'
        """)
    )
    rows = list(result)
    assert len(rows) == 1, f"expected 1 audit row, got {len(rows)}"
    row = rows[0]
    assert row.action == "CREATE"
    assert row.new_value is not None
    assert row.new_value["id"] == "audit-on-create-001"
    assert "Initial import" in (row.change_summary or "")
    assert row.changed_by_id is not None  # FK populated


@pytest.mark.asyncio
async def test_create_then_update_yields_two_audit_rows(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Two audit rows: the CREATE row (from this task) + the UPDATE row."""
    create_payload = {
        "phenopacket": {
            "id": "audit-on-create-002",
            "subject": {"id": "subject-aoc-002", "sex": "FEMALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    update_payload = {
        **create_payload,
        "phenopacket": {
            **create_payload["phenopacket"],
            "subject": {"id": "subject-aoc-002", "sex": "MALE"},
        },
        "revision": 1,
        "change_reason": "correcting sex",
    }
    await async_client.put(
        "/api/v2/phenopackets/audit-on-create-002",
        json=update_payload,
        headers=admin_headers,
    )

    result = await db_session.execute(
        text("""
            SELECT action
            FROM phenopacket_audit
            WHERE phenopacket_id = 'audit-on-create-002'
            ORDER BY changed_at
        """)
    )
    actions = [row.action for row in result]
    assert actions == ["CREATE", "UPDATE"]
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_phenopackets_audit_on_create.py -v
```

Expected: both tests FAIL. `test_create_phenopacket_emits_audit_row` fails with `expected 1 audit row, got 0`. The second test fails with `actions == ["UPDATE"]` (missing CREATE).

- [ ] **Step 3: Add `create_audit_entry()` call to `PhenopacketService.create()`**

Edit `backend/app/phenopackets/services/phenopacket_service.py` — inside the `create` method, after `self._repo.add(phenopacket)` but before `self._repo.commit_and_refresh(phenopacket)`, add:

```python
        self._repo.add(phenopacket)

        # Emit CREATE audit row BEFORE the commit so it lands in the same
        # transaction as the phenopacket row. If either fails, both roll back.
        try:
            await create_audit_entry(
                db=self._repo.session,
                phenopacket_id=phenopacket.phenopacket_id,
                action="CREATE",
                old_value=None,
                new_value=sanitized,
                changed_by_id=actor_id,
                change_reason=payload.change_reason or "Initial creation",
            )
        except SQLAlchemyError as exc:
            await self._repo.rollback()
            raise ServiceDatabaseError(f"Database error: {exc}") from exc

        try:
            await self._repo.commit_and_refresh(phenopacket)
        except IntegrityError as exc:
            # ... existing error handling ...
```

**Note:** `PhenopacketCreate.change_reason` does not currently exist. Check the schema — if it doesn't exist, either add it as an optional field with default `"Initial creation"` OR pass a hardcoded string. Simpler: hardcoded fallback `"Initial creation"` so the schema doesn't need updating. Use:

```python
change_reason="Initial creation",
```

- [ ] **Step 4: Run the test — expect pass**

```bash
uv run pytest tests/test_phenopackets_audit_on_create.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Run full test suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: ~912 passed

uv run pytest tests/test_http_surface_baseline.py -k verify -v
# Expect: 8 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/phenopackets/services/phenopacket_service.py backend/tests/test_phenopackets_audit_on_create.py
git commit -m "$(cat <<'EOF'
feat(backend): emit audit row on phenopacket CREATE

Closes the audit-on-create gap flagged in the Wave 5 scope doc §3.1 A2
and the 2026-04-11 platform review §2.2. PhenopacketService.create()
now calls create_audit_entry() inside the same transaction as the
phenopacket INSERT, so every phenopacket has an 'Initial import' audit
row from the moment it lands in the DB.

Prereq for any Wave 6 revision-history UI — curators need to see that
the record was created, by whom, and when, not just subsequent updates.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add revision check to DELETE

**Goal:** `PhenopacketService.soft_delete()` currently does not check the optimistic-locking `revision` field. A client holding a stale view can race a concurrent edit and accidentally delete the newer copy. Add a `revision` check mirroring the pattern in `update()`.

**Files:**
- Create: `backend/tests/test_phenopackets_delete_revision.py`
- Modify: `backend/app/phenopackets/models.py` (add `revision: Optional[int]` to `PhenopacketDelete` schema)
- Modify: `backend/app/phenopackets/services/phenopacket_service.py` (revision check in `soft_delete()`)
- Modify: `backend/app/phenopackets/routers/crud.py` (handle `ServiceConflict` on delete)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phenopackets_delete_revision.py`:

```python
"""Wave 5a: DELETE must honour the optimistic-locking revision.

Before this fix, soft_delete() blindly set deleted_at/deleted_by
regardless of the client's revision number, so a curator holding a
stale view could delete a record that a co-curator had just updated.

The behavior mirrors UPDATE: if the client's revision doesn't match
the current row revision, return 409 Conflict.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_delete_with_matching_revision_succeeds(
    async_client: AsyncClient, admin_headers: dict
):
    create_payload = {
        "phenopacket": {
            "id": "delete-revision-ok",
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-ok",
        json={"change_reason": "test", "revision": 1},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_delete_with_stale_revision_returns_409(
    async_client: AsyncClient, admin_headers: dict
):
    create_payload = {
        "phenopacket": {
            "id": "delete-revision-stale",
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    # Simulate concurrent update by another client
    update_payload = {
        **create_payload,
        "revision": 1,
        "change_reason": "concurrent edit",
    }
    await async_client.put(
        "/api/v2/phenopackets/delete-revision-stale",
        json=update_payload,
        headers=admin_headers,
    )
    # Current revision is now 2. Client still holds revision 1.

    # Stale delete
    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-stale",
        json={"change_reason": "stale delete", "revision": 1},
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["detail"]["current_revision"] == 2
    assert body["detail"]["expected_revision"] == 1


@pytest.mark.asyncio
async def test_delete_without_revision_still_works(
    async_client: AsyncClient, admin_headers: dict
):
    """Backwards compat: clients that omit `revision` are not broken.

    Revision is optional; if not provided, the delete proceeds without
    a check. This preserves existing client behavior until the frontend
    is updated.
    """
    create_payload = {
        "phenopacket": {
            "id": "delete-revision-optional",
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
        }
    }
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-optional",
        json={"change_reason": "no revision"},
        headers=admin_headers,
    )
    assert response.status_code == 200
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_phenopackets_delete_revision.py -v
```

Expected: `test_delete_with_stale_revision_returns_409` FAILS with `assert 200 == 409` (no revision check yet). The other two tests may pass already depending on the current schema.

- [ ] **Step 3: Add `revision` to `PhenopacketDelete` schema**

Edit `backend/app/phenopackets/models.py` — find the `PhenopacketDelete` class and add an optional `revision` field:

```python
class PhenopacketDelete(BaseModel):
    """Request schema for deleting a phenopacket."""

    change_reason: str = Field(..., min_length=1, max_length=1000)
    revision: Optional[int] = Field(
        None,
        description=(
            "Optional optimistic-locking revision. If provided, the delete "
            "returns 409 Conflict when the current row revision differs."
        ),
    )
```

- [ ] **Step 4: Enforce the revision check in `soft_delete()`**

Edit `backend/app/phenopackets/services/phenopacket_service.py` — update `soft_delete()` to accept an optional `expected_revision` parameter and raise `ServiceConflict` on mismatch. Route it through from the router via `delete_request.revision`.

```python
    async def soft_delete(
        self,
        phenopacket_id: str,
        change_reason: str,
        *,
        actor_id: int,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        phenopacket = await self._repo.get_by_id(phenopacket_id)
        if phenopacket is None:
            raise ServiceNotFound(
                f"Phenopacket {phenopacket_id} not found or already deleted"
            )

        if expected_revision is not None and phenopacket.revision != expected_revision:
            raise ServiceConflict(
                {
                    "error": "Conflict detected",
                    "message": (
                        f"Phenopacket was modified by another user. "
                        f"Expected revision {expected_revision}, "
                        f"current revision is {phenopacket.revision}"
                    ),
                    "current_revision": phenopacket.revision,
                    "expected_revision": expected_revision,
                },
                code="revision_mismatch",
            )

        # ... rest of the method unchanged ...
```

- [ ] **Step 5: Update the router to pass through `revision` and handle 409**

Edit `backend/app/phenopackets/routers/crud.py:280-291`:

```python
@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    delete_request: PhenopacketDelete,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Soft delete a phenopacket with optimistic-locking + audit trail."""
    service = PhenopacketService(PhenopacketRepository(db))
    try:
        return await service.soft_delete(
            phenopacket_id,
            delete_request.change_reason,
            actor_id=current_user.id,
            expected_revision=delete_request.revision,
        )
    except ServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Phenopacket not found or already deleted",
        ) from exc
    except ServiceConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except ServiceDatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

- [ ] **Step 6: Run the test — expect pass**

```bash
uv run pytest tests/test_phenopackets_delete_revision.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Run full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: ~915 passed

uv run pytest tests/test_http_surface_baseline.py -k verify -v
# Expect: 8 passed
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/phenopackets/models.py backend/app/phenopackets/services/phenopacket_service.py backend/app/phenopackets/routers/crud.py backend/tests/test_phenopackets_delete_revision.py
git commit -m "$(cat <<'EOF'
fix(backend): add optimistic-locking revision check to DELETE

Closes the DELETE race-condition gap flagged in the Wave 5 scope doc §3.1
A3 and the platform review §2.2. PhenopacketService.soft_delete now
accepts an optional expected_revision argument; on mismatch, raises
ServiceConflict which the router maps to 409.

Revision is optional for backwards compatibility — clients that omit it
get the old blind-delete behavior. The frontend delete dialog will start
passing revision in Wave 5b.

Mirrors the optimistic-locking pattern already used in update().

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add global soft-delete filter for `Phenopacket` entity

**Goal:** Move the per-query `deleted_at IS NULL` filter from `PhenopacketRepository` methods to a centralized SQLAlchemy `do_orm_execute` event listener scoped to the `Phenopacket` entity. Future queries from any router that forgets to filter can't accidentally leak deleted rows. The `include_deleted=True` escape hatch via `execution_options` continues to work for the audit-history endpoint.

**Files:**
- Create: `backend/tests/test_soft_delete_global_filter.py`
- Modify: `backend/app/database.py` (add `do_orm_execute` listener + `soft_delete_filter` flag)
- Modify: `backend/app/phenopackets/repositories/phenopacket_repository.py` (remove per-method `deleted_at.is_(None)` filters now that the listener owns them; `include_deleted=True` passes `execution_options` instead)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_soft_delete_global_filter.py`:

```python
"""Wave 5a: global soft-delete filter for Phenopacket.

Before this change, every router method that queried Phenopacket had
to remember to add `.where(Phenopacket.deleted_at.is_(None))`. A router
that forgot would leak deleted rows. The SQLAlchemy do_orm_execute
event listener now adds this filter transparently; an escape hatch
via execution_options(include_deleted=True) lets the audit/history
endpoints still see deleted rows.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket


@pytest.mark.asyncio
async def test_global_filter_hides_deleted_from_list(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """GET /phenopackets omits a soft-deleted row even without explicit filter."""
    # Create
    await async_client.post(
        "/api/v2/phenopackets/",
        json={
            "phenopacket": {
                "id": "soft-delete-001",
                "subject": {"id": "s", "sex": "MALE"},
                "phenotypicFeatures": [],
                "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
            }
        },
        headers=admin_headers,
    )

    # Soft delete
    await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/soft-delete-001",
        json={"change_reason": "test"},
        headers=admin_headers,
    )

    # Any plain SELECT Phenopacket should NOT return the deleted row
    stmt = select(Phenopacket).where(Phenopacket.phenopacket_id == "soft-delete-001")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_include_deleted_escape_hatch_still_works(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """execution_options(include_deleted=True) bypasses the global filter."""
    await async_client.post(
        "/api/v2/phenopackets/",
        json={
            "phenopacket": {
                "id": "soft-delete-002",
                "subject": {"id": "s", "sex": "MALE"},
                "phenotypicFeatures": [],
                "metaData": {"created": "2026-04-11T00:00:00Z", "createdBy": "pytest"},
            }
        },
        headers=admin_headers,
    )
    await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/soft-delete-002",
        json={"change_reason": "test"},
        headers=admin_headers,
    )

    # Query WITH the escape hatch
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id == "soft-delete-002")
        .execution_options(include_deleted=True)
    )
    result = await db_session.execute(stmt)
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.deleted_at is not None
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_soft_delete_global_filter.py -v
```

The first test may already pass because `PhenopacketRepository.get_by_id` has a manual filter. The second test (`test_include_deleted_escape_hatch_still_works`) will FAIL because `execution_options(include_deleted=True)` is not yet wired — the query still respects the manual filter.

- [ ] **Step 3: Implement the global filter in `database.py`**

Edit `backend/app/database.py` — after the `Base` class definition and before `get_db`, add:

```python
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy import event

# Import inside the function to avoid circular import with app.phenopackets.models
def _register_soft_delete_filter():
    """Attach a global soft-delete filter to the Phenopacket entity.

    Every SELECT touching Phenopacket gets an implicit
    `deleted_at IS NULL` predicate unless the statement carries
    execution_options(include_deleted=True). This mirrors the
    SQLAlchemy docs "Soft-Delete" recipe (do_orm_execute listener
    + with_loader_criteria) and is scoped to the Phenopacket entity
    only — other models are unaffected.
    """
    from app.phenopackets.models import Phenopacket

    @event.listens_for(async_session_maker.sync_session_class, "do_orm_execute")
    def _soft_delete_filter(execute_state):
        if execute_state.execution_options.get("include_deleted", False):
            return
        if not execute_state.is_select:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                Phenopacket,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


_register_soft_delete_filter()
```

- [ ] **Step 4: Remove now-redundant manual filters from `PhenopacketRepository`**

Edit `backend/app/phenopackets/repositories/phenopacket_repository.py`:

- `get_by_id`: change `include_deleted=True` branch to use `.execution_options(include_deleted=True)` instead of conditionally adding the predicate.
- `get_batch`: remove `Phenopacket.deleted_at.is_(None)` from the WHERE clause (now handled by the event listener).
- `base_list_query`: remove the initial `.where(Phenopacket.deleted_at.is_(None))` (handled by the listener).
- `count_filtered`: remove the initial `.where(Phenopacket.deleted_at.is_(None))`.

New `get_by_id`:

```python
async def get_by_id(
    self, phenopacket_id: str, *, include_deleted: bool = False
) -> Optional[Phenopacket]:
    """Fetch a phenopacket by its public id.

    Soft-deleted rows are filtered out by the global event listener.
    Set include_deleted=True to pass through the escape hatch.
    """
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id == phenopacket_id)
        .options(
            selectinload(Phenopacket.created_by_user),
            selectinload(Phenopacket.updated_by_user),
            selectinload(Phenopacket.deleted_by_user),
        )
    )
    if include_deleted:
        stmt = stmt.execution_options(include_deleted=True)
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Run the test — expect pass**

```bash
uv run pytest tests/test_soft_delete_global_filter.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Run full suite + baselines**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: ~917 passed

uv run pytest tests/test_http_surface_baseline.py -k verify -v
# Expect: 8 passed
```

If the audit-history endpoint test fails (`tests/test_phenopackets_audit_history.py` or similar), it's because that endpoint reads deleted rows via `get_by_id(..., include_deleted=True)` and the underlying query isn't passing through the option. Debug the repository method.

- [ ] **Step 7: Commit**

```bash
git add backend/app/database.py backend/app/phenopackets/repositories/phenopacket_repository.py backend/tests/test_soft_delete_global_filter.py
git commit -m "$(cat <<'EOF'
feat(backend): add global soft-delete filter for Phenopacket entity

Closes the soft-delete leak risk from the Wave 5 scope doc §3.1 A5 and
the platform review §2.2. A SQLAlchemy do_orm_execute event listener
now transparently adds `deleted_at IS NULL` to every SELECT touching
Phenopacket, so a new router that forgets to filter can't leak
deleted rows.

The escape hatch via execution_options(include_deleted=True) is
preserved for the audit/history endpoint and any future admin restore
workflow.

Scoped to Phenopacket only — other models are unaffected. Removes the
now-redundant per-method `deleted_at.is_(None)` filters from
PhenopacketRepository.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: v-html sanitization audit on About.vue and FAQ.vue

**Goal:** Route every `v-html="renderMarkdown(...)"` call in `About.vue` and `FAQ.vue` through the existing `frontend/src/utils/sanitize.js` utility. Closes the CRITICAL XSS finding from the 2026-04-09 codebase-quality review (P1 #1).

**Files:**
- Create: `frontend/tests/unit/utils/sanitize.spec.js`
- Modify: `frontend/src/views/About.vue:50, 79, 131` (v-html sinks)
- Modify: `frontend/src/views/FAQ.vue:56, 64, 73, 139, 177` (v-html sinks)

- [ ] **Step 1: Write the failing vitest**

Create `frontend/tests/unit/utils/sanitize.spec.js`:

```javascript
import { describe, it, expect } from 'vitest';
import { sanitize } from '@/utils/sanitize';

describe('sanitize', () => {
  it('strips script tags', () => {
    const dirty = '<p>Hello<script>alert(1)</script></p>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('<script>');
    expect(clean).toContain('Hello');
  });

  it('strips onerror attributes', () => {
    const dirty = '<img src=x onerror="alert(1)">';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('onerror');
  });

  it('strips javascript: urls', () => {
    const dirty = '<a href="javascript:alert(1)">click</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('javascript:');
  });

  it('keeps safe anchor targets with injected rel', () => {
    const dirty = '<a href="https://example.com" target="_blank">link</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('href="https://example.com"');
    expect(clean).toContain('rel="noopener noreferrer"');
  });

  it('preserves allowed markdown tags', () => {
    const dirty = '<p><strong>bold</strong> and <em>italic</em></p>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<strong>bold</strong>');
    expect(clean).toContain('<em>italic</em>');
  });

  it('returns empty string for null/undefined/empty', () => {
    expect(sanitize(null)).toBe('');
    expect(sanitize(undefined)).toBe('');
    expect(sanitize('')).toBe('');
  });
});
```

- [ ] **Step 2: Run the vitest — expect pass (sanitize already exists)**

```bash
cd frontend
npm run test -- --run tests/unit/utils/sanitize.spec.js
```

Expected: 6 PASSED. The sanitize utility already exists and these tests codify its contract. If any fail, the contract drifted — investigate before continuing.

- [ ] **Step 3: Wrap v-html in `About.vue`**

Edit `frontend/src/views/About.vue`. Find every `v-html="renderMarkdown(...)"` at lines 50, 79, 131 and wrap the value through `sanitize`:

At the top of the script section, add:

```javascript
import { sanitize } from '@/utils/sanitize';
```

Then change each call site. Line 50 goes from:

```html
<p class="mb-4" v-html="renderMarkdown(section.content.intro)" />
```

to:

```html
<p class="mb-4" v-html="sanitize(renderMarkdown(section.content.intro))" />
```

Apply the same wrap to lines 79 (`v-html="renderMarkdown(para)"`) and 131 (`v-html="formatCitation(section.content.formats.apa.template)"` — wrap the `formatCitation` output too).

- [ ] **Step 4: Wrap v-html in `FAQ.vue`**

Edit `frontend/src/views/FAQ.vue`. Apply the same wrap to lines 56, 64, 73, 139, 177:

```javascript
import { sanitize } from '@/utils/sanitize';
```

Then change each call site from `v-html="renderMarkdown(...)"` to `v-html="sanitize(renderMarkdown(...))"`.

- [ ] **Step 5: Run frontend lint to confirm no new warnings**

```bash
cd frontend
npm run lint 2>&1 | tail -20
```

Expected: warnings count should be ≤ 23 (the pre-existing baseline). The ESLint `v-html` warnings at the 8 wrapped locations will remain (ESLint doesn't know about sanitize); the warning is a recommendation, not a blocker. Note the count.

- [ ] **Step 6: Run frontend tests**

```bash
npm run test -- --run
```

Expected: all green (no view-level tests should have broken).

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/src/views/About.vue frontend/src/views/FAQ.vue frontend/tests/unit/utils/sanitize.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): sanitize v-html in About.vue and FAQ.vue

Closes the CRITICAL XSS finding from the 2026-04-09 codebase-quality
review (P1 #1): every v-html sink in About.vue (:50,:79,:131) and
FAQ.vue (:56,:64,:73,:139,:177) now routes through the existing
DOMPurify wrapper in frontend/src/utils/sanitize.js.

sanitize() already strips script tags, on* attributes, javascript:
URLs, and injects rel="noopener noreferrer" on target=_blank anchors.
This commit only adds the wrap — no changes to the utility itself.

Added tests/unit/utils/sanitize.spec.js as the durable contract.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Dev-mode config (Layer 1 of 5)

**Goal:** Add `environment: Literal["development","staging","production"]` and `enable_dev_auth: bool` to `Settings` with a `model_validator` that refuses to start if `enable_dev_auth=True` outside development. This is Layer 1 of the dev-mode 5-layer defense — the process won't even boot if the flags are wrong in prod.

**Files:**
- Create: `backend/tests/test_config_refuses_dev_auth_in_prod.py`
- Modify: `backend/app/core/config.py` (add two new `Settings` fields + `model_validator`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config_refuses_dev_auth_in_prod.py`:

```python
"""Wave 5a: Settings must refuse to instantiate with enable_dev_auth=True
outside ENVIRONMENT=development. Mirrors the JWT_SECRET / ADMIN_PASSWORD
fail-fast validators already in config.py.
"""
from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dev_auth_allowed_in_development():
    s = Settings(
        JWT_SECRET="x" * 32,
        ADMIN_PASSWORD="A" * 20,
        environment="development",
        enable_dev_auth=True,
    )
    assert s.enable_dev_auth is True
    assert s.environment == "development"


def test_dev_auth_refused_in_staging():
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="staging",
            enable_dev_auth=True,
        )


def test_dev_auth_refused_in_production():
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="production",
            enable_dev_auth=True,
        )


def test_default_environment_is_production():
    """Unset env defaults to production — an unset env must never default
    to development (that would defeat the whole purpose of Layer 1)."""
    s = Settings(JWT_SECRET="x" * 32, ADMIN_PASSWORD="A" * 20)
    assert s.environment == "production"
    assert s.enable_dev_auth is False
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend
uv run pytest tests/test_config_refuses_dev_auth_in_prod.py -v
```

Expected: all 4 tests FAIL with `AttributeError: 'Settings' object has no attribute 'environment'` — because the fields don't exist yet.

- [ ] **Step 3: Add the fields and validator to `Settings`**

Edit `backend/app/core/config.py` — inside the `Settings` class, after `DEBUG: bool = False` at line 299, add:

```python
    # === Environment and dev-mode gating (Wave 5a Layer 1) ===

    environment: Literal["development", "staging", "production"] = "production"
    enable_dev_auth: bool = False
```

Then import `Literal` and `model_validator`:

```python
from typing import List, Literal, Optional
from pydantic import Field, field_validator, model_validator
```

After the existing validators (after `validate_cors_origins`), add:

```python
    @model_validator(mode="after")
    def _refuse_dev_auth_in_prod(self) -> "Settings":
        """Fail fast if ENABLE_DEV_AUTH is True outside development.

        Wave 5a Layer 1 of the dev-mode 5-layer defense (review §5.3).
        An unset ENVIRONMENT must never be interpreted as dev — the
        default is production. This mirrors the JWT_SECRET / ADMIN_PASSWORD
        validators in that refusing to start is the right response to a
        dangerous misconfiguration.
        """
        if self.enable_dev_auth and self.environment != "development":
            raise ValueError(
                "REFUSING TO START: ENABLE_DEV_AUTH=true is only permitted "
                f"when ENVIRONMENT=development (got {self.environment!r}). "
                "This is the first of five dev-mode defense layers — see "
                "docs/reviews/2026-04-11-platform-readiness-review.md §5.3."
            )
        return self
```

- [ ] **Step 4: Run the test — expect pass**

```bash
uv run pytest tests/test_config_refuses_dev_auth_in_prod.py -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: ~921 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config_refuses_dev_auth_in_prod.py
git commit -m "$(cat <<'EOF'
feat(backend): add environment + enable_dev_auth config with refusal validator

Wave 5a Layer 1 of the dev-mode quick-login 5-layer defense (platform
review §5.3). Settings now has:

  environment: Literal["development","staging","production"] = "production"
  enable_dev_auth: bool = False

Plus a model_validator that raises ValueError if enable_dev_auth=True
outside development. The process refuses to start, mirroring the
existing JWT_SECRET and ADMIN_PASSWORD fail-fast validators.

The default environment is explicitly "production" — an unset env
must never be interpreted as dev, which is the entire point of
Layer 1.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Dev-mode backend router (Layers 2 + dev-login baseline)

**Goal:** Create `backend/app/api/dev_endpoints.py` with a `POST /api/v2/dev/login-as/{username}` endpoint that mints access + refresh tokens for a fixture user without password verification. Conditionally mount the router in `main.py`. Add the endpoint to the HTTP baseline suite (gated behind `ENABLE_DEV_AUTH=true`).

**Files:**
- Create: `backend/app/api/dev_endpoints.py`
- Create: `backend/tests/test_dev_endpoints.py`
- Modify: `backend/app/main.py` (conditional router mount after line 87)
- Modify: `backend/tests/test_http_surface_baseline.py` (add `dev_login_as_admin` fixture)
- Create: `backend/tests/fixtures/http_baselines/dev_login_as_admin.json` (baseline fixture)
- Modify: `backend/tests/conftest.py` (add `dev_auth_client` fixture for testing with `ENABLE_DEV_AUTH=true`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dev_endpoints.py`:

```python
"""Wave 5a: dev-mode quick-login router — 5-layer gating tests.

Layer 1 (config validator) is tested in test_config_refuses_dev_auth_in_prod.
Layer 2 tests are here: module-level assert, loopback-only, fixture-user gate.
Layers 3-5 (seed script, frontend DCE, CI grep) tested in their own files.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_dev_login_rejects_non_fixture_user(
    dev_auth_client: AsyncClient, admin_headers: dict
):
    """POST /dev/login-as/{username} returns 404 for a non-fixture user.

    Even if a user exists in prod with username='admin', the dev
    endpoint refuses because is_fixture_user=False.
    """
    response = await dev_auth_client.post("/api/v2/dev/login-as/admin")
    assert response.status_code == 404
    assert "fixture" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dev_login_accepts_fixture_user(
    dev_auth_client: AsyncClient, db_session: AsyncSession
):
    """A seeded fixture user gets a valid access token without password."""
    # Seed a fixture user directly in the test DB
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'dev-admin@hnf1b-db.local',
                'dev-admin',
                '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
                'admin',
                true,
                true,
                true,
                0,
                NOW()
            )
            ON CONFLICT (username) DO UPDATE SET is_fixture_user = true
        """)
    )
    await db_session.commit()

    response = await dev_auth_client.post("/api/v2/dev/login-as/dev-admin")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_dev_login_refuses_inactive_fixture_user(
    dev_auth_client: AsyncClient, db_session: AsyncSession
):
    """Even a fixture user with is_active=False is refused."""
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'dev-inactive@hnf1b-db.local',
                'dev-inactive',
                '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
                'viewer',
                false,
                true,
                true,
                0,
                NOW()
            )
            ON CONFLICT (username) DO UPDATE SET is_active = false, is_fixture_user = true
        """)
    )
    await db_session.commit()

    response = await dev_auth_client.post("/api/v2/dev/login-as/dev-inactive")
    assert response.status_code == 403
```

- [ ] **Step 2: Add the `dev_auth_client` fixture to `conftest.py`**

Edit `backend/tests/conftest.py`. Add a new fixture that builds a test client against an app whose `settings.enable_dev_auth` is forced to `True`. Pattern:

```python
@pytest.fixture
async def dev_auth_client():
    """Async HTTP client with ENABLE_DEV_AUTH=true + ENVIRONMENT=development.

    Rebuilds the FastAPI app against a patched Settings so the dev
    router is mounted. Used only by Wave 5a dev-mode tests.
    """
    from fastapi import FastAPI
    from app.core.config import settings as app_settings

    # Monkey-patch for the duration of the fixture — avoid rebuilding
    # the app from scratch. The main.py conditional mount reads these
    # two flags at import time, so we need a different approach:
    # explicitly import and include the dev router after patching.
    original_env = app_settings.environment
    original_flag = app_settings.enable_dev_auth
    app_settings.environment = "development"
    app_settings.enable_dev_auth = True

    try:
        from app.api import dev_endpoints
        from app.main import app
        # Include the dev router if not already present
        if not any(r.path.startswith("/api/v2/dev") for r in app.router.routes):
            app.include_router(dev_endpoints.router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testclient",
        ) as client:
            yield client
    finally:
        app_settings.environment = original_env
        app_settings.enable_dev_auth = original_flag
```

**Note:** this is a simplified fixture pattern. The real challenge is that `app/main.py` evaluates the conditional mount at import time. If that proves fragile in testing, use `dependency_overrides` or a separate test app fixture. The exact shape depends on the existing `conftest.py` layout — read it first.

- [ ] **Step 3: Run the failing test**

```bash
uv run pytest tests/test_dev_endpoints.py -v
```

Expected: all tests FAIL with import errors or 404s (the module doesn't exist yet).

- [ ] **Step 4: Create `dev_endpoints.py`**

Create `backend/app/api/dev_endpoints.py`:

```python
"""Dev-only quick-login router — NEVER MOUNTED IN PRODUCTION.

Wave 5a Layer 2 of the dev-mode 5-layer defense (platform review §5.3).

This module is only imported from app/main.py when BOTH
settings.enable_dev_auth and settings.environment == "development" are
true. A module-level assert crashes on load if those conditions
aren't met, so an accidental import outside dev mode cannot silently
succeed.

The endpoint mints access + refresh tokens for a fixture user
(is_fixture_user=True) without password verification. This is only
safe because:

- Layer 1 (config.py validator) refused to start if dev_auth + non-dev
- Layer 2 (this file's module-level assert) crashes on accidental import
- Layer 3 (is_fixture_user column) refuses non-fixture users
- Layer 4 (frontend build-time DCE) strips the UI in prod
- Layer 5 (CI grep) catches any leaked string

NEVER attempt to harden this file by adding password checks. The
entire gating scheme depends on this file not existing in prod.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token
from app.core.config import settings
from app.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token

logger = logging.getLogger(__name__)

# Hard runtime assert — belt + suspenders for the import gate.
# If this module is ever loaded outside dev mode (e.g., someone
# removed the conditional mount in main.py but forgot to remove the
# import), the process crashes on import.
assert settings.enable_dev_auth and settings.environment == "development", (
    "dev_endpoints.py was imported outside of dev mode — investigate main.py"
)

router = APIRouter(
    prefix="/api/v2/dev",
    tags=["dev-only"],
    include_in_schema=False,  # Hides from /api/v2/docs — cosmetic, not security
)

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def _require_loopback(request: Request) -> None:
    """Refuse requests that don't come from the local host."""
    client_host = request.client.host if request.client else None
    if client_host not in _LOOPBACK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="dev-mode login is loopback-only",
        )


@router.post("/login-as/{username}", response_model=Token)
async def dev_login_as(
    username: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_loopback),
) -> Token:
    """Mint a fresh access + refresh token for a fixture user.

    Layer 3 (is_fixture_user) is enforced here: non-fixture users get
    404 regardless of whether they exist.
    """
    repo = UserRepository(db)
    user = await repo.get_by_username(username)

    if user is None or not user.is_fixture_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not a fixture user",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="inactive fixture user",
        )

    access_token = create_access_token(
        username=user.username,
        role=user.role,
        permissions=user.get_permissions(),
    )
    refresh_token = create_refresh_token(username=user.username)
    await repo.update_refresh_token(user, refresh_token)

    logger.warning(
        "DEV LOGIN as %s from %s",
        username,
        request.client.host if request.client else "unknown",
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
```

Note: `settings.access_token_expire_minutes` may or may not exist in the current config — check. If it doesn't exist, hardcode `expires_in=1800` (30 min) or look up the current convention.

- [ ] **Step 5: Mount the router conditionally in `main.py`**

Edit `backend/app/main.py` — after the existing `app.include_router(seo_router, ...)` call at line 87, add:

```python
# Wave 5a dev-mode quick-login — Layer 2 conditional mount.
# The dev_endpoints module has a module-level assert that crashes
# on accidental import outside dev, so even if this block runs in
# prod due to a misconfig, the import itself fails closed.
if settings.enable_dev_auth and settings.environment == "development":
    from app.api import dev_endpoints  # noqa: E402  (intentional conditional import)

    app.include_router(dev_endpoints.router)

    import logging

    _dev_logger = logging.getLogger(__name__)
    _dev_logger.warning("=" * 60)
    _dev_logger.warning("DEV AUTH ROUTER MOUNTED — DO NOT RUN IN PRODUCTION")
    _dev_logger.warning("=" * 60)
```

- [ ] **Step 6: Run the tests — expect pass**

```bash
uv run pytest tests/test_dev_endpoints.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Add a new HTTP surface baseline for dev-login-as**

Edit `backend/tests/test_http_surface_baseline.py`:

Add a new tuple to `AFFECTED_ENDPOINTS` (after the existing 8):

```python
    # Wave 5a: dev-mode quick-login. Gated behind ENABLE_DEV_AUTH=true,
    # so the verify step is skipped unless the test is running in the
    # dev_auth_client. Capture produces a baseline; verify ensures
    # the endpoint still returns the same shape across future refactors.
    (
        "dev_login_as_admin",
        "dev_auth",  # new auth mode — handled via dev_auth_client fixture
        "POST",
        "/api/v2/dev/login-as/dev-admin",
        None,
        None,
    ),
```

Update the test parametrization to skip the `dev_auth` baselines unless `settings.enable_dev_auth` is true. The cleanest way: add a `skipif` guard on the verify parametrize where the auth mode is `dev_auth`.

**Capture the baseline** once with the fixture user seeded:

```bash
# First seed the fixture user manually
PGPASSWORD=hnf1b_pass psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "
  INSERT INTO users (email, username, hashed_password, role, is_active, is_verified, is_fixture_user, failed_login_attempts, created_at)
  VALUES ('dev-admin@hnf1b-db.local', 'dev-admin', '\$2b\$12\$placeholder.not.used.not.used.not.used.not.used.xx', 'admin', true, true, true, 0, NOW())
  ON CONFLICT (username) DO UPDATE SET is_fixture_user = true, is_active = true;
"

# Then capture the baseline in dev mode
ENVIRONMENT=development ENABLE_DEV_AUTH=true WAVE4_CAPTURE_BASELINE=1 uv run pytest tests/test_http_surface_baseline.py -k "capture and dev_login_as_admin" -v -s
```

This writes `backend/tests/fixtures/http_baselines/dev_login_as_admin.json`. Review the file; it should contain a normalized access_token placeholder and a 200 status.

**Important:** The capture step writes actual token fragments to the baseline. The existing `_normalize` function in `test_http_surface_baseline.py` masks timestamps/counters/IDs; add token masking too:

```python
def _normalize(obj: Any) -> Any:
    """Mask fields that vary between runs."""
    # ... existing masks ...
    if isinstance(obj, dict):
        return {
            k: ("<REDACTED_TOKEN>" if k in {"access_token", "refresh_token"} else _normalize(v))
            for k, v in obj.items()
        }
    # ... rest unchanged ...
```

Re-capture the baseline after adding the mask.

- [ ] **Step 8: Run the verify step in dev mode**

```bash
ENVIRONMENT=development ENABLE_DEV_AUTH=true uv run pytest tests/test_http_surface_baseline.py -k "verify and dev_login_as_admin" -v
```

Expected: PASS.

Run the full suite:

```bash
uv run pytest -q --no-header 2>&1 | tail -5
# Expect: ~924 passed
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/dev_endpoints.py backend/app/main.py backend/tests/test_dev_endpoints.py backend/tests/conftest.py backend/tests/test_http_surface_baseline.py backend/tests/fixtures/http_baselines/dev_login_as_admin.json
git commit -m "$(cat <<'EOF'
feat(backend): add dev-only quick-login router with 5-layer gating

Wave 5a Layers 2 + partial 3 of the dev-mode 5-layer defense (review
§5.3). Creates backend/app/api/dev_endpoints.py with a single endpoint
POST /api/v2/dev/login-as/{username} that mints access + refresh
tokens for a fixture user (is_fixture_user=True) without password
verification.

Layers in place after this commit:
- Layer 1 (Task 8): config refuses to boot with enable_dev_auth + non-dev
- Layer 2 (this commit): module-level assert + loopback-only guard
  + conditional mount in main.py
- Layer 3 (partial): the endpoint queries is_fixture_user to gate
  user selection (Task 10 adds the seed script)
- Layer 4 (Task 11): frontend build-time DCE
- Layer 5 (Task 12): CI grep on prod bundle

New HTTP baseline fixture dev_login_as_admin.json captures the
response shape; tokens are masked by _normalize.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Dev-mode seed script + Makefile target (Layer 3)

**Goal:** Create `backend/scripts/seed_dev_users.py` — an idempotent script that upserts `dev-admin`, `dev-curator`, `dev-viewer` fixture users with `is_fixture_user=True`. Refuses to run outside `ENVIRONMENT=development`. Add a `make dev-seed-users` target. This is the first real runtime caller of the otherwise-dead `backend/app/auth/user_import_service.py` (review §2.2).

**Files:**
- Create: `backend/scripts/seed_dev_users.py`
- Create: `backend/tests/test_seed_dev_users.py`
- Modify: `backend/Makefile` (add `dev-seed-users` target)
- Modify: `Makefile` (root-level passthrough)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_seed_dev_users.py`:

```python
"""Wave 5a Layer 3: seed_dev_users script refuses to run outside dev.

The script's main purpose is local developer ergonomics — one
command, three fixture users ready to log in via the dev quick-login
endpoint. It must refuse to run in staging or production even if
someone sources a .env file with the wrong ENVIRONMENT.
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def test_seed_script_refuses_production_env():
    """Running the script with ENVIRONMENT=production exits non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "backend.scripts.seed_dev_users"],
        env={"ENVIRONMENT": "production", "PATH": "/usr/bin:/bin", "JWT_SECRET": "x" * 32, "ADMIN_PASSWORD": "A" * 20},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "refuses" in (result.stdout + result.stderr).lower() or "development" in (result.stdout + result.stderr).lower()
```

Note: this test runs the script as a subprocess because the refusal happens at module load time. Adjust paths if the project layout rejects `python -m backend.scripts...` — use the direct file path instead: `[sys.executable, "backend/scripts/seed_dev_users.py"]`.

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/test_seed_dev_users.py -v
```

Expected: FAIL (script doesn't exist).

- [ ] **Step 3: Create `backend/scripts/seed_dev_users.py`**

```python
"""Seed dev-mode fixture users for Wave 5a quick-login.

Wave 5a Layer 3 of the dev-mode 5-layer defense (review §5.3).

Idempotent: upserts three fixture users with is_fixture_user=True.
Refuses to run outside ENVIRONMENT=development.

Usage:
    make dev-seed-users
    # or
    ENVIRONMENT=development uv run python -m backend.scripts.seed_dev_users
"""
from __future__ import annotations

import asyncio
import sys

from app.auth.password import hash_password
from app.core.config import settings
from app.database import async_session_maker
from app.models.user import User
from sqlalchemy import select

FIXTURE_USERS = [
    {
        "email": "dev-admin@hnf1b-db.local",
        "username": "dev-admin",
        "full_name": "Dev Admin",
        "role": "admin",
        "password": "DevAdmin!2026",
    },
    {
        "email": "dev-curator@hnf1b-db.local",
        "username": "dev-curator",
        "full_name": "Dev Curator",
        "role": "curator",
        "password": "DevCurator!2026",
    },
    {
        "email": "dev-viewer@hnf1b-db.local",
        "username": "dev-viewer",
        "full_name": "Dev Viewer",
        "role": "viewer",
        "password": "DevViewer!2026",
    },
]


async def _seed():
    async with async_session_maker() as session:
        for spec in FIXTURE_USERS:
            result = await session.execute(
                select(User).where(User.username == spec["username"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                user = User(
                    email=spec["email"],
                    username=spec["username"],
                    hashed_password=hash_password(spec["password"]),
                    full_name=spec["full_name"],
                    role=spec["role"],
                    is_active=True,
                    is_verified=True,
                    is_fixture_user=True,
                )
                session.add(user)
                print(f"seeded {spec['username']} ({spec['role']})")
            else:
                # Idempotent: ensure flags and role are correct
                existing.is_active = True
                existing.is_verified = True
                existing.is_fixture_user = True
                existing.role = spec["role"]
                existing.hashed_password = hash_password(spec["password"])
                print(f"refreshed {spec['username']}")
        await session.commit()


def main() -> int:
    if settings.environment != "development":
        print(
            "seed_dev_users refuses to run outside development "
            f"(ENVIRONMENT={settings.environment!r})",
            file=sys.stderr,
        )
        return 1
    asyncio.run(_seed())
    print("Seeded 3 fixture users — dev-admin, dev-curator, dev-viewer")
    print("Passwords: DevAdmin!2026 / DevCurator!2026 / DevViewer!2026")
    print("Use via /api/v2/dev/login-as/<username> (dev mode only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Add `dev-seed-users` to `backend/Makefile`**

Edit `backend/Makefile`. Add (near the other `db-*` targets):

```makefile
dev-seed-users:  ## Seed dev-mode fixture users (dev-admin/dev-curator/dev-viewer)
	@ENVIRONMENT=development uv run python -m app.scripts.seed_dev_users || \
	 ENVIRONMENT=development uv run python backend/scripts/seed_dev_users.py
```

The double fallback handles different project layouts.

- [ ] **Step 5: Add root-level passthrough in `Makefile`**

Edit the root `Makefile`. Add:

```makefile
dev-seed-users:  ## Seed dev-mode fixture users
	@$(MAKE) -C backend dev-seed-users
```

- [ ] **Step 6: Test the script manually**

```bash
cd backend
ENVIRONMENT=development uv run python scripts/seed_dev_users.py
```

Expected output:

```
seeded dev-admin (admin)
seeded dev-curator (curator)
seeded dev-viewer (viewer)
Seeded 3 fixture users — dev-admin, dev-curator, dev-viewer
Passwords: DevAdmin!2026 / DevCurator!2026 / DevViewer!2026
Use via /api/v2/dev/login-as/<username> (dev mode only)
```

Run it again — expect "refreshed" lines instead of "seeded" (idempotent).

- [ ] **Step 7: Verify the refusal path**

```bash
ENVIRONMENT=production uv run python scripts/seed_dev_users.py
echo "exit code: $?"
```

Expected: stderr says `seed_dev_users refuses to run outside development (ENVIRONMENT='production')`, exit code 1.

Note: the refusal happens on `Settings` load — the `model_validator` from Task 8 only raises when `enable_dev_auth=True`, not when `environment=production` alone. Double-check: the script's own check `settings.environment != "development"` is what blocks this.

- [ ] **Step 8: Run the test**

```bash
uv run pytest tests/test_seed_dev_users.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/scripts/seed_dev_users.py backend/tests/test_seed_dev_users.py backend/Makefile Makefile
git commit -m "$(cat <<'EOF'
feat(backend): add dev fixture user seed script + Makefile target

Wave 5a Layer 3 of the dev-mode 5-layer defense (review §5.3).
`make dev-seed-users` upserts three fixture users with
is_fixture_user=True:

  dev-admin   (admin)    DevAdmin!2026
  dev-curator (curator)  DevCurator!2026
  dev-viewer  (viewer)   DevViewer!2026

Refuses to run outside ENVIRONMENT=development. Idempotent — safe
to re-run. The script is also the first runtime caller of the
previously-dead user_import_service.py pattern (review §2.2).

Passwords are hardcoded in the script — not secrets, the whole
feature is dev-only and Layer 1/2 prevent any of this from reaching
a non-dev environment.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Frontend DevQuickLogin component with build-time DCE gate (Layer 4)

**Goal:** Create `frontend/src/components/auth/DevQuickLogin.vue` with three Vuetify buttons. Mount it in `Login.vue` only when `import.meta.env.DEV` is true via dynamic `import()` + `shallowRef` so Rollup's DCE strips the entire component and its URL strings from production builds. Add `devLoginAs(username)` action to `authStore.js` with a `DEV` guard.

**Files:**
- Create: `frontend/src/components/auth/DevQuickLogin.vue`
- Create: `frontend/tests/unit/components/auth/DevQuickLogin.spec.js`
- Modify: `frontend/src/views/Login.vue` (conditional import via dynamic import + shallowRef)
- Modify: `frontend/src/stores/authStore.js` (devLoginAs action, DEV-gated)

- [ ] **Step 1: Create `DevQuickLogin.vue`**

```vue
<template>
  <v-card class="mt-4" variant="tonal" color="warning">
    <v-card-title class="text-caption">
      DEV MODE — not available in production
    </v-card-title>
    <v-card-text>
      <v-btn
        v-for="u in fixtureUsers"
        :key="u.username"
        class="mr-2 mb-2"
        color="primary"
        variant="outlined"
        :loading="loadingUser === u.username"
        @click="onClick(u.username)"
      >
        Log in as {{ u.label }}
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();

const fixtureUsers = [
  { username: 'dev-admin', label: 'admin' },
  { username: 'dev-curator', label: 'curator' },
  { username: 'dev-viewer', label: 'viewer' },
];

const loadingUser = ref(null);

async function onClick(username) {
  loadingUser.value = username;
  try {
    await authStore.devLoginAs(username);
  } catch (err) {
    window.logService.error('dev login failed', { username, error: err.message });
  } finally {
    loadingUser.value = null;
  }
}
</script>
```

- [ ] **Step 2: Add `devLoginAs` to `authStore.js`**

Edit `frontend/src/stores/authStore.js`. Add a new action inside the `defineStore` callback — after `login`:

```javascript
  // Wave 5a Layer 4 — the DEV gate is critical. Vite replaces
  // import.meta.env.DEV with literal `false` during production build
  // and Rollup DCE eliminates the entire function body, including
  // the URL string literal /api/v2/dev/login-as/. Never read
  // import.meta.env.DEV into a variable first — keep the literal
  // inside the guard so the static replacement is structural.
  async function devLoginAs(username) {
    if (!import.meta.env.DEV) return;

    isLoading.value = true;
    try {
      const { data } = await apiClient.post(`/api/v2/dev/login-as/${username}`);
      accessToken.value = data.access_token;
      refreshToken.value = data.refresh_token;
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      await fetchCurrentUser();
      window.logService.info('dev quick-login', { username });
      return true;
    } catch (err) {
      window.logService.error('dev quick-login failed', { username, error: err.message });
      throw err;
    } finally {
      isLoading.value = false;
    }
  }
```

And add `devLoginAs` to the returned object at the bottom:

```javascript
  return {
    // ... existing exports ...
    devLoginAs,
  };
```

- [ ] **Step 3: Mount `DevQuickLogin` in `Login.vue` via dynamic import**

Edit `frontend/src/views/Login.vue`. At the top of `<script setup>`, add:

```javascript
import { shallowRef, defineAsyncComponent } from 'vue';

// Wave 5a Layer 4: DCE-friendly conditional import.
// Rollup drops the entire chunk + URL string from prod bundles.
const DevQuickLogin = shallowRef(null);
if (import.meta.env.DEV) {
  DevQuickLogin.value = defineAsyncComponent(
    () => import('@/components/auth/DevQuickLogin.vue')
  );
}
```

In the template, after the main login form (wherever appropriate), add:

```html
<component :is="DevQuickLogin" v-if="DevQuickLogin" />
```

Critical: do NOT use `import DevQuickLogin from ...` at the top of the file — a top-level import keeps the module in the dependency graph and defeats DCE. The dynamic `import()` inside the `if (import.meta.env.DEV)` block is mandatory.

- [ ] **Step 4: Write the failing vitest for DevQuickLogin**

Create `frontend/tests/unit/components/auth/DevQuickLogin.spec.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import DevQuickLogin from '@/components/auth/DevQuickLogin.vue';
import vuetify from '@/plugins/vuetify';  // adjust path if needed
import { useAuthStore } from '@/stores/authStore';

describe('DevQuickLogin', () => {
  let wrapper;

  beforeEach(() => {
    wrapper = mount(DevQuickLogin, {
      global: {
        plugins: [createTestingPinia({ createSpy: vi.fn }), vuetify],
      },
    });
  });

  it('renders three fixture user buttons', () => {
    const buttons = wrapper.findAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(3);
    const labels = buttons.map(b => b.text());
    expect(labels.some(l => l.includes('admin'))).toBe(true);
    expect(labels.some(l => l.includes('curator'))).toBe(true);
    expect(labels.some(l => l.includes('viewer'))).toBe(true);
  });

  it('calls authStore.devLoginAs when a button is clicked', async () => {
    const authStore = useAuthStore();
    const buttons = wrapper.findAll('button');
    await buttons[0].trigger('click');
    expect(authStore.devLoginAs).toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Run vitest**

```bash
cd frontend
npm run test -- --run tests/unit/components/auth/DevQuickLogin.spec.js
```

Expected: both tests PASS. If vuetify plugin import fails, check the existing frontend tests for the correct import path.

- [ ] **Step 6: Verify production build strips dev-mode**

```bash
NODE_ENV=production npm run build 2>&1 | tail -5
# Expect: success, no errors

grep -r "dev-admin\|DevQuickLogin\|dev/login-as" dist/ 2>/dev/null
# Expect: empty output
```

If grep finds anything, the DCE didn't strip what we expected. Common causes:
- Top-level static import of `DevQuickLogin.vue`
- Reading `import.meta.env.DEV` into a variable before branching
- Using `VITE_` custom env var instead of the built-in `DEV`
- Registering `DevQuickLogin` globally in `plugins/vuetify.js` or elsewhere

Debug and re-run until `grep` returns empty.

- [ ] **Step 7: Run full frontend test suite**

```bash
npm run test -- --run 2>&1 | tail -10
# Expect: all green
```

- [ ] **Step 8: Commit**

```bash
cd ..
git add frontend/src/components/auth/DevQuickLogin.vue frontend/src/views/Login.vue frontend/src/stores/authStore.js frontend/tests/unit/components/auth/DevQuickLogin.spec.js
git commit -m "$(cat <<'EOF'
feat(frontend): add DevQuickLogin component with build-time DCE gating

Wave 5a Layer 4 of the dev-mode 5-layer defense (review §5.3 + Vite
issue #15256). The component is dynamically imported via
defineAsyncComponent + shallowRef only when import.meta.env.DEV is
true — Vite replaces the literal at build time and Rollup DCE strips
the entire component chunk (and the URL string
"/api/v2/dev/login-as/") from production bundles.

The devLoginAs action on authStore has the same DEV guard, so even
if the component were accidentally bundled, the store action would
still be stripped.

Verified: `grep -r "dev-admin\|DevQuickLogin\|dev/login-as" dist/`
returns empty on a production build.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: CI Layer 5 grep jobs + docker-compose.prod.yml + README

**Goal:** Add three CI grep jobs that fail the build if dev-mode strings leak into the production frontend bundle. Pin `ENVIRONMENT=production` explicitly in `docker-compose.prod.yml`. Add a short README paragraph documenting how to enable dev-mode locally.

**Files:**
- Modify: `.github/workflows/ci.yml` (3 new grep jobs)
- Modify: `docker-compose.prod.yml` (ENVIRONMENT=production explicit)
- Modify: `README.md` (one-paragraph dev-mode section)

- [ ] **Step 1: Read the existing CI workflow**

```bash
cat .github/workflows/ci.yml | head -100
```

Find the job that runs the frontend build. You'll add the grep steps there.

- [ ] **Step 2: Add the three Layer 5 grep jobs to `ci.yml`**

After the existing `frontend build` step (or wherever `npm run build` is called), add:

```yaml
      - name: Verify no dev-auth strings in production bundle (Wave 5a Layer 5)
        if: always()
        run: |
          cd frontend
          if grep -rq "dev/login-as\|DevQuickLogin\|dev-admin\|dev-curator\|dev-viewer" dist/ 2>/dev/null; then
            echo "::error::dev-auth strings leaked into production bundle — check Task 11 DCE gating"
            grep -rn "dev/login-as\|DevQuickLogin\|dev-admin\|dev-curator\|dev-viewer" dist/ || true
            exit 1
          fi
          echo "dev-auth strings are NOT in the production bundle — Layer 5 green"

      - name: Verify ENABLE_DEV_AUTH not truthy in prod compose
        if: always()
        run: |
          if grep -Eq "^\s*ENABLE_DEV_AUTH\s*[:=]\s*(true|True|TRUE|1|yes|YES)" docker-compose.prod.yml; then
            echo "::error::ENABLE_DEV_AUTH must not be truthy in docker-compose.prod.yml"
            exit 1
          fi

      - name: Verify ENVIRONMENT=production in prod compose
        if: always()
        run: |
          if ! grep -Eq "^\s*ENVIRONMENT\s*[:=]\s*production" docker-compose.prod.yml; then
            echo "::error::docker-compose.prod.yml must set ENVIRONMENT=production explicitly"
            exit 1
          fi
```

- [ ] **Step 3: Explicit `ENVIRONMENT=production` in `docker-compose.prod.yml`**

Read `docker-compose.prod.yml` first. In the backend service's `environment:` section, add `ENVIRONMENT=production`. Example:

```yaml
services:
  backend:
    # ... existing config ...
    environment:
      - ENVIRONMENT=production
      # ... existing env vars ...
```

Also ensure there is NO `ENABLE_DEV_AUTH` line (or if present, it must be `false`).

- [ ] **Step 4: Add the dev-mode README paragraph**

Edit `README.md`. After the "Quick Start" section (or wherever makes sense), add:

```markdown
### Dev-mode quick-login (local development only)

For faster iteration on features that need to switch between admin,
curator, and viewer roles, Wave 5a adds a dev-only quick-login feature
guarded by five layers of defense (see
`docs/superpowers/plans/2026-04-11-wave-5-scope.md` §R3).

To enable it locally:

```bash
# Add to backend/.env:
ENVIRONMENT=development
ENABLE_DEV_AUTH=true

# Seed three fixture users (dev-admin / dev-curator / dev-viewer):
make dev-seed-users

# Start the backend; the login page will show the three dev buttons.
make backend
```

Passwords: `DevAdmin!2026`, `DevCurator!2026`, `DevViewer!2026`.
They're hardcoded in the seed script because they're not secrets —
the feature is structurally impossible to ship to production:

1. Backend config refuses to start with `ENABLE_DEV_AUTH=true` if
   `ENVIRONMENT != development`
2. The router module has a load-time `assert` that crashes on import
3. The `is_fixture_user` column gates which users can be targeted
4. The frontend component is tree-shaken out of production builds
5. CI grep jobs fail the build if any dev-mode string leaks into `dist/`
```

- [ ] **Step 5: Test the CI grep locally**

```bash
cd frontend && npm run build && cd ..
grep -rq "dev/login-as\|DevQuickLogin\|dev-admin" frontend/dist/ && echo "LEAKED" || echo "CLEAN"
# Expect: CLEAN
```

Test the compose grep:

```bash
grep -Eq "^\s*ENABLE_DEV_AUTH\s*[:=]\s*(true|1|yes)" docker-compose.prod.yml && echo "FAIL" || echo "PASS"
# Expect: PASS

grep -Eq "^\s*ENVIRONMENT\s*[:=]\s*production" docker-compose.prod.yml && echo "PASS" || echo "FAIL"
# Expect: PASS
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml docker-compose.prod.yml README.md
git commit -m "$(cat <<'EOF'
ci: add Wave 5a Layer 5 grep jobs + prod compose ENVIRONMENT pin + README

Wave 5a Layer 5 of the dev-mode 5-layer defense (review §5.3). Adds
three CI grep jobs that fail the build if:

1. Any dev-auth string (dev/login-as, DevQuickLogin, dev-admin/
   dev-curator/dev-viewer) appears in the production frontend bundle
2. docker-compose.prod.yml has ENABLE_DEV_AUTH truthy
3. docker-compose.prod.yml doesn't explicitly set ENVIRONMENT=production

Pins ENVIRONMENT=production in docker-compose.prod.yml so a runtime
override can't silently fall back to the default.

README gains a short paragraph documenting how to enable dev-mode
locally and reiterating the five defense layers.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Wave 5a exit note + pre-merge verification

**Goal:** Write the `docs/refactor/wave-5a-exit.md` exit note following the Wave 4 template. Run every verification command from the scope doc §4.1 exit criteria and capture the results in the exit note. This commit closes out PR 1.

**Files:**
- Create: `docs/refactor/wave-5a-exit.md`

- [ ] **Step 1: Run every exit-criteria check from the scope doc**

```bash
# Backend full suite
cd backend
uv run pytest -q --no-header 2>&1 | tail -5
# Record the pass count (expect ~937)

# HTTP baselines (including the new dev_login_as_admin)
uv run pytest tests/test_http_surface_baseline.py -k verify -v 2>&1 | tail -15
# Expect: 8 pre-existing + 1 dev-mode (skipped unless ENABLE_DEV_AUTH=true)

# Lint / typecheck / format
uv run ruff check app/ 2>&1 | tail -5
uv run mypy app/ 2>&1 | tail -5

cd ..

# Frontend
cd frontend
npm run test -- --run 2>&1 | tail -10
npm run lint 2>&1 | tail -5
# Record lint warning count (expect <= 23)

# Production build grep (Layer 5)
NODE_ENV=production npm run build > /dev/null 2>&1
grep -r "dev-admin\|DevQuickLogin\|dev/login-as" dist/ 2>/dev/null && echo "LEAKED" || echo "CLEAN"
# Expect: CLEAN

cd ..

# Git commit count
git log --oneline main..chore/wave-5a-foundations | wc -l
# Expect: 13 commits

# File count
git diff --stat main..chore/wave-5a-foundations | tail -1
# Record
```

Capture all outputs — you'll put them in the exit note.

- [ ] **Step 2: Verify Alembic round-trip**

```bash
cd backend
uv run alembic current
# Note the current revision

uv run alembic downgrade -1
uv run alembic downgrade -1
# Downgrade past both Wave 5a migrations

uv run pytest tests/test_audit_actor_fk.py -v 2>&1 | tail -5
# Expect: failures (FK columns don't exist in downgraded state)

uv run alembic upgrade head
uv run pytest tests/test_audit_actor_fk.py -v 2>&1 | tail -5
# Expect: 3 PASS (state restored)

cd ..
```

- [ ] **Step 3: Write the exit note**

Create `docs/refactor/wave-5a-exit.md`:

```markdown
# Wave 5a Exit Note

**Date:** 2026-04-XX (fill in)
**Branch:** `chore/wave-5a-foundations` (worktree at `~/development/hnf1b-db.worktrees/chore-wave-5a-foundations/`)
**Starting test counts:** backend 907 passed + 9 skipped + 3 xfailed (post Wave 4 merge, commit `7c5d079`)
**Ending test counts:** backend XXX passed + YY skipped + 3 xfailed (+XX tests). Frontend: ZZ tests passing.

## What landed (13 commits)

1. `<hash>` — **refactor(tests): rename http baseline fixtures dir to drop wave4 prefix.** Pure rename — zero logic changes.

2. `<hash>` — **feat(db): add is_fixture_user BOOLEAN column to users table.** Prerequisite for dev-mode Layer 3. Non-nullable, server_default=FALSE.

3. `<hash>` — **refactor(db): FK-ify audit actor columns with system-migration placeholder.** Converts 4 audit-actor columns from String(100) to BigInt FK → users.id. Data migration seeds `_system_migration_` user and maps existing strings. Downgrade tested reversible. Updates call sites: PhenopacketService, create_audit_entry, PhenopacketRepository, build_phenopacket_response, migration/database/storage.py.

4. `<hash>` — **feat(backend): emit audit row on phenopacket CREATE.** Closes the audit-on-create gap. Every phenopacket now has an 'Initial import' audit row from creation onward.

5. `<hash>` — **fix(backend): add optimistic-locking revision check to DELETE.** PhenopacketDelete gains optional `revision` field; soft_delete returns 409 on mismatch. Optional for backwards compat.

6. `<hash>` — **feat(backend): add global soft-delete filter for Phenopacket entity.** SQLAlchemy do_orm_execute event listener scoped to Phenopacket. Escape hatch via execution_options(include_deleted=True).

7. `<hash>` — **fix(frontend): sanitize v-html in About.vue and FAQ.vue.** Closes 2026-04-09 P1 #1 CRITICAL XSS finding. All v-html sinks routed through frontend/src/utils/sanitize.js.

8. `<hash>` — **feat(backend): add environment + enable_dev_auth config with refusal validator.** Dev-mode Layer 1. Settings refuses to instantiate if enable_dev_auth=True outside development.

9. `<hash>` — **feat(backend): add dev-only quick-login router with 5-layer gating.** Dev-mode Layers 2 + partial 3. New dev_endpoints.py with module-level assert + loopback guard + fixture-user gate. Conditional mount in main.py.

10. `<hash>` — **feat(backend): add dev fixture user seed script + Makefile target.** Dev-mode Layer 3 completion. `make dev-seed-users` seeds dev-admin / dev-curator / dev-viewer.

11. `<hash>` — **feat(frontend): add DevQuickLogin component with build-time DCE gating.** Dev-mode Layer 4. Dynamic import + shallowRef inside `if (import.meta.env.DEV)` ensures Rollup strips the chunk and URL strings from prod builds.

12. `<hash>` — **ci: add Wave 5a Layer 5 grep jobs + prod compose ENVIRONMENT pin + README.** Dev-mode Layer 5. CI fails if dev-auth strings leak into dist/ or if docker-compose.prod.yml has enable_dev_auth truthy.

13. `<hash>` — **docs(refactor): wave 5a exit note.** This file.

## Exit criteria (all green)

- [x] **Every phenopacket CREATE emits an audit row.** Verified by `test_phenopackets_audit_on_create.py` — 2 tests passing.

- [x] **DELETE returns 409 on stale revision.** Verified by `test_phenopackets_delete_revision.py` — 3 tests passing.

- [x] **Audit actor columns are nullable BigInt FK → users.id.** Verified by `test_audit_actor_fk.py` — 3 tests passing. Downgrade migration tested reversible.

- [x] **Global soft-delete filter in place.** Verified by `test_soft_delete_global_filter.py` — 2 tests passing.

- [x] **v-html XSS closed in About.vue + FAQ.vue.** All 8 v-html sinks wrapped through sanitize(). Vitest contract covers XSS payloads.

- [x] **Dev-mode 5 layers operational.**
  - Layer 1: config refuses dev_auth + non-dev (test_config_refuses_dev_auth_in_prod)
  - Layer 2: loopback guard + module-level assert (test_dev_endpoints)
  - Layer 3: is_fixture_user gate + seed script (test_dev_endpoints, test_seed_dev_users)
  - Layer 4: build-time DCE (verified by `grep -r dev-admin dist/` → empty)
  - Layer 5: CI grep jobs green

- [x] **HTTP baseline directory renamed.** 8 existing + 1 new dev-mode fixture.

- [x] **Backend `make check` green.** XXX passed, YY skipped, 3 xfailed. Lint/typecheck/format clean.

- [x] **Frontend `make check` green.** ZZ tests passing, ≤23 lint warnings.

- [x] **Tech-debt register unchanged.** No new entries required — all choices fit Wave 5 cleanly.

## Test count delta

| Stage | Backend tests | Delta |
|-------|--------------:|------:|
| Post Wave 4 baseline (commit 7c5d079) | 907 | — |
| Task 3: test_audit_actor_fk.py (3) | 910 | +3 |
| Task 4: test_phenopackets_audit_on_create.py (2) | 912 | +2 |
| Task 5: test_phenopackets_delete_revision.py (3) | 915 | +3 |
| Task 6: test_soft_delete_global_filter.py (2) | 917 | +2 |
| Task 8: test_config_refuses_dev_auth_in_prod.py (4) | 921 | +4 |
| Task 9: test_dev_endpoints.py (3) | 924 | +3 |
| Task 9: test_http_surface_baseline.py gains dev_login_as_admin (1) | 925 | +1 |
| Task 10: test_seed_dev_users.py (1) | 926 | +1 |
| **Wave 5a total** | **XXX** | **+XX** |

## Surprises

<!-- Fill in any gotchas discovered during execution. Examples from Wave 4: test-compatibility issues, legacy print() statements, ruff docstring rules. -->

## What was deferred

Nothing from the plan. All 13 tasks landed.

## Entry conditions for Wave 5b

- [x] Every phenopacket CRUD operation leaves a FK'd audit row.
- [x] `/api/v2/dev/login-as/<username>` works locally — faster iteration for Wave 5b admin UI development.
- [x] Global soft-delete filter in place — Wave 5b's admin user UI can't accidentally show soft-deleted phenopacket references.
- [x] v-html XSS closed — one less CRITICAL finding.
- [x] HTTP surface is locked in by baseline fixtures. Any Wave 5b refactor that drifts responses fails verify.
- [x] All backend tests green (XXX passing).
- [x] Frontend unchanged from Wave 4 baseline (<=23 lint warnings).

Wave 5a is done.
```

Fill in the XXX / YY / ZZ placeholders from Step 1 outputs. Fill in commit hashes via `git log --oneline main..chore/wave-5a-foundations`.

- [ ] **Step 4: Commit**

```bash
git add docs/refactor/wave-5a-exit.md
git commit -m "$(cat <<'EOF'
docs(refactor): wave 5a exit note

Records Wave 5a PR 1 completion: 13 commits, +XX tests, 8 HTTP
baseline fixtures preserved + 1 new dev-mode fixture, all exit
criteria from docs/superpowers/plans/2026-04-11-wave-5-scope.md §4.1
verified green.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Final verification before pushing**

```bash
# Verify branch is clean
git status --short
# Expect: clean

# Verify commit count
git log --oneline main..chore/wave-5a-foundations | wc -l
# Expect: 13

# Run EVERY check one more time
cd backend && make check && cd ..
cd frontend && make check && cd ..

# Verify the untracked review files are still untracked
git status --short
# Expect: ?? docs/refactor/wave-4-kickoff-prompt.md
#         ?? docs/reviews/2026-04-11-platform-readiness-review.md
#         ?? docs/reviews/codebase-best-practices-review-2026-04-09.md
#         (and nothing else)
```

- [ ] **Step 6: Push and create PR**

```bash
git push -u origin chore/wave-5a-foundations

gh pr create --title "chore(wave-5a): platform readiness foundations" --body "$(cat <<'EOF'
## Summary

Wave 5 PR 1 — foundations. Implements Bundle A from the platform-readiness
review plus the CRITICAL v-html XSS fix from the 2026-04-09 codebase
quality review. Prereq for Wave 5 PRs 2 and 3 (admin user management,
identity lifecycle).

Scope doc: `docs/superpowers/plans/2026-04-11-wave-5-scope.md`
Implementation plan: `docs/superpowers/plans/2026-04-11-wave-5a-foundations-plan.md`

## Commits

13 atomic commits — refactor → schema → behavior → dev-mode layers → exit note.

## Test plan

- [ ] `cd backend && make check` — expect XXX passing, YY skipped, 3 xfailed
- [ ] `cd frontend && make check` — expect all green, ≤23 lint warnings
- [ ] `uv run pytest tests/test_http_surface_baseline.py -k verify -v` — 8 existing baselines pass
- [ ] `uv run alembic downgrade -1 && uv run alembic upgrade head` — round-trip clean
- [ ] `NODE_ENV=production npm run build && grep -r "dev-admin\|DevQuickLogin\|dev/login-as" dist/` — empty (Layer 5)
- [ ] Manual: seed dev users, log in via `/api/v2/dev/login-as/dev-admin` in dev, verify prod 404s

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Plan execution summary

After all 13 tasks commit cleanly and the PR is open, you have:

- 13 commits under the 14-commit cap
- `main` unchanged (PR targets main but isn't merged yet)
- `chore/wave-5a-foundations` branch pushed to origin
- A PR ready for review
- The three untracked review files still untracked

**Next step:** wait for PR review. On merge, tear down the worktree:

```bash
cd ~/development/hnf1b-db
git worktree remove ~/development/hnf1b-db.worktrees/chore-wave-5a-foundations
git worktree prune
```

Then Wave 5b can start — create the next worktree against fresh main and follow `docs/superpowers/plans/2026-04-11-wave-5b-user-management-plan.md` (written by the next writing-plans session).
