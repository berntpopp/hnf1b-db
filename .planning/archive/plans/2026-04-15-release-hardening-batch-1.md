# Release Hardening Batch 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the fastest-moving release blockers on `main` by hardening auth semantics, stabilizing verification, and closing the highest-risk workflow guardrail gaps in parallel.

**Architecture:** The work is split into three parallel tracks with disjoint ownership: `Track A` owns auth behavior and frontend auth transport, `Track B` owns harness stability and test execution reliability, and `Track C` owns workflow visibility and delete/state race protection. The main thread coordinates track boundaries, runs integration verification, and resolves any cross-track contract changes.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Alembic, Pydantic 2, Vue 3, Pinia, Axios, Vitest, Playwright, pytest, npm, uv.

---

## Spec

Primary spec:

- `.planning/specs/2026-04-15-release-hardening-batch-1-design.md`

Supporting references:

- `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`
- `.planning/reviews/2026-04-15-senior-codebase-platform-review.md`
- `.planning/reviews/2026-04-15-path-to-8plus-and-pr-254-review.md`

## Parallel Track Ownership

### Track A — Auth Core

Owns:

- `backend/app/api/auth_endpoints.py`
- `backend/app/auth/*`
- `backend/app/repositories/user_repository.py`
- `backend/app/models/user.py`
- `frontend/src/stores/authStore.js`
- `frontend/src/api/session.js`
- `frontend/src/api/transport.js`
- auth-specific tests in `backend/tests/` and `frontend/tests/`

### Track B — Verification Stability

Owns:

- `backend/tests/conftest.py`
- failing auth/workflow test files when the failure is harness-related
- `frontend/package.json`
- `frontend/package-lock.json`
- frontend test config files if needed

### Track C — Workflow Guardrails

Owns:

- `backend/app/phenopackets/routers/crud_timeline.py`
- `backend/app/phenopackets/services/phenopacket_service.py`
- related workflow visibility/concurrency tests

## Pre-Flight

### Task 1: Create the three sibling worktrees

**Files:**
- Modify: none

- [ ] **Step 1 — confirm the current repository is clean enough to branch from**

```bash
cd ~/development/hnf1b-db
git status --short
git branch --show-current
```

Expected:

- current branch is `main`
- no unexpected staged changes for the hardening batch

- [ ] **Step 2 — create three sibling worktrees**

```bash
cd ~/development
git worktree add hnf1b-db.worktrees/release-hardening-auth-core -b chore/release-hardening-auth-core
git worktree add hnf1b-db.worktrees/release-hardening-verification -b chore/release-hardening-verification
git worktree add hnf1b-db.worktrees/release-hardening-workflow -b chore/release-hardening-workflow
```

Expected:

- three sibling worktrees exist
- each is on its own branch

- [ ] **Step 3 — sync dependencies in each worktree**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/backend && uv sync --group test
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/frontend && npm install
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/backend && uv sync --group test
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/frontend && npm install
cd ~/development/hnf1b-db.worktrees/release-hardening-workflow/backend && uv sync --group test
```

Expected:

- backend virtualenvs are ready
- frontend deps are installed where needed

- [ ] **Step 4 — commit nothing; hand each worktree to its track owner**

No commit for this setup task.

---

# Track B First — Verification Stability

Track B starts first because current verification is failing for a mix of environment, dependency, and harness reasons. It should restore trustworthy signals before the final integration gate, but Track A and Track C may begin in parallel.

### Task 2: Restore frontend test dependency resolution

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1 — reproduce the frontend failure from a clean install**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/frontend
npm install
npm test
```

Expected current failure shape:

- missing or unresolved `markdown-it`
- missing or unresolved `@tiptap/vue-3`
- missing or unresolved `@tiptap/starter-kit`

- [ ] **Step 2 — verify the dependencies are declared and lockfile is aligned**

The package section should include:

```json
"dependencies": {
  "@tiptap/extension-mention": "^3.22.3",
  "@tiptap/starter-kit": "^3.22.3",
  "@tiptap/vue-3": "^3.22.3",
  "markdown-it": "^14.1.1"
}
```

If `package.json` or `package-lock.json` drifted, regenerate the lockfile with:

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/frontend
npm install
```

- [ ] **Step 3 — rerun only the previously failing component suites**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/frontend
npx vitest run tests/unit/components/comments/CommentBody.spec.js tests/unit/components/comments/CommentComposer.spec.js tests/unit/components/comments/CommentItem.spec.js
```

Expected:

- imports resolve cleanly
- test files either pass or fail for product reasons rather than missing packages

- [ ] **Step 4 — commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "fix(frontend): restore comment test dependency resolution"
```

### Task 3: Fix backend test isolation deadlocks and duplicate seeded-user collisions

**Files:**
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_dev_endpoints.py`
- Test: `backend/tests/test_pwdlib_rehash.py`
- Test: `backend/tests/test_state_flows.py`

- [ ] **Step 1 — reproduce the current backend harness failures**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/backend
uv run pytest tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py -v
uv run pytest tests/test_state_flows.py tests/test_api_transitions.py tests/test_phenopackets_delete_revision.py tests/test_crud_related_and_timeline.py -v
```

Expected current failure shape:

- `DeadlockDetectedError` during `TRUNCATE ... RESTART IDENTITY CASCADE`
- duplicate `users.email`
- `StaleDataError` / refresh problems caused by fixture/session interference

- [ ] **Step 2 — replace table-truncation autouse isolation with per-test transaction-safe cleanup or a serialized cleanup primitive**

The current hotspot is:

```python
@pytest_asyncio.fixture(autouse=True)
async def _isolate_database_between_tests():
    await _truncate_mutable_tables()
    yield
```

Refactor toward one of these safe shapes:

```python
@pytest_asyncio.fixture(autouse=True)
async def _isolate_database_between_tests():
    async with engine.begin() as conn:
        joined = ", ".join(_MUTABLE_TABLES)
        await conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
    yield
```

plus a guard that prevents concurrent sessions from holding write locks across cleanup, or:

```python
@pytest_asyncio.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session
        await session.rollback()
```

The concrete implementation must ensure:

- cleanup is not racing against fixture teardown writes
- user fixtures do not leave committed rows that collide with later fixtures
- the same test DB remains usable for multi-session concurrency tests

- [ ] **Step 3 — remove fixture teardown deletes that fight the autouse cleanup**

Current fixture pattern to simplify:

```python
yield user
try:
    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()
except Exception:
    ...
```

Replace with:

```python
yield user
```

Use one isolation strategy, not two competing cleanup strategies.

- [ ] **Step 4 — rerun the previously failing backend slices**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-verification/backend
uv run pytest tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py -v
uv run pytest tests/test_state_flows.py tests/test_api_transitions.py tests/test_phenopackets_delete_revision.py tests/test_crud_related_and_timeline.py -v
```

Expected:

- no deadlock in cleanup
- no duplicate seeded-user collisions
- remaining failures, if any, are product defects and should be handed to Track A or C

- [ ] **Step 5 — commit**

```bash
git add backend/tests/conftest.py
git commit -m "fix(test): stabilize backend auth and workflow isolation"
```

### Task 4: Publish the batch verification command set

**Files:**
- Modify: `.planning/plans/2026-04-15-release-hardening-batch-1.md`

- [ ] **Step 1 — append the verified command set to the end of this plan**

Add:

```md
## Batch 1 Verification Commands

- `cd backend && uv run pytest tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py -v`
- `cd backend && uv run pytest tests/test_state_flows.py tests/test_api_transitions.py tests/test_phenopackets_delete_revision.py tests/test_crud_related_and_timeline.py -v`
- `cd frontend && npx vitest run tests/unit/components/comments/CommentBody.spec.js tests/unit/components/comments/CommentComposer.spec.js tests/unit/components/comments/CommentItem.spec.js`
```

- [ ] **Step 2 — commit**

```bash
git add .planning/plans/2026-04-15-release-hardening-batch-1.md
git commit -m "docs(planning): add batch 1 verification commands"
```

---

# Track A — Auth Core

### Task 5: Add failing backend auth regression tests for locked and inactive token issuance

**Files:**
- Test: `backend/tests/test_auth_token_issuance_hardening.py`

- [ ] **Step 1 — create the failing test file**

```python
import pytest


@pytest.mark.asyncio
async def test_login_rejects_locked_user(async_client, db_session, viewer_user_factory):
    user = await viewer_user_factory(username="lockeduser", email="locked@example.com")
    user.locked_until = user.created_at
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "lockeduser", "password": "TestPass123!"},
    )

    assert response.status_code == 423


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(async_client, active_user_with_refresh_token):
    user, refresh_token = active_user_with_refresh_token
    user.is_active = False
    await async_client.app.state.db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_refresh_rejects_locked_user(async_client, active_user_with_refresh_token, db_session):
    user, refresh_token = active_user_with_refresh_token
    user.locked_until = user.created_at
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 423
```

If helper fixtures do not exist, create equivalent local setup in the file using the existing user fixtures from `backend/tests/conftest.py`.

- [ ] **Step 2 — run the file and confirm failure**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/backend
uv run pytest tests/test_auth_token_issuance_hardening.py -v
```

Expected:

- failures because current code allows token issuance for locked/inactive paths

- [ ] **Step 3 — commit the failing tests**

```bash
git add backend/tests/test_auth_token_issuance_hardening.py
git commit -m "test(auth): cover locked and inactive token issuance rules"
```

### Task 6: Enforce account state on login and refresh paths

**Files:**
- Modify: `backend/app/api/auth_endpoints.py`
- Modify: `backend/app/repositories/user_repository.py`

- [ ] **Step 1 — add a shared account-state guard in the auth flow**

Use a helper like:

```python
def _assert_user_can_receive_tokens(user: User) -> None:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}",
        )
```

Apply it in:

- `login()` before creating tokens
- `refresh_access_token()` before rotating tokens

- [ ] **Step 2 — reduce multi-commit mutation churn in the login path**

Current path commits in:

- `record_successful_login()`
- `update_refresh_token()`

Refactor repository helpers to flush without multiple commits, for example:

```python
async def record_successful_login(self, user: User) -> None:
    user.last_login = datetime.now(timezone.utc)
    user.failed_login_attempts = 0
    user.locked_until = None
    await self.db.flush()


async def update_refresh_token(self, user: User, refresh_token: str) -> None:
    user.refresh_token = refresh_token
    await self.db.flush()
```

Then commit once in the endpoint after all related mutations and logging inputs are ready.

- [ ] **Step 3 — rerun the auth slice**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/backend
uv run pytest tests/test_auth_token_issuance_hardening.py tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py -v
```

Expected:

- locked and inactive token issuance tests pass
- no stale-data regression from the login write path

- [ ] **Step 4 — commit**

```bash
git add backend/app/api/auth_endpoints.py backend/app/repositories/user_repository.py
git commit -m "fix(auth): enforce account state before token issuance"
```

### Task 7: Invalidate refresh capability on credential rotation

**Files:**
- Modify: `backend/app/api/auth_endpoints.py`
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/models/user.py`
- Test: `backend/tests/test_auth_refresh_invalidation.py`

- [ ] **Step 1 — write regression tests first**

Create tests covering:

```python
async def test_change_password_clears_refresh_token(...):
    ...


async def test_password_reset_confirm_clears_refresh_token(...):
    ...
```

Each test should:

- obtain a valid refresh token
- perform password change or reset confirmation
- attempt refresh with the old token
- assert refresh is rejected

- [ ] **Step 2 — implement the minimum invalidation model**

Minimum acceptable change:

```python
user.refresh_token = None
await self.db.flush()
```

Apply that when:

- password is changed
- password reset is confirmed

If a token-version field is introduced instead, Track A owns the full implementation and all affected tests.

- [ ] **Step 3 — run the auth invalidation tests**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/backend
uv run pytest tests/test_auth_refresh_invalidation.py -v
```

Expected:

- old refresh tokens are rejected after credential rotation

- [ ] **Step 4 — commit**

```bash
git add backend/app/api/auth_endpoints.py backend/app/repositories/user_repository.py backend/app/models/user.py backend/tests/test_auth_refresh_invalidation.py
git commit -m "fix(auth): invalidate refresh tokens on credential rotation"
```

### Task 8: Replace frontend long-lived token persistence with the release-safe transport model

**Files:**
- Modify: `frontend/src/stores/authStore.js`
- Modify: `frontend/src/api/session.js`
- Modify: `frontend/src/api/transport.js`
- Test: `frontend/tests/unit/stores/authStore.spec.js`

- [ ] **Step 1 — choose the minimum release-safe client contract**

Implement this shape:

```js
const accessToken = ref(null)
```

and remove direct persistence calls such as:

```js
localStorage.setItem('access_token', access_token)
localStorage.setItem('refresh_token', refresh_token)
```

If backend cookie refresh is not shipped in this batch, the fallback contract must still eliminate `localStorage` persistence and document the temporary in-memory session behavior explicitly.

- [ ] **Step 2 — refactor the session helpers to stop reading from `localStorage`**

Replace helpers like:

```js
export function getAccessToken() {
  return localStorage.getItem('access_token')
}
```

with an in-memory module store, for example:

```js
let accessToken = null

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token) {
  accessToken = token
}

export function clearTokens() {
  accessToken = null
}
```

- [ ] **Step 3 — update the transport layer to use the new helpers and stop direct `localStorage` cleanup**

Replace:

```js
localStorage.removeItem('access_token')
localStorage.removeItem('refresh_token')
```

with:

```js
clearTokens()
```

and import the session helpers centrally.

- [ ] **Step 4 — add or update unit tests for the new auth-store/session behavior**

Key assertions:

- login stores access token only in memory
- logout clears in-memory token state
- refresh path updates in-memory token state
- no test depends on `localStorage`

- [ ] **Step 5 — run the frontend auth tests**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-auth-core/frontend
npx vitest run tests/unit/stores/authStore.spec.js
```

Expected:

- auth store behavior passes without `localStorage`

- [ ] **Step 6 — commit**

```bash
git add frontend/src/stores/authStore.js frontend/src/api/session.js frontend/src/api/transport.js frontend/tests/unit/stores/authStore.spec.js
git commit -m "fix(frontend): remove long-lived auth token persistence"
```

---

# Track C — Workflow Guardrails

### Task 9: Add failing visibility tests for timeline access

**Files:**
- Modify: `backend/tests/test_crud_related_and_timeline.py`

- [ ] **Step 1 — add failing tests for unauthorized draft/deleted timeline access**

Add tests shaped like:

```python
async def test_timeline_hides_soft_deleted_phenopacket_from_public_client(...):
    response = await async_client.get(f"/api/v2/phenopackets/{phenopacket_id}/timeline")
    assert response.status_code == 404


async def test_timeline_hides_draft_phenopacket_from_public_client(...):
    response = await async_client.get(f"/api/v2/phenopackets/{phenopacket_id}/timeline")
    assert response.status_code == 404
```

If curator/admin access to deleted content is intended, add one explicit positive-role test for that chosen policy.

- [ ] **Step 2 — run the timeline subset and confirm failure**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-workflow/backend
uv run pytest tests/test_crud_related_and_timeline.py -v
```

Expected:

- new visibility tests fail against current open endpoint

- [ ] **Step 3 — commit the failing tests**

```bash
git add backend/tests/test_crud_related_and_timeline.py
git commit -m "test(workflow): cover timeline visibility rules"
```

### Task 10: Apply visibility enforcement to the timeline endpoint

**Files:**
- Modify: `backend/app/phenopackets/routers/crud_timeline.py`
- Modify: related repository/visibility helper files only if required

- [ ] **Step 1 — align timeline access with the detail/list visibility model**

Follow the same dependency style used by `crud.py`:

```python
from app.auth import get_optional_user, is_curator_or_admin

async def get_phenotype_timeline(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    ...
```

Apply the appropriate visibility rule before returning the record:

```python
if current_user is None or not is_curator_or_admin(current_user):
    # public path: exclude draft/in-review/deleted
    ...
```

- [ ] **Step 2 — rerun the timeline tests**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-workflow/backend
uv run pytest tests/test_crud_related_and_timeline.py -v
```

Expected:

- public visibility tests pass
- no regression in the non-sensitive helper tests

- [ ] **Step 3 — commit**

```bash
git add backend/app/phenopackets/routers/crud_timeline.py backend/tests/test_crud_related_and_timeline.py
git commit -m "fix(workflow): enforce visibility rules on timeline reads"
```

### Task 11: Add failing concurrency protection tests for delete/state races

**Files:**
- Modify: `backend/tests/test_phenopackets_delete_revision.py`

- [ ] **Step 1 — add a test that proves final mutation must be guarded**

Use a shape like:

```python
async def test_delete_fails_when_revision_changes_before_commit(...):
    ...
```

The test should simulate:

- actor A loads record at revision `n`
- actor B updates the record to revision `n+1`
- actor A attempts delete with expected revision `n`
- delete is rejected

If a true multi-session concurrent test already exists elsewhere, extend it instead of duplicating it.

- [ ] **Step 2 — run and confirm failure or insufficiency**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-workflow/backend
uv run pytest tests/test_phenopackets_delete_revision.py -v
```

Expected:

- test demonstrates the current race window or proves the current implementation is still only pre-read guarded

- [ ] **Step 3 — commit the failing test**

```bash
git add backend/tests/test_phenopackets_delete_revision.py
git commit -m "test(workflow): cover delete and revision race protection"
```

### Task 12: Guard the final delete mutation atomically

**Files:**
- Modify: `backend/app/phenopackets/services/phenopacket_service.py`

- [ ] **Step 1 — replace the blind final write with a guarded mutation**

Move away from:

```python
phenopacket = await self._repo.get_by_id(phenopacket_id)
...
phenopacket.deleted_at = datetime.now(timezone.utc)
phenopacket.deleted_by_id = actor_id
await self._repo.session.commit()
```

Use either:

```python
stmt = (
    update(Phenopacket)
    .where(
        Phenopacket.id == phenopacket_id,
        Phenopacket.deleted_at.is_(None),
        Phenopacket.revision == expected_revision,
    )
    .values(
        deleted_at=datetime.now(timezone.utc),
        deleted_by_id=actor_id,
    )
)
```

or an explicit `SELECT ... FOR UPDATE` plus guarded revision check in the same transaction.

- [ ] **Step 2 — rerun the delete-revision tests**

```bash
cd ~/development/hnf1b-db.worktrees/release-hardening-workflow/backend
uv run pytest tests/test_phenopackets_delete_revision.py tests/test_state_flows.py tests/test_api_transitions.py -v
```

Expected:

- delete race protection test passes
- no state-flow regression

- [ ] **Step 3 — commit**

```bash
git add backend/app/phenopackets/services/phenopacket_service.py backend/tests/test_phenopackets_delete_revision.py
git commit -m "fix(workflow): guard delete mutation with final revision check"
```

---

# Integration

### Task 13: Rebase or merge the three tracks and resolve only contract conflicts

**Files:**
- Modify: integration branch only as required

- [ ] **Step 1 — integrate Track B first**

```bash
cd ~/development/hnf1b-db
git checkout main
git merge --no-ff chore/release-hardening-verification
```

- [ ] **Step 2 — integrate Track A and Track C**

```bash
git merge --no-ff chore/release-hardening-auth-core
git merge --no-ff chore/release-hardening-workflow
```

Expected:

- only genuine contract conflicts are resolved
- no track’s owned files are manually rewritten without review

- [ ] **Step 3 — commit merge resolutions if needed**

Use standard merge commits only if Git requires them.

### Task 14: Run the full Batch 1 verification gate

**Files:**
- Modify: none

- [ ] **Step 1 — run backend auth verification**

```bash
cd ~/development/hnf1b-db/backend
uv run pytest tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py tests/test_auth_token_issuance_hardening.py tests/test_auth_refresh_invalidation.py -v
```

- [ ] **Step 2 — run backend workflow verification**

```bash
cd ~/development/hnf1b-db/backend
uv run pytest tests/test_state_flows.py tests/test_api_transitions.py tests/test_phenopackets_delete_revision.py tests/test_crud_related_and_timeline.py -v
```

- [ ] **Step 3 — run frontend verification**

```bash
cd ~/development/hnf1b-db/frontend
npx vitest run tests/unit/components/comments/CommentBody.spec.js tests/unit/components/comments/CommentComposer.spec.js tests/unit/components/comments/CommentItem.spec.js tests/unit/stores/authStore.spec.js
```

- [ ] **Step 4 — record the real outcome**

If all commands pass, note Batch 1 as verification-green in the release-hardening master plan.

If any command fails:

- classify each failure as Track A, B, or C ownership
- do not claim completion

### Task 15: Update the master release-hardening plan with Batch 1 status

**Files:**
- Modify: `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`

- [ ] **Step 1 — add a short Batch 1 status section**

Insert:

```md
## Batch 1 Status

- Track A: [done / follow-up needed]
- Track B: [done / follow-up needed]
- Track C: [done / follow-up needed]
- Verification: [green / not yet green]
```

- [ ] **Step 2 — commit**

```bash
git add .planning/plans/2026-04-15-release-hardening-and-8plus-plan.md
git commit -m "docs(planning): record batch 1 hardening status"
```

---

## Self-Review

After writing this plan I checked:

1. **Spec coverage.** The plan covers the three-track design from the Batch 1 spec: auth core, verification stability, and workflow guardrails, plus integration and status update.
2. **Placeholder scan.** The plan uses exact files, commands, and target tests. Where an implementation choice has two valid approaches, the allowable options are explicit and bounded.
3. **Type consistency.** Track ownership, worktree names, and verification commands are named consistently throughout the document.
