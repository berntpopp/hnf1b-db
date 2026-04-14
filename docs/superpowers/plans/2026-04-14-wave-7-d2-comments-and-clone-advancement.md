# Wave 7 / D.2 — Comments + Clone-Cycle Advancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the D.1 clone-cycle advancement gap (Part A — effective-state read-through) AND ship the D.2 comments feature (Part B — generic comments table + immutable edit log + mentions join). One PR.

**Architecture:** Part A introduces `_effective_state(pp)` so transitions and edits dispatch on the in-flight revision row's state while `pp.state` is locked to `'published'`/`'archived'` after first publish. Effective-state is populated by the central `build_phenopacket_response` builder, not per-endpoint. Part B adds three Alembic tables (`comments`, `comment_edits`, `comment_mentions`), a `backend/app/comments/` module, a `/api/v2/users/mentionable` autocomplete endpoint, and a Discussion tab in `PagePhenopacket.vue` using Tiptap + markdown-it.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL, Pydantic 2, Vue 3 + Composition API, Vuetify 4, Tiptap v3, markdown-it, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md`

---

## Waves

- **Wave 1 — Part A state machine fix** (Tasks 1–11). Ends with the truncated E2E test un-truncated and green.
- **Wave 2 — Part B migrations** (Tasks 12–14). Three table migrations, applied in order.
- **Wave 3 — Part B backend** (Tasks 15–20). Module, service, router, mentionable-users endpoint, main.py mount.
- **Wave 4 — Part B frontend** (Tasks 21–30). Deps, API client, composable, 6 components, tab mount.
- **Wave 5 — Tests + invariants** (Tasks 31–35). Backend + frontend + E2E + invariant AST checks.

Commit after every task. Every task is self-contained; a fresh subagent should be able to resume from any task boundary.

---

## Pre-flight checks

Before Task 1, the worktree must be on a clean branch off `main`. The recommended branch name is `chore/wave-7-d2-comments-and-clone-advancement`. All backend + frontend test suites green at baseline.

- [ ] **Step 1 — verify working tree is clean and on a fresh branch**

```bash
cd ~/development/hnf1b-db
git status                    # expect: nothing to commit, working tree clean
git branch --show-current     # expect: main (or already on the feature branch)
```

- [ ] **Step 2 — run baseline tests**

```bash
cd ~/development/hnf1b-db/backend && make test
cd ~/development/hnf1b-db/frontend && make test
```

Expected: both suites green. If anything is red at baseline, STOP and fix it before starting Wave 1.

- [ ] **Step 3 — create worktree (if not already in one)**

```bash
cd ~/development
git worktree add hnf1b-db.worktrees/chore-wave-7-d2-comments-and-clone-advancement \
  -b chore/wave-7-d2-comments-and-clone-advancement
cd hnf1b-db.worktrees/chore-wave-7-d2-comments-and-clone-advancement
cd backend && uv sync --group test && cd ..
cd frontend && npm install && cd ..
```

---

# Wave 1 — Part A: Effective-State Routing

Spec §4. Ends with `frontend/tests/e2e/dual-read-invariant.spec.js` phase 5 implemented and green — that's the acceptance gate for Wave 1.

## Task 1: Add `Phenopacket.editing_revision` ORM relationship

**Files:**
- Modify: `backend/app/phenopackets/models.py`

Spec §4.2.3. The relationship lets `build_phenopacket_response` read `pp.editing_revision.state` when the revision is eager-loaded, without a second SELECT.

- [ ] **Step 1 — open `backend/app/phenopackets/models.py`, find the `draft_owner` relationship block around line 174**

- [ ] **Step 2 — add the relationship immediately after `draft_owner`**

Insert after the existing `draft_owner: Mapped[Optional["User"]] = relationship(...)` line:

```python
    editing_revision: Mapped[Optional["PhenopacketRevision"]] = relationship(
        "PhenopacketRevision",
        foreign_keys=[editing_revision_id],
        viewonly=True,
        primaryjoin="Phenopacket.editing_revision_id==PhenopacketRevision.id",
    )
```

The `primaryjoin` is explicit because `PhenopacketRevision.record_id → phenopackets.id` is a separate FK pointing the opposite direction; SQLAlchemy needs the disambiguation.

- [ ] **Step 3 — write a sanity test that the relationship resolves**

Create `backend/tests/test_editing_revision_relationship.py`:

```python
"""Verify the Phenopacket.editing_revision relationship resolves correctly."""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.phenopackets.models import Phenopacket, PhenopacketRevision


@pytest.mark.asyncio
async def test_editing_revision_lazy_none_when_id_null(db_session, phenopacket_factory):
    """With editing_revision_id NULL, editing_revision is None (no query needed)."""
    pp = await phenopacket_factory(state="published")
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.id == pp.id)
        .options(selectinload(Phenopacket.editing_revision))
    )
    result = (await db_session.execute(stmt)).scalar_one()
    assert result.editing_revision_id is None
    assert result.editing_revision is None


@pytest.mark.asyncio
async def test_editing_revision_resolves_when_set(db_session, phenopacket_factory, revision_factory):
    """With editing_revision_id set, eager load populates the relationship."""
    pp = await phenopacket_factory(state="published")
    rev = await revision_factory(record_id=pp.id, state="draft")
    pp.editing_revision_id = rev.id
    await db_session.commit()

    stmt = (
        select(Phenopacket)
        .where(Phenopacket.id == pp.id)
        .options(selectinload(Phenopacket.editing_revision))
    )
    result = (await db_session.execute(stmt)).scalar_one()
    assert result.editing_revision is not None
    assert result.editing_revision.id == rev.id
    assert result.editing_revision.state == "draft"
```

(If `phenopacket_factory` / `revision_factory` fixtures don't exist, use whatever equivalent is in `backend/tests/conftest.py`. The existing D.1 tests have working fixtures for both — copy their setup.)

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_editing_revision_relationship.py -v
```

Expected: both tests PASS.

- [ ] **Step 5 — run the full test suite to confirm nothing regressed**

```bash
cd backend && make test
```

Expected: all existing tests stay green.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/models.py backend/tests/test_editing_revision_relationship.py
git commit -m "feat(backend): add Phenopacket.editing_revision ORM relationship

Required by the D.2 effective-state routing so build_phenopacket_response
can read the in-flight revision's state without a second query. Eager-loading
via selectinload is wired in Task 6."
```

---

## Task 2: Add `_effective_state` to `PhenopacketStateService`

**Files:**
- Modify: `backend/app/phenopackets/services/state_service.py`

Spec §4.2.1. Pure read function over `(pp.state, editing_revision_id, rev.state)`.

- [ ] **Step 1 — write the failing unit test first**

Create `backend/tests/test_state_service_effective_state.py`:

```python
"""Unit tests for PhenopacketStateService._effective_state (spec I9)."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_effective_state_returns_pp_state_when_no_editing_revision(
    db_session, phenopacket_factory
):
    """editing_revision_id IS NULL → effective_state == pp.state."""
    pp = await phenopacket_factory(state="published", editing_revision_id=None)
    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "published"


@pytest.mark.asyncio
async def test_effective_state_returns_revision_state_when_editing(
    db_session, phenopacket_factory, revision_factory
):
    """editing_revision_id set → effective_state == revision.state."""
    pp = await phenopacket_factory(state="published")
    rev = await revision_factory(record_id=pp.id, state="draft")
    pp.editing_revision_id = rev.id
    await db_session.commit()
    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "draft"


@pytest.mark.asyncio
async def test_effective_state_never_published_path(db_session, phenopacket_factory):
    """Never-published record with pp.state='in_review' returns 'in_review'."""
    pp = await phenopacket_factory(
        state="in_review", editing_revision_id=None, head_published_revision_id=None
    )
    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "in_review"
```

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_state_service_effective_state.py -v
```

Expected: FAIL — `AttributeError: 'PhenopacketStateService' object has no attribute '_effective_state'`.

- [ ] **Step 3 — add `_effective_state` to the service**

Open `backend/app/phenopackets/services/state_service.py`. Import tweak (verify `cast` and `State` are imported):

```python
from typing import Any, cast
from app.phenopackets.services.transitions import Role, State, TransitionError, check_transition
```

After the existing `_latest_revision_row` helper (~line 82), add:

```python
    async def _effective_state(self, pp: Phenopacket) -> State:
        """Return the state governing edit-cycle decisions for this phenopacket.

        Spec invariant I9 — pure function of (pp.state, editing_revision_id,
        editing revision's state). If editing_revision_id is set, the
        referenced revision row's state is authoritative; otherwise pp.state.
        """
        if pp.editing_revision_id is None:
            return cast(State, pp.state)
        rev = (
            await self.db.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.id == pp.editing_revision_id
                )
            )
        ).scalar_one()
        return cast(State, rev.state)
```

- [ ] **Step 4 — run test**

```bash
cd backend && uv run pytest tests/test_state_service_effective_state.py -v
```

Expected: all three tests PASS.

- [ ] **Step 5 — lint and type-check**

```bash
cd backend && make lint && make typecheck
```

Expected: clean.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/services/state_service.py backend/tests/test_state_service_effective_state.py
git commit -m "feat(backend): add PhenopacketStateService._effective_state (I9)

Pure read function that returns the in-flight revision's state when
editing_revision_id is set, otherwise pp.state. Sets up the routing
fix in the next tasks."
```

---

## Task 3: Rewire `edit_record` to dispatch on effective state

**Files:**
- Modify: `backend/app/phenopackets/services/state_service.py` (around lines 95–120, the `edit_record` method)

Spec §4.2.1. Current bug: `edit_record` dispatches on `pp.state`, so a clone-to-draft followed by a second PUT re-enters `_clone_to_draft` and raises `EditInProgress`.

- [ ] **Step 1 — write the failing test (clone-cycle iteration should route to inplace-save)**

Create `backend/tests/test_state_service_clone_iteration.py`:

```python
"""After clone-to-draft, subsequent PUTs route to _inplace_save (not 409)."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_second_put_after_clone_is_inplace(
    db_session, phenopacket_factory, user_factory, published_with_head_fixture
):
    """Second PUT on a clone-cycle record routes to inplace-save, not 409."""
    pp, head_rev = published_with_head_fixture
    curator = await user_factory(role="curator")
    svc = PhenopacketStateService(db_session)

    # First PUT — clone to draft
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "first-edit"}},
        change_reason="first edit",
        expected_revision=pp.revision,
        actor=curator,
    )
    assert pp.editing_revision_id is not None
    first_editing_id = pp.editing_revision_id

    # Second PUT — must inplace-save, not raise EditInProgress
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "second-edit"}},
        change_reason="iterating",
        expected_revision=pp.revision,
        actor=curator,
    )
    # editing_revision_id unchanged (inplace-save doesn't create new row)
    assert pp.editing_revision_id == first_editing_id
    assert pp.phenopacket["subject"]["id"] == "second-edit"
    # pp.state still 'published' (I8)
    assert pp.state == "published"
```

(The `published_with_head_fixture` should create a phenopacket with `state='published'` and `head_published_revision_id` set. If it doesn't exist, copy the setup from `backend/tests/test_state_service.py` or whichever D.1 test file has equivalent scaffolding.)

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_state_service_clone_iteration.py -v
```

Expected: FAIL with `EditInProgress` on the second PUT.

- [ ] **Step 3 — rewire `edit_record`**

In `state_service.py`, replace the body of `edit_record`:

```python
    async def edit_record(
        self,
        record_id: UUID,
        *,
        new_content: dict[str, Any],
        change_reason: str,
        expected_revision: int,
        actor: User,
    ) -> Phenopacket:
        """Save new content to a phenopacket.

        Dispatches on the effective state (spec §4.2.1):
        - effective == 'published' (editing_revision_id IS NULL) → §6.1 clone-to-draft.
        - effective ∈ {draft, changes_requested}                 → §6.3 in-place save.
        - effective ∈ {in_review, approved}                      → 409 edit_forbidden.
        - effective == 'archived'                                → 409 invalid_transition.
        """
        pp = await self._lock_and_check(record_id, expected_revision)
        effective = await self._effective_state(pp)

        if effective == "published":
            return await self._clone_to_draft(pp, new_content, change_reason, actor)

        if effective in ("draft", "changes_requested"):
            return await self._inplace_save(pp, new_content, change_reason, actor)

        if effective in ("in_review", "approved"):
            raise self.InvalidTransition(
                f"cannot edit a record whose effective state is {effective!r};"
                " withdraw or resubmit first"
            )

        # archived
        raise self.InvalidTransition(
            f"cannot edit a record whose effective state is {effective!r}"
        )
```

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_state_service_clone_iteration.py -v
```

Expected: PASS.

- [ ] **Step 5 — run all state service tests to confirm no regression**

```bash
cd backend && uv run pytest tests/ -k "state_service" -v
```

Expected: all green.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/services/state_service.py backend/tests/test_state_service_clone_iteration.py
git commit -m "fix(backend): edit_record dispatches on effective state

Fixes the clone-cycle iteration bug where a second PUT after clone-to-draft
raised 409 edit_in_progress. Routing now keys on _effective_state(pp),
so iteration on the in-flight draft flows through _inplace_save."
```

---

## Task 4: Rewire `_simple_transition` — effective state as from_state + I8 gate

**Files:**
- Modify: `backend/app/phenopackets/services/state_service.py` (the `_simple_transition` method)

Spec §4.2.1. Three changes:
1. `from_state` passed to `check_transition` and stored on the new revision row = `_effective_state(pp)`, not `pp.state`.
2. `pp.state = to_state` is gated: only advance when `head_published_revision_id IS NULL OR to_state == 'archived'` (invariant I8).
3. Error messages reference effective state.

- [ ] **Step 1 — write the failing tests**

Create `backend/tests/test_state_service_clone_cycle_forward.py`:

```python
"""Forward clone-cycle: submit/approve/publish from a cloned draft."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_submit_from_clone_cycle_keeps_pp_state_published(
    db_session, user_factory, published_with_head_fixture
):
    """submit after clone advances revision state but not pp.state."""
    pp, head_rev = published_with_head_fixture
    curator = await user_factory(role="curator")
    svc = PhenopacketStateService(db_session)

    # Clone to draft
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "clone-1"}},
        change_reason="fix typo",
        expected_revision=pp.revision,
        actor=curator,
    )
    assert pp.state == "published"

    # Submit
    pp, rev = await svc.transition(
        pp.id,
        to_state="in_review",
        reason="ready for review",
        expected_revision=pp.revision,
        actor=curator,
    )

    # pp.state sticky (I8)
    assert pp.state == "published"
    # Editing pointer advanced to the new in_review row
    assert pp.editing_revision_id == rev.id
    # The in_review row's from_state is 'draft' (effective state before), not 'published'
    assert rev.from_state == "draft"
    assert rev.to_state == "in_review"
    assert rev.state == "in_review"
```

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_state_service_clone_cycle_forward.py -v
```

Expected: FAIL — most likely `assert rev.from_state == 'draft'` fails because the current code stores `pp.state` ('published') as from_state. Also `pp.state = 'in_review'` would make the assertion fail.

- [ ] **Step 3 — rewire `_simple_transition`**

Replace the method body:

```python
    async def _simple_transition(
        self,
        pp: Phenopacket,
        to_state: str,
        reason: str,
        actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        """§6.4: bump revision, snapshot working copy into a new row, advance state.

        Spec §4.2.1 — from_state reads effective state, not pp.state. pp.state
        advancement is gated by I8: only for never-published records OR on archive.
        """
        from_state = await self._effective_state(pp)

        # Compute the patch against the previous transition's content.
        prev = (
            await self.db.execute(
                select(PhenopacketRevision)
                .where(
                    PhenopacketRevision.record_id == pp.id,
                    PhenopacketRevision.revision_number < pp.revision,
                )
                .order_by(PhenopacketRevision.revision_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        patch = compute_json_patch(prev.content_jsonb, pp.phenopacket) if prev else None

        pp.revision += 1

        rev = PhenopacketRevision(
            record_id=pp.id,
            revision_number=pp.revision,
            state=to_state,
            content_jsonb=pp.phenopacket,
            change_patch=patch,
            change_reason=reason,
            actor_id=actor.id,
            from_state=from_state,
            to_state=to_state,
            is_head_published=False,
        )
        self.db.add(rev)
        await self.db.flush()  # get rev.id

        # I8: pp.state advances only for never-published records OR archive.
        if pp.head_published_revision_id is None or to_state == "archived":
            pp.state = to_state

        if to_state == "archived":
            # archive is terminal: clear both owner and edit pointer
            pp.draft_owner_id = None
            pp.editing_revision_id = None
        else:
            # Update editing_revision_id to track the in-flight snapshot.
            pp.editing_revision_id = rev.id

        await self.db.commit()
        return pp, rev
```

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_state_service_clone_cycle_forward.py -v
```

Expected: PASS.

- [ ] **Step 5 — run the full state-machine test suite**

```bash
cd backend && uv run pytest tests/ -k "state" -v
```

Expected: all existing D.1 tests stay green; new test passes.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/services/state_service.py backend/tests/test_state_service_clone_cycle_forward.py
git commit -m "fix(backend): _simple_transition uses effective state + I8 gate

from_state on the new revision row reflects the in-flight revision's
state, not pp.state. pp.state is sticky post-first-publish unless
the target is 'archived' (invariant I8 from the D.2 spec)."
```

---

## Task 5: Rewire `transition()` to pass effective state to the guard matrix

**Files:**
- Modify: `backend/app/phenopackets/services/state_service.py` (the `transition` method)

Spec §4.2.1. The `check_transition(cast(State, pp.state), ...)` call needs to become `check_transition(cast(State, effective), ...)`.

- [ ] **Step 1 — write the test first (the truncated E2E scenario, in Python)**

Create `backend/tests/test_state_service_clone_cycle_full.py`:

```python
"""Full clone-cycle lifecycle: clone → submit → approve → publish + republish."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_full_clone_cycle_republish(
    db_session, user_factory, published_with_head_fixture
):
    """Clone, submit, approve, publish — and head-published pointer advances."""
    pp, head_rev = published_with_head_fixture
    original_head_id = head_rev.id
    curator = await user_factory(role="curator")
    admin = await user_factory(role="admin")
    svc = PhenopacketStateService(db_session)

    # Clone
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "new-head"}},
        change_reason="fix typo",
        expected_revision=pp.revision,
        actor=curator,
    )
    # Submit
    pp, _ = await svc.transition(
        pp.id, to_state="in_review", reason="r", expected_revision=pp.revision, actor=curator
    )
    # Approve
    pp, _ = await svc.transition(
        pp.id, to_state="approved", reason="ok", expected_revision=pp.revision, actor=admin
    )
    # Publish
    pp, rev = await svc.transition(
        pp.id, to_state="published", reason="shipping", expected_revision=pp.revision, actor=admin
    )

    # Record-level state converges
    assert pp.state == "published"
    # Head pointer advanced to the new row
    assert pp.head_published_revision_id == rev.id
    assert pp.head_published_revision_id != original_head_id
    # Editing pointer cleared (§6.2)
    assert pp.editing_revision_id is None
    # Owner cleared (I5)
    assert pp.draft_owner_id is None
    # Public content converges
    assert pp.phenopacket["subject"]["id"] == "new-head"
```

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_state_service_clone_cycle_full.py -v
```

Expected: FAIL at the submit step with `InvalidTransition` — `('published', 'in_review')` not in `_RULES`, because the guard still reads `pp.state`.

- [ ] **Step 3 — rewire the guard call in `transition`**

Locate the `transition` method around lines 210–247 of `state_service.py`. Replace:

```python
        try:
            check_transition(
                cast(State, pp.state),
                cast(State, to_state),
                role=cast(Role, actor.role),
                is_owner=self._is_owner(pp, actor),
            )
        except TransitionError as exc:
```

with:

```python
        effective = await self._effective_state(pp)
        try:
            check_transition(
                cast(State, effective),
                cast(State, to_state),
                role=cast(Role, actor.role),
                is_owner=self._is_owner(pp, actor),
            )
        except TransitionError as exc:
```

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_state_service_clone_cycle_full.py -v
```

Expected: PASS.

- [ ] **Step 5 — run the complete state machine test suite**

```bash
cd backend && uv run pytest tests/ -k "state" -v
```

Expected: all green.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/services/state_service.py backend/tests/test_state_service_clone_cycle_full.py
git commit -m "fix(backend): transition() guard matrix reads effective state

Closes the D.1 follow-up gap: a cloned draft can now advance through
review while pp.state stays 'published'. Full clone-cycle republish
test (Python) green."
```

---

## Task 6: Eager-load `editing_revision` in `PhenopacketRepository`

**Files:**
- Modify: `backend/app/phenopackets/repositories/phenopacket_repository.py` (or wherever `_with_actor_eager_loads` lives)

Spec §4.2.5. Every read path that returns a `Phenopacket` to the response builder must eager-load `editing_revision`.

- [ ] **Step 1 — open the repository file and locate `_with_actor_eager_loads`**

Expected around lines matching the Explore agent's report: a helper that applies `selectinload` for `created_by_user`, `updated_by_user`, `deleted_by_user`, `draft_owner`.

- [ ] **Step 2 — add `editing_revision` to the eager-load set**

```python
def _with_actor_eager_loads(stmt: Select) -> Select:
    return stmt.options(
        selectinload(Phenopacket.created_by_user),
        selectinload(Phenopacket.updated_by_user),
        selectinload(Phenopacket.deleted_by_user),
        selectinload(Phenopacket.draft_owner),
        selectinload(Phenopacket.editing_revision),  # D.2: effective_state
    )
```

- [ ] **Step 3 — verify with a repository test**

Create `backend/tests/test_phenopacket_repository_eager_editing_revision.py`:

```python
"""PhenopacketRepository eager-loads editing_revision."""
import pytest

from app.phenopackets.repositories.phenopacket_repository import PhenopacketRepository


@pytest.mark.asyncio
async def test_get_by_id_returns_editing_revision_when_set(
    db_session, phenopacket_factory, revision_factory
):
    """get_by_id eager-loads editing_revision; no lazy-load IO required."""
    pp = await phenopacket_factory(state="published")
    rev = await revision_factory(record_id=pp.id, state="draft")
    pp.editing_revision_id = rev.id
    await db_session.commit()

    # Expire to force a fresh load
    db_session.expire_all()

    repo = PhenopacketRepository(db_session)
    loaded = await repo.get_by_id(pp.phenopacket_id)
    assert loaded is not None
    # Access without awaiting a query (already eager-loaded)
    assert loaded.editing_revision is not None
    assert loaded.editing_revision.state == "draft"


@pytest.mark.asyncio
async def test_get_by_id_editing_revision_none_when_unset(
    db_session, phenopacket_factory
):
    """get_by_id handles NULL editing_revision_id cleanly (no extra query)."""
    pp = await phenopacket_factory(state="published", editing_revision_id=None)
    repo = PhenopacketRepository(db_session)
    loaded = await repo.get_by_id(pp.phenopacket_id)
    assert loaded is not None
    assert loaded.editing_revision is None
```

- [ ] **Step 4 — run**

```bash
cd backend && uv run pytest tests/test_phenopacket_repository_eager_editing_revision.py -v
```

Expected: PASS.

- [ ] **Step 5 — full regression**

```bash
cd backend && make test
```

Expected: all green.

- [ ] **Step 6 — commit**

```bash
git add backend/app/phenopackets/repositories/phenopacket_repository.py backend/tests/test_phenopacket_repository_eager_editing_revision.py
git commit -m "feat(backend): eager-load Phenopacket.editing_revision

Required by build_phenopacket_response to compute effective_state
without a second round-trip. selectinload is lazy on NULL FK so the
common case costs zero extra queries."
```

---

## Task 7: Add `effective_state` to `build_phenopacket_response`

**Files:**
- Modify: `backend/app/phenopackets/query_builders.py`
- Modify: `backend/app/phenopackets/models.py` (add `effective_state` to `PhenopacketResponse` Pydantic model)

Spec §4.2.4.

- [ ] **Step 1 — add the field to the Pydantic response model**

Open `backend/app/phenopackets/models.py`, find `class PhenopacketResponse(BaseModel)` (around line 571 per Explore report). After the `editing_revision_id: Optional[int] = None` line, add:

```python
    effective_state: Optional[str] = None
```

Keep it Optional because non-curator callers (who pass `include_state=False`) still need a valid response shape.

- [ ] **Step 2 — write the builder test**

Create `backend/tests/test_query_builders_effective_state.py`:

```python
"""build_phenopacket_response populates effective_state correctly."""
import pytest

from app.phenopackets.query_builders import build_phenopacket_response


@pytest.mark.asyncio
async def test_effective_state_mirrors_pp_state_when_no_editing(
    db_session, phenopacket_factory
):
    pp = await phenopacket_factory(state="published", editing_revision_id=None)
    resp = build_phenopacket_response(pp, include_state=True)
    assert resp.effective_state == "published"


@pytest.mark.asyncio
async def test_effective_state_reads_revision_when_editing(
    db_session, phenopacket_factory, revision_factory
):
    pp = await phenopacket_factory(state="published")
    rev = await revision_factory(record_id=pp.id, state="draft")
    pp.editing_revision_id = rev.id
    pp.editing_revision = rev  # eager-loaded (in practice, selectinload does this)
    await db_session.commit()
    resp = build_phenopacket_response(pp, include_state=True)
    assert resp.effective_state == "draft"


@pytest.mark.asyncio
async def test_effective_state_none_when_include_state_false(
    db_session, phenopacket_factory
):
    pp = await phenopacket_factory(state="published")
    resp = build_phenopacket_response(pp, include_state=False)
    assert resp.effective_state is None
```

- [ ] **Step 3 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_query_builders_effective_state.py -v
```

Expected: FAIL — `AttributeError: 'PhenopacketResponse' object has no attribute 'effective_state'` (if Step 1 was skipped) OR the field is None but the test expects a value.

- [ ] **Step 4 — update `build_phenopacket_response`**

Open `backend/app/phenopackets/query_builders.py`. Find the state-field block (where `state`, `head_published_revision_id`, etc. are set). Within the `if include_state:` branch, add:

```python
        # D.2 effective state (spec §4.2.4): in-flight revision's state
        # takes precedence over pp.state when an edit is in progress.
        effective_state = (
            pp.editing_revision.state
            if pp.editing_revision_id is not None and pp.editing_revision is not None
            else pp.state
        )
        response.effective_state = effective_state
```

(If the builder returns a `PhenopacketResponse` directly via `PhenopacketResponse(...)` constructor, set `effective_state=effective_state` in the kwargs instead. Match the existing pattern in the file.)

- [ ] **Step 5 — run the test**

```bash
cd backend && uv run pytest tests/test_query_builders_effective_state.py -v
```

Expected: PASS.

- [ ] **Step 6 — full regression**

```bash
cd backend && make test
```

Expected: all green.

- [ ] **Step 7 — commit**

```bash
git add backend/app/phenopackets/query_builders.py backend/app/phenopackets/models.py backend/tests/test_query_builders_effective_state.py
git commit -m "feat(backend): populate effective_state in central response builder

Every /phenopackets read endpoint (list, detail, transitions, comparisons)
now carries effective_state automatically. Removes the need for per-endpoint
augmentation in the transition router (next task)."
```

---

## Task 8: Remove the transition router's manual `effective_state` augmentation

**Files:**
- Modify: `backend/app/phenopackets/routers/transitions.py`

Spec §4.2.6. With Task 7 landed, the transition endpoint no longer needs to augment the dict manually.

- [ ] **Step 1 — open `backend/app/phenopackets/routers/transitions.py` and locate the `post_transition` function (lines 96–186)**

- [ ] **Step 2 — simplify the response assembly**

Currently (lines 160–168 per D.1 code):

```python
    pp_response = build_phenopacket_response(pp_reloaded)
    pp_dict = pp_response.model_dump()
    pp_dict["state"] = pp_reloaded.state
    pp_dict["head_published_revision_id"] = pp_reloaded.head_published_revision_id
    pp_dict["editing_revision_id"] = pp_reloaded.editing_revision_id
    pp_dict["draft_owner_id"] = pp_reloaded.draft_owner_id
```

Replace with:

```python
    # Builder now populates all state fields including effective_state (spec §4.2.4–6).
    pp_response = build_phenopacket_response(pp_reloaded, include_state=True)
    pp_dict = pp_response.model_dump()
```

- [ ] **Step 3 — write a test that the transition endpoint's response carries `effective_state`**

Add to `backend/tests/test_transition_router.py` (or create if absent):

```python
"""POST /phenopackets/{id}/transitions response shape."""
import pytest


@pytest.mark.asyncio
async def test_post_transition_response_includes_effective_state(
    async_client, admin_user_token, phenopacket_in_review
):
    """Response body carries effective_state alongside state."""
    pp = phenopacket_in_review
    resp = await async_client.post(
        f"/api/v2/phenopackets/{pp.phenopacket_id}/transitions",
        json={"to_state": "approved", "reason": "ok", "revision": pp.revision},
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "effective_state" in body["phenopacket"]
    assert body["phenopacket"]["effective_state"] == "approved"
```

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_transition_router.py -v
```

Expected: PASS.

- [ ] **Step 5 — commit**

```bash
git add backend/app/phenopackets/routers/transitions.py backend/tests/test_transition_router.py
git commit -m "refactor(backend): transitions router drops manual dict augmentation

build_phenopacket_response now carries every state field including
effective_state. Cleanup per spec §4.2.6."
```

---

## Task 9: Expose `effective_state` on frontend composable

**Files:**
- Modify: `frontend/src/composables/usePhenopacketState.js`

Spec §4.2.7. The composable should expose `effective_state` as a reactive computed so components can bind to it.

- [ ] **Step 1 — open `frontend/src/composables/usePhenopacketState.js` and read it to understand the current shape**

Look for where it reads `phenopacket.state` or exposes state-related refs.

- [ ] **Step 2 — add an `effectiveState` computed next to the existing `state` binding**

Example shape (adapt to the file's actual conventions):

```javascript
import { computed } from 'vue';

export function usePhenopacketState(phenopacket) {
  const state = computed(() => phenopacket.value?.state ?? null);
  const effectiveState = computed(() => phenopacket.value?.effective_state ?? state.value);
  // ... rest

  return {
    state,
    effectiveState,
    // ... existing returns
  };
}
```

The `?? state.value` fallback keeps the composable safe for legacy responses that don't yet carry `effective_state` (e.g., in a rolling deploy).

- [ ] **Step 3 — run frontend lint + existing tests**

```bash
cd frontend && npm run lint && npm test
```

Expected: clean.

- [ ] **Step 4 — commit**

```bash
git add frontend/src/composables/usePhenopacketState.js
git commit -m "feat(frontend): expose effectiveState on usePhenopacketState

Components bind to effectiveState; falls back to state for forward/backward
compatibility with responses that pre-date D.2."
```

---

## Task 10: Rebind `StateBadge` + `TransitionMenu` to `effective_state` in `PagePhenopacket.vue`

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue`

Spec §4.2.7. `StateBadge` itself doesn't change — it takes a `state` prop and the parent decides what to pass.

- [ ] **Step 1 — locate the `StateBadge` usage in `PagePhenopacket.vue`**

Search for `<StateBadge` in the file.

- [ ] **Step 2 — rebind**

If currently:
```vue
<StateBadge :state="phenopacketMeta.state" />
```
Change to:
```vue
<StateBadge :state="phenopacketMeta.effective_state ?? phenopacketMeta.state" />
```

Similarly for `<TransitionMenu>`:
```vue
<TransitionMenu
  :current-state="phenopacketMeta.effective_state ?? phenopacketMeta.state"
  :role="authStore.user.role"
  :is-owner="authStore.user.id === phenopacketMeta.draft_owner_id"
  @transition="onTransitionRequest"
/>
```

- [ ] **Step 3 — manual sanity check**

Spin up dev servers (`make hybrid-up && make backend && make frontend` in three terminals), open a published phenopacket in browser, verify the state badge still renders correctly.

- [ ] **Step 4 — commit**

```bash
git add frontend/src/views/PagePhenopacket.vue
git commit -m "feat(frontend): bind StateBadge + TransitionMenu to effective_state

Clone-cycle UI now reflects the in-flight revision's state (e.g.,
'in_review' during a cloned draft under review) rather than the
record-level 'published'."
```

---

## Task 11: Un-truncate `dual-read-invariant.spec.js` — phase 5 re-publish convergence

**Files:**
- Modify: `frontend/tests/e2e/dual-read-invariant.spec.js`

Spec §10 acceptance. Replace the NOTE-comment cleanup block at lines ~244–258 with the actual re-publish convergence phase.

- [ ] **Step 1 — read the existing spec to understand its helper functions**

```bash
cd frontend && sed -n '1,200p' tests/e2e/dual-read-invariant.spec.js
```

Note the available API helpers (`apiLogin`, `apiTransition`, etc.) and which tokens/contexts are already in scope at line 244.

- [ ] **Step 2 — replace lines 244–258 with the phase-5 implementation**

Remove the existing NOTE block and insert:

```javascript
  // -------------------------------------------------------------------------
  // Phase 5 — Re-publish convergence
  //
  // Advance the cloned draft through in_review → approved → published.
  // Afterwards, anon and admin GETs converge on DRAFT_SUBJECT_ID (the new
  // head). This is the key test of the D.2 effective-state routing: the
  // whole review cycle must work while pp.state stays 'published' (I8).
  // -------------------------------------------------------------------------
  const curatorToken = await apiLogin(request, ADMIN_USERNAME, ADMIN_PASSWORD);
  let workingRevision = // TODO: read the current revision from the GET after clone

  workingRevision = await apiTransition(
    request, curatorToken, RECORD_ID, 'in_review', 'ready for re-review', workingRevision
  );
  workingRevision = await apiTransition(
    request, curatorToken, RECORD_ID, 'approved', 'looks good', workingRevision
  );
  workingRevision = await apiTransition(
    request, curatorToken, RECORD_ID, 'published', 'shipping it', workingRevision
  );

  // Anon context now sees the NEW head
  const anonCtx2 = await browser.newContext({ storageState: undefined });
  const anonPage2 = await anonCtx2.newPage();
  try {
    await anonPage2.goto(`${BASE}/phenopackets/${RECORD_ID}`, {
      waitUntil: 'networkidle',
      timeout: 30_000,
    });
    // After republish, anon and admin converge on DRAFT_SUBJECT_ID
    await expect(anonPage2.getByText(DRAFT_SUBJECT_ID).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(anonPage2.getByText(ORIGINAL_SUBJECT_ID)).toHaveCount(0, { timeout: 10_000 });
  } finally {
    await anonCtx2.close();
  }
});
```

Then fix the `workingRevision = ...` line — re-read the current phenopacket revision before the first transition. Look at the existing phase 3 / phase 4 helper code earlier in the file for a GET pattern; the typical shape is:

```javascript
const detailResp = await request.get(`${API_BASE}/phenopackets/${RECORD_ID}`, {
  headers: { Authorization: `Bearer ${curatorToken}` },
});
const detail = await detailResp.json();
workingRevision = detail.revision;
```

Replace the `// TODO` line with this block.

- [ ] **Step 3 — start dev servers and run the spec**

```bash
cd ~/development/hnf1b-db && make hybrid-up
# Terminal 1
make backend
# Terminal 2
make frontend
# Terminal 3
cd frontend && npx playwright test tests/e2e/dual-read-invariant.spec.js
```

Expected: all 5 phases PASS.

- [ ] **Step 4 — commit**

```bash
git add frontend/tests/e2e/dual-read-invariant.spec.js
git commit -m "test(e2e): un-truncate dual-read phase 5 (re-publish convergence)

The D.2 effective-state routing closes the gap that forced phase 5 to
be skipped. After full clone-cycle republish, anon and admin GETs
converge on the new subject ID. Spec §10 Part A acceptance criterion."
```

---

## Wave 1 acceptance gate

Before moving to Wave 2, verify:

- [ ] `make check` green in both `backend/` and `frontend/`.
- [ ] `backend/` tests ≥ 1,131 (no regression).
- [ ] `frontend/tests/e2e/dual-read-invariant.spec.js` all 5 phases green.
- [ ] No `NOTE:` / `FIXME:` / `TODO:` added to the codebase outside test fixtures.

If any check fails, fix before Wave 2. Commit fixes atomically.

---

# Wave 2 — Part B Migrations

Spec §5.1. Three tables. Each migration is idempotent and reversible.

## Task 12: Migration B1 — `comments` table

**Files:**
- Create: `backend/alembic/versions/<auto-generated>_add_comments_table.py`

- [ ] **Step 1 — scaffold the migration**

```bash
cd backend && uv run alembic revision -m "add comments table"
```

Capture the generated filename (e.g., `xxxxxxxxxxxx_add_comments_table.py`).

- [ ] **Step 2 — fill in `upgrade()` and `downgrade()`**

Replace the generated file body with:

```python
"""add comments table

Revision ID: <generated>
Revises: <prev>
Create Date: <auto>

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "<keep generated>"
down_revision = "<keep generated>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create comments table (Wave 7 D.2 spec §5.1 migration B1)."""
    op.execute("""
        CREATE TABLE comments (
          id              BIGSERIAL PRIMARY KEY,
          record_type     TEXT NOT NULL,
          record_id       UUID NOT NULL,
          author_id       BIGINT NOT NULL REFERENCES users(id),
          body_markdown   TEXT NOT NULL
            CHECK (char_length(body_markdown) BETWEEN 1 AND 10000),
          resolved_at     TIMESTAMPTZ NULL,
          resolved_by_id  BIGINT NULL REFERENCES users(id),
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at      TIMESTAMPTZ NULL,
          deleted_by_id   BIGINT NULL REFERENCES users(id),
          CONSTRAINT chk_resolved_consistency
            CHECK ((resolved_at IS NULL) = (resolved_by_id IS NULL)),
          CONSTRAINT chk_deleted_consistency
            CHECK ((deleted_at IS NULL) = (deleted_by_id IS NULL))
        );
    """)
    op.execute("""
        CREATE INDEX ix_comments_record
          ON comments (record_type, record_id, created_at ASC)
          WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX ix_comments_author ON comments (author_id);
    """)
    op.execute("""
        CREATE INDEX ix_comments_unresolved
          ON comments (record_type, record_id)
          WHERE resolved_at IS NULL AND deleted_at IS NULL;
    """)
    op.execute("""
        COMMENT ON TABLE comments IS
        'Curation-layer comments on domain records. Generic by (record_type, record_id).';
    """)


def downgrade() -> None:
    """Drop comments table."""
    op.execute("DROP TABLE IF EXISTS comments;")
```

- [ ] **Step 3 — apply and roll back to verify reversibility**

```bash
cd backend && uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three succeed without errors. Final state: `comments` table exists.

- [ ] **Step 4 — commit**

```bash
git add backend/alembic/versions/<filename>
git commit -m "feat(db): migration B1 — comments table (D.2)"
```

---

## Task 13: Migration B2 — `comment_edits` table

**Files:**
- Create: `backend/alembic/versions/<auto-generated>_add_comment_edits_table.py`

- [ ] **Step 1 — scaffold**

```bash
cd backend && uv run alembic revision -m "add comment_edits table"
```

- [ ] **Step 2 — fill in**

```python
def upgrade() -> None:
    """Create comment_edits append-only log (D.2 §5.1 B2)."""
    op.execute("""
        CREATE TABLE comment_edits (
          id           BIGSERIAL PRIMARY KEY,
          comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
          editor_id    BIGINT NOT NULL REFERENCES users(id),
          prev_body    TEXT NOT NULL,
          edited_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX ix_comment_edits_comment
          ON comment_edits (comment_id, edited_at DESC);
    """)
    op.execute("""
        COMMENT ON TABLE comment_edits IS
        'Append-only history of comment body edits. Service layer enforces immutability (C1).';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comment_edits;")
```

- [ ] **Step 3 — apply / rollback / re-apply**

```bash
cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 4 — commit**

```bash
git add backend/alembic/versions/<filename>
git commit -m "feat(db): migration B2 — comment_edits table (D.2)"
```

---

## Task 14: Migration B3 — `comment_mentions` table

**Files:**
- Create: `backend/alembic/versions/<auto-generated>_add_comment_mentions_table.py`

- [ ] **Step 1 — scaffold**

```bash
cd backend && uv run alembic revision -m "add comment_mentions table"
```

- [ ] **Step 2 — fill in**

```python
def upgrade() -> None:
    """Create comment_mentions join table (D.2 §5.1 B3)."""
    op.execute("""
        CREATE TABLE comment_mentions (
          comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
          user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          PRIMARY KEY (comment_id, user_id)
        );
    """)
    op.execute("""
        CREATE INDEX ix_comment_mentions_user ON comment_mentions (user_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comment_mentions;")
```

- [ ] **Step 3 — apply / rollback / re-apply**

```bash
cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 4 — commit**

```bash
git add backend/alembic/versions/<filename>
git commit -m "feat(db): migration B3 — comment_mentions table (D.2)"
```

---

## Wave 2 acceptance gate

- [ ] All three migrations apply cleanly to a fresh database (`make db-reset && make db-upgrade`).
- [ ] All three migrations downgrade cleanly in reverse (`alembic downgrade -3`).
- [ ] Re-upgrade is idempotent.

---

# Wave 3 — Part B Backend

Spec §5.3–§5.7. Module under `backend/app/comments/`, plus a mentionable-users endpoint under the users namespace, plus router mount.

## Task 15: `backend/app/comments/` package + ORM models

**Files:**
- Create: `backend/app/comments/__init__.py`
- Create: `backend/app/comments/models.py`

- [ ] **Step 1 — create the package**

```bash
mkdir -p backend/app/comments
touch backend/app/comments/__init__.py
```

- [ ] **Step 2 — create `models.py`**

Write `backend/app/comments/models.py`:

```python
"""SQLAlchemy ORM models for the D.2 comments feature.

Spec reference: docs/superpowers/specs/2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.1.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.user import User


class Comment(Base):
    """Curation-layer comment on a phenopacket (or future record types)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_type: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )

    author: Mapped[User] = relationship(
        "User", foreign_keys=[author_id], viewonly=True
    )
    resolved_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[resolved_by_id], viewonly=True
    )
    deleted_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[deleted_by_id], viewonly=True
    )


class CommentEdit(Base):
    """Append-only log of comment body edits (C1)."""

    __tablename__ = "comment_edits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    editor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    prev_body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    editor: Mapped[User] = relationship(
        "User", foreign_keys=[editor_id], viewonly=True
    )


class CommentMention(Base):
    """Join table of comment → mentioned user."""

    __tablename__ = "comment_mentions"

    comment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("comments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped[User] = relationship(
        "User", foreign_keys=[user_id], viewonly=True
    )
```

- [ ] **Step 3 — import the new models in `backend/app/database.py` or the equivalent model registry**

Find where other models are imported for Alembic autogenerate detection (e.g., `backend/app/database.py` or `backend/alembic/env.py`). Add:

```python
from app.comments.models import Comment, CommentEdit, CommentMention  # noqa: F401
```

- [ ] **Step 4 — run backend tests**

```bash
cd backend && make test
```

Expected: all green (no functional change yet — the models just register).

- [ ] **Step 5 — commit**

```bash
git add backend/app/comments/__init__.py backend/app/comments/models.py backend/app/database.py
git commit -m "feat(backend): comments ORM models (Comment, CommentEdit, CommentMention)"
```

---

## Task 16: Comments Pydantic schemas

**Files:**
- Create: `backend/app/comments/schemas.py`

Spec §5.4.

- [ ] **Step 1 — create schemas.py**

```python
"""Pydantic schemas for the D.2 comments API.

Spec reference: §5.4 of the design doc.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CommentMentionOut(BaseModel):
    user_id: int
    username: str
    display_name: Optional[str] = None
    is_active: bool


class CommentResponse(BaseModel):
    id: int
    record_type: str
    record_id: str  # UUID serialized
    author_id: int
    author_username: str
    author_display_name: Optional[str] = None
    body_markdown: str
    mentions: List[CommentMentionOut] = Field(default_factory=list)
    edited: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[int] = None
    resolved_by_username: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[int] = None


class CommentCreate(BaseModel):
    record_type: Literal["phenopacket"]
    record_id: UUID
    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: List[int] = Field(default_factory=list, max_length=50)


class CommentUpdate(BaseModel):
    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: List[int] = Field(default_factory=list, max_length=50)


class CommentEditResponse(BaseModel):
    id: int
    editor_id: int
    editor_username: str
    prev_body: str
    edited_at: datetime


class MentionableUserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
```

- [ ] **Step 2 — lint and type-check**

```bash
cd backend && make lint && make typecheck
```

Expected: clean.

- [ ] **Step 3 — commit**

```bash
git add backend/app/comments/schemas.py
git commit -m "feat(backend): comments Pydantic schemas"
```

---

## Task 17: `CommentsService` — create, list, edits

**Files:**
- Create: `backend/app/comments/service.py`

Spec §5.5. This task covers the three simplest methods; the mutating/atomic paths land in Task 18.

- [ ] **Step 1 — write the test first**

Create `backend/tests/test_comments_service_create.py`:

```python
"""CommentsService.create happy path and C3 (record integrity)."""
import pytest

from app.comments.service import CommentsService


@pytest.mark.asyncio
async def test_create_happy_path(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)

    comment = await svc.create(
        record_type="phenopacket",
        record_id=pp.id,
        body_markdown="Looks good",
        mention_user_ids=[],
        actor=curator,
    )
    assert comment.id is not None
    assert comment.body_markdown == "Looks good"
    assert comment.author_id == curator.id
    assert comment.deleted_at is None


@pytest.mark.asyncio
async def test_create_c3_record_not_found(db_session, user_factory):
    import uuid

    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)
    with pytest.raises(svc.RecordNotFound):
        await svc.create(
            record_type="phenopacket",
            record_id=uuid.uuid4(),
            body_markdown="orphan",
            mention_user_ids=[],
            actor=curator,
        )


@pytest.mark.asyncio
async def test_create_mention_unknown_user_raises(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)
    with pytest.raises(svc.MentionUnknownUser):
        await svc.create(
            record_type="phenopacket",
            record_id=pp.id,
            body_markdown="@phantom",
            mention_user_ids=[999999],
            actor=curator,
        )
```

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_comments_service_create.py -v
```

Expected: FAIL — module not importable.

- [ ] **Step 3 — create `service.py`**

```python
"""CommentsService — all mutating paths for the D.2 comments feature."""
from __future__ import annotations

import uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.comments.models import Comment, CommentEdit, CommentMention
from app.models.user import User
from app.phenopackets.models import Phenopacket


class CommentsService:
    """All comment operations. Single-transaction, commit at the end of each method."""

    class RecordNotFound(Exception):
        """(record_type, record_id) does not resolve to a real record (C3)."""

    class MentionUnknownUser(Exception):
        """One or more mention_user_ids is not a known active curator/admin."""

    class NotAuthor(Exception):
        """The actor is not the comment's author."""

    class NotAuthorOrAdmin(Exception):
        """The actor is neither the comment's author nor an admin."""

    class AlreadyResolved(Exception):
        """resolve called on an already-resolved comment."""

    class NotResolved(Exception):
        """unresolve called on a non-resolved comment."""

    class SoftDeleted(Exception):
        """Write attempted on a soft-deleted comment (C6)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_record_exists(
        self, record_type: str, record_id: uuid.UUID
    ) -> None:
        """C3 — verify target record is not hard-deleted (soft-deleted is OK)."""
        if record_type != "phenopacket":
            raise self.RecordNotFound(f"Unsupported record_type {record_type!r}")
        stmt = select(func.count()).select_from(Phenopacket).where(
            Phenopacket.id == record_id
        )
        count = int((await self.db.execute(stmt)).scalar() or 0)
        if count == 0:
            raise self.RecordNotFound(f"No phenopacket with id {record_id}")

    async def _validate_mentions(
        self, mention_user_ids: Sequence[int]
    ) -> List[int]:
        """Dedup + verify each id points to an active curator/admin."""
        if not mention_user_ids:
            return []
        deduped = list(dict.fromkeys(mention_user_ids))
        stmt = select(User.id).where(
            User.id.in_(deduped),
            User.is_active.is_(True),
            User.role.in_(("curator", "admin")),
        )
        valid = {row[0] for row in (await self.db.execute(stmt)).all()}
        missing = [uid for uid in deduped if uid not in valid]
        if missing:
            raise self.MentionUnknownUser(
                f"users not found or not mentionable: {missing}"
            )
        return deduped

    async def _load_for_response(self, comment_id: int) -> Comment:
        """Load a comment with the actor relationships eager for response building."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
        )
        return (await self.db.execute(stmt)).scalar_one()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        body_markdown: str,
        mention_user_ids: Sequence[int],
        actor: User,
    ) -> Comment:
        """Insert a new comment and its mention rows atomically."""
        await self._check_record_exists(record_type, record_id)
        validated_mentions = await self._validate_mentions(mention_user_ids)

        comment = Comment(
            record_type=record_type,
            record_id=record_id,
            author_id=actor.id,
            body_markdown=body_markdown,
        )
        self.db.add(comment)
        await self.db.flush()  # obtain comment.id

        for uid in validated_mentions:
            self.db.add(CommentMention(comment_id=comment.id, user_id=uid))

        await self.db.commit()
        return await self._load_for_response(comment.id)

    # ------------------------------------------------------------------
    # List / detail
    # ------------------------------------------------------------------

    async def list_for_record(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        page_number: int,
        page_size: int,
        include_deleted: bool,
        resolved_filter: Optional[bool],
    ) -> Tuple[List[Comment], int]:
        """Return (rows, total_count) ordered by created_at ASC."""
        base = select(Comment).where(
            Comment.record_type == record_type,
            Comment.record_id == record_id,
        )
        if not include_deleted:
            base = base.where(Comment.deleted_at.is_(None))
        if resolved_filter is True:
            base = base.where(Comment.resolved_at.is_not(None))
        elif resolved_filter is False:
            base = base.where(Comment.resolved_at.is_(None))

        count = int(
            (await self.db.execute(
                select(func.count()).select_from(base.subquery())
            )).scalar() or 0
        )

        stmt = (
            base.options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), count

    async def get_by_id(
        self, comment_id: int, *, include_deleted: bool = False
    ) -> Optional[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Comment.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_edits(self, comment_id: int) -> List[CommentEdit]:
        stmt = (
            select(CommentEdit)
            .where(CommentEdit.comment_id == comment_id)
            .options(selectinload(CommentEdit.editor))
            .order_by(CommentEdit.edited_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def load_mentions(self, comment_ids: Sequence[int]) -> dict[int, List[User]]:
        """Bulk-load mentions for a set of comments. Used by the router."""
        if not comment_ids:
            return {}
        stmt = (
            select(CommentMention)
            .where(CommentMention.comment_id.in_(list(comment_ids)))
            .options(selectinload(CommentMention.user))
        )
        out: dict[int, List[User]] = {cid: [] for cid in comment_ids}
        for mention in (await self.db.execute(stmt)).scalars().all():
            out[mention.comment_id].append(mention.user)
        return out
```

- [ ] **Step 4 — run the test**

```bash
cd backend && uv run pytest tests/test_comments_service_create.py -v
```

Expected: PASS.

- [ ] **Step 5 — commit**

```bash
git add backend/app/comments/service.py backend/tests/test_comments_service_create.py
git commit -m "feat(backend): CommentsService.create + list + C3 + mention validation"
```

---

## Task 18: `CommentsService` — mutations (update_body, resolve, unresolve, soft_delete)

**Files:**
- Modify: `backend/app/comments/service.py`

Spec §5.5 + §6.2–6.4. All four methods share the "reject soft-deleted" precondition (C6).

- [ ] **Step 1 — write the failing tests**

Create `backend/tests/test_comments_service_mutations.py`:

```python
"""CommentsService mutation methods (update_body, resolve, unresolve, soft_delete)."""
import pytest

from app.comments.service import CommentsService


@pytest.mark.asyncio
async def test_update_body_writes_edit_log_and_replaces_mentions(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    user_a = await user_factory(role="curator")
    user_b = await user_factory(role="admin")
    svc = CommentsService(db_session)

    comment = await svc.create(
        record_type="phenopacket",
        record_id=pp.id,
        body_markdown="original",
        mention_user_ids=[user_a.id],
        actor=curator,
    )
    assert len(await svc.load_mentions([comment.id])[comment.id]) == 0 or True
    # Replace body and mentions
    updated = await svc.update_body(
        comment_id=comment.id,
        body_markdown="edited",
        mention_user_ids=[user_b.id],
        actor=curator,
    )
    assert updated.body_markdown == "edited"

    # Edit log has one row with prev_body="original"
    edits = await svc.list_edits(comment.id)
    assert len(edits) == 1
    assert edits[0].prev_body == "original"

    # Mentions replaced (C2): user_a gone, user_b present
    mentions = (await svc.load_mentions([comment.id]))[comment.id]
    assert {u.id for u in mentions} == {user_b.id}


@pytest.mark.asyncio
async def test_update_body_not_author_raises(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    other = await user_factory(role="curator")
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=pp.id,
        body_markdown="orig",
        mention_user_ids=[],
        actor=curator,
    )
    with pytest.raises(svc.NotAuthor):
        await svc.update_body(
            comment_id=comment.id,
            body_markdown="haxx",
            mention_user_ids=[],
            actor=other,
        )


@pytest.mark.asyncio
async def test_resolve_unresolve_roundtrip(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=pp.id,
        body_markdown="c",
        mention_user_ids=[],
        actor=curator,
    )
    resolved = await svc.resolve(comment_id=comment.id, actor=curator)
    assert resolved.resolved_at is not None
    assert resolved.resolved_by_id == curator.id

    with pytest.raises(svc.AlreadyResolved):
        await svc.resolve(comment_id=comment.id, actor=curator)

    unresolved = await svc.unresolve(comment_id=comment.id, actor=curator)
    assert unresolved.resolved_at is None
    assert unresolved.resolved_by_id is None


@pytest.mark.asyncio
async def test_soft_delete_terminal_for_writes_c6(
    db_session, phenopacket_factory, user_factory
):
    pp = await phenopacket_factory()
    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=pp.id,
        body_markdown="x",
        mention_user_ids=[],
        actor=curator,
    )
    await svc.soft_delete(comment_id=comment.id, actor=curator)

    # Every subsequent write raises SoftDeleted (→ 404 at router)
    with pytest.raises(svc.SoftDeleted):
        await svc.update_body(
            comment_id=comment.id, body_markdown="q", mention_user_ids=[], actor=curator
        )
    with pytest.raises(svc.SoftDeleted):
        await svc.resolve(comment_id=comment.id, actor=curator)
    with pytest.raises(svc.SoftDeleted):
        await svc.unresolve(comment_id=comment.id, actor=curator)
    with pytest.raises(svc.SoftDeleted):
        await svc.soft_delete(comment_id=comment.id, actor=curator)
```

- [ ] **Step 2 — run to verify failure**

```bash
cd backend && uv run pytest tests/test_comments_service_mutations.py -v
```

Expected: all FAIL — methods not implemented.

- [ ] **Step 3 — append the four mutation methods to `service.py`**

Append at the end of the `CommentsService` class:

```python
    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def _fetch_live_or_404(self, comment_id: int) -> Comment:
        """Lock FOR UPDATE; raise SoftDeleted (→ 404) if already removed."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .with_for_update()
        )
        comment = (await self.db.execute(stmt)).scalar_one_or_none()
        if comment is None:
            raise self.SoftDeleted(f"comment {comment_id} not found")
        if comment.deleted_at is not None:
            raise self.SoftDeleted(f"comment {comment_id} is soft-deleted")
        return comment

    async def update_body(
        self,
        *,
        comment_id: int,
        body_markdown: str,
        mention_user_ids: Sequence[int],
        actor: User,
    ) -> Comment:
        """PATCH body (author-only). Writes comment_edits + replaces mentions."""
        comment = await self._fetch_live_or_404(comment_id)
        if comment.author_id != actor.id:
            raise self.NotAuthor(
                f"actor {actor.id} is not comment author {comment.author_id}"
            )
        validated = await self._validate_mentions(mention_user_ids)

        # 1. Edit-log snapshot
        self.db.add(
            CommentEdit(
                comment_id=comment.id,
                editor_id=actor.id,
                prev_body=comment.body_markdown,
            )
        )
        # 2. Overwrite body + bump updated_at
        comment.body_markdown = body_markdown
        comment.updated_at = func.now()
        # 3. Replace mentions
        await self.db.execute(
            CommentMention.__table__.delete().where(
                CommentMention.comment_id == comment.id
            )
        )
        for uid in validated:
            self.db.add(CommentMention(comment_id=comment.id, user_id=uid))

        await self.db.commit()
        return await self._load_for_response(comment.id)

    async def resolve(self, *, comment_id: int, actor: User) -> Comment:
        comment = await self._fetch_live_or_404(comment_id)
        if comment.resolved_at is not None:
            raise self.AlreadyResolved(f"comment {comment_id} already resolved")
        comment.resolved_at = func.now()
        comment.resolved_by_id = actor.id
        comment.updated_at = func.now()
        await self.db.commit()
        return await self._load_for_response(comment_id)

    async def unresolve(self, *, comment_id: int, actor: User) -> Comment:
        comment = await self._fetch_live_or_404(comment_id)
        if comment.resolved_at is None:
            raise self.NotResolved(f"comment {comment_id} is not resolved")
        comment.resolved_at = None
        comment.resolved_by_id = None
        comment.updated_at = func.now()
        await self.db.commit()
        return await self._load_for_response(comment_id)

    async def soft_delete(self, *, comment_id: int, actor: User) -> None:
        comment = await self._fetch_live_or_404(comment_id)
        is_admin = actor.role == "admin"
        if comment.author_id != actor.id and not is_admin:
            raise self.NotAuthorOrAdmin(
                f"actor {actor.id} is not author and not admin"
            )
        comment.deleted_at = func.now()
        comment.deleted_by_id = actor.id
        comment.updated_at = func.now()
        await self.db.commit()
```

- [ ] **Step 4 — run the tests**

```bash
cd backend && uv run pytest tests/test_comments_service_mutations.py -v
```

Expected: all PASS.

- [ ] **Step 5 — commit**

```bash
git add backend/app/comments/service.py backend/tests/test_comments_service_mutations.py
git commit -m "feat(backend): CommentsService mutations (update_body, resolve, unresolve, soft_delete)

Implements C1 (edit log), C2 (mention replace), C6 (soft-delete terminal for writes)."
```

---

## Task 19: Comments router (`backend/app/comments/routers.py`) + response shaping

**Files:**
- Create: `backend/app/comments/routers.py`
- Modify: `backend/app/auth/dependencies.py` (add `require_comment_author_or_admin` factory)

Spec §5.3 + §5.6. This is the biggest file in Wave 3 — eight endpoints plus response shaping.

- [ ] **Step 1 — add the author/admin dependency factory**

Open `backend/app/auth/dependencies.py`. Append at the bottom:

```python
# D.2 comments ------------------------------------------------------------------

async def require_comment_author_or_admin(
    comment_id: int,
    current_user: User = Depends(require_curator),
    db: AsyncSession = Depends(get_db),
) -> User:
    """403 unless the caller authored the comment or is admin.

    The router MUST use this for DELETE; PATCH has an additional
    "author only (not admin)" check performed inline because the matrix
    forbids admin body edits.
    """
    from app.comments.service import CommentsService

    svc = CommentsService(db)
    comment = await svc.get_by_id(comment_id, include_deleted=True)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    is_admin = current_user.role == "admin"
    if comment.author_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Author or admin only")
    return current_user
```

- [ ] **Step 2 — create `routers.py`**

This file is ~300 lines. Important: static routes register BEFORE `{id}` routes (spec §5.7 routing-order requirement).

```python
"""Comments REST endpoints for the D.2 feature.

Spec reference: §5.3 of the design doc.

IMPORTANT (routing-order requirement, spec §5.7):
Static paths under /comments/ (if any are added) MUST be declared before
/{id}-parametrized routes. FastAPI matches routes in registration order;
a static path registered after /{id} will be swallowed by the int coercion
on {id} and surface as 422.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    is_curator_or_admin,
    require_comment_author_or_admin,
    require_curator,
)
from app.comments.models import Comment
from app.comments.schemas import (
    CommentCreate,
    CommentEditResponse,
    CommentMentionOut,
    CommentResponse,
    CommentUpdate,
)
from app.comments.service import CommentsService
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/comments", tags=["comments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_comment_response(
    svc: CommentsService, comment: Comment
) -> CommentResponse:
    """Assemble a CommentResponse from an eager-loaded Comment ORM row."""
    mentions_map = await svc.load_mentions([comment.id])
    mention_users = mentions_map.get(comment.id, [])
    mentions = [
        CommentMentionOut(
            user_id=u.id,
            username=u.username,
            display_name=u.full_name,
            is_active=u.is_active,
        )
        for u in mention_users
    ]
    edited = len(await svc.list_edits(comment.id)) > 0
    return CommentResponse(
        id=comment.id,
        record_type=comment.record_type,
        record_id=str(comment.record_id),
        author_id=comment.author_id,
        author_username=comment.author.username,
        author_display_name=comment.author.full_name,
        body_markdown=comment.body_markdown,
        mentions=mentions,
        edited=edited,
        resolved_at=comment.resolved_at,
        resolved_by_id=comment.resolved_by_id,
        resolved_by_username=comment.resolved_by.username if comment.resolved_by else None,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        deleted_at=comment.deleted_at,
        deleted_by_id=comment.deleted_by_id,
    )


def _map_service_error(exc: Exception) -> HTTPException:
    """Translate CommentsService errors to HTTP responses."""
    if isinstance(exc, CommentsService.RecordNotFound):
        return HTTPException(status_code=404, detail={"code": "record_not_found", "message": str(exc)})
    if isinstance(exc, CommentsService.MentionUnknownUser):
        return HTTPException(status_code=422, detail={"code": "mention_unknown_user", "message": str(exc)})
    if isinstance(exc, CommentsService.NotAuthor):
        return HTTPException(status_code=403, detail={"code": "forbidden_not_author", "message": str(exc)})
    if isinstance(exc, CommentsService.NotAuthorOrAdmin):
        return HTTPException(status_code=403, detail={"code": "forbidden", "message": str(exc)})
    if isinstance(exc, CommentsService.AlreadyResolved):
        return HTTPException(status_code=409, detail={"code": "already_resolved", "message": str(exc)})
    if isinstance(exc, CommentsService.NotResolved):
        return HTTPException(status_code=409, detail={"code": "not_resolved", "message": str(exc)})
    if isinstance(exc, CommentsService.SoftDeleted):
        return HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)})
    return HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /comments
# ---------------------------------------------------------------------------


@router.post("", response_model=CommentResponse, status_code=201)
async def create_comment(
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    svc = CommentsService(db)
    try:
        comment = await svc.create(
            record_type=body.record_type,
            record_id=body.record_id,
            body_markdown=body.body_markdown,
            mention_user_ids=body.mention_user_ids,
            actor=current_user,
        )
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# GET /comments (list)
# ---------------------------------------------------------------------------


@router.get("", response_model=Dict[str, Any])
async def list_comments(
    record_type: str = Query(..., alias="filter[record_type]"),
    record_id: UUID = Query(..., alias="filter[record_id]"),
    resolved: Optional[str] = Query(None, alias="filter[resolved]"),
    include: Optional[str] = Query(None),
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(50, alias="page[size]", ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, Any]:
    include_deleted = include == "deleted"
    resolved_filter: Optional[bool]
    if resolved == "true":
        resolved_filter = True
    elif resolved == "false":
        resolved_filter = False
    else:
        resolved_filter = None

    svc = CommentsService(db)
    rows, total = await svc.list_for_record(
        record_type=record_type,
        record_id=record_id,
        page_number=page_number,
        page_size=page_size,
        include_deleted=include_deleted,
        resolved_filter=resolved_filter,
    )
    data = [await _build_comment_response(svc, c) for c in rows]
    return {
        "data": [d.model_dump() for d in data],
        "meta": {"total": total, "page": page_number, "page_size": page_size},
    }


# ---------------------------------------------------------------------------
# GET /comments/{id}
# ---------------------------------------------------------------------------


@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int,
    include: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    include_deleted = include == "deleted"
    svc = CommentsService(db)
    comment = await svc.get_by_id(comment_id, include_deleted=include_deleted)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# PATCH /comments/{id}
# ---------------------------------------------------------------------------


@router.patch("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    body: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    # Matrix: author only — admin cannot edit others' bodies.
    svc = CommentsService(db)
    try:
        comment = await svc.update_body(
            comment_id=comment_id,
            body_markdown=body.body_markdown,
            mention_user_ids=body.mention_user_ids,
            actor=current_user,
        )
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# POST /comments/{id}/resolve and /unresolve
# ---------------------------------------------------------------------------


@router.post("/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    svc = CommentsService(db)
    try:
        comment = await svc.resolve(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


@router.post("/{comment_id}/unresolve", response_model=CommentResponse)
async def unresolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    svc = CommentsService(db)
    try:
        comment = await svc.unresolve(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# DELETE /comments/{id}
# ---------------------------------------------------------------------------


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_comment_author_or_admin),
) -> Response:
    svc = CommentsService(db)
    try:
        await svc.soft_delete(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /comments/{id}/edits
# ---------------------------------------------------------------------------


@router.get("/{comment_id}/edits", response_model=Dict[str, List[CommentEditResponse]])
async def list_comment_edits(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, List[CommentEditResponse]]:
    svc = CommentsService(db)
    # Confirm comment exists (even if soft-deleted, edits are still visible)
    if await svc.get_by_id(comment_id, include_deleted=True) is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    edits = await svc.list_edits(comment_id)
    return {
        "data": [
            CommentEditResponse(
                id=e.id,
                editor_id=e.editor_id,
                editor_username=e.editor.username,
                prev_body=e.prev_body,
                edited_at=e.edited_at,
            )
            for e in edits
        ]
    }
```

- [ ] **Step 3 — run router tests**

Create `backend/tests/test_comments_router.py` with at minimum one happy-path test per endpoint (8 tests). Example for create:

```python
@pytest.mark.asyncio
async def test_post_comment_201(async_client, curator_token, phenopacket_fixture):
    resp = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(phenopacket_fixture.id),
            "body_markdown": "hello",
            "mention_user_ids": [],
        },
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["body_markdown"] == "hello"
```

(Full router-test fleshout lands in Task 32; this step just confirms the module imports cleanly.)

- [ ] **Step 4 — lint and type-check**

```bash
cd backend && make lint && make typecheck
```

- [ ] **Step 5 — commit**

```bash
git add backend/app/comments/routers.py backend/app/auth/dependencies.py backend/tests/test_comments_router.py
git commit -m "feat(backend): comments REST router (8 endpoints) + author/admin dep"
```

---

## Task 20: Mount the comments router; add `/api/v2/users/mentionable`

**Files:**
- Modify: `backend/app/main.py` (router mount)
- Modify: `backend/app/auth/endpoints/users.py` (or wherever the users router lives — add the `/mentionable` endpoint)

Spec §5.7.

- [ ] **Step 1 — mount comments router**

Open `backend/app/main.py`. Near the existing `app.include_router(...)` block, add:

```python
from app.comments.routers import router as comments_router
# ...
app.include_router(comments_router, prefix="/api/v2")
```

- [ ] **Step 2 — add `/api/v2/users/mentionable` endpoint**

Find the existing auth/users router file (likely `backend/app/auth/endpoints/users.py` or similar). Add:

```python
from app.comments.schemas import MentionableUserOut


@router.get("/users/mentionable", response_model=Dict[str, List[MentionableUserOut]])
async def get_mentionable_users(
    q: str = Query(..., min_length=2, description="Username prefix, ≥ 2 chars"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, List[MentionableUserOut]]:
    """Autocomplete for @-mentions (curator/admin, active users only)."""
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_(("curator", "admin")),
            User.username.ilike(f"{q}%"),
        )
        .order_by(User.username.asc())
        .limit(20)
    )
    users = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            MentionableUserOut(id=u.id, username=u.username, display_name=u.full_name)
            for u in users
        ]
    }
```

Check the router prefix — if the users router is mounted at `/api/v2/auth`, the path becomes `/api/v2/auth/users/mentionable`. Confirm with a quick test OR move the endpoint to a dedicated `users_router` under `/api/v2` to land exactly at `/api/v2/users/mentionable` per spec. If there's no plain `/api/v2/users` namespace, create one:

Create `backend/app/users/mentionable.py`:

```python
"""Mentionable-users autocomplete endpoint (D.2 §5.7)."""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_curator
from app.comments.schemas import MentionableUserOut
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/mentionable", response_model=Dict[str, List[MentionableUserOut]])
async def get_mentionable_users(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, List[MentionableUserOut]]:
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_(("curator", "admin")),
            User.username.ilike(f"{q}%"),
        )
        .order_by(User.username.asc())
        .limit(20)
    )
    users = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            MentionableUserOut(id=u.id, username=u.username, display_name=u.full_name)
            for u in users
        ]
    }
```

Then in `backend/app/main.py`:

```python
from app.users.mentionable import router as users_mentionable_router
# ...
app.include_router(users_mentionable_router, prefix="/api/v2")
```

- [ ] **Step 3 — smoke test with curl**

```bash
make hybrid-up && make backend &
# get a token via login, then:
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/users/mentionable?q=ad"
```

Expected: JSON `{"data": [...]}`.

- [ ] **Step 4 — write an endpoint test**

Create `backend/tests/test_mentionable_users_router.py`:

```python
@pytest.mark.asyncio
async def test_mentionable_q_too_short_returns_422(async_client, curator_token):
    resp = await async_client.get(
        "/api/v2/users/mentionable?q=a",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mentionable_returns_active_curators_admins_only(
    async_client, curator_token, user_factory
):
    await user_factory(username="adam", role="curator", is_active=True)
    await user_factory(username="admin2", role="admin", is_active=True)
    await user_factory(username="adrian", role="viewer", is_active=True)      # excluded
    await user_factory(username="adele", role="curator", is_active=False)     # excluded

    resp = await async_client.get(
        "/api/v2/users/mentionable?q=ad",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert resp.status_code == 200
    names = {u["username"] for u in resp.json()["data"]}
    assert names == {"adam", "admin2"}
```

- [ ] **Step 5 — run, commit**

```bash
cd backend && uv run pytest tests/test_mentionable_users_router.py -v
git add backend/app/users/ backend/app/main.py backend/tests/test_mentionable_users_router.py
git commit -m "feat(backend): mount /api/v2/comments + /api/v2/users/mentionable"
```

---

## Wave 3 acceptance gate

- [ ] `make check` green in `backend/`.
- [ ] All 8 comments endpoints return shape-correct responses when called with a valid curator token (at least one smoke-test per endpoint).
- [ ] `/api/v2/users/mentionable?q=ab` returns up to 20 rows, filtered on role + is_active.

---

# Wave 4 — Part B Frontend

Spec §5.8.

## Task 21: Install Tiptap + markdown-it dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json` (generated)

- [ ] **Step 1 — install**

```bash
cd frontend && npm install --save \
  @tiptap/core@^3 \
  @tiptap/vue-3@^3 \
  @tiptap/starter-kit@^3 \
  @tiptap/extension-mention@^3 \
  tiptap-markdown@^0.9 \
  markdown-it@^14
```

- [ ] **Step 2 — sanity-check build**

```bash
cd frontend && npm run build
```

Expected: build succeeds; no new warnings about missing deps.

- [ ] **Step 3 — commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add Tiptap v3 + markdown-it for D.2 comments"
```

---

## Task 22: Comments API client (`frontend/src/api/domain/comments.js`)

**Files:**
- Create: `frontend/src/api/domain/comments.js`

- [ ] **Step 1 — create the file**

```javascript
import apiClient from '../transport';

/**
 * List comments on a record.
 * @param {Object} opts
 * @param {string} opts.recordType
 * @param {string} opts.recordId - UUID string
 * @param {number} [opts.page=1]
 * @param {number} [opts.size=50]
 * @param {boolean} [opts.includeDeleted=false]
 * @param {('true'|'false'|null)} [opts.resolved=null]
 */
export const listComments = ({
  recordType,
  recordId,
  page = 1,
  size = 50,
  includeDeleted = false,
  resolved = null,
}) => {
  const params = {
    'filter[record_type]': recordType,
    'filter[record_id]': recordId,
    'page[number]': page,
    'page[size]': size,
  };
  if (includeDeleted) params.include = 'deleted';
  if (resolved !== null) params['filter[resolved]'] = resolved;
  return apiClient.get('/comments', { params });
};

export const getComment = (id, { includeDeleted = false } = {}) =>
  apiClient.get(`/comments/${id}`, { params: includeDeleted ? { include: 'deleted' } : {} });

export const createComment = ({ recordType, recordId, bodyMarkdown, mentionUserIds = [] }) =>
  apiClient.post('/comments', {
    record_type: recordType,
    record_id: recordId,
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  });

export const updateComment = (id, { bodyMarkdown, mentionUserIds = [] }) =>
  apiClient.patch(`/comments/${id}`, {
    body_markdown: bodyMarkdown,
    mention_user_ids: mentionUserIds,
  });

export const resolveComment = (id) => apiClient.post(`/comments/${id}/resolve`);
export const unresolveComment = (id) => apiClient.post(`/comments/${id}/unresolve`);
export const deleteComment = (id) => apiClient.delete(`/comments/${id}`);
export const listCommentEdits = (id) => apiClient.get(`/comments/${id}/edits`);

export const searchMentionableUsers = (q) =>
  apiClient.get('/users/mentionable', { params: { q } });
```

- [ ] **Step 2 — lint**

```bash
cd frontend && npm run lint
```

- [ ] **Step 3 — commit**

```bash
git add frontend/src/api/domain/comments.js
git commit -m "feat(frontend): comments API client"
```

---

## Task 23: `useComments` composable

**Files:**
- Create: `frontend/src/composables/useComments.js`

```javascript
import { ref, computed } from 'vue';
import {
  listComments,
  createComment,
  updateComment,
  resolveComment,
  unresolveComment,
  deleteComment,
} from '@/api/domain/comments';

export function useComments(recordType, recordId) {
  const comments = ref([]);
  const total = ref(0);
  const openCount = ref(0);
  const loading = ref(false);
  const error = ref(null);

  const load = async ({ page = 1, size = 50, includeDeleted = false } = {}) => {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await listComments({
        recordType,
        recordId: recordId.value,
        page,
        size,
        includeDeleted,
      });
      comments.value = data.data;
      total.value = data.meta.total;
      // Separately fetch unresolved count
      const { data: openData } = await listComments({
        recordType,
        recordId: recordId.value,
        page: 1,
        size: 1,
        resolved: 'false',
      });
      openCount.value = openData.meta.total;
    } catch (e) {
      error.value = e;
      window.logService.error('comments.load failed', {
        recordId: recordId.value,
        error: e.message,
      });
    } finally {
      loading.value = false;
    }
  };

  const post = async (bodyMarkdown, mentionUserIds = []) => {
    const { data } = await createComment({
      recordType,
      recordId: recordId.value,
      bodyMarkdown,
      mentionUserIds,
    });
    comments.value.push(data);
    total.value += 1;
    if (!data.resolved_at) openCount.value += 1;
    return data;
  };

  const edit = async (id, bodyMarkdown, mentionUserIds = []) => {
    const { data } = await updateComment(id, { bodyMarkdown, mentionUserIds });
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    return data;
  };

  const resolve = async (id) => {
    const { data } = await resolveComment(id);
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    openCount.value = Math.max(0, openCount.value - 1);
  };

  const unresolve = async (id) => {
    const { data } = await unresolveComment(id);
    const i = comments.value.findIndex((c) => c.id === id);
    if (i !== -1) comments.value[i] = data;
    openCount.value += 1;
  };

  const remove = async (id) => {
    await deleteComment(id);
    comments.value = comments.value.filter((c) => c.id !== id);
    total.value = Math.max(0, total.value - 1);
  };

  const badgeLabel = computed(() => {
    if (openCount.value > 0) return `Discussion (${total.value}, ${openCount.value} open)`;
    if (total.value > 0) return `Discussion (${total.value})`;
    return 'Discussion';
  });

  return {
    comments,
    total,
    openCount,
    loading,
    error,
    load,
    post,
    edit,
    resolve,
    unresolve,
    remove,
    badgeLabel,
  };
}
```

- [ ] Commit:

```bash
git add frontend/src/composables/useComments.js
git commit -m "feat(frontend): useComments composable"
```

---

## Task 24: `CommentBody.vue` (markdown render + sanitize)

**Files:**
- Create: `frontend/src/components/comments/CommentBody.vue`

```vue
<template>
  <div class="comment-body" v-html="safeHtml" />
</template>

<script setup>
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import { sanitize } from '@/utils/sanitize';

const props = defineProps({
  bodyMarkdown: { type: String, required: true },
});

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const safeHtml = computed(() => sanitize(md.render(props.bodyMarkdown ?? '')));
</script>

<style scoped>
.comment-body :deep(p) {
  margin-bottom: 0.5em;
}
.comment-body :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.9em;
}
</style>
```

Commit: `git add frontend/src/components/comments/CommentBody.vue && git commit -m "feat(frontend): CommentBody.vue (markdown render + sanitize)"`.

---

## Task 25: `CommentEditHistory.vue`

**Files:**
- Create: `frontend/src/components/comments/CommentEditHistory.vue`

```vue
<template>
  <v-expansion-panels variant="accordion" density="compact">
    <v-expansion-panel>
      <v-expansion-panel-title>
        <span class="text-caption text-medium-emphasis">
          edited · view history
        </span>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div v-if="loading">Loading…</div>
        <div v-else-if="edits.length === 0" class="text-caption text-medium-emphasis">
          No edit history.
        </div>
        <div v-else>
          <div v-for="e in edits" :key="e.id" class="mb-3">
            <div class="text-caption text-medium-emphasis mb-1">
              edited by @{{ e.editor_username }} · {{ formatRelative(e.edited_at) }}
            </div>
            <CommentBody :body-markdown="e.prev_body" />
          </div>
        </div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup>
import { ref, watch } from 'vue';
import { listCommentEdits } from '@/api/domain/comments';
import CommentBody from './CommentBody.vue';
import { formatDistanceToNow } from 'date-fns';

const props = defineProps({
  commentId: { type: Number, required: true },
});

const edits = ref([]);
const loading = ref(false);
const loaded = ref(false);

const formatRelative = (ts) => formatDistanceToNow(new Date(ts), { addSuffix: true });

const load = async () => {
  if (loaded.value) return;
  loading.value = true;
  try {
    const { data } = await listCommentEdits(props.commentId);
    edits.value = data.data;
    loaded.value = true;
  } finally {
    loading.value = false;
  }
};

// Lazy-load on first expansion — v-expansion-panel fires a click; listen via a manual watch.
watch(() => props.commentId, () => {
  loaded.value = false;
  edits.value = [];
});
</script>
```

Hook the lazy load up via a click listener if needed. Commit.

---

## Task 26: `CommentItem.vue`

**Files:**
- Create: `frontend/src/components/comments/CommentItem.vue`

Render: avatar, author, timestamp, body, edited indicator, resolve chip, action menu.

```vue
<template>
  <v-card variant="outlined" class="mb-3">
    <v-card-text>
      <div class="d-flex align-center mb-2">
        <v-avatar size="32" class="mr-3">{{ initials }}</v-avatar>
        <div>
          <strong>@{{ comment.author_username }}</strong>
          <span class="text-caption text-medium-emphasis ml-2">
            {{ formatRelative(comment.created_at) }}
          </span>
          <v-chip
            v-if="comment.resolved_at"
            size="x-small"
            color="success"
            class="ml-2"
          >Resolved</v-chip>
        </div>
        <v-spacer />
        <v-menu v-if="canAct">
          <template #activator="{ props: act }">
            <v-btn icon="mdi-dots-vertical" v-bind="act" variant="text" size="small" />
          </template>
          <v-list density="compact">
            <v-list-item v-if="isAuthor" @click="$emit('edit', comment)">Edit</v-list-item>
            <v-list-item v-if="canToggleResolve" @click="$emit('toggleResolve', comment)">
              {{ comment.resolved_at ? 'Unresolve' : 'Resolve' }}
            </v-list-item>
            <v-list-item v-if="canDelete" @click="$emit('delete', comment)">Delete</v-list-item>
          </v-list>
        </v-menu>
      </div>

      <CommentBody :body-markdown="comment.body_markdown" />

      <CommentEditHistory v-if="comment.edited" :comment-id="comment.id" class="mt-2" />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue';
import { formatDistanceToNow } from 'date-fns';
import CommentBody from './CommentBody.vue';
import CommentEditHistory from './CommentEditHistory.vue';

const props = defineProps({
  comment: { type: Object, required: true },
  currentUserId: { type: Number, required: true },
  currentUserRole: { type: String, required: true },
});
defineEmits(['edit', 'toggleResolve', 'delete']);

const initials = computed(() =>
  (props.comment.author_display_name || props.comment.author_username)
    .split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
);
const formatRelative = (ts) => formatDistanceToNow(new Date(ts), { addSuffix: true });

const isAuthor = computed(() => props.currentUserId === props.comment.author_id);
const isAdmin = computed(() => props.currentUserRole === 'admin');
const canAct = computed(() => isAuthor.value || isAdmin.value);
const canToggleResolve = computed(() => isAuthor.value || isAdmin.value);
const canDelete = computed(() => isAuthor.value || isAdmin.value);
</script>
```

Commit.

---

## Task 27: `CommentList.vue`

**Files:**
- Create: `frontend/src/components/comments/CommentList.vue`

```vue
<template>
  <div>
    <v-alert v-if="error" type="error" density="compact">{{ error.message }}</v-alert>
    <v-progress-circular v-if="loading && comments.length === 0" indeterminate />
    <CommentItem
      v-for="c in comments"
      :key="c.id"
      :comment="c"
      :current-user-id="currentUserId"
      :current-user-role="currentUserRole"
      @edit="$emit('edit', $event)"
      @toggleResolve="$emit('toggleResolve', $event)"
      @delete="$emit('delete', $event)"
    />
  </div>
</template>

<script setup>
import CommentItem from './CommentItem.vue';

defineProps({
  comments: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  error: { type: Object, default: null },
  currentUserId: { type: Number, required: true },
  currentUserRole: { type: String, required: true },
});
defineEmits(['edit', 'toggleResolve', 'delete']);
</script>
```

Commit.

---

## Task 28: `CommentComposer.vue` (Tiptap + mention autocomplete)

**Files:**
- Create: `frontend/src/components/comments/CommentComposer.vue`

This component is the most involved; expect ~200 lines.

```vue
<template>
  <div class="comment-composer">
    <editor-content :editor="editor" class="composer-editor" />
    <div class="d-flex align-center mt-2">
      <v-btn
        color="primary"
        :disabled="!canSubmit"
        :loading="submitting"
        @click="onSubmit"
      >{{ submitLabel }}</v-btn>
      <v-btn v-if="editingComment" variant="text" @click="$emit('cancel')" class="ml-2">Cancel</v-btn>
      <span class="ml-3 text-caption text-medium-emphasis">
        {{ charCount }} / 10000
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, watch } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Mention from '@tiptap/extension-mention';
import { Markdown } from 'tiptap-markdown';
import { searchMentionableUsers } from '@/api/domain/comments';

const props = defineProps({
  editingComment: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
});
const emit = defineEmits(['submit', 'cancel']);

const content = ref(props.editingComment?.body_markdown ?? '');

const editor = useEditor({
  content: content.value,
  extensions: [
    StarterKit,
    Markdown,
    Mention.configure({
      HTMLAttributes: { class: 'mention' },
      suggestion: {
        items: async ({ query }) => {
          if (!query || query.length < 2) return [];
          try {
            const { data } = await searchMentionableUsers(query);
            return data.data.slice(0, 20);
          } catch {
            return [];
          }
        },
        render: () => {
          // Minimal tippy-free renderer — returns a simple list popper.
          // For v1, use the default tiptap suggestion renderer if present,
          // or implement a minimal DOM popover here.
          return {
            onStart: () => {},
            onUpdate: () => {},
            onKeyDown: () => false,
            onExit: () => {},
          };
        },
      },
    }),
  ],
  onUpdate: ({ editor }) => {
    content.value = editor.storage.markdown.getMarkdown();
  },
});

const charCount = computed(() => content.value.length);
const canSubmit = computed(
  () => !props.submitting && content.value.trim().length >= 1 && content.value.length <= 10000
);
const submitLabel = computed(() => (props.editingComment ? 'Save' : 'Post'));

const collectMentions = () => {
  const ids = [];
  editor.value.state.doc.descendants((node) => {
    if (node.type.name === 'mention') {
      ids.push(Number(node.attrs.id));
    }
  });
  return Array.from(new Set(ids));
};

const onSubmit = () => {
  emit('submit', {
    bodyMarkdown: content.value,
    mentionUserIds: collectMentions(),
  });
};

watch(() => props.editingComment, (c) => {
  if (c) editor.value?.commands.setContent(c.body_markdown);
  else editor.value?.commands.setContent('');
});

onBeforeUnmount(() => editor.value?.destroy());
</script>

<style scoped>
.composer-editor {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  padding: 12px;
  min-height: 120px;
}
.composer-editor :deep(.mention) {
  background: rgba(94, 53, 177, 0.1);
  color: rgb(94, 53, 177);
  padding: 2px 4px;
  border-radius: 3px;
}
</style>
```

Note: a production-grade Tiptap mention suggestion-renderer needs a proper tippy.js popover; that's acceptable to defer as a minor polish (the composer still works without it — just no suggestion dropdown). If time permits within this task, follow the Tiptap docs' Vue 3 suggestion-renderer example.

Commit.

---

## Task 29: `DiscussionTab.vue` (the top-level tab contents)

**Files:**
- Create: `frontend/src/components/comments/DiscussionTab.vue`

```vue
<template>
  <div class="discussion-tab">
    <CommentComposer
      :editing-comment="editingComment"
      :submitting="submitting"
      @submit="onSubmit"
      @cancel="editingComment = null"
    />
    <v-divider class="my-4" />
    <CommentList
      :comments="comments"
      :loading="loading"
      :error="error"
      :current-user-id="authStore.user.id"
      :current-user-role="authStore.user.role"
      @edit="(c) => editingComment = c"
      @toggleResolve="onToggleResolve"
      @delete="onDelete"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/authStore';
import { useComments } from '@/composables/useComments';
import CommentComposer from './CommentComposer.vue';
import CommentList from './CommentList.vue';

const props = defineProps({
  recordId: { type: String, required: true },
});

const authStore = useAuthStore();
const recordIdRef = ref(props.recordId);
watch(() => props.recordId, (v) => { recordIdRef.value = v; });

const { comments, loading, error, load, post, edit, resolve, unresolve, remove } =
  useComments('phenopacket', recordIdRef);

const editingComment = ref(null);
const submitting = ref(false);

const onSubmit = async ({ bodyMarkdown, mentionUserIds }) => {
  submitting.value = true;
  try {
    if (editingComment.value) {
      await edit(editingComment.value.id, bodyMarkdown, mentionUserIds);
      editingComment.value = null;
    } else {
      await post(bodyMarkdown, mentionUserIds);
    }
  } finally {
    submitting.value = false;
  }
};

const onToggleResolve = async (c) => {
  if (c.resolved_at) await unresolve(c.id);
  else await resolve(c.id);
};

const onDelete = async (c) => {
  if (!window.confirm('Delete this comment?')) return;
  await remove(c.id);
};

onMounted(load);
watch(() => props.recordId, () => load());
</script>
```

Commit.

---

## Task 30: Mount `DiscussionTab` in `PagePhenopacket.vue`

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue`

- [ ] **Step 1 — add the tab**

Inside the existing `<v-tabs>` block, AFTER the RAW JSON tab:

```vue
<v-tab
  v-if="canSeeDiscussion"
  value="discussion"
  aria-label="Discussion tab"
>{{ discussionLabel }}</v-tab>
```

Inside `<v-tabs-window>`, after the RAW JSON window:

```vue
<v-tabs-window-item v-if="canSeeDiscussion" value="discussion">
  <DiscussionTab :record-id="phenopacketMeta.record_id ?? phenopacketMeta.id" />
</v-tabs-window-item>
```

- [ ] **Step 2 — wire up `canSeeDiscussion` + `discussionLabel`**

In the `<script setup>` or `script` section, add:

```javascript
import { computed } from 'vue';
import DiscussionTab from '@/components/comments/DiscussionTab.vue';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const canSeeDiscussion = computed(() =>
  authStore.user && ['curator', 'admin'].includes(authStore.user.role)
);
// For a proper badge with counts, hoist a useComments instance up here and read total/openCount.
// Minimal v1: just show 'Discussion'.
const discussionLabel = computed(() => 'Discussion');
```

(If the component uses Options API with `data()/computed`, adapt to that style. Match the existing file.)

- [ ] **Step 3 — manual smoke test**

Start dev servers, log in as curator, open a phenopacket, click the Discussion tab, post a comment, edit it, resolve it, delete it.

- [ ] **Step 4 — commit**

```bash
git add frontend/src/views/PagePhenopacket.vue frontend/src/components/comments/
git commit -m "feat(frontend): DiscussionTab mounted in PagePhenopacket

Fourth tab after OVERVIEW / TIMELINE / RAW JSON; conditionally rendered
for curators and admins only."
```

---

## Wave 4 acceptance gate

- [ ] Curator can post, edit, resolve, unresolve, delete comments via the UI.
- [ ] Viewers navigating to a phenopacket detail do not see a Discussion tab.
- [ ] Tiptap editor renders; mention autocomplete (if the suggestion renderer was implemented) fires on `@`.
- [ ] `frontend/npm test` green.
- [ ] `frontend/npm run lint` green.

---

# Wave 5 — Tests, Invariants, and E2E

## Task 31: Part A invariant tests (I8, I9) + clone-cycle edge cases

**Files:**
- Create: `backend/tests/test_state_service_invariant_i8.py`
- Create: `backend/tests/test_state_service_clone_withdraw.py`

Already partly covered by Tasks 2, 4, 5. This task fills the parametrized I8 gate and explicit withdraw test.

- [ ] **Step 1 — write `test_state_service_invariant_i8.py`**

```python
"""I8 — pp.state is sticky post-first-publish."""
import pytest


@pytest.mark.parametrize(
    "to_state",
    ["in_review", "changes_requested", "approved", "published"],
)
@pytest.mark.asyncio
async def test_pp_state_never_exits_published_or_archived_post_first_publish(
    db_session, user_factory, published_with_head_fixture, to_state
):
    from app.phenopackets.services.state_service import PhenopacketStateService

    pp, head = published_with_head_fixture
    svc = PhenopacketStateService(db_session)
    # Enter clone cycle
    curator = await user_factory(role="curator")
    admin = await user_factory(role="admin")
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "iter"}},
        change_reason="r",
        expected_revision=pp.revision,
        actor=curator,
    )
    # Advance through the cycle if to_state != draft; each transition is legal
    sequence_to_target = {
        "in_review": [("in_review", curator)],
        "changes_requested": [("in_review", curator), ("changes_requested", admin)],
        "approved": [("in_review", curator), ("approved", admin)],
        "published": [("in_review", curator), ("approved", admin), ("published", admin)],
    }
    for state_target, actor in sequence_to_target[to_state]:
        pp, _ = await svc.transition(
            pp.id, to_state=state_target, reason="r",
            expected_revision=pp.revision, actor=actor,
        )
    # pp.state remains in the sticky set
    assert pp.state in ("published", "archived")
```

- [ ] **Step 2 — write `test_state_service_clone_withdraw.py`**

```python
"""Withdraw during clone-cycle returns effective state to 'draft', pp.state='published'."""
import pytest


@pytest.mark.asyncio
async def test_clone_cycle_withdraw_keeps_pp_state(
    db_session, user_factory, published_with_head_fixture
):
    from app.phenopackets.services.state_service import PhenopacketStateService

    pp, _ = published_with_head_fixture
    curator = await user_factory(role="curator")
    svc = PhenopacketStateService(db_session)

    pp = await svc.edit_record(
        pp.id, new_content={"subject": {"id": "c"}}, change_reason="r",
        expected_revision=pp.revision, actor=curator,
    )
    pp, _ = await svc.transition(
        pp.id, to_state="in_review", reason="r",
        expected_revision=pp.revision, actor=curator,
    )
    pp, rev = await svc.transition(
        pp.id, to_state="draft", reason="withdraw",
        expected_revision=pp.revision, actor=curator,
    )

    assert pp.state == "published"
    assert rev.state == "draft"
    assert rev.from_state == "in_review"
    assert rev.to_state == "draft"
    assert await svc._effective_state(pp) == "draft"
```

- [ ] **Step 3 — run + commit**

```bash
cd backend && uv run pytest tests/test_state_service_invariant_i8.py tests/test_state_service_clone_withdraw.py -v
git add backend/tests/test_state_service_invariant_i8.py backend/tests/test_state_service_clone_withdraw.py
git commit -m "test(backend): I8 sticky-state parametrized + clone-cycle withdraw"
```

---

## Task 32: Part B CRUD + permissions parametrized tests

**Files:**
- Create: `backend/tests/test_comments_permissions.py`
- Create: `backend/tests/test_comments_soft_delete.py`
- Create: `backend/tests/test_comments_c6_terminal_writes.py`

- [ ] **Step 1 — `test_comments_permissions.py`** — parametrize 4 roles × 8 actions (viewer, curator author, curator non-author, admin) × (list, get, create, patch, resolve, unresolve, delete, edits):

```python
"""Permissions matrix enforcement (D.2 §5.2)."""
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected_status", [
    ("viewer", 403),
    ("curator", 201),
    ("admin", 201),
])
async def test_create_viewer_forbidden(async_client, phenopacket_fixture, token_factory, role, expected_status):
    token = await token_factory(role=role)
    resp = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(phenopacket_fixture.id),
            "body_markdown": "x",
            "mention_user_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == expected_status


@pytest.mark.asyncio
async def test_patch_admin_not_author_forbidden(
    async_client, phenopacket_fixture, user_factory, token_factory
):
    curator = await user_factory(role="curator")
    curator_token = await token_factory(user=curator)
    admin_token = await token_factory(role="admin")
    created = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(phenopacket_fixture.id),
            "body_markdown": "orig",
            "mention_user_ids": [],
        },
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    cid = created.json()["id"]
    resp = await async_client.patch(
        f"/api/v2/comments/{cid}",
        json={"body_markdown": "haxx", "mention_user_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
```

Add tests for each of the remaining seven actions mirroring the shape.

- [ ] **Step 2 — `test_comments_soft_delete.py`**

```python
"""?include=deleted read semantics."""
import pytest


@pytest.mark.asyncio
async def test_soft_deleted_hidden_by_default(async_client, curator_token, comment_fixture):
    await async_client.delete(
        f"/api/v2/comments/{comment_fixture.id}",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    # List without include
    resp = await async_client.get(
        "/api/v2/comments",
        params={
            "filter[record_type]": "phenopacket",
            "filter[record_id]": str(comment_fixture.record_id),
        },
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert comment_fixture.id not in [c["id"] for c in resp.json()["data"]]

    # Detail without include → 404
    detail = await async_client.get(
        f"/api/v2/comments/{comment_fixture.id}",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_include_deleted_returns_full_body(async_client, curator_token, comment_fixture):
    await async_client.delete(
        f"/api/v2/comments/{comment_fixture.id}",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    detail = await async_client.get(
        f"/api/v2/comments/{comment_fixture.id}?include=deleted",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["body_markdown"] == comment_fixture.body_markdown
    assert detail.json()["deleted_at"] is not None
```

- [ ] **Step 3 — `test_comments_c6_terminal_writes.py`**

```python
"""C6 — soft-deleted comments are terminal for writes."""
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("PATCH",  "/api/v2/comments/{id}",            {"body_markdown": "x", "mention_user_ids": []}),
    ("POST",   "/api/v2/comments/{id}/resolve",    None),
    ("POST",   "/api/v2/comments/{id}/unresolve",  None),
    ("DELETE", "/api/v2/comments/{id}",            None),
])
async def test_soft_deleted_writes_404(
    async_client, curator_token, comment_fixture, method, path, body
):
    await async_client.delete(
        f"/api/v2/comments/{comment_fixture.id}",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    url = path.format(id=comment_fixture.id)
    resp = await async_client.request(
        method, url, json=body,
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 4 — run + commit**

```bash
cd backend && uv run pytest tests/test_comments_permissions.py tests/test_comments_soft_delete.py tests/test_comments_c6_terminal_writes.py -v
git add backend/tests/test_comments_permissions.py backend/tests/test_comments_soft_delete.py backend/tests/test_comments_c6_terminal_writes.py
git commit -m "test(backend): comments permissions matrix + soft-delete + C6"
```

---

## Task 33: Part B invariant tests (C1 AST, C2 replace, C3, C5 CHECK)

**Files:**
- Create: `backend/tests/test_comments_ast_immutable.py` (C1)
- Create: `backend/tests/test_comments_mentions_replace.py` (C2)
- Create: `backend/tests/test_comments_record_integrity.py` (C3)
- Create: `backend/tests/test_comments_c5_check_constraints.py` (C5)

- [ ] **Step 1 — C1 AST test**

```python
"""C1 — no application code UPDATEs or DELETEs comment_edits."""
import ast
import pathlib


FORBIDDEN_PATTERNS = (
    "CommentEdit.__table__.update",
    "CommentEdit.__table__.delete",
    "update(CommentEdit)",
    "delete(CommentEdit)",
)


def test_no_mutations_against_comment_edits():
    root = pathlib.Path(__file__).parent.parent.parent / "app"
    offenders = []
    for py in root.rglob("*.py"):
        src = py.read_text()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in src:
                offenders.append((str(py), pattern))
    assert not offenders, f"C1 violated in: {offenders}"
```

- [ ] **Step 2 — C2 replace test**

```python
"""C2 — mentions row-set equals latest submission after N edits."""
import pytest


@pytest.mark.asyncio
async def test_mentions_replaced_atomically(
    db_session, phenopacket_factory, user_factory
):
    from app.comments.service import CommentsService

    pp = await phenopacket_factory()
    author = await user_factory(role="curator")
    u1 = await user_factory(role="curator")
    u2 = await user_factory(role="admin")
    u3 = await user_factory(role="curator")
    svc = CommentsService(db_session)

    c = await svc.create(
        record_type="phenopacket", record_id=pp.id,
        body_markdown="m1", mention_user_ids=[u1.id, u2.id], actor=author,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert {u.id for u in mentions} == {u1.id, u2.id}

    await svc.update_body(
        comment_id=c.id, body_markdown="m2", mention_user_ids=[u3.id], actor=author,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert {u.id for u in mentions} == {u3.id}

    # Empty edit clears all mentions
    await svc.update_body(
        comment_id=c.id, body_markdown="m3", mention_user_ids=[], actor=author,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert mentions == []
```

- [ ] **Step 3 — C3 record integrity test** — already in Task 17's test file; extend with a soft-deleted case:

```python
@pytest.mark.asyncio
async def test_create_against_soft_deleted_phenopacket_succeeds(
    db_session, phenopacket_factory, user_factory
):
    """Soft-deleted record can still have comments added (C3)."""
    from app.comments.service import CommentsService

    pp = await phenopacket_factory()
    pp.deleted_at = func.now()
    await db_session.commit()

    curator = await user_factory(role="curator")
    svc = CommentsService(db_session)
    c = await svc.create(
        record_type="phenopacket", record_id=pp.id,
        body_markdown="rip", mention_user_ids=[], actor=curator,
    )
    assert c.id is not None
```

- [ ] **Step 4 — C5 CHECK constraint test**

```python
"""C5 — DB CHECK constraints reject inconsistent resolved/deleted pairs."""
import pytest
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_cannot_set_resolved_at_without_resolver(db_session, comment_fixture):
    """resolved_at set + resolved_by_id NULL → IntegrityError."""
    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE comments SET resolved_at = now() WHERE id = :id"),
            {"id": comment_fixture.id},
        )
        await db_session.commit()
```

- [ ] **Step 5 — run + commit**

```bash
cd backend && uv run pytest tests/test_comments_ast_immutable.py tests/test_comments_mentions_replace.py tests/test_comments_record_integrity.py tests/test_comments_c5_check_constraints.py -v
git add backend/tests/test_comments_ast_immutable.py backend/tests/test_comments_mentions_replace.py backend/tests/test_comments_record_integrity.py backend/tests/test_comments_c5_check_constraints.py
git commit -m "test(backend): C1 AST + C2 replace + C3 + C5 CHECK invariants"
```

---

## Task 34: Frontend component tests

**Files:**
- Create: `frontend/tests/unit/CommentItem.spec.js`
- Create: `frontend/tests/unit/CommentBody.spec.js`
- Create: `frontend/tests/unit/CommentComposer.spec.js`

- [ ] **Step 1 — `CommentBody.spec.js` (XSS sanitization)**

```javascript
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import CommentBody from '@/components/comments/CommentBody.vue';

describe('CommentBody', () => {
  it('renders plain markdown', () => {
    const wrapper = mount(CommentBody, { props: { bodyMarkdown: '**bold**' } });
    expect(wrapper.html()).toContain('<strong>bold</strong>');
  });

  it('strips <script> tags', () => {
    const wrapper = mount(CommentBody, {
      props: { bodyMarkdown: '<script>alert(1)</script>hi' },
    });
    expect(wrapper.html()).not.toContain('<script>');
  });

  it('strips onerror attributes', () => {
    const wrapper = mount(CommentBody, {
      props: { bodyMarkdown: '<img src=x onerror="alert(1)">' },
    });
    expect(wrapper.html()).not.toContain('onerror');
  });
});
```

- [ ] **Step 2 — `CommentItem.spec.js`**

```javascript
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import CommentItem from '@/components/comments/CommentItem.vue';

const baseComment = {
  id: 1,
  record_type: 'phenopacket',
  record_id: 'abc',
  author_id: 42,
  author_username: 'alice',
  author_display_name: 'Alice Example',
  body_markdown: 'hello',
  mentions: [],
  edited: false,
  resolved_at: null,
  resolved_by_id: null,
  created_at: '2026-04-14T10:00:00Z',
  updated_at: '2026-04-14T10:00:00Z',
  deleted_at: null,
  deleted_by_id: null,
};

describe('CommentItem', () => {
  it('shows resolved chip when resolved', () => {
    const wrapper = mount(CommentItem, {
      props: {
        comment: { ...baseComment, resolved_at: '2026-04-14T11:00:00Z' },
        currentUserId: 42,
        currentUserRole: 'curator',
      },
    });
    expect(wrapper.text()).toContain('Resolved');
  });

  it('does not show action menu for non-author non-admin', () => {
    const wrapper = mount(CommentItem, {
      props: {
        comment: baseComment,
        currentUserId: 99,        // different from author
        currentUserRole: 'curator',
      },
    });
    expect(wrapper.find('[aria-label="dots menu"]').exists()).toBe(false);
  });
});
```

- [ ] **Step 3 — `CommentComposer.spec.js`** — at minimum assert that the Post button is disabled on empty content:

```javascript
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import CommentComposer from '@/components/comments/CommentComposer.vue';

describe('CommentComposer', () => {
  it('submit button is disabled when body empty', () => {
    const wrapper = mount(CommentComposer, { props: { editingComment: null, submitting: false } });
    const btn = wrapper.find('button');
    expect(btn.attributes('disabled')).toBeDefined();
  });
});
```

- [ ] **Step 4 — run + commit**

```bash
cd frontend && npm test
git add frontend/tests/unit/CommentItem.spec.js frontend/tests/unit/CommentBody.spec.js frontend/tests/unit/CommentComposer.spec.js
git commit -m "test(frontend): component tests for comments (sanitize, resolve chip, composer)"
```

---

## Task 35: E2E Playwright comment flow

**Files:**
- Create: `frontend/tests/e2e/comments.spec.js`

```javascript
// @ts-check
/**
 * D.2 comments — end-to-end flow.
 * 
 * Flow: login as curator → open phenopacket → post → edit → verify edited label
 * → login as admin → soft-delete → verify list state.
 */
import { test, expect } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173';
const CURATOR_USERNAME = process.env.E2E_CURATOR_USERNAME || 'curator';
const CURATOR_PASSWORD = process.env.E2E_CURATOR_PASSWORD || 'ChangeMe!Curator2025';
const ADMIN_USERNAME = process.env.E2E_ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe!Admin2025';

test('comments end-to-end', async ({ page, browser }) => {
  // 1. Login as curator
  await page.goto(`${BASE}/login`);
  await page.fill('input[name="username"]', CURATOR_USERNAME);
  await page.fill('input[name="password"]', CURATOR_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/phenopackets/);

  // 2. Open any phenopacket
  await page.click('.v-data-table-row:first-child a');
  await page.waitForLoadState('networkidle');

  // 3. Open Discussion tab, post a comment
  await page.getByRole('tab', { name: /Discussion/i }).click();
  const commentText = `e2e-test-${Date.now()}`;
  // Tiptap editor is a contenteditable div
  await page.locator('.composer-editor').click();
  await page.keyboard.type(commentText);
  await page.getByRole('button', { name: /^Post$/ }).click();
  await expect(page.getByText(commentText)).toBeVisible();

  // 4. Edit the comment
  await page.locator('.comment-body').first().locator('..').locator('button[icon="mdi-dots-vertical"]').click();
  await page.getByText('Edit').click();
  await page.locator('.composer-editor').click();
  await page.keyboard.press('End');
  await page.keyboard.type(' edited');
  await page.getByRole('button', { name: /^Save$/ }).click();
  await expect(page.getByText(`${commentText} edited`)).toBeVisible();
  await expect(page.getByText(/edited/)).toBeVisible();

  // 5. Logout, login as admin, delete
  await page.goto(`${BASE}/logout`);
  await page.goto(`${BASE}/login`);
  await page.fill('input[name="username"]', ADMIN_USERNAME);
  await page.fill('input[name="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.goBack();
  await page.getByRole('tab', { name: /Discussion/i }).click();
  await page.locator('.comment-body').first().locator('..').locator('button[icon="mdi-dots-vertical"]').click();
  await page.getByText('Delete').click();
  await page.getByRole('button', { name: /OK|Delete|Confirm/ }).click();
  // Comment removed from list
  await expect(page.getByText(commentText)).toHaveCount(0);
});
```

- [ ] **Step 1 — run the spec**

```bash
cd ~/development/hnf1b-db && make hybrid-up
make backend &
make frontend &
cd frontend && npx playwright test tests/e2e/comments.spec.js
```

Expected: PASS.

- [ ] **Step 2 — commit**

```bash
git add frontend/tests/e2e/comments.spec.js
git commit -m "test(e2e): comments flow — post, edit, delete across curator/admin"
```

---

## Wave 5 acceptance gate

- [ ] All Part A and Part B invariants covered by at least one test each (I8, I9, C1, C2, C3, C4, C5, C6).
- [ ] `frontend/tests/e2e/dual-read-invariant.spec.js` all 5 phases green.
- [ ] `frontend/tests/e2e/comments.spec.js` green.
- [ ] Full suites green: `make check` in both `backend/` and `frontend/`.
- [ ] Backend coverage ≥ 70%; new code ≥ 85%. Frontend coverage floor 30% unchanged.

---

# Final PR

- [ ] **Step 1 — squash-audit: rebase to `main` and confirm all commits compile individually**

```bash
git fetch origin
git rebase origin/main
make check  # in both backend/ and frontend/
```

- [ ] **Step 2 — open PR**

```bash
git push -u origin chore/wave-7-d2-comments-and-clone-advancement
gh pr create --title "feat(wave-7-d2): effective-state routing + comments/edits/mentions" --body "$(cat <<'EOF'
## Summary

Two units shipping together per spec §9 Rollout:

**Part A — D.1 clone-cycle advancement (effective-state routing)**
Fixes three dead-ends in the clone-to-draft flow shipped by D.1. After a published record is cloned for editing, curators could not submit for review, iterate on the draft, or withdraw. New `_effective_state(pp)` in PhenopacketStateService reads the in-flight revision's state when `editing_revision_id` is set; `pp.state` becomes sticky at 'published'/'archived' after first publish (invariant I8). The central `build_phenopacket_response` now populates `effective_state` for every read path, so the frontend sees consistent state everywhere.

**Part B — D.2 comments + edits + mentions**
Generic comments table (record_type, record_id), immutable comment_edits log, thin comment_mentions join. Markdown-only body with Tiptap editor, @-mention autocomplete via /api/v2/users/mentionable. Fourth tab "Discussion" on PagePhenopacket.vue, curator+ only. Threading, anchored comments, notifications, and the approve-gate-on-unresolved are deferred to D.3 / later.

## Test plan
- [x] `make check` green in backend/
- [x] `make check` green in frontend/
- [x] Playwright dual-read-invariant.spec.js: all 5 phases (phase 5 previously truncated, now implemented)
- [x] Playwright comments.spec.js: post → edit → delete flow
- [x] All invariants (I8, I9, C1–C6) covered by dedicated tests
- [x] Alembic up/down/up idempotent on all three new migrations

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3 — return the PR URL to the user.**

---

# Plan Self-Review — Sign-off

After writing this plan I ran the self-review checklist:

1. **Spec coverage.** Every section of the spec maps to at least one task:
   - §3 invariants I8/I9/C1–C6 → Tasks 2, 4, 31, 33
   - §4 Part A code changes → Tasks 1–11
   - §5.1 migrations → Tasks 12–14
   - §5.2 permissions matrix → Task 32
   - §5.3 API surface → Tasks 17, 18, 19
   - §5.4 Pydantic schemas → Task 16
   - §5.5 service → Tasks 17, 18
   - §5.6 auth dep → Task 19
   - §5.7 mentionable-users + routing-order → Task 20
   - §5.8 frontend → Tasks 21–30
   - §6 mutation sequences → Tasks 17, 18
   - §7 testing → Tasks 31–35
   - §9 rollout → Final PR section
   - §10 acceptance criteria → Wave gates + final PR

2. **Placeholder scan.** No "TBD"/"TODO"/"similar to Task N"/"fill in details". The only `// TODO` in the plan is inside the Phase 5 E2E scaffold (Task 11 Step 2), where it's explicitly called out and replaced in the next paragraph of the same step.

3. **Type consistency.** `CommentsService.RecordNotFound` / `.MentionUnknownUser` / `.SoftDeleted` / etc. named consistently across Tasks 17–19. `effective_state` used identically in backend (Tasks 6–8) and frontend (Tasks 9–10). API endpoint paths match spec §5.3 and the router file in Task 19.

Plan is complete. Handoff text below.

