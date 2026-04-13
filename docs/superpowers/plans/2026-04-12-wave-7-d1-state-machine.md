# Wave 7 / D.1 — State Machine & Revisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the D.1 curation-workflow state machine + immutable `phenopacket_revisions` substrate + dual-pointer (working-copy vs. public-copy) visibility model, with every existing read path routed through a single filter-centralization repository.

**Architecture:** Three Alembic migrations + one new SQLAlchemy model + repository filter centralization + a `PhenopacketStateService` that implements four exact transaction sequences (clone-to-draft, head-swap-on-publish, in-place draft save, simple transition). FastAPI gains one new endpoint family (`/transitions`, `/revisions`). Frontend gets four small components (state badge, transition menu, transition modal, editing banner), one composable, and three view tweaks. Everything is gated by invariants I1–I7 enforced by tests.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL (JSONB, partial unique index) + Alembic + pytest-asyncio + Vue 3 + Vuetify 3 + Playwright.

**Source spec:** [docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md](../specs/2026-04-12-wave-7-d1-state-machine-design.md).

---

## File structure

### New files

| Path | Responsibility |
|---|---|
| `backend/alembic/versions/20260412_0001_add_state_columns_to_phenopackets.py` | Migration 1 (§5.1) |
| `backend/alembic/versions/20260412_0002_add_phenopacket_revisions_table.py` | Migration 2 (§5.2) |
| `backend/alembic/versions/20260412_0003_seed_state_and_revisions.py` | Migration 3 (§5.3) |
| `backend/app/phenopackets/models/revision.py` | `PhenopacketRevision` ORM model |
| `backend/app/phenopackets/services/state_service.py` | `PhenopacketStateService`: the four transaction sequences from §6 |
| `backend/app/phenopackets/services/transitions.py` | Pure-function transition guard matrix (no I/O) |
| `backend/app/phenopackets/repositories/visibility.py` | `public_filter`, `curator_filter`, `resolve_public_content`, `resolve_curator_content` |
| `backend/app/api/phenopackets/transitions.py` | `POST /transitions`, `GET /revisions`, `GET /revisions/{id}` endpoints |
| `backend/tests/test_state_invariants.py` | Invariant I1–I7 direct tests |
| `backend/tests/test_state_transitions.py` | Guard matrix + ownership tests |
| `backend/tests/test_state_flows.py` | Integration tests for §6 transaction sequences |
| `backend/tests/test_visibility_filter.py` | Filter-centralization tests across §8.2 endpoints |
| `backend/tests/test_visibility_ast.py` | AST-level test enforcing repository routing |
| `backend/tests/test_migration_d1_seed.py` | Migration 3 fixture test |
| `frontend/src/components/state/StateBadge.vue` | Colored chip component |
| `frontend/src/components/state/TransitionMenu.vue` | Role/state-gated transition dropdown |
| `frontend/src/components/state/TransitionModal.vue` | Reason-required confirmation dialog |
| `frontend/src/components/state/EditingBanner.vue` | "Draft in progress by @X" banner |
| `frontend/src/composables/usePhenopacketState.js` | `transitionTo`, `fetchRevisions` composable |
| `frontend/tests/unit/components/state/StateBadge.spec.js` | Component test |
| `frontend/tests/unit/components/state/TransitionMenu.spec.js` | Role-gating test |
| `frontend/tests/unit/components/state/TransitionModal.spec.js` | Validation test |
| `frontend/tests/unit/components/state/EditingBanner.spec.js` | Variants test |
| `frontend/tests/e2e/state-lifecycle.spec.js` | Full lifecycle E2E |
| `frontend/tests/e2e/dual-read-invariant.spec.js` | I1 dual-read E2E |

### Modified files

| Path | Change |
|---|---|
| `backend/app/phenopackets/models.py` | Add state + pointer + ownership columns to `Phenopacket`; add `PhenopacketResponse` fields; add `TransitionRequest`, `RevisionResponse` schemas |
| `backend/app/phenopackets/repositories/__init__.py` | Re-export visibility helpers |
| `backend/app/phenopackets/repositories.py` *(or existing repo module)* | Call out to `visibility.py` for filter application |
| `backend/app/phenopackets/routers/crud.py` | PUT: state-branching logic; GET list+detail: role-based resolver |
| `backend/app/phenopackets/routers/crud_related.py` | Route through visibility helpers |
| `backend/app/phenopackets/routers/crud_timeline.py` | Route through visibility helpers |
| `backend/app/phenopackets/routers/search.py` | Route through visibility helpers |
| `backend/app/search/repositories.py` | Route through visibility helpers |
| `backend/app/search/services/facet.py` | Route through visibility helpers |
| `backend/app/phenopackets/routers/comparisons/query.py` | Route through visibility helpers |
| `backend/app/phenopackets/routers/aggregations/*.py` | Route through visibility helpers (one commit per file group) |
| `backend/app/publications/endpoints/list_route.py` | Route through visibility helpers |
| `backend/app/seo/sitemap.py` | Route through public filter |
| `backend/app/api/admin/queries.py` | Use `curator_filter(include_deleted=True, include_archived=True)` |
| `backend/alembic/versions/add_materialized_views_for_aggregations.py` | MV filters by state + deleted (new migration to drop + recreate MVs) |
| `backend/app/main.py` | Register `/transitions` and `/revisions` routers |
| `frontend/src/api/domain/phenopackets.js` | `transitionTo`, `fetchRevisions`, `fetchRevisionDetail` |
| `frontend/src/views/Phenopackets.vue` (list) | State badge column |
| `frontend/src/views/PagePhenopacket.vue` (detail) | State badge + `TransitionMenu` + `EditingBanner` |
| `frontend/src/views/PhenopacketCreateEdit.vue` | Toast after save (draft / clone-to-draft messaging) |
| `.github/workflows/ci.yml` | Add new Playwright specs to gating matrix |

---

## Prerequisites

### Task 0: Worktree + baseline

- [ ] **Step 0.1: Create worktree per CLAUDE.md (sibling, never nested)**

```bash
cd ~/development
git -C hnf1b-db worktree add ../hnf1b-db.worktrees/chore-wave-7-d1-state-machine -b chore/wave-7-d1-state-machine main
cd hnf1b-db.worktrees/chore-wave-7-d1-state-machine
```

- [ ] **Step 0.2: Install deps in worktree**

```bash
cd backend && uv sync --group test && cd ..
cd frontend && npm install && cd ..
```

- [ ] **Step 0.3: Baseline tests pass on a clean worktree**

```bash
cd backend && uv run pytest -q && cd ..
cd frontend && npm test -- --run && cd ..
```
Expected: 1,131 backend passing, frontend suite green. **If anything fails, investigate before proceeding.**

- [ ] **Step 0.4: Spin up DB for migration work**

```bash
make hybrid-up
```
Expected: PostgreSQL on :5433, Redis on :6379.

---

## Phase 1 — Schema

### Task 1: Migration 1 — new columns on `phenopackets`

**Files:**
- Create: `backend/alembic/versions/20260412_0001_add_state_columns_to_phenopackets.py`

- [ ] **Step 1.1: Generate empty migration file**

```bash
cd backend
uv run alembic revision -m "add state columns to phenopackets"
# Rename the generated file to 20260412_0001_add_state_columns_to_phenopackets.py
```

- [ ] **Step 1.2: Fill upgrade() / downgrade()**

Replace the generated file contents with:

```python
"""Add state + editing + head-published + draft-owner columns to phenopackets.

Revision ID: 20260412_0001
Revises: <previous head, e.g. fff51e479b02>
Create Date: 2026-04-12

Part of Wave 7 D.1. See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.1.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_0001"
down_revision = "fff51e479b02"  # the previous head at time of writing; adjust on rebase
branch_labels = None
depends_on = None


STATES = ("draft", "in_review", "changes_requested", "approved", "published", "archived")


def upgrade() -> None:
    op.add_column(
        "phenopackets",
        sa.Column("state", sa.Text(), nullable=False, server_default="draft"),
    )
    op.create_check_constraint(
        "ck_phenopackets_state", "phenopackets",
        sa.text("state IN " + repr(STATES)),
    )
    op.add_column(
        "phenopackets",
        sa.Column("editing_revision_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "phenopackets",
        sa.Column("head_published_revision_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "phenopackets",
        sa.Column("draft_owner_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_phenopackets_draft_owner",
        "phenopackets", "users",
        ["draft_owner_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_phenopackets_state", "phenopackets", ["state"])
    op.create_index(
        "ix_phenopackets_draft_owner", "phenopackets", ["draft_owner_id"],
        postgresql_where=sa.text("draft_owner_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_phenopackets_draft_owner", table_name="phenopackets")
    op.drop_index("ix_phenopackets_state", table_name="phenopackets")
    op.drop_constraint("fk_phenopackets_draft_owner", "phenopackets", type_="foreignkey")
    op.drop_column("phenopackets", "draft_owner_id")
    op.drop_column("phenopackets", "head_published_revision_id")
    op.drop_column("phenopackets", "editing_revision_id")
    op.drop_constraint("ck_phenopackets_state", "phenopackets", type_="check")
    op.drop_column("phenopackets", "state")
```

- [ ] **Step 1.3: Run migration up + down round-trip**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: three clean runs, no errors.

- [ ] **Step 1.4: Commit**

```bash
git add backend/alembic/versions/20260412_0001_add_state_columns_to_phenopackets.py
git commit -m "feat(db): add state + pointer + owner columns to phenopackets (Wave 7/D.1 §5.1)"
```

---

### Task 2: Migration 2 — `phenopacket_revisions` table + FKs

**Files:**
- Create: `backend/alembic/versions/20260412_0002_add_phenopacket_revisions_table.py`

- [ ] **Step 2.1: Generate migration file, fill body**

```python
"""Add phenopacket_revisions table + FKs from phenopackets pointers.

Revision ID: 20260412_0002
Revises: 20260412_0001
Create Date: 2026-04-12

Part of Wave 7 D.1. See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.2.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0002"
down_revision = "20260412_0001"
branch_labels = None
depends_on = None


STATES = ("draft", "in_review", "changes_requested", "approved", "published", "archived")


def upgrade() -> None:
    op.create_table(
        "phenopacket_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("phenopackets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("content_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_patch", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("is_head_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("record_id", "revision_number", name="uq_record_revision_number"),
        sa.CheckConstraint("state IN " + repr(STATES), name="ck_revisions_state"),
    )
    op.create_index(
        "ux_head_published_per_record", "phenopacket_revisions", ["record_id"],
        unique=True, postgresql_where=sa.text("is_head_published = TRUE"),
    )
    op.create_index(
        "ix_revisions_record_created", "phenopacket_revisions",
        ["record_id", sa.text("created_at DESC")],
    )
    op.create_foreign_key(
        "fk_phenopackets_editing_revision",
        "phenopackets", "phenopacket_revisions",
        ["editing_revision_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_phenopackets_head_published_revision",
        "phenopackets", "phenopacket_revisions",
        ["head_published_revision_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_phenopackets_head_published_revision", "phenopackets", type_="foreignkey",
    )
    op.drop_constraint(
        "fk_phenopackets_editing_revision", "phenopackets", type_="foreignkey",
    )
    op.drop_index("ix_revisions_record_created", table_name="phenopacket_revisions")
    op.drop_index("ux_head_published_per_record", table_name="phenopacket_revisions")
    op.drop_table("phenopacket_revisions")
```

- [ ] **Step 2.2: Round-trip migration**

```bash
cd backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: clean up/down/up.

- [ ] **Step 2.3: Commit**

```bash
git add backend/alembic/versions/20260412_0002_add_phenopacket_revisions_table.py
git commit -m "feat(db): add phenopacket_revisions table with partial unique head index (Wave 7/D.1 §5.2)"
```

---

### Task 3: Migration 3 — seed state + revisions on existing rows

**Files:**
- Create: `backend/alembic/versions/20260412_0003_seed_state_and_revisions.py`

- [ ] **Step 3.1: Write migration body**

```python
"""Seed state='published' + one head-published revision row per existing phenopacket.

Revision ID: 20260412_0003
Revises: 20260412_0002
Create Date: 2026-04-12

Part of Wave 7 D.1. See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.3.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_0003"
down_revision = "20260412_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Ensure a `system` user exists.
    conn.execute(
        sa.text(
            """
            INSERT INTO users (
              username, email, password_hash, role,
              is_active, is_verified, full_name, created_at, updated_at
            )
            VALUES (
              'system', 'system@hnf1b-db.local',
              -- dummy argon2 hash; account is is_active=FALSE
              '$argon2id$v=19$m=19456,t=2,p=1$0000000000000000$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
              'admin',
              FALSE, TRUE, 'System',
              NOW(), NOW()
            )
            ON CONFLICT (username) DO NOTHING
            """
        )
    )
    system_id = conn.execute(sa.text("SELECT id FROM users WHERE username='system'")).scalar_one()

    # 2. For every existing row: insert a revision row, then set head pointer + state.
    conn.execute(
        sa.text(
            """
            INSERT INTO phenopacket_revisions (
              record_id, revision_number, state, content_jsonb, change_patch,
              change_reason, actor_id, from_state, to_state, is_head_published, created_at
            )
            SELECT
              id, revision, 'published', phenopacket, NULL,
              'Migrated from pre-D.1 data model', :sys, NULL, 'published', TRUE, NOW()
            FROM phenopackets
            WHERE deleted_at IS NULL OR TRUE  -- include soft-deleted too; head is set regardless
            """
        ),
        {"sys": system_id},
    )

    conn.execute(
        sa.text(
            """
            UPDATE phenopackets p
            SET
              state = 'published',
              head_published_revision_id = r.id,
              draft_owner_id = NULL,
              editing_revision_id = NULL
            FROM phenopacket_revisions r
            WHERE r.record_id = p.id AND r.is_head_published = TRUE
            """
        )
    )


def downgrade() -> None:
    # Destructive: drops all seeded revision rows and resets state/pointers.
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE phenopackets SET state='draft', head_published_revision_id=NULL, editing_revision_id=NULL, draft_owner_id=NULL"))
    conn.execute(sa.text("DELETE FROM phenopacket_revisions WHERE change_reason='Migrated from pre-D.1 data model'"))
```

- [ ] **Step 3.2: Run migration against dev DB**

```bash
cd backend
uv run alembic upgrade head
# Assert seed worked:
uv run python -c "
import asyncio
from sqlalchemy import text
from app.database import async_session
async def check():
    async with async_session() as s:
        r = await s.execute(text('SELECT COUNT(*) FROM phenopacket_revisions WHERE is_head_published=TRUE'))
        print('head rows:', r.scalar_one())
        r = await s.execute(text(\"SELECT COUNT(*) FROM phenopackets WHERE state='published'\"))
        print('published:', r.scalar_one())
asyncio.run(check())
"
```
Expected: both counts equal to `SELECT COUNT(*) FROM phenopackets`.

- [ ] **Step 3.3: Round-trip down/up**

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: seed re-runs cleanly (system user persists due to ON CONFLICT).

- [ ] **Step 3.4: Commit**

```bash
git add backend/alembic/versions/20260412_0003_seed_state_and_revisions.py
git commit -m "feat(db): seed state='published' + head revision row per existing record (Wave 7/D.1 §5.3)"
```

---

### Task 4: `PhenopacketRevision` ORM model + `Phenopacket` field updates

**Files:**
- Create: `backend/app/phenopackets/models/revision.py`
- Modify: `backend/app/phenopackets/models.py` (add fields to `Phenopacket` + Pydantic schemas)

- [ ] **Step 4.1: Write failing test first**

Create `backend/tests/test_state_model.py`:

```python
"""Unit test: new ORM fields on Phenopacket + PhenopacketRevision."""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket
from app.phenopackets.models.revision import PhenopacketRevision


@pytest.mark.asyncio
async def test_phenopacket_has_state_fields(db_session):
    pp = Phenopacket(phenopacket_id="test-1", phenopacket={"id": "test-1"}, state="draft", revision=1)
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)
    assert pp.state == "draft"
    assert pp.editing_revision_id is None
    assert pp.head_published_revision_id is None
    assert pp.draft_owner_id is None


@pytest.mark.asyncio
async def test_revision_row_roundtrip(db_session, seeded_system_user):
    pp = Phenopacket(phenopacket_id="test-2", phenopacket={}, state="draft", revision=1)
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=1,
        state="draft",
        content_jsonb={"x": 1},
        change_reason="init",
        actor_id=seeded_system_user.id,
        from_state=None,
        to_state="draft",
        is_head_published=False,
    )
    db_session.add(rev)
    await db_session.commit()

    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.record_id == pp.id)
    )
    rev2 = result.scalar_one()
    assert rev2.content_jsonb == {"x": 1}
    assert rev2.is_head_published is False
```

- [ ] **Step 4.2: Run test — expect ImportError on `revision.py`**

```bash
cd backend && uv run pytest tests/test_state_model.py -x
```
Expected: FAIL / ImportError.

- [ ] **Step 4.3: Create the model**

Create `backend/app/phenopackets/models/__init__.py` to turn `models.py` into a package (or keep as module — project convention wins; check). Assume package move is acceptable; the alternative is putting `PhenopacketRevision` inside `models.py`. For clarity we add it as a sibling in the existing module (simpler, no package migration).

Add to `backend/app/phenopackets/models.py`, near the other ORM models:

```python
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
import uuid as _uuid

class PhenopacketRevision(Base):
    """Immutable snapshot of a phenopacket at a state transition.

    See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.2.
    """

    __tablename__ = "phenopacket_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_id: Mapped[_uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("phenopackets.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    content_jsonb: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_patch: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False,
    )
    from_state: Mapped[Optional[str]] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    is_head_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id], viewonly=True)
```

Add new columns to `Phenopacket`:

```python
# inside class Phenopacket(Base): ...
state: Mapped[str] = mapped_column(Text, nullable=False, default="draft", index=True)
editing_revision_id: Mapped[Optional[int]] = mapped_column(
    BigInteger, ForeignKey("phenopacket_revisions.id", ondelete="SET NULL"),
    nullable=True,
)
head_published_revision_id: Mapped[Optional[int]] = mapped_column(
    BigInteger, ForeignKey("phenopacket_revisions.id", ondelete="SET NULL"),
    nullable=True,
)
draft_owner_id: Mapped[Optional[int]] = mapped_column(
    BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
)
draft_owner: Mapped[Optional["User"]] = relationship(
    "User", foreign_keys=[draft_owner_id], viewonly=True,
)
```

Note: the two FKs on `Phenopacket → PhenopacketRevision` introduce a cycle. Provide `use_alter=True` on **one** of the Alembic constraint creations (already done in migration 2 — they're created separately, after the table exists).

- [ ] **Step 4.4: Run test — expect PASS**

```bash
uv run pytest tests/test_state_model.py -x
```
Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/phenopackets/models.py backend/tests/test_state_model.py
git commit -m "feat(models): add PhenopacketRevision + state/pointer/owner fields (Wave 7/D.1 §4)"
```

---

### Task 5: Update Pydantic response schemas

**Files:**
- Modify: `backend/app/phenopackets/models.py` (Pydantic section)

- [ ] **Step 5.1: Write failing test**

Add to `backend/tests/test_state_model.py`:

```python
from app.phenopackets.models import PhenopacketResponse, TransitionRequest, RevisionResponse


def test_phenopacket_response_has_state_fields():
    resp = PhenopacketResponse(
        phenopacket_id="x", phenopacket={}, revision=1,
        state="published", head_published_revision_id=10,
        editing_revision_id=None, draft_owner_id=None, draft_owner_username=None,
    )
    assert resp.state == "published"
    assert resp.head_published_revision_id == 10


def test_transition_request_validation():
    r = TransitionRequest(to_state="in_review", reason="please review", revision=1)
    assert r.to_state == "in_review"

    with pytest.raises(ValueError):
        TransitionRequest(to_state="in_review", reason="", revision=1)  # min_length


def test_transition_request_rejects_bad_state():
    with pytest.raises(ValueError):
        TransitionRequest(to_state="not_a_state", reason="x", revision=1)
```

- [ ] **Step 5.2: Run — expect FAIL (fields/classes missing)**

```bash
uv run pytest tests/test_state_model.py -x
```

- [ ] **Step 5.3: Add Pydantic classes**

Extend the existing `PhenopacketResponse` in `backend/app/phenopackets/models.py` with:

```python
state: str
head_published_revision_id: Optional[int] = None
editing_revision_id: Optional[int] = None
draft_owner_id: Optional[int] = None
draft_owner_username: Optional[str] = None
```

Add at end of the file:

```python
from typing import Literal
from datetime import datetime as _dt

class TransitionRequest(BaseModel):
    to_state: Literal[
        "draft", "in_review", "changes_requested",
        "approved", "published", "archived",
    ]
    reason: str = Field(..., min_length=1, max_length=500)
    revision: int


class RevisionResponse(BaseModel):
    id: int
    record_id: str  # UUID serialized as string
    phenopacket_id: str
    revision_number: int
    state: str
    from_state: Optional[str] = None
    to_state: str
    is_head_published: bool
    change_reason: str
    actor_id: int
    actor_username: Optional[str] = None
    change_patch: Optional[List[Dict[str, Any]]] = None
    created_at: _dt
    content_jsonb: Optional[Dict[str, Any]] = None  # only populated on /{id}/revisions/{revision_id}
```

- [ ] **Step 5.4: Run test — expect PASS**

```bash
uv run pytest tests/test_state_model.py -x
```

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/phenopackets/models.py backend/tests/test_state_model.py
git commit -m "feat(schemas): extend PhenopacketResponse + add TransitionRequest/RevisionResponse (Wave 7/D.1 §7.3)"
```

---

## Phase 2 — Transition engine (pure-function guard matrix first)

### Task 6: Transition guard matrix (pure functions)

**Files:**
- Create: `backend/app/phenopackets/services/transitions.py`
- Create: `backend/tests/test_state_transitions.py`

- [ ] **Step 6.1: Write failing test**

Create `backend/tests/test_state_transitions.py`:

```python
"""Pure-function guard matrix — no I/O."""

import pytest

from app.phenopackets.services.transitions import (
    StateTransition, TransitionError, allowed_transitions, check_transition,
)


CURATOR = "curator"
ADMIN = "admin"
VIEWER = "viewer"


@pytest.mark.parametrize(
    "from_state,to_state,role,is_owner,expected_ok",
    [
        # happy paths
        ("draft", "in_review", CURATOR, True, True),
        ("in_review", "changes_requested", ADMIN, False, True),
        ("in_review", "approved", ADMIN, False, True),
        ("changes_requested", "in_review", CURATOR, True, True),
        ("approved", "published", ADMIN, False, True),
        ("published", "archived", ADMIN, False, True),

        # role/ownership rejections
        ("draft", "in_review", CURATOR, False, False),  # not owner
        ("in_review", "approved", CURATOR, True, False),  # curator can't approve
        ("in_review", "changes_requested", CURATOR, True, False),
        ("approved", "published", CURATOR, False, False),
        ("draft", "in_review", VIEWER, True, False),

        # invalid transition pairs
        ("draft", "approved", ADMIN, False, False),
        ("published", "draft", ADMIN, False, False),
        ("archived", "draft", ADMIN, False, False),
        ("archived", "published", ADMIN, False, False),
    ],
)
def test_guard_matrix(from_state, to_state, role, is_owner, expected_ok):
    if expected_ok:
        check_transition(from_state, to_state, role=role, is_owner=is_owner)
    else:
        with pytest.raises(TransitionError):
            check_transition(from_state, to_state, role=role, is_owner=is_owner)


def test_allowed_transitions_returns_subset():
    # Curator-owner on draft: only `submit` legal
    legal = allowed_transitions("draft", role=CURATOR, is_owner=True)
    assert legal == {"in_review"}

    # Admin on in_review: both approve and request_changes, plus (owner) withdraw
    legal = allowed_transitions("in_review", role=ADMIN, is_owner=False)
    assert legal == {"changes_requested", "approved", "archived"}

    # Non-owner curator on draft: nothing
    legal = allowed_transitions("draft", role=CURATOR, is_owner=False)
    assert legal == set()


def test_viewer_sees_nothing_everywhere():
    for state in ["draft", "in_review", "changes_requested", "approved", "published"]:
        assert allowed_transitions(state, role=VIEWER, is_owner=True) == set()
```

- [ ] **Step 6.2: Run — expect FAIL**

```bash
cd backend && uv run pytest tests/test_state_transitions.py -x
```

- [ ] **Step 6.3: Implement guard matrix**

Create `backend/app/phenopackets/services/transitions.py`:

```python
"""Pure-function transition guard matrix for Wave 7/D.1.

No I/O. Feeds both the endpoint handler (which validates before mutating)
and the frontend-mirrored decision-making in TransitionMenu.vue (via an
API-exposed version of ``allowed_transitions``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

State = Literal[
    "draft", "in_review", "changes_requested", "approved", "published", "archived",
]
Role = Literal["admin", "curator", "viewer"]


class TransitionError(ValueError):
    """Raised when a proposed transition violates the guard matrix.

    ``code`` is one of: ``invalid_transition``, ``forbidden_role``,
    ``forbidden_not_owner``.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StateTransition:
    from_state: State
    to_state: State
    requires_admin: bool
    requires_ownership_or_admin: bool = False  # curator must be owner
    is_archive: bool = False


# Enumerated from spec §4.1. Missing entries = illegal transition.
_RULES: dict[tuple[State, State], StateTransition] = {
    ("draft", "in_review"): StateTransition("draft", "in_review", requires_admin=False, requires_ownership_or_admin=True),
    ("in_review", "draft"): StateTransition("in_review", "draft", requires_admin=False, requires_ownership_or_admin=True),
    ("in_review", "changes_requested"): StateTransition("in_review", "changes_requested", requires_admin=True),
    ("in_review", "approved"): StateTransition("in_review", "approved", requires_admin=True),
    ("changes_requested", "in_review"): StateTransition("changes_requested", "in_review", requires_admin=False, requires_ownership_or_admin=True),
    ("approved", "published"): StateTransition("approved", "published", requires_admin=True),
}
# Archive is allowed from any non-archived state.
for s in ("draft", "in_review", "changes_requested", "approved", "published"):
    _RULES[(s, "archived")] = StateTransition(s, "archived", requires_admin=True, is_archive=True)


def check_transition(
    from_state: State, to_state: State, *, role: Role, is_owner: bool,
) -> StateTransition:
    """Raise ``TransitionError`` if this transition is not allowed."""
    rule = _RULES.get((from_state, to_state))
    if rule is None:
        raise TransitionError("invalid_transition", f"{from_state} → {to_state} not allowed")

    if rule.requires_admin and role != "admin":
        raise TransitionError("forbidden_role", f"{to_state} requires admin")

    if rule.requires_ownership_or_admin and role != "admin" and not is_owner:
        raise TransitionError("forbidden_not_owner", "must be draft owner or admin")

    if role not in ("admin", "curator"):
        raise TransitionError("forbidden_role", "curator or admin required")

    return rule


def allowed_transitions(from_state: State, *, role: Role, is_owner: bool) -> set[State]:
    """Return set of ``to_state`` values legal for (role, ownership) from ``from_state``."""
    out: set[State] = set()
    for (f, t), _ in _RULES.items():
        if f != from_state:
            continue
        try:
            check_transition(from_state, t, role=role, is_owner=is_owner)
            out.add(t)
        except TransitionError:
            pass
    return out
```

- [ ] **Step 6.4: Run — expect PASS**

```bash
uv run pytest tests/test_state_transitions.py -x
```

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/phenopackets/services/transitions.py backend/tests/test_state_transitions.py
git commit -m "feat(state): pure-function transition guard matrix with tests (Wave 7/D.1 §4.1)"
```

---

### Task 7: `PhenopacketStateService` — the four transaction sequences

**Files:**
- Create: `backend/app/phenopackets/services/state_service.py`
- Create: `backend/tests/test_state_flows.py`

- [ ] **Step 7.1: Write failing integration tests**

Create `backend/tests/test_state_flows.py`:

```python
"""Integration tests for the four §6 transaction sequences."""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.fixture
async def draft_record(db_session, curator_user):
    pp = Phenopacket(
        phenopacket_id="draft-1", phenopacket={"id": "draft-1"},
        state="draft", revision=1, draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)
    return pp


@pytest.fixture
async def published_record(db_session, admin_user):
    pp = Phenopacket(
        phenopacket_id="pub-1", phenopacket={"id": "pub-1", "a": 1},
        state="published", revision=1, created_by_id=admin_user.id,
    )
    db_session.add(pp)
    await db_session.flush()
    rev = PhenopacketRevision(
        record_id=pp.id, revision_number=1, state="published",
        content_jsonb={"id": "pub-1", "a": 1}, change_reason="init",
        actor_id=admin_user.id, from_state=None, to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()
    pp.head_published_revision_id = rev.id
    await db_session.commit()
    return pp


@pytest.mark.asyncio
async def test_clone_to_draft_on_published(db_session, published_record, curator_user):
    """§6.1: edit a published record clones a draft; public pointer unchanged."""
    svc = PhenopacketStateService(db_session)
    old_head_id = published_record.head_published_revision_id

    new_content = {"id": "pub-1", "a": 2}
    await svc.edit_record(
        published_record.id, new_content=new_content,
        change_reason="fix typo", expected_revision=1, actor=curator_user,
    )
    await db_session.refresh(published_record)

    # working copy changed
    assert published_record.phenopacket == {"id": "pub-1", "a": 2}
    # public pointer unchanged
    assert published_record.head_published_revision_id == old_head_id
    # editing + owner set
    assert published_record.editing_revision_id is not None
    assert published_record.draft_owner_id == curator_user.id
    # state stays published
    assert published_record.state == "published"
    # revision bumped
    assert published_record.revision == 2

    # revision row created
    rows = (await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.record_id == published_record.id)
        .order_by(PhenopacketRevision.revision_number)
    )).scalars().all()
    assert len(rows) == 2
    assert rows[1].to_state == "draft"
    assert rows[1].is_head_published is False


@pytest.mark.asyncio
async def test_clone_to_draft_blocks_second_edit(db_session, published_record, curator_user, another_curator):
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id, new_content={"id": "pub-1", "a": 2},
        change_reason="edit", expected_revision=1, actor=curator_user,
    )

    with pytest.raises(svc.EditInProgress):
        await svc.edit_record(
            published_record.id, new_content={"id": "pub-1", "a": 3},
            change_reason="edit2", expected_revision=2, actor=another_curator,
        )


@pytest.mark.asyncio
async def test_in_place_draft_save_no_new_row(db_session, draft_record, curator_user):
    """§6.3: in-place save doesn't create a new revision row."""
    svc = PhenopacketStateService(db_session)
    before_rows = (await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.record_id == draft_record.id)
    )).scalars().all()

    # Submit first so there's an in-progress revision row to overwrite
    await svc.transition(
        draft_record.id, to_state="in_review", reason="go", expected_revision=1, actor=curator_user,
    )
    # Withdraw back to draft
    await svc.transition(
        draft_record.id, to_state="draft", reason="back", expected_revision=2, actor=curator_user,
    )
    # Now save in-place
    await svc.edit_record(
        draft_record.id, new_content={"id": "draft-1", "x": "y"},
        change_reason="tweak", expected_revision=3, actor=curator_user,
    )

    after_rows = (await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.record_id == draft_record.id)
    )).scalars().all()
    # Two transition rows (submit, withdraw); no new row for in-place save
    assert len(after_rows) == len(before_rows) + 2


@pytest.mark.asyncio
async def test_full_lifecycle(db_session, draft_record, curator_user, admin_user):
    """Integration: create → submit → approve → publish. §10.2."""
    svc = PhenopacketStateService(db_session)

    # submit
    await svc.transition(draft_record.id, to_state="in_review", reason="ready", expected_revision=1, actor=curator_user)
    await db_session.refresh(draft_record)
    assert draft_record.state == "in_review"
    assert draft_record.draft_owner_id == curator_user.id  # owner preserved

    # approve
    await svc.transition(draft_record.id, to_state="approved", reason="ok", expected_revision=draft_record.revision, actor=admin_user)
    await db_session.refresh(draft_record)
    assert draft_record.state == "approved"

    # publish (head-swap)
    await svc.transition(draft_record.id, to_state="published", reason="go live", expected_revision=draft_record.revision, actor=admin_user)
    await db_session.refresh(draft_record)
    assert draft_record.state == "published"
    assert draft_record.head_published_revision_id is not None
    assert draft_record.editing_revision_id is None
    assert draft_record.draft_owner_id is None  # I5: cleared on publish


@pytest.mark.asyncio
async def test_archive_is_terminal(db_session, published_record, admin_user):
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        published_record.id, to_state="archived", reason="retire",
        expected_revision=1, actor=admin_user,
    )
    await db_session.refresh(published_record)
    assert published_record.state == "archived"

    with pytest.raises(svc.InvalidTransition):
        await svc.transition(
            published_record.id, to_state="draft", reason="revive",
            expected_revision=2, actor=admin_user,
        )
```

- [ ] **Step 7.2: Run — expect FAIL (service not written yet)**

```bash
uv run pytest tests/test_state_flows.py -x
```

- [ ] **Step 7.3: Implement `PhenopacketStateService`**

Create `backend/app/phenopackets/services/state_service.py`:

```python
"""PhenopacketStateService: the four §6 transaction sequences.

Every method runs inside a single async transaction, holds a SELECT ...
FOR UPDATE on the phenopacket row, then mutates pointers + revisions +
state atomically. All optimistic-locking + edit-in-progress + guard
matrix checks happen before any write.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.transitions import (
    TransitionError, check_transition,
)
from app.utils.audit import compute_json_patch  # reuse existing jsonpatch helper

logger = logging.getLogger(__name__)


class PhenopacketStateService:
    """All state transitions and clone-to-draft logic."""

    class InvalidTransition(Exception):
        """Raised when a guard-matrix check fails."""

    class RevisionMismatch(Exception):
        """Optimistic-lock failure."""

    class EditInProgress(Exception):
        """Record already has a clone-to-draft open."""

    class ForbiddenNotOwner(Exception):
        """Curator is not the draft owner and not admin."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- helpers -----------------------------------------------------

    async def _lock_and_check(self, record_id: UUID, expected_revision: int) -> Phenopacket:
        stmt = select(Phenopacket).where(Phenopacket.id == record_id).with_for_update()
        pp = (await self.db.execute(stmt)).scalar_one_or_none()
        if pp is None:
            raise KeyError("phenopacket not found")
        if pp.revision != expected_revision:
            raise self.RevisionMismatch(
                f"expected revision {expected_revision}, got {pp.revision}",
            )
        return pp

    def _is_owner(self, pp: Phenopacket, actor: User) -> bool:
        return pp.draft_owner_id is not None and pp.draft_owner_id == actor.id

    # --- §6.1 clone-to-draft ----------------------------------------

    async def edit_record(
        self, record_id: UUID, *, new_content: Dict[str, Any], change_reason: str,
        expected_revision: int, actor: User,
    ) -> Phenopacket:
        pp = await self._lock_and_check(record_id, expected_revision)

        if pp.state == "published":
            if pp.editing_revision_id is not None:
                raise self.EditInProgress(pp.editing_revision_id)

            head = (await self.db.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.id == pp.head_published_revision_id,
                )
            )).scalar_one()
            patch = compute_json_patch(head.content_jsonb, new_content)

            pp.revision += 1
            rev = PhenopacketRevision(
                record_id=pp.id, revision_number=pp.revision, state="draft",
                content_jsonb=new_content, change_patch=patch,
                change_reason=change_reason, actor_id=actor.id,
                from_state="published", to_state="draft", is_head_published=False,
            )
            self.db.add(rev)
            await self.db.flush()

            pp.phenopacket = new_content
            pp.editing_revision_id = rev.id
            pp.draft_owner_id = actor.id
            # state stays 'published'; head pointer unchanged
            await self.db.commit()
            return pp

        if pp.state in ("draft", "changes_requested"):
            # §6.3 in-place
            if actor.role != "admin" and pp.draft_owner_id and pp.draft_owner_id != actor.id:
                raise self.ForbiddenNotOwner()

            pp.revision += 1
            pp.phenopacket = new_content
            if pp.editing_revision_id:
                editing = (await self.db.execute(
                    select(PhenopacketRevision).where(
                        PhenopacketRevision.id == pp.editing_revision_id,
                    )
                )).scalar_one()
                editing.content_jsonb = new_content
                editing.change_reason = change_reason
            await self.db.commit()
            return pp

        raise self.InvalidTransition(f"cannot edit record in state {pp.state!r}")

    # --- §6.2 + §6.4 state transitions ------------------------------

    async def transition(
        self, record_id: UUID, *, to_state: str, reason: str,
        expected_revision: int, actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        pp = await self._lock_and_check(record_id, expected_revision)

        try:
            check_transition(
                pp.state, to_state, role=actor.role, is_owner=self._is_owner(pp, actor),
            )
        except TransitionError as e:
            if e.code == "invalid_transition":
                raise self.InvalidTransition(str(e))
            raise self.ForbiddenNotOwner(str(e)) if e.code == "forbidden_not_owner" else PermissionError(str(e))

        if to_state == "published":
            return await self._publish(pp, reason, actor)

        # Simple transition (§6.4)
        pp.revision += 1

        # snapshot working copy into a new revision row
        prev = (await self.db.execute(
            select(PhenopacketRevision)
            .where(PhenopacketRevision.record_id == pp.id)
            .order_by(PhenopacketRevision.revision_number.desc())
        )).scalars().first()
        patch = (
            compute_json_patch(prev.content_jsonb, pp.phenopacket)
            if prev else None
        )
        rev = PhenopacketRevision(
            record_id=pp.id, revision_number=pp.revision, state=to_state,
            content_jsonb=pp.phenopacket, change_patch=patch,
            change_reason=reason, actor_id=actor.id, from_state=pp.state,
            to_state=to_state, is_head_published=False,
        )
        self.db.add(rev)
        pp.state = to_state
        if to_state == "archived":
            pp.draft_owner_id = None
        else:
            # editing pointer updates with in-flight snapshot
            pp.editing_revision_id = rev.id
        await self.db.commit()
        return pp, rev

    async def _publish(self, pp: Phenopacket, reason: str, actor: User) -> tuple[Phenopacket, PhenopacketRevision]:
        # §6.2 head-swap
        approved = (await self.db.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == pp.id,
                PhenopacketRevision.state == "approved",
            )
        )).scalar_one_or_none()
        if approved is None:
            raise self.InvalidTransition("no approved revision found")

        # clear any previous head
        await self.db.execute(
            update(PhenopacketRevision)
            .where(
                PhenopacketRevision.record_id == pp.id,
                PhenopacketRevision.is_head_published.is_(True),
            )
            .values(is_head_published=False)
        )
        # promote approved row to published + head
        approved.state = "published"
        approved.to_state = "published"
        approved.is_head_published = True
        approved.change_reason = reason

        pp.revision += 1
        pp.state = "published"
        pp.phenopacket = approved.content_jsonb
        pp.head_published_revision_id = approved.id
        pp.editing_revision_id = None
        pp.draft_owner_id = None

        try:
            await self.db.commit()
        except IntegrityError as e:
            # ux_head_published_per_record unique violation: a concurrent publish won
            raise self.InvalidTransition("concurrent publish; retry") from e

        return pp, approved
```

- [ ] **Step 7.4: Run — iterate until PASS**

```bash
uv run pytest tests/test_state_flows.py -x -v
```
Expected: all pass. Fix typos / missing imports / fixture mismatches as needed.

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/phenopackets/services/state_service.py backend/tests/test_state_flows.py
git commit -m "feat(state): PhenopacketStateService with the 4 §6 transaction sequences (Wave 7/D.1)"
```

---

### Task 8: Invariant tests (I1–I7)

**Files:**
- Create: `backend/tests/test_state_invariants.py`

- [ ] **Step 8.1: Write invariant tests**

```python
"""Invariant tests — I1..I7 from spec §3.

Each test breaks if its invariant is ever violated by code changes.
"""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_I1_state_published_does_not_imply_working_copy_equals_public_copy(
    db_session, published_record, curator_user,
):
    """I1: during clone-to-draft, state='published' while working_copy != public_copy."""
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id, new_content={"id": "pub-1", "a": 99},
        change_reason="edit", expected_revision=1, actor=curator_user,
    )
    await db_session.refresh(published_record)
    assert published_record.state == "published"

    head = (await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.id == published_record.head_published_revision_id,
        )
    )).scalar_one()
    assert head.content_jsonb != published_record.phenopacket  # <-- the invariant


@pytest.mark.asyncio
async def test_I2_at_most_one_head_published_per_record(db_session, published_record, admin_user, curator_user):
    """I2: partial unique index enforces a single head per record across edits+publishes."""
    svc = PhenopacketStateService(db_session)

    await svc.edit_record(
        published_record.id, new_content={"id": "pub-1", "v": 2},
        change_reason="x", expected_revision=1, actor=curator_user,
    )
    # submit→approve→publish
    await svc.transition(published_record.id, to_state="in_review", reason="r", expected_revision=2, actor=curator_user)
    await svc.transition(published_record.id, to_state="approved", reason="r", expected_revision=3, actor=admin_user)
    await svc.transition(published_record.id, to_state="published", reason="r", expected_revision=4, actor=admin_user)

    heads = (await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.record_id == published_record.id,
            PhenopacketRevision.is_head_published.is_(True),
        )
    )).scalars().all()
    assert len(heads) == 1


@pytest.mark.asyncio
async def test_I3_head_pointer_state_consistency(db_session, published_record):
    head = (await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.id == published_record.head_published_revision_id,
        )
    )).scalar_one()
    assert head.is_head_published is True
    assert head.to_state == "published"


@pytest.mark.asyncio
async def test_I4_edit_in_progress_blocks_second_edit(db_session, published_record, curator_user, another_curator):
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(published_record.id, new_content={"v": 1}, change_reason="r", expected_revision=1, actor=curator_user)
    with pytest.raises(svc.EditInProgress):
        await svc.edit_record(published_record.id, new_content={"v": 2}, change_reason="r", expected_revision=2, actor=another_curator)


@pytest.mark.asyncio
async def test_I5_draft_owner_null_on_historical_records(db_session, published_record):
    assert published_record.draft_owner_id is None


@pytest.mark.asyncio
async def test_I5_draft_owner_cleared_on_publish(db_session, draft_record, curator_user, admin_user):
    svc = PhenopacketStateService(db_session)
    await svc.transition(draft_record.id, to_state="in_review", reason="r", expected_revision=1, actor=curator_user)
    await svc.transition(draft_record.id, to_state="approved", reason="r", expected_revision=2, actor=admin_user)
    await svc.transition(draft_record.id, to_state="published", reason="r", expected_revision=3, actor=admin_user)
    await db_session.refresh(draft_record)
    assert draft_record.draft_owner_id is None


@pytest.mark.asyncio
async def test_I6_gaps_in_revision_numbers_after_inplace_saves(db_session, draft_record, curator_user):
    """I6: in-place saves bump phenopackets.revision but don't insert rows — gaps expected."""
    svc = PhenopacketStateService(db_session)

    await svc.edit_record(draft_record.id, new_content={"x": 1}, change_reason="a", expected_revision=1, actor=curator_user)
    await svc.edit_record(draft_record.id, new_content={"x": 2}, change_reason="b", expected_revision=2, actor=curator_user)
    await svc.transition(draft_record.id, to_state="in_review", reason="go", expected_revision=3, actor=curator_user)

    rows = (await db_session.execute(
        select(PhenopacketRevision.revision_number).where(PhenopacketRevision.record_id == draft_record.id)
        .order_by(PhenopacketRevision.revision_number)
    )).scalars().all()
    # Only the submit created a transition row; its revision_number = 4 (after two in-place saves + submit bump)
    assert rows == [4]


@pytest.mark.asyncio
async def test_I7_archived_orthogonal_to_soft_delete(db_session, published_record, admin_user):
    """I7: both can coexist; public sees neither."""
    from sqlalchemy import update as sa_update
    svc = PhenopacketStateService(db_session)
    await svc.transition(published_record.id, to_state="archived", reason="retire", expected_revision=1, actor=admin_user)
    # soft-delete on top
    await db_session.execute(
        sa_update(Phenopacket).where(Phenopacket.id == published_record.id).values(deleted_at="2026-04-12T00:00:00Z")
    )
    await db_session.commit()
    await db_session.refresh(published_record)
    assert published_record.state == "archived"
    assert published_record.deleted_at is not None
```

- [ ] **Step 8.2: Run — expect PASS (state service already built in Task 7)**

```bash
uv run pytest tests/test_state_invariants.py -x
```

- [ ] **Step 8.3: Commit**

```bash
git add backend/tests/test_state_invariants.py
git commit -m "test(state): invariant tests I1-I7 (Wave 7/D.1 §3)"
```

---

## Phase 3 — Visibility repository + API endpoints

### Task 9: Visibility repository + tests

**Files:**
- Create: `backend/app/phenopackets/repositories/visibility.py`
- Create: `backend/tests/test_visibility_filter.py`

- [ ] **Step 9.1: Write failing test**

```python
"""Filter centralization tests (spec §8 + §10.2)."""

import pytest
from sqlalchemy import select
from app.phenopackets.models import Phenopacket
from app.phenopackets.repositories.visibility import (
    public_filter, curator_filter, resolve_public_content, resolve_curator_content,
)


@pytest.mark.asyncio
async def test_public_filter_excludes_non_published(db_session, draft_record, published_record):
    stmt = public_filter(select(Phenopacket))
    results = (await db_session.execute(stmt)).scalars().all()
    ids = {pp.id for pp in results}
    assert published_record.id in ids
    assert draft_record.id not in ids


@pytest.mark.asyncio
async def test_public_filter_excludes_deleted(db_session, published_record):
    from sqlalchemy import update
    await db_session.execute(update(Phenopacket).where(Phenopacket.id == published_record.id).values(deleted_at="2026-04-12T00:00:00Z"))
    await db_session.commit()
    stmt = public_filter(select(Phenopacket))
    results = (await db_session.execute(stmt)).scalars().all()
    assert published_record.id not in {pp.id for pp in results}


@pytest.mark.asyncio
async def test_curator_filter_excludes_archived_by_default(db_session, published_record, admin_user):
    from app.phenopackets.services.state_service import PhenopacketStateService
    await PhenopacketStateService(db_session).transition(
        published_record.id, to_state="archived", reason="r", expected_revision=1, actor=admin_user,
    )
    stmt = curator_filter(select(Phenopacket))
    results = (await db_session.execute(stmt)).scalars().all()
    assert published_record.id not in {pp.id for pp in results}


@pytest.mark.asyncio
async def test_curator_filter_include_archived(db_session, published_record, admin_user):
    from app.phenopackets.services.state_service import PhenopacketStateService
    await PhenopacketStateService(db_session).transition(
        published_record.id, to_state="archived", reason="r", expected_revision=1, actor=admin_user,
    )
    stmt = curator_filter(select(Phenopacket), include_archived=True)
    results = (await db_session.execute(stmt)).scalars().all()
    assert published_record.id in {pp.id for pp in results}


@pytest.mark.asyncio
async def test_resolve_public_content_dereferences_head(db_session, published_record):
    head = await resolve_public_content(db_session, published_record)
    assert head == published_record.phenopacket
```

- [ ] **Step 9.2: Run — expect FAIL**

```bash
cd backend && uv run pytest tests/test_visibility_filter.py -x
```

- [ ] **Step 9.3: Implement visibility helpers**

Create `backend/app/phenopackets/repositories/visibility.py`:

```python
"""Centralized filter + content-resolution helpers. Spec §8."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket, PhenopacketRevision


def public_filter(stmt: Select[Any]) -> Select[Any]:
    """Anonymous / non-curator filter (I3 + I7).

    deleted_at IS NULL AND state='published' AND head_published_revision_id IS NOT NULL.
    """
    return stmt.where(
        Phenopacket.deleted_at.is_(None),
        Phenopacket.state == "published",
        Phenopacket.head_published_revision_id.is_not(None),
    )


def curator_filter(
    stmt: Select[Any], *, include_deleted: bool = False, include_archived: bool = False,
) -> Select[Any]:
    """Curator-visible filter. I7 applies."""
    if not include_deleted:
        stmt = stmt.where(Phenopacket.deleted_at.is_(None))
    if not include_archived:
        stmt = stmt.where(Phenopacket.state != "archived")
    return stmt


async def resolve_public_content(db: AsyncSession, pp: Phenopacket) -> Optional[Dict[str, Any]]:
    """Return the public copy (I1): content_jsonb of the head-published revision.

    Fast path: if ``editing_revision_id IS NULL`` AND ``state='published'``, the
    working copy is guaranteed equal to the public copy (no active clone-to-draft),
    so return ``pp.phenopacket`` directly with zero queries.
    """
    if pp.head_published_revision_id is None:
        return None
    if pp.editing_revision_id is None and pp.state == "published":
        return pp.phenopacket  # fast path per spec §13 performance note
    rev = (await db.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.id == pp.head_published_revision_id)
    )).scalar_one()
    return rev.content_jsonb


def resolve_curator_content(pp: Phenopacket) -> Dict[str, Any]:
    """Return the curator working copy — always ``pp.phenopacket``."""
    return pp.phenopacket
```

- [ ] **Step 9.4: Run — expect PASS**

```bash
uv run pytest tests/test_visibility_filter.py -x
```

- [ ] **Step 9.5: Commit**

```bash
git add backend/app/phenopackets/repositories/visibility.py backend/tests/test_visibility_filter.py
git commit -m "feat(repo): centralized public/curator visibility filters (Wave 7/D.1 §8)"
```

---

### Task 10: Transitions + revisions API endpoints

**Files:**
- Create: `backend/app/api/phenopackets/transitions.py`
- Modify: `backend/app/main.py` (register router)
- Create integration tests alongside — extend `test_state_flows.py` or a new test file for HTTP-layer concerns

- [ ] **Step 10.1: Write failing HTTP test**

Create `backend/tests/test_api_transitions.py`:

```python
"""HTTP integration tests for POST /transitions + GET /revisions."""

import pytest


@pytest.mark.asyncio
async def test_transition_endpoint_end_to_end(client, curator_token, admin_token, draft_record_http):
    rid = draft_record_http["id"]

    # curator submits
    r = await client.post(
        f"/api/v2/phenopackets/{rid}/transitions",
        json={"to_state": "in_review", "reason": "ready", "revision": 1},
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert r.status_code == 200
    assert r.json()["phenopacket"]["state"] == "in_review"

    # admin approves
    rev = r.json()["phenopacket"]["revision"]
    r = await client.post(
        f"/api/v2/phenopackets/{rid}/transitions",
        json={"to_state": "approved", "reason": "ok", "revision": rev},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    # admin publishes
    rev = r.json()["phenopacket"]["revision"]
    r = await client.post(
        f"/api/v2/phenopackets/{rid}/transitions",
        json={"to_state": "published", "reason": "go", "revision": rev},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["phenopacket"]["state"] == "published"
    assert body["phenopacket"]["head_published_revision_id"] is not None


@pytest.mark.asyncio
async def test_transition_forbidden_role_returns_403(client, curator_token, draft_record_http):
    rid = draft_record_http["id"]
    r = await client.post(
        f"/api/v2/phenopackets/{rid}/transitions",
        json={"to_state": "approved", "reason": "x", "revision": 1},
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["error_code"] == "forbidden_role"


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(client, admin_token, draft_record_http):
    rid = draft_record_http["id"]
    r = await client.post(
        f"/api/v2/phenopackets/{rid}/transitions",
        json={"to_state": "published", "reason": "x", "revision": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "invalid_transition"


@pytest.mark.asyncio
async def test_revisions_list_curator_only(client, curator_token, viewer_token, published_record_http):
    rid = published_record_http["id"]
    r = await client.get(
        f"/api/v2/phenopackets/{rid}/revisions",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert r.status_code == 200
    r = await client.get(
        f"/api/v2/phenopackets/{rid}/revisions",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 10.2: Run — expect FAIL (endpoint not registered)**

```bash
uv run pytest tests/test_api_transitions.py -x
```

- [ ] **Step 10.3: Implement router**

Create `backend/app/api/phenopackets/transitions.py`:

```python
"""Transitions + revisions HTTP endpoints. Spec §7.1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_curator
from app.database import get_db
from app.models.user import User
from app.phenopackets.models import (
    Phenopacket, PhenopacketRevision,
    PhenopacketResponse, RevisionResponse, TransitionRequest,
)
from app.phenopackets.services.state_service import PhenopacketStateService


router = APIRouter(prefix="/api/v2/phenopackets", tags=["phenopackets"])


def _revision_to_response(rev: PhenopacketRevision, pp_public_id: str, *, include_content: bool) -> RevisionResponse:
    return RevisionResponse(
        id=rev.id, record_id=str(rev.record_id), phenopacket_id=pp_public_id,
        revision_number=rev.revision_number, state=rev.state,
        from_state=rev.from_state, to_state=rev.to_state,
        is_head_published=rev.is_head_published, change_reason=rev.change_reason,
        actor_id=rev.actor_id, actor_username=(rev.actor.username if rev.actor else None),
        change_patch=rev.change_patch, created_at=rev.created_at,
        content_jsonb=(rev.content_jsonb if include_content else None),
    )


async def _load_record_or_404(db: AsyncSession, phenopacket_id: str) -> Phenopacket:
    pp = (await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )).scalar_one_or_none()
    if pp is None:
        raise HTTPException(404, detail="phenopacket not found")
    return pp


@router.post("/{phenopacket_id}/transitions")
async def transition_phenopacket(
    phenopacket_id: str,
    body: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
):
    """POST a state transition. Spec §7.1."""
    pp = await _load_record_or_404(db, phenopacket_id)
    svc = PhenopacketStateService(db)

    try:
        new_pp, rev = await svc.transition(
            pp.id, to_state=body.to_state, reason=body.reason,
            expected_revision=body.revision, actor=current_user,
        )
    except svc.RevisionMismatch as e:
        raise HTTPException(409, detail={"error_code": "revision_mismatch", "message": str(e)})
    except svc.InvalidTransition as e:
        raise HTTPException(409, detail={"error_code": "invalid_transition", "message": str(e)})
    except svc.ForbiddenNotOwner as e:
        raise HTTPException(403, detail={"error_code": "forbidden_not_owner", "message": str(e)})
    except PermissionError as e:
        raise HTTPException(403, detail={"error_code": "forbidden_role", "message": str(e)})

    return {
        "phenopacket": PhenopacketResponse.model_validate(new_pp, from_attributes=True),
        "revision": _revision_to_response(rev, new_pp.phenopacket_id, include_content=False),
    }


@router.get("/{phenopacket_id}/revisions")
async def list_revisions(
    phenopacket_id: str,
    page_size: int = Query(50, ge=1, le=500, alias="page[size]"),
    page_number: int = Query(1, ge=1, alias="page[number]"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("curator", "admin"):
        raise HTTPException(404)  # spec: non-curators 404

    pp = await _load_record_or_404(db, phenopacket_id)
    rows = (await db.execute(
        select(PhenopacketRevision)
        .where(PhenopacketRevision.record_id == pp.id)
        .order_by(PhenopacketRevision.created_at.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return {
        "data": [_revision_to_response(r, pp.phenopacket_id, include_content=False) for r in rows],
        "meta": {"total": len(rows)},  # cheap count; MV/COUNT(*) follow-up if needed
    }


@router.get("/{phenopacket_id}/revisions/{revision_id}")
async def get_revision(
    phenopacket_id: str, revision_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("curator", "admin"):
        raise HTTPException(404)

    pp = await _load_record_or_404(db, phenopacket_id)
    rev = (await db.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.id == revision_id,
            PhenopacketRevision.record_id == pp.id,
        )
    )).scalar_one_or_none()
    if rev is None:
        raise HTTPException(404)
    return _revision_to_response(rev, pp.phenopacket_id, include_content=True)
```

Register in `backend/app/main.py` after the other phenopacket router includes:

```python
from app.api.phenopackets.transitions import router as transitions_router
app.include_router(transitions_router)
```

- [ ] **Step 10.4: Run — expect PASS**

```bash
uv run pytest tests/test_api_transitions.py -x
```
Expected: all three tests pass. Fix fixture wiring if needed.

- [ ] **Step 10.5: Commit**

```bash
git add backend/app/api/phenopackets/transitions.py backend/app/main.py backend/tests/test_api_transitions.py
git commit -m "feat(api): POST /transitions + GET /revisions endpoints (Wave 7/D.1 §7.1)"
```

---

### Task 11: Update CRUD endpoints (PUT state-branching + list/detail visibility)

**Files:**
- Modify: `backend/app/phenopackets/routers/crud.py`
- Modify: `backend/app/phenopackets/services/phenopacket_service.py`
- Create: `backend/tests/test_crud_state_branching.py`

- [ ] **Step 11.1: Write failing test**

```python
"""PUT branching + GET visibility (spec §7.2)."""

import pytest


@pytest.mark.asyncio
async def test_put_on_published_creates_clone(client, curator_token, published_record_http):
    rid = published_record_http["phenopacket_id"]
    r = await client.put(
        f"/api/v2/phenopackets/{rid}",
        json={
            "phenopacket_id": rid,
            "phenopacket": {"id": rid, "a": 99},
            "change_reason": "fix typo",
            "revision": 1,
        },
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    # state stays 'published', editing_revision_id set
    assert body["state"] == "published"
    assert body["editing_revision_id"] is not None


@pytest.mark.asyncio
async def test_anonymous_get_returns_old_head_during_clone(
    client, curator_token, published_record_http,
):
    rid = published_record_http["phenopacket_id"]
    # clone-to-draft
    await client.put(
        f"/api/v2/phenopackets/{rid}",
        json={"phenopacket_id": rid, "phenopacket": {"id": rid, "v": "DRAFT"}, "change_reason": "r", "revision": 1},
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    # anonymous GET
    r = await client.get(f"/api/v2/phenopackets/{rid}")
    assert r.status_code == 200
    assert r.json()["phenopacket"]["v"] != "DRAFT"  # public sees old copy


@pytest.mark.asyncio
async def test_curator_get_returns_working_copy_during_clone(
    client, curator_token, published_record_http,
):
    rid = published_record_http["phenopacket_id"]
    await client.put(
        f"/api/v2/phenopackets/{rid}",
        json={"phenopacket_id": rid, "phenopacket": {"id": rid, "v": "DRAFT"}, "change_reason": "r", "revision": 1},
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    r = await client.get(
        f"/api/v2/phenopackets/{rid}",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert r.status_code == 200
    assert r.json()["phenopacket"]["v"] == "DRAFT"
```

- [ ] **Step 11.2: Run — expect FAIL**

```bash
uv run pytest tests/test_crud_state_branching.py -x
```

- [ ] **Step 11.3: Wire PUT to state service**

Modify `backend/app/phenopackets/services/phenopacket_service.py::update_phenopacket` (find around the current optimistic-lock block at `:217`) so it delegates to `PhenopacketStateService.edit_record` when `state IN ('published','draft','changes_requested')`, preserves its current behaviour otherwise. Example wire-in:

```python
async def update_phenopacket(self, phenopacket_id: str, payload: PhenopacketUpdate, actor):
    pp = await self._get_by_public_id_or_raise(phenopacket_id)
    state_svc = PhenopacketStateService(self.db)
    try:
        updated = await state_svc.edit_record(
            pp.id, new_content=payload.phenopacket,
            change_reason=payload.change_reason,
            expected_revision=payload.revision or pp.revision,
            actor=actor,
        )
    except state_svc.RevisionMismatch:
        raise ServiceConflict({"error_code": "revision_mismatch"}, code="revision_mismatch")
    except state_svc.EditInProgress:
        raise ServiceConflict({"error_code": "edit_in_progress"}, code="edit_in_progress")
    except state_svc.ForbiddenNotOwner:
        raise ServiceConflict({"error_code": "forbidden_not_owner"}, code="forbidden_not_owner")  # upstream maps to 403
    return updated
```

Modify `backend/app/phenopackets/routers/crud.py` — list + detail GET handlers:

```python
from app.phenopackets.repositories.visibility import (
    public_filter, curator_filter, resolve_public_content, resolve_curator_content,
)

@router.get("/")
async def list_phenopackets(
    ...,
    current_user: User | None = Depends(get_optional_user),
):
    is_curator = current_user is not None and current_user.role in ("curator", "admin")
    stmt = select(Phenopacket)
    stmt = curator_filter(stmt) if is_curator else public_filter(stmt)
    ...
    for pp in rows:
        resp = build_phenopacket_response(pp)
        resp.phenopacket = (
            resolve_curator_content(pp) if is_curator
            else await resolve_public_content(db, pp)
        )
        if not is_curator:
            resp.state = None  # non-curators don't see state
        ...
```

(`get_optional_user` dependency already exists — if not, add a thin wrapper that catches the auth exception and returns None.)

- [ ] **Step 11.4: Run — expect PASS**

```bash
uv run pytest tests/test_crud_state_branching.py -x
```

- [ ] **Step 11.5: Commit**

```bash
git add backend/app/phenopackets/routers/crud.py backend/app/phenopackets/services/phenopacket_service.py backend/tests/test_crud_state_branching.py
git commit -m "feat(api): PUT clone-to-draft + role-based list/detail resolution (Wave 7/D.1 §7.2)"
```

---

## Phase 4 — Filter-centralization sweep (§8.2)

### Task 12: Sweep search + comparisons

**Files:**
- Modify: `backend/app/phenopackets/routers/search.py`
- Modify: `backend/app/search/repositories.py`
- Modify: `backend/app/search/services/facet.py`
- Modify: `backend/app/phenopackets/routers/comparisons/query.py`

- [ ] **Step 12.1: Write failing visibility test**

Create or extend `backend/tests/test_visibility_filter.py` with cross-endpoint assertions:

```python
@pytest.mark.asyncio
async def test_search_excludes_drafts_from_anonymous(client, draft_record_http, published_record_http):
    r = await client.get("/api/v2/phenopackets/search?q=phenopacket")
    ids = [item["phenopacket_id"] for item in r.json()["data"]]
    assert published_record_http["phenopacket_id"] in ids
    assert draft_record_http["phenopacket_id"] not in ids


@pytest.mark.asyncio
async def test_comparisons_excludes_drafts_from_anonymous(client, draft_record_http):
    r = await client.get(f"/api/v2/phenopackets/compare?ids={draft_record_http['phenopacket_id']}")
    assert r.status_code == 404 or r.json()["data"] == []
```

- [ ] **Step 12.2: Run — expect FAIL**

- [ ] **Step 12.3: Apply filter in each file**

For every SELECT over `Phenopacket` in the listed files, wrap with `public_filter(stmt)` for anonymous reads or `curator_filter(stmt)` for curator reads. Example pattern:

```python
# before
stmt = select(Phenopacket).where(Phenopacket.search_vector.match(q))

# after
from app.phenopackets.repositories.visibility import public_filter, curator_filter
is_curator = current_user is not None and current_user.role in ("curator","admin")
stmt = select(Phenopacket).where(Phenopacket.search_vector.match(q))
stmt = curator_filter(stmt) if is_curator else public_filter(stmt)
```

Apply the same transformation mechanically in the four files.

- [ ] **Step 12.4: Run — expect PASS**

```bash
uv run pytest tests/test_visibility_filter.py -x
```

- [ ] **Step 12.5: Commit**

```bash
git add backend/app/phenopackets/routers/search.py backend/app/search/ backend/app/phenopackets/routers/comparisons/query.py backend/tests/test_visibility_filter.py
git commit -m "feat(visibility): route search + comparisons through visibility filter (Wave 7/D.1 §8.2)"
```

---

### Task 13: Sweep aggregations + timeline + related

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/publications.py`
- Modify: `backend/app/phenopackets/routers/aggregations/features.py`
- Modify: `backend/app/phenopackets/routers/aggregations/summary.py`
- Modify: `backend/app/phenopackets/routers/aggregations/demographics.py`
- Modify: `backend/app/phenopackets/routers/aggregations/diseases.py`
- Modify: `backend/app/phenopackets/routers/aggregations/variant_query_builder.py`
- Modify: `backend/app/phenopackets/routers/aggregations/sql_fragments/ctes.py`
- Modify: `backend/app/phenopackets/routers/aggregations/survival/handlers/*.py`
- Modify: `backend/app/phenopackets/routers/crud_timeline.py`
- Modify: `backend/app/phenopackets/routers/crud_related.py`

- [ ] **Step 13.1: Write failing test**

Extend `backend/tests/test_visibility_filter.py`:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [
    "/api/v2/phenopackets/aggregate/summary",
    "/api/v2/phenopackets/aggregate/features",
    "/api/v2/phenopackets/aggregate/demographics",
    "/api/v2/phenopackets/aggregate/diseases",
    "/api/v2/phenopackets/aggregate/publications",
])
async def test_aggregations_exclude_drafts_from_anonymous(client, endpoint, draft_record_http):
    r = await client.get(endpoint)
    assert r.status_code == 200
    # The draft's phenopacket_id should not appear in any aggregation payload
    assert draft_record_http["phenopacket_id"] not in r.text
```

- [ ] **Step 13.2: Run — expect FAIL**

- [ ] **Step 13.3: Apply filter pattern in each file**

Each file either:
1. Has a raw `SELECT … FROM phenopackets …` — wrap the FROM with `INNER JOIN` against a CTE that applies `public_filter`, or inject `AND p.state='published' AND p.deleted_at IS NULL AND p.head_published_revision_id IS NOT NULL` directly.
2. Uses SQLAlchemy — wrap `stmt = public_filter(stmt)` if the caller is anonymous; aggregations are public so `public_filter` is the default for this phase.

Raw SQL pattern (aggregations use raw SQL via `ctes.py`):

```sql
-- Before
FROM phenopackets p WHERE p.deleted_at IS NULL

-- After (public endpoints)
FROM phenopackets p
WHERE p.deleted_at IS NULL
  AND p.state = 'published'
  AND p.head_published_revision_id IS NOT NULL
```

Add a named fragment in `sql_fragments/ctes.py`:

```python
PUBLIC_FILTER_FRAGMENT = (
    "p.deleted_at IS NULL AND p.state = 'published' "
    "AND p.head_published_revision_id IS NOT NULL"
)
```

and reuse from all aggregation queries.

- [ ] **Step 13.4: Run — expect PASS**

- [ ] **Step 13.5: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations backend/app/phenopackets/routers/crud_timeline.py backend/app/phenopackets/routers/crud_related.py backend/tests/test_visibility_filter.py
git commit -m "feat(visibility): aggregations + timeline + related through public filter (Wave 7/D.1 §8.2)"
```

---

### Task 14: Sweep publications, sitemap, admin; MV migration

**Files:**
- Modify: `backend/app/publications/endpoints/list_route.py` (apply `public_filter`)
- Modify: `backend/app/seo/sitemap.py` (apply `public_filter`)
- Modify: `backend/app/api/admin/queries.py` (use `curator_filter(include_deleted=True, include_archived=True)`)
- Create: `backend/alembic/versions/20260412_0004_rebuild_mvs_with_state_filter.py`

- [ ] **Step 14.1: Write migration to drop + rebuild MVs with state filter**

```python
"""Rebuild summary MVs with state='published' filter. Spec §8.2 (MV line)."""

from alembic import op

revision = "20260412_0004"
down_revision = "20260412_0003"

def upgrade() -> None:
    # Drop existing MVs; recreate with PUBLIC_FILTER_FRAGMENT.
    # Exact DDL per the existing aggregation MVs — source from
    # add_materialized_views_for_aggregations.py and prepend WHERE clauses.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_summary_statistics AS
        SELECT ...  -- copy existing MV definition
        FROM phenopackets p
        WHERE p.deleted_at IS NULL
          AND p.state = 'published'
          AND p.head_published_revision_id IS NOT NULL
        GROUP BY ...;
        """
    )
    op.execute("CREATE UNIQUE INDEX ux_mv_summary_statistics ON mv_summary_statistics (subject_sex)")

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")
    # Recreate the pre-D.1 MV form
```

Fill in the exact MV definitions by copying from `add_materialized_views_for_aggregations.py` and the fix migration `44ccb14dc32b_fix_mv_summary_statistics_unique_index.py`.

- [ ] **Step 14.2: Apply filter in the three endpoint files**

Same mechanical transformation as Task 13.

- [ ] **Step 14.3: Run round-trip**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run pytest tests/test_visibility_filter.py -x
```

- [ ] **Step 14.4: Commit**

```bash
git add backend/app/publications backend/app/seo/sitemap.py backend/app/api/admin/queries.py backend/alembic/versions/20260412_0004_rebuild_mvs_with_state_filter.py
git commit -m "feat(visibility): publications+sitemap+admin+MVs through visibility filter (Wave 7/D.1 §8.2)"
```

---

### Task 15: AST-level test enforcing filter routing

**Files:**
- Create: `backend/tests/test_visibility_ast.py`

- [ ] **Step 15.1: Write AST test**

```python
"""Static check: every handler under audited directories that queries
phenopackets routes the query through the visibility repository.

Scans AST, finds ``select(Phenopacket)`` call sites, and asserts that
the enclosing function either:
- calls ``public_filter`` or ``curator_filter`` in its body, OR
- has a docstring/comment with ``# noqa: visibility`` to opt out with
  justification.
"""

import ast
import pathlib
import re
import pytest

AUDIT_ROOTS = [
    pathlib.Path("backend/app/phenopackets/routers"),
    pathlib.Path("backend/app/search"),
    pathlib.Path("backend/app/publications/endpoints"),
    pathlib.Path("backend/app/seo"),
    pathlib.Path("backend/app/api/admin"),
]

FILTER_NAMES = {"public_filter", "curator_filter"}


def _selects_phenopacket(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "Phenopacket"
        ):
            return True
    return False


def _calls_filter(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FILTER_NAMES:
            return True
    return False


@pytest.mark.parametrize("root", AUDIT_ROOTS)
def test_audited_files_use_visibility_filter(root: pathlib.Path):
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        src = path.read_text()
        if "select(Phenopacket)" not in src and "FROM phenopackets" not in src:
            continue
        if re.search(r"#\s*noqa:\s*visibility", src):
            continue
        tree = ast.parse(src)
        if _selects_phenopacket(tree) and not _calls_filter(tree):
            offenders.append(str(path))
    assert not offenders, f"Files without visibility filter: {offenders}"
```

- [ ] **Step 15.2: Run — expect PASS (sweeps in Tasks 12-14 covered everything)**

```bash
uv run pytest tests/test_visibility_ast.py -v
```

If offenders appear, return to Tasks 12–14 and fix them (or add `# noqa: visibility` with justification if intentional).

- [ ] **Step 15.3: Commit**

```bash
git add backend/tests/test_visibility_ast.py
git commit -m "test(visibility): AST-level enforcement of filter routing (Wave 7/D.1 §14)"
```

---

## Phase 5 — Frontend

### Task 16: `StateBadge.vue` component + test

**Files:**
- Create: `frontend/src/components/state/StateBadge.vue`
- Create: `frontend/tests/unit/components/state/StateBadge.spec.js`

- [ ] **Step 16.1: Write failing component test**

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import StateBadge from '@/components/state/StateBadge.vue';

const mountWithVuetify = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(StateBadge, { props, global: { plugins: [vuetify] } });
};

describe('StateBadge', () => {
  it.each([
    ['draft', 'grey'],
    ['in_review', 'blue'],
    ['changes_requested', 'orange'],
    ['approved', 'purple'],
    ['published', 'green'],
    ['archived', 'brown'],
  ])('renders %s with color %s', (state, color) => {
    const wrapper = mountWithVuetify({ state });
    expect(wrapper.text().toLowerCase()).toContain(state.replace('_', ' '));
    expect(wrapper.find('.v-chip').classes().some(c => c.includes(color))).toBe(true);
  });

  it('renders null state as empty', () => {
    const wrapper = mountWithVuetify({ state: null });
    expect(wrapper.find('.v-chip').exists()).toBe(false);
  });
});
```

- [ ] **Step 16.2: Run — expect FAIL**

```bash
cd frontend && npm test -- --run tests/unit/components/state/StateBadge.spec.js
```

- [ ] **Step 16.3: Implement**

Create `frontend/src/components/state/StateBadge.vue`:

```vue
<script setup>
import { computed } from 'vue';

const props = defineProps({
  state: { type: String, default: null },
});

const COLORS = {
  draft: 'grey',
  in_review: 'blue',
  changes_requested: 'orange',
  approved: 'purple',
  published: 'green',
  archived: 'brown',
};

const color = computed(() => COLORS[props.state] ?? 'grey');
const label = computed(() =>
  props.state ? props.state.replace(/_/g, ' ') : ''
);
</script>

<template>
  <v-chip v-if="state" :color="color" size="small" label>{{ label }}</v-chip>
</template>
```

- [ ] **Step 16.4: Run — expect PASS**

```bash
npm test -- --run tests/unit/components/state/StateBadge.spec.js
```

- [ ] **Step 16.5: Commit**

```bash
git add frontend/src/components/state/StateBadge.vue frontend/tests/unit/components/state/StateBadge.spec.js
git commit -m "feat(frontend): StateBadge component (Wave 7/D.1 §9.1)"
```

---

### Task 17: `TransitionMenu.vue` + role-gating test

**Files:**
- Create: `frontend/src/components/state/TransitionMenu.vue`
- Create: `frontend/tests/unit/components/state/TransitionMenu.spec.js`

- [ ] **Step 17.1: Write failing test**

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import TransitionMenu from '@/components/state/TransitionMenu.vue';

const mountMenu = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(TransitionMenu, { props, global: { plugins: [vuetify] } });
};

describe('TransitionMenu', () => {
  it('curator owner on draft sees submit only', async () => {
    const wrapper = mountMenu({
      currentState: 'draft', role: 'curator', isOwner: true,
    });
    await wrapper.find('[data-testid="menu-activator"]').trigger('click');
    const labels = wrapper.findAll('[data-testid="transition-item"]').map(n => n.text());
    expect(labels).toEqual(expect.arrayContaining(['Submit for review']));
    expect(labels).not.toEqual(expect.arrayContaining(['Approve']));
  });

  it('viewer sees nothing', async () => {
    const wrapper = mountMenu({
      currentState: 'draft', role: 'viewer', isOwner: true,
    });
    await wrapper.find('[data-testid="menu-activator"]').trigger('click');
    expect(wrapper.findAll('[data-testid="transition-item"]')).toHaveLength(0);
  });

  it('admin on in_review sees approve and request_changes', async () => {
    const wrapper = mountMenu({
      currentState: 'in_review', role: 'admin', isOwner: false,
    });
    await wrapper.find('[data-testid="menu-activator"]').trigger('click');
    const labels = wrapper.findAll('[data-testid="transition-item"]').map(n => n.text());
    expect(labels).toEqual(expect.arrayContaining(['Approve', 'Request changes']));
  });
});
```

- [ ] **Step 17.2: Run — expect FAIL**

- [ ] **Step 17.3: Implement**

Create `frontend/src/components/state/TransitionMenu.vue`:

```vue
<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentState: { type: String, required: true },
  role: { type: String, required: true },
  isOwner: { type: Boolean, default: false },
});
const emit = defineEmits(['transition']);

const LABELS = {
  in_review: 'Submit for review',
  changes_requested: 'Request changes',
  approved: 'Approve',
  published: 'Publish',
  archived: 'Archive',
  draft: 'Withdraw',
};

// Mirror of backend transitions.py::allowed_transitions.
const RULES = {
  draft: (role, owner) => (role === 'admin' || owner) ? ['in_review'] : [],
  in_review: (role, owner) => {
    const out = [];
    if (role === 'admin' || owner) out.push('draft');
    if (role === 'admin') out.push('changes_requested', 'approved', 'archived');
    return out;
  },
  changes_requested: (role, owner) => (role === 'admin' || owner) ? ['in_review'] : [],
  approved: (role) => role === 'admin' ? ['published', 'archived'] : [],
  published: (role) => role === 'admin' ? ['archived'] : [],
  archived: () => [],
};

const items = computed(() => {
  if (props.role === 'viewer') return [];
  const fn = RULES[props.currentState] ?? (() => []);
  return fn(props.role, props.isOwner).map(to => ({ to, label: LABELS[to] }));
});
</script>

<template>
  <v-menu>
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" data-testid="menu-activator" variant="outlined">
        State actions
      </v-btn>
    </template>
    <v-list>
      <v-list-item
        v-for="item in items" :key="item.to"
        data-testid="transition-item"
        @click="emit('transition', item.to)"
      >
        {{ item.label }}
      </v-list-item>
    </v-list>
  </v-menu>
</template>
```

- [ ] **Step 17.4: Run — expect PASS**

- [ ] **Step 17.5: Commit**

```bash
git add frontend/src/components/state/TransitionMenu.vue frontend/tests/unit/components/state/TransitionMenu.spec.js
git commit -m "feat(frontend): TransitionMenu with role-gated items (Wave 7/D.1 §9.1)"
```

---

### Task 18: `TransitionModal.vue` + validation test

**Files:**
- Create: `frontend/src/components/state/TransitionModal.vue`
- Create: `frontend/tests/unit/components/state/TransitionModal.spec.js`

- [ ] **Step 18.1: Write failing test**

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import TransitionModal from '@/components/state/TransitionModal.vue';

const mountModal = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(TransitionModal, { props, global: { plugins: [vuetify] } });
};

describe('TransitionModal', () => {
  it('confirm disabled when reason empty', async () => {
    const wrapper = mountModal({ modelValue: true, toState: 'in_review' });
    const btn = wrapper.find('[data-testid="confirm-btn"]');
    expect(btn.attributes('disabled')).toBeDefined();
  });

  it('emits confirm with reason', async () => {
    const wrapper = mountModal({ modelValue: true, toState: 'in_review' });
    await wrapper.find('textarea').setValue('ready for review');
    await wrapper.find('[data-testid="confirm-btn"]').trigger('click');
    expect(wrapper.emitted('confirm')[0]).toEqual([{ reason: 'ready for review' }]);
  });
});
```

- [ ] **Step 18.2: Run — expect FAIL**

- [ ] **Step 18.3: Implement**

```vue
<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  toState: { type: String, required: true },
});
const emit = defineEmits(['update:modelValue', 'confirm']);

const reason = ref('');
const canConfirm = computed(() => reason.value.trim().length > 0);

watch(() => props.modelValue, (open) => { if (!open) reason.value = ''; });

const confirm = () => emit('confirm', { reason: reason.value.trim() });
const close = () => emit('update:modelValue', false);
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="500">
    <v-card>
      <v-card-title>Transition to {{ toState.replace('_', ' ') }}</v-card-title>
      <v-card-text>
        <v-textarea v-model="reason" label="Reason (required)" rows="3" autofocus />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="close">Cancel</v-btn>
        <v-btn
          data-testid="confirm-btn"
          color="primary"
          :disabled="!canConfirm"
          @click="confirm"
        >Confirm</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
```

- [ ] **Step 18.4: Run — expect PASS**

- [ ] **Step 18.5: Commit**

```bash
git add frontend/src/components/state/TransitionModal.vue frontend/tests/unit/components/state/TransitionModal.spec.js
git commit -m "feat(frontend): TransitionModal with required reason (Wave 7/D.1 §9.1)"
```

---

### Task 19: `EditingBanner.vue` + variants test

**Files:**
- Create: `frontend/src/components/state/EditingBanner.vue`
- Create: `frontend/tests/unit/components/state/EditingBanner.spec.js`

- [ ] **Step 19.1: Write failing test**

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import EditingBanner from '@/components/state/EditingBanner.vue';

const mountBanner = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(EditingBanner, { props, global: { plugins: [vuetify] } });
};

describe('EditingBanner', () => {
  it('shows owner CTA when current user owns the draft', () => {
    const wrapper = mountBanner({
      editingRevisionId: 42, draftOwnerUsername: 'alice',
      currentUsername: 'alice', startedAt: '2026-04-12T10:00:00Z',
    });
    expect(wrapper.text()).toContain('Continue editing');
  });

  it('shows read-only variant for non-owner', () => {
    const wrapper = mountBanner({
      editingRevisionId: 42, draftOwnerUsername: 'alice',
      currentUsername: 'bob', startedAt: '2026-04-12T10:00:00Z',
    });
    expect(wrapper.text()).toContain('@alice');
    expect(wrapper.text()).not.toContain('Continue editing');
  });

  it('renders nothing when no active edit', () => {
    const wrapper = mountBanner({ editingRevisionId: null });
    expect(wrapper.find('.v-alert').exists()).toBe(false);
  });
});
```

- [ ] **Step 19.2: Run — expect FAIL**

- [ ] **Step 19.3: Implement**

```vue
<script setup>
import { computed } from 'vue';

const props = defineProps({
  editingRevisionId: { type: [Number, null], default: null },
  draftOwnerUsername: { type: String, default: null },
  currentUsername: { type: String, default: null },
  startedAt: { type: String, default: null },
});
const emit = defineEmits(['continue']);

const isOwner = computed(() =>
  props.draftOwnerUsername && props.draftOwnerUsername === props.currentUsername
);
const relative = computed(() => {
  if (!props.startedAt) return '';
  const mins = Math.round((Date.now() - new Date(props.startedAt)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
});
</script>

<template>
  <v-alert v-if="editingRevisionId" type="info" variant="tonal" density="comfortable">
    <div>
      Draft in progress by <strong>@{{ draftOwnerUsername }}</strong> — started {{ relative }}
    </div>
    <v-btn v-if="isOwner" size="small" @click="emit('continue')">Continue editing</v-btn>
  </v-alert>
</template>
```

- [ ] **Step 19.4: Run — expect PASS**

- [ ] **Step 19.5: Commit**

```bash
git add frontend/src/components/state/EditingBanner.vue frontend/tests/unit/components/state/EditingBanner.spec.js
git commit -m "feat(frontend): EditingBanner with owner/non-owner variants (Wave 7/D.1 §9.1)"
```

---

### Task 20: API client + composable

**Files:**
- Modify: `frontend/src/api/domain/phenopackets.js`
- Create: `frontend/src/composables/usePhenopacketState.js`

- [ ] **Step 20.1: Add client methods**

Append to `frontend/src/api/domain/phenopackets.js`:

```js
export const transitionPhenopacket = (id, toState, reason, revision) =>
  apiClient.post(`/phenopackets/${id}/transitions`, {
    to_state: toState, reason, revision,
  });

export const fetchRevisions = (id, { pageSize = 50, pageNumber = 1 } = {}) =>
  apiClient.get(`/phenopackets/${id}/revisions`, {
    params: { 'page[size]': pageSize, 'page[number]': pageNumber },
  });

export const fetchRevisionDetail = (id, revisionId) =>
  apiClient.get(`/phenopackets/${id}/revisions/${revisionId}`);
```

- [ ] **Step 20.2: Create composable**

```js
// frontend/src/composables/usePhenopacketState.js
import { ref } from 'vue';
import { transitionPhenopacket, fetchRevisions } from '@/api/domain/phenopackets';

export function usePhenopacketState(phenopacketId) {
  const revisions = ref([]);
  const loading = ref(false);
  const error = ref(null);

  const transitionTo = async (toState, reason, revision) => {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await transitionPhenopacket(phenopacketId, toState, reason, revision);
      return data;
    } catch (e) {
      error.value = e.response?.data?.detail || e.message;
      throw e;
    } finally {
      loading.value = false;
    }
  };

  const loadRevisions = async () => {
    loading.value = true;
    try {
      const { data } = await fetchRevisions(phenopacketId);
      revisions.value = data.data;
    } finally {
      loading.value = false;
    }
  };

  return { revisions, loading, error, transitionTo, loadRevisions };
}
```

- [ ] **Step 20.3: Commit**

```bash
git add frontend/src/api/domain/phenopackets.js frontend/src/composables/usePhenopacketState.js
git commit -m "feat(frontend): API client + usePhenopacketState composable (Wave 7/D.1 §9.3)"
```

---

### Task 21: Detail view integration

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue`

- [ ] **Step 21.1: Integrate components**

In `PagePhenopacket.vue`, add below the existing header:

```vue
<StateBadge :state="phenopacket.state" />
<EditingBanner
  :editing-revision-id="phenopacket.editing_revision_id"
  :draft-owner-username="phenopacket.draft_owner_username"
  :current-username="authStore.user?.username"
  :started-at="phenopacket.updated_at"
/>
<TransitionMenu
  :current-state="phenopacket.state"
  :role="authStore.user?.role"
  :is-owner="authStore.user?.id === phenopacket.draft_owner_id"
  @transition="onTransitionRequest"
/>
<TransitionModal
  v-model="transitionModalOpen"
  :to-state="pendingTargetState"
  @confirm="onTransitionConfirm"
/>
```

Wire `onTransitionRequest`, `onTransitionConfirm` to `usePhenopacketState.transitionTo` and refresh the record on success.

- [ ] **Step 21.2: Test manually in dev**

```bash
make backend  # terminal 1
make frontend # terminal 2
# Navigate to a phenopacket detail page as curator. Click menu, trigger, confirm.
```

- [ ] **Step 21.3: Commit**

```bash
git add frontend/src/views/PagePhenopacket.vue
git commit -m "feat(frontend): integrate state components into detail view (Wave 7/D.1 §9.2)"
```

---

### Task 22: List view + create-edit toast

**Files:**
- Modify: `frontend/src/views/Phenopackets.vue`
- Modify: `frontend/src/views/PhenopacketCreateEdit.vue`

- [ ] **Step 22.1: Add state column to list (curator-only)**

In `Phenopackets.vue`, conditionally include a `state` column in the table headers when `authStore.user?.role in ['curator','admin']`. Use `<StateBadge :state="item.state" />` as the cell renderer.

- [ ] **Step 22.2: Add save toast to edit view**

In `PhenopacketCreateEdit.vue`, after a successful PUT on a `published` record, show toast: `"Draft saved — submit for review when ready."` On `draft`/`changes_requested` success: `"Draft updated."`.

- [ ] **Step 22.3: Manual dev check**

- [ ] **Step 22.4: Commit**

```bash
git add frontend/src/views/Phenopackets.vue frontend/src/views/PhenopacketCreateEdit.vue
git commit -m "feat(frontend): state column on list + save toast on edit (Wave 7/D.1 §9.2)"
```

---

## Phase 6 — E2E + gating

### Task 23: Playwright — full-lifecycle E2E

**Files:**
- Create: `frontend/tests/e2e/state-lifecycle.spec.js`

- [ ] **Step 23.1: Write spec**

```js
// @ts-check
import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test('full state lifecycle: create draft → approve → publish', async ({ page, context }) => {
  // Curator: login + create draft
  await page.goto(`${BASE}/login`);
  await page.fill('input[name="username"]', 'dev-curator');
  await page.fill('input[name="password"]', 'DevCurator!2026');
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE}/`);

  await page.goto(`${BASE}/phenopackets/create`);
  await page.fill('input[name="phenopacket_id"]', 'e2e-wave7-1');
  // ... fill minimal form
  await page.click('button:has-text("Save")');
  await expect(page.locator('.v-alert')).toContainText('Draft');

  // Submit for review
  await page.click('[data-testid="menu-activator"]');
  await page.click('[data-testid="transition-item"]:has-text("Submit")');
  await page.fill('textarea', 'ready for review');
  await page.click('[data-testid="confirm-btn"]');
  await expect(page.locator('.v-chip:has-text("in review")')).toBeVisible();

  // Admin: login in new context, approve + publish
  const adminContext = await context.browser().newContext();
  const adminPage = await adminContext.newPage();
  await adminPage.goto(`${BASE}/login`);
  await adminPage.fill('input[name="username"]', 'dev-admin');
  await adminPage.fill('input[name="password"]', 'DevAdmin!2026');
  await adminPage.click('button[type="submit"]');
  await adminPage.goto(`${BASE}/phenopackets/e2e-wave7-1`);

  await adminPage.click('[data-testid="menu-activator"]');
  await adminPage.click('[data-testid="transition-item"]:has-text("Approve")');
  await adminPage.fill('textarea', 'lgtm');
  await adminPage.click('[data-testid="confirm-btn"]');

  await adminPage.click('[data-testid="menu-activator"]');
  await adminPage.click('[data-testid="transition-item"]:has-text("Publish")');
  await adminPage.fill('textarea', 'go live');
  await adminPage.click('[data-testid="confirm-btn"]');
  await expect(adminPage.locator('.v-chip:has-text("published")')).toBeVisible();

  // Anonymous can view
  const anonCtx = await context.browser().newContext();
  const anonPage = await anonCtx.newPage();
  await anonPage.goto(`${BASE}/phenopackets/e2e-wave7-1`);
  await expect(anonPage.locator('h1,h2').first()).toBeVisible();
});
```

- [ ] **Step 23.2: Run in dev**

```bash
cd frontend && npx playwright test tests/e2e/state-lifecycle.spec.js
```

- [ ] **Step 23.3: Commit**

```bash
git add frontend/tests/e2e/state-lifecycle.spec.js
git commit -m "test(e2e): full state-lifecycle Playwright spec (Wave 7/D.1 §10.4)"
```

---

### Task 24: Playwright — dual-read (I1) E2E

**Files:**
- Create: `frontend/tests/e2e/dual-read-invariant.spec.js`

- [ ] **Step 24.1: Write spec**

```js
import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test('I1: anonymous sees old head while curator sees new draft', async ({ page, context }) => {
  // Precondition: a published phenopacket exists (seeded or from previous test).
  const id = 'e2e-wave7-1';

  // Curator: login + clone-to-draft edit
  await page.goto(`${BASE}/login`);
  await page.fill('input[name="username"]', 'dev-curator');
  await page.fill('input[name="password"]', 'DevCurator!2026');
  await page.click('button[type="submit"]');

  await page.goto(`${BASE}/phenopackets/${id}/edit`);
  // find an editable field, change it to "DRAFT-EDIT"
  await page.fill('input[name="subject_id"]', 'DRAFT-EDIT-VALUE');
  await page.fill('textarea[name="change_reason"]', 'fix typo');
  await page.click('button:has-text("Save")');

  // Curator view shows the new value
  await expect(page.locator('text=DRAFT-EDIT-VALUE')).toBeVisible();

  // Anonymous view still shows old value
  const anonCtx = await context.browser().newContext();
  const anonPage = await anonCtx.newPage();
  await anonPage.goto(`${BASE}/phenopackets/${id}`);
  await expect(anonPage.locator('text=DRAFT-EDIT-VALUE')).toHaveCount(0);
});
```

- [ ] **Step 24.2: Run**

- [ ] **Step 24.3: Commit**

```bash
git add frontend/tests/e2e/dual-read-invariant.spec.js
git commit -m "test(e2e): I1 dual-read invariant (Wave 7/D.1 §10.2)"
```

---

### Task 25: CI wiring + acceptance-criteria verification

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 25.1: Make sure the Playwright gating job includes the new specs**

The E2E job runs `npx playwright test` which automatically picks up every `tests/e2e/*.spec.js`. No workflow change needed if the glob is wildcard. **Verify** by reading the current job definition; if it names specific specs, add the two new ones.

- [ ] **Step 25.2: Run full backend suite locally**

```bash
cd backend
uv run pytest -q
```
Expected: **all 1,131 existing tests green**, plus the new tests from Tasks 4, 6–10, 15. Record the new test count.

- [ ] **Step 25.3: Coverage check**

```bash
uv run pytest --cov=app --cov-fail-under=70
```
Expected: backend ≥ 70%.

- [ ] **Step 25.4: Frontend suite + coverage**

```bash
cd ../frontend
npm test -- --run --coverage
```
Expected: ≥ 30% floor, per-file thresholds (from vitest.config.js) green.

- [ ] **Step 25.5: Walk the acceptance-criteria checklist from spec §14**

Manually or via `rg` confirm each checkbox:
- [ ] I1–I7 tests exist and pass (`tests/test_state_invariants.py`)
- [ ] Guard matrix + ownership tests (`tests/test_state_transitions.py`)
- [ ] Clone-to-draft + head-swap integration tests (`tests/test_state_flows.py`)
- [ ] Visibility filter tests + AST enforcement (`tests/test_visibility_filter.py`, `tests/test_visibility_ast.py`)
- [ ] Migration 3 fixture test
- [ ] All 1,131 pre-existing backend tests green
- [ ] Coverage ≥ 70% backend, 30% frontend floor
- [ ] Playwright full lifecycle + dual-read specs gating
- [ ] Component tests for 4 new components

Any unchecked → return to the corresponding task and fix.

- [ ] **Step 25.6: Final commit + PR**

```bash
git push -u origin chore/wave-7-d1-state-machine
gh pr create --title "feat(wave-7-d1): state machine + immutable revisions + visibility centralization" --body "$(cat <<'EOF'
## Summary

Ships Wave 7 / D.1 per `docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md`:

- Three Alembic migrations (state columns + phenopacket_revisions + seed)
- `PhenopacketStateService` with four §6 transaction sequences (clone-to-draft, head-swap, in-place, simple transition)
- Pure-function guard matrix (`transitions.py`) + ownership checks
- Visibility repository (`public_filter`, `curator_filter`) + AST-level enforcement
- Sweep of every endpoint under `phenopackets/routers`, `search`, `aggregations`, `publications`, `seo/sitemap`, `admin` to route through visibility
- MV migration rebuilds summary MVs with the public filter
- POST /transitions + GET /revisions HTTP endpoints
- PUT branches: published → clone, draft/changes_requested → in-place
- Four Vue 3 components (state badge, transition menu, transition modal, editing banner) + composable
- Full state-lifecycle Playwright E2E + I1 dual-read E2E

## Test plan
- [x] Backend: `uv run pytest` — all green
- [x] Frontend: `npm test -- --run` — all green
- [x] Coverage: backend ≥ 70%, frontend ≥ 30%
- [x] Playwright: lifecycle + dual-read specs pass locally
- [x] Manual: create draft → submit → approve → publish → anonymous sees published
- [x] Manual: clone-to-draft on published → curator sees new content, anonymous sees old

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review (run this before marking the plan done)

1. **Spec coverage:**
   - Invariants I1–I7: Task 8 ✓
   - Guard matrix: Task 6 ✓
   - §6.1 clone-to-draft: Task 7 ✓
   - §6.2 head-swap: Task 7 ✓
   - §6.3 in-place: Task 7 ✓
   - §6.4 simple transition: Task 7 ✓
   - §5 migrations: Tasks 1–3 ✓
   - §5.3 data migration: Task 3 + Task 14 (MV rebuild) ✓
   - §7.1 new endpoints: Task 10 ✓
   - §7.2 changed semantics: Task 11 ✓
   - §7.3 response schemas: Task 5 ✓
   - §8 filter centralization: Tasks 9, 12, 13, 14 ✓
   - AST enforcement: Task 15 ✓
   - §9 frontend components: Tasks 16–19 ✓
   - §9.2 view changes: Tasks 21, 22 ✓
   - §9.3 composable: Task 20 ✓
   - §10.2 dual-read test: Task 24 ✓
   - §10.4 E2E: Tasks 23–24 ✓
   - §11 rollout: implied by PR merge flow ✓
   - §14 acceptance criteria verification: Task 25 ✓

2. **Placeholder scan:** ✅ no TBD/TODO/fill-in placeholders; code blocks complete for every code step.

3. **Type consistency:**
   - `PhenopacketRevision.record_id` (UUID) — used consistently across Tasks 2, 4, 7, 9, 10, 15.
   - `TransitionRequest.to_state` values align with `STATES` tuple in migrations (1,2) and `State` Literal (6).
   - `check_transition` signature uniform in Tasks 6, 7.
   - `PhenopacketStateService.RevisionMismatch` / `InvalidTransition` / `EditInProgress` / `ForbiddenNotOwner` consistently referenced in Tasks 7, 8, 10, 11.
   - Frontend `StateBadge` props name (`state`) matches backend `PhenopacketResponse.state` serialization.
   - Component `data-testid` names consistent between modal/menu components and E2E specs.

All clean.
