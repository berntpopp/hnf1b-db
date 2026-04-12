# Wave 7 / D.1 — Phenopacket State Machine & Revisions

**Date:** 2026-04-12
**Source review:** [docs/reviews/2026-04-11-platform-readiness-review.md](../../reviews/2026-04-11-platform-readiness-review.md) Bundle D.1
**Follows:** Wave 6 (2026-04-10 refactor roadmap exit at 8.1/10)
**Scope:** Bundle D is split into three sub-waves. This spec covers D.1 only (state machine + immutable revisions + visibility gating). D.2 (comments) and D.3 (GitHub-PR review UI + diff rendering) are separate specs.

## 1. Purpose

Add a curation workflow state machine and immutable revision history to phenopackets. Replaces the current "every saved record is immediately public and overwritten in place" model with a `draft → in_review → changes_requested → approved → published` pipeline plus `archived` terminal state. Keeps the previously published copy live and publicly visible while curators edit a new draft revision, so fixing a typo never blinks a record out of public view.

## 2. Goals & non-goals

**Goals**
- Record-level lifecycle state that gates public visibility.
- Immutable per-transition snapshot rows (`phenopacket_revisions`) suitable as the substrate for D.3 diff rendering.
- Clone-to-draft semantics for editing published records with a dual-pointer model (working copy vs. public copy).
- One-shot data migration that seeds existing 864 rows into `state='published'` with a single revision row, no public regression.
- Role-based transition guards on top of the existing `curator` / `admin` roles, plus explicit draft ownership for withdrawal/resubmit rights.
- Filter centralization: one place defines "what's visible to the public" and "what's visible to curators"; every read path routes through it.

**Non-goals (explicitly out of D.1 scope)**
- Comments, discussion threads, @-mentions — D.2
- `PhenopacketReviewView.vue` GitHub-PR 3-lane UI — D.3
- RFC 6902 diff *rendering* — D.3 (the `change_patch` **data** is captured in D.1)
- CRediT role tagging on transition events — deferred to Bundle E per review §7
- Separate ClinGen VCEP-style specialist role — review §7 decision: stay with `curator` / `admin`
- `superseded` state — review §7 decision: deferred; new publishes replace, not supplement
- Draft visibility to non-curators — review §7 decision: public sees `published` only

## 3. Invariants

These invariants are the contract of the data model. **Every read and write path must preserve them; tests enforce them directly.**

### I1 — State + public-pointer independence
`phenopackets.state = 'published'` does **NOT** imply that `phenopackets.phenopacket` (the working copy) equals the public copy. The only authoritative public content is `phenopacket_revisions[head_published_revision_id].content_jsonb`. Public reads **must** dereference through `head_published_revision_id`, never through `phenopackets.phenopacket` directly.

### I2 — Single head-published revision per record
At most one `phenopacket_revisions` row per `record_id` has `is_head_published = TRUE`. Enforced by a partial unique index. Any transition that changes the head-published pointer does so atomically in a single transaction.

### I3 — head_published_revision_id ↔ state consistency
- `phenopackets.state = 'published'` ⟹ `head_published_revision_id IS NOT NULL`.
- `head_published_revision_id IS NOT NULL` ⟹ the referenced revision row has `is_head_published = TRUE` AND `to_state = 'published'`.
- `phenopackets.state ∈ {draft, in_review, changes_requested, approved}` AND record has never been published ⟹ `head_published_revision_id IS NULL`.
- `phenopackets.state = 'archived'`: `head_published_revision_id` may be non-null (last published snapshot is preserved for audit) but is **never** served to the public because the public filter also rejects `state='archived'`.

### I4 — editing_revision_id gates clone-to-draft
- `editing_revision_id IS NOT NULL` ⟹ the referenced revision row has `is_head_published = FALSE` AND that revision represents the in-progress draft.
- A record with `phenopackets.state = 'published'` AND `editing_revision_id IS NOT NULL` has two distinct copies: the public one at `head_published_revision_id`, and the in-progress curator working copy at `phenopackets.phenopacket` (which equals the `editing_revision_id` row's `content_jsonb`).
- At most one `editing_revision_id` per record at a time — concurrent clone-to-draft attempts return 409.

### I5 — draft_owner_id is meaningful only when there's a draft
- `draft_owner_id IS NOT NULL` ⟺ the record has an in-progress draft the owner can withdraw/resubmit, i.e. one of:
  - `state ∈ {draft, in_review, changes_requested, approved}` AND (the record has never published, in which case the initial creator owns) OR
  - `state = 'published'` AND `editing_revision_id IS NOT NULL` (clone-to-draft in progress; ownership belongs to whoever opened the edit).
- On `publish` and on `archive`, `draft_owner_id` is **cleared to NULL**.
- Migrated historical records (all `state='published'` with no active edit) have `draft_owner_id = NULL` — ownership semantics don't apply to them until a curator opens a clone-to-draft, at which point `draft_owner_id` is set to that curator.
- Admin role **bypasses** ownership checks. Curator role **requires** `user.id == draft_owner_id` for withdraw/resubmit/in-place-save on non-draft states.

### I6 — Revision numbering: unified counter, meaningful gaps
- `phenopackets.revision` increments on **every write** (in-place content save AND state transition).
- `phenopacket_revisions` rows are created on **state transitions only**.
- A revision row's `revision_number` = the `phenopackets.revision` value that was committed at that transition.
- Gaps in `revision_number` across revision rows for the same record are **expected and meaningful**: a gap means one or more in-place content saves happened between transitions.
- `UNIQUE(record_id, revision_number)` holds (each transition gets a distinct counter value; in-place saves never create rows).

### I7 — archived vs. soft-delete are orthogonal
- `deleted_at IS NOT NULL` = curator removed the record (mistake/duplicate). Hidden from curators by default (needs `?include=deleted`); admin-only restore.
- `state = 'archived'` = admin retired the record from the active lifecycle; still visible to curators in dedicated archive views; never visible to the public.
- Both can coexist. The public filter rejects either being set. The curator filter applies them independently.

## 4. State model

5 + 1 states:

```
draft ──submit──▶ in_review ──request_changes──▶ changes_requested
  ▲                  │                                  │
  │                  │                                  └──resubmit──▶ in_review
  │                  ├──withdraw──▶ draft
  │                  │
  │                  └──approve──▶ approved ──publish──▶ published
  │                                                         │
  └─────────────────────── edit (clone) ────────────────────┘
                                                            │
Any non-archived state ──archive──▶ archived  (terminal; admin only)
```

### 4.1 Transition guard matrix

| From state | Transition | To state | Required role/ownership | Notes |
|---|---|---|---|---|
| `draft` | `submit` | `in_review` | curator == `draft_owner_id`, or admin | |
| `in_review` | `withdraw` | `draft` | curator == `draft_owner_id`, or admin | |
| `in_review` | `request_changes` | `changes_requested` | admin | Cannot self-review: admin ≠ `draft_owner_id` required if admin is also the owner? **No** — admin bypass always applies (I5). |
| `in_review` | `approve` | `approved` | admin | Same |
| `changes_requested` | `resubmit` | `in_review` | curator == `draft_owner_id`, or admin | |
| `approved` | `publish` | `published` | admin | Head-swap per §6.2 |
| `published` | `edit` | *(clone to new draft revision; see §6.1)* | curator or admin | Creates new revision row; `phenopackets.state` stays `published`; `editing_revision_id` + `draft_owner_id` set |
| *(any non-archived)* | `archive` | `archived` | admin | Terminal |

No other transitions are legal. The backend rejects all unknown `{from_state, to_state}` pairs with `HTTP 409 {"error_code": "invalid_transition"}`. Role/ownership failures return `403 {"error_code": "forbidden_role"}` or `403 {"error_code": "forbidden_not_owner"}`.

## 5. Schema

Three Alembic migrations, in order.

### 5.1 Migration 1 — new columns on `phenopackets`

```sql
ALTER TABLE phenopackets
  ADD COLUMN state TEXT NOT NULL DEFAULT 'draft'
    CHECK (state IN ('draft','in_review','changes_requested','approved','published','archived')),
  ADD COLUMN editing_revision_id BIGINT NULL,
  ADD COLUMN head_published_revision_id BIGINT NULL,
  ADD COLUMN draft_owner_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX ix_phenopackets_state ON phenopackets (state);
CREATE INDEX ix_phenopackets_draft_owner ON phenopackets (draft_owner_id)
  WHERE draft_owner_id IS NOT NULL;

-- FKs on editing_revision_id and head_published_revision_id added in
-- migration 2 (revisions table must exist first).
```

### 5.2 Migration 2 — `phenopacket_revisions`

```sql
CREATE TABLE phenopacket_revisions (
  id BIGSERIAL PRIMARY KEY,
  record_id UUID NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
  revision_number INTEGER NOT NULL,
  state TEXT NOT NULL
    CHECK (state IN ('draft','in_review','changes_requested','approved','published','archived')),
  content_jsonb JSONB NOT NULL,
  change_patch JSONB,
  change_reason TEXT NOT NULL,
  actor_id BIGINT NOT NULL REFERENCES users(id),
  from_state TEXT NULL,
  to_state TEXT NOT NULL,
  is_head_published BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (record_id, revision_number)
);

-- I2: at most one head-published row per record (partial unique index)
CREATE UNIQUE INDEX ux_head_published_per_record
  ON phenopacket_revisions (record_id)
  WHERE is_head_published = TRUE;

-- Activity lookups
CREATE INDEX ix_revisions_record_created
  ON phenopacket_revisions (record_id, created_at DESC);

-- Add the deferred FKs on phenopackets
ALTER TABLE phenopackets
  ADD CONSTRAINT fk_phenopackets_editing_revision
    FOREIGN KEY (editing_revision_id)
    REFERENCES phenopacket_revisions(id)
    ON DELETE SET NULL,
  ADD CONSTRAINT fk_phenopackets_head_published_revision
    FOREIGN KEY (head_published_revision_id)
    REFERENCES phenopacket_revisions(id)
    ON DELETE SET NULL;
```

(Note: `record_id` is a UUID internal FK to `phenopackets.id`. The public stable identifier `phenopacket_id` stays as `String(100)` and is resolved on the way out to API responses — never used as a FK target.)

### 5.3 Migration 3 — data migration for existing 864 rows

One-shot, idempotent:

1. Ensure a `system` user exists (username=`system`, role=`admin`, `is_active=FALSE`, `is_verified=TRUE`, random hashed password; used only as an audit actor on historical snapshots).
2. For every existing `phenopackets` row:
   - Set `state = 'published'`
   - Set `draft_owner_id = NULL` — historical records have no active draft; ownership is meaningful only when a curator opens a clone-to-draft later (I5)
   - Insert one `phenopacket_revisions` row:
     - `record_id = phenopackets.id`
     - `revision_number = phenopackets.revision` (uses the existing optimistic-lock counter)
     - `state = 'published'`
     - `content_jsonb = phenopackets.phenopacket`
     - `change_patch = NULL`
     - `change_reason = 'Migrated from pre-D.1 data model'`
     - `actor_id = <system user id>`
     - `from_state = NULL`
     - `to_state = 'published'`
     - `is_head_published = TRUE`
   - Set `phenopackets.head_published_revision_id = <new revision row id>`
   - `editing_revision_id` stays NULL (no in-progress edit)

After migration, every existing record is publicly visible exactly as before. **No public regression.**

## 6. Clone-to-draft edit flow — exact transition sequences

### 6.1 Editing a `published` record (clone path)

Triggered by `PUT /api/v2/phenopackets/{id}` when `phenopackets.state = 'published'`.

**Preconditions:** current user is curator or admin. Request body includes the expected `revision` for optimistic locking.

**Transaction body** (single `BEGIN … COMMIT`):

| # | Operation | Target | Change |
|---|---|---|---|
| 1 | Lock row | `phenopackets` WHERE `id = ?` FOR UPDATE | — |
| 2 | Optimistic-lock check | `phenopackets.revision` | 409 `revision_mismatch` if `request.revision ≠ phenopackets.revision` |
| 3 | Edit-in-progress check | `phenopackets.editing_revision_id` | 409 `edit_in_progress` if NOT NULL |
| 4 | Compute patch | — | `change_patch = jsonpatch(head_published.content_jsonb, new_content)` |
| 5 | Bump counter | `phenopackets.revision` | `+= 1` |
| 6 | Insert revision row | `phenopacket_revisions` | new row with `record_id, revision_number=phenopackets.revision, state='draft', content_jsonb=new_content, change_patch, change_reason, actor_id=current_user.id, from_state='published', to_state='draft', is_head_published=FALSE` |
| 7 | Update working copy | `phenopackets.phenopacket` | `:= new_content` (curators see the fresh draft) |
| 8 | Set edit pointer | `phenopackets.editing_revision_id` | `:= <new revision row id>` |
| 9 | Set draft owner | `phenopackets.draft_owner_id` | `:= current_user.id` |
| 10 | State unchanged | `phenopackets.state` | stays `'published'` (public still sees old head) |
| 11 | head_published pointer unchanged | `phenopackets.head_published_revision_id` | stays pointing at previous public copy |
| 12 | COMMIT | | |

After commit: curator GET returns the new draft content via `phenopackets.phenopacket`; public GET continues serving the original via `head_published_revision_id → content_jsonb` (invariant I1).

### 6.2 Publishing a draft (head-swap path)

Triggered by `POST /api/v2/phenopackets/{id}/transitions` with `to_state='published'` from `from_state='approved'`.

**Preconditions:** current user is admin. Record has exactly one revision row with `state='approved'`. `phenopackets.editing_revision_id` is NULL or points at that approved row.

**Transaction body:**

| # | Operation | Target | Change |
|---|---|---|---|
| 1 | Lock row | `phenopackets` FOR UPDATE | — |
| 2 | Optimistic-lock check | `phenopackets.revision` | 409 if mismatch |
| 3 | Find new head | `phenopacket_revisions` | the single row with `record_id=? AND state='approved'`; 409 if 0 or >1 |
| 4 | Clear old head | `phenopacket_revisions` WHERE `record_id=? AND is_head_published=TRUE` | `is_head_published := FALSE` |
| 5 | Set new head | `phenopacket_revisions` row found in step 3 | `is_head_published := TRUE` (partial unique index guarantees at most one per record — concurrent publishes: loser's COMMIT fails with unique violation) |
| 6 | Advance record state | `phenopackets.state` | `:= 'published'` |
| 7 | Bump counter | `phenopackets.revision` | `+= 1` |
| 8 | Update working copy | `phenopackets.phenopacket` | `:= new_head.content_jsonb` (curator working copy = public copy now) |
| 9 | Update head pointer | `phenopackets.head_published_revision_id` | `:= new head row id` |
| 10 | Clear edit pointer | `phenopackets.editing_revision_id` | `:= NULL` |
| 11 | Clear draft owner | `phenopackets.draft_owner_id` | `:= NULL` (I5) |
| 12 | Insert transition row | `phenopacket_revisions` | Optional: insert a zero-delta row with `to_state='published'` for the audit trail if the approved row's `state` field still reads 'approved'. Design choice: **re-use the approved revision row — update its `state` column from 'approved' to 'published' and its `is_head_published` to TRUE** rather than insert a separate row. This keeps a 1:1 mapping between "the approved snapshot" and "the published snapshot"; see §6.4 for the rationale. |
| 13 | COMMIT | | |

After commit: curator working copy, public head, and record state are all aligned. `draft_owner_id` cleared. `editing_revision_id` cleared.

### 6.3 In-place edit on a draft (no new revision row)

Triggered by `PUT /api/v2/phenopackets/{id}` when `phenopackets.state ∈ {draft, changes_requested}`.

**Preconditions:** curator is the `draft_owner_id`, OR caller is admin. Request body includes expected `revision`.

**Transaction body:**

| # | Operation | Target | Change |
|---|---|---|---|
| 1 | Lock row | `phenopackets` FOR UPDATE | — |
| 2 | Ownership check | `draft_owner_id` vs. `current_user.id` | 403 `forbidden_not_owner` if mismatch and not admin |
| 3 | Optimistic-lock check | `phenopackets.revision` | 409 if mismatch |
| 4 | Bump counter | `phenopackets.revision` | `+= 1` |
| 5 | Overwrite working copy | `phenopackets.phenopacket` | `:= new_content` |
| 6 | Update in-progress revision row | if `editing_revision_id IS NOT NULL`: `phenopacket_revisions` row at that id | `content_jsonb := new_content`, `change_reason := new_reason` (row's `revision_number` is unchanged — gap from now on is recorded, per I6) |
| 7 | COMMIT | | |

No new revision row is created. The gap between the previous transition's `revision_number` and the next transition's will reflect how many in-place saves happened.

For a `draft` record that has never been published (no `editing_revision_id`), step 6 is skipped — the revision row representing the current draft state is created at `submit` time, not at draft-save time. (Rationale: a draft that never reaches `in_review` shouldn't leave a revision trail; only transitions do.)

### 6.4 Simple state transitions (no content change)

Triggered by `POST /api/v2/phenopackets/{id}/transitions` for transitions that are not `publish`.

**Transaction body** (e.g. `draft → in_review`):

| # | Operation | Target | Change |
|---|---|---|---|
| 1 | Lock row | `phenopackets` FOR UPDATE | — |
| 2 | Authz check | role + ownership per §4.1 | 403 on failure |
| 3 | Optimistic-lock check | `phenopackets.revision` | 409 if mismatch |
| 4 | Bump counter | `phenopackets.revision` | `+= 1` |
| 5 | Advance state | `phenopackets.state` | `:= to_state` |
| 6 | Maintain owner | `phenopackets.draft_owner_id` | Unchanged for within-draft-family transitions (`submit`, `withdraw`, `request_changes`, `resubmit`); **cleared** on `approve`? **No** — kept through `approved` so the curator can still withdraw. Cleared only on `publish` and `archive`. |
| 7 | Insert revision row | `phenopacket_revisions` | new row with `record_id, revision_number=phenopackets.revision, state=to_state, content_jsonb=phenopackets.phenopacket (snapshot of the working copy), change_patch=jsonpatch(prev_revision.content_jsonb, phenopackets.phenopacket), change_reason, actor_id=current_user.id, from_state, to_state, is_head_published=FALSE` |
| 8 | Update editing pointer | `phenopackets.editing_revision_id` | on transitions out of `draft` (e.g. `submit`): point at the new row (the "active draft" is now the in-review snapshot). Cleared only at `publish`/`archive`. |
| 9 | COMMIT | | |

`archive` follows the same shape with `to_state='archived'` and `draft_owner_id` cleared.

## 7. API surface

### 7.1 New endpoints

```
POST   /api/v2/phenopackets/{id}/transitions
       auth: curator or admin (per §4.1)
       body: { to_state, reason, revision }
       200:  { phenopacket: PhenopacketResponse, revision: RevisionResponse }
       403:  forbidden_role | forbidden_not_owner
       409:  invalid_transition | revision_mismatch | edit_in_progress
       400:  validation errors

GET    /api/v2/phenopackets/{id}/revisions
       auth: curator or admin (non-curators: 404)
       query: page[size], page[number], sort=-created_at
       200:  { data: RevisionResponse[], meta: { total } }

GET    /api/v2/phenopackets/{id}/revisions/{revision_id}
       auth: curator or admin
       200:  RevisionResponse (full content_jsonb + change_patch)
```

### 7.2 Changed semantics

```
PUT    /api/v2/phenopackets/{id}
       body unchanged
       new behavior:
         - state == 'published': clone-to-draft path (§6.1)
         - state ∈ {draft, changes_requested}: in-place path (§6.3)
         - state ∈ {in_review, approved}: 409 edit_forbidden — resubmit/withdraw first
         - state == 'archived': 409 invalid_transition
         - 409 edit_in_progress if editing_revision_id already set
         - 403 forbidden_not_owner if ownership check fails

GET    /api/v2/phenopackets/          # list
GET    /api/v2/phenopackets/{id}      # detail
       new visibility behavior:
         anonymous / non-curator caller:
           - filter: deleted_at IS NULL AND state='published' AND head_published_revision_id IS NOT NULL
           - content: dereference head_published_revision_id → content_jsonb
         curator / admin caller:
           - filter: (deleted_at IS NULL OR ?include=deleted)
                     AND (state != 'archived' OR ?include=archived)
           - content: phenopackets.phenopacket (working copy)

POST   /api/v2/phenopackets/
       default new record: state='draft', draft_owner_id=current_user.id
       inserts the initial revision row at submit time, not at create time.

DELETE /api/v2/phenopackets/{id}
       unchanged — soft-delete remains orthogonal to state; archived != deleted.
```

### 7.3 Response schema — **this is a contract change, not a wording tweak**

`PhenopacketResponse` gains four new fields:

```python
class PhenopacketResponse(BaseModel):
    # ... existing fields ...
    state: str  # 'draft' | 'in_review' | ... | 'archived'
    head_published_revision_id: int | None
    editing_revision_id: int | None
    draft_owner_id: int | None
    draft_owner_username: str | None   # joined display

class TransitionRequest(BaseModel):
    to_state: Literal['draft','in_review','changes_requested','approved','published','archived']
    reason: str = Field(min_length=1, max_length=500)
    revision: int

class RevisionResponse(BaseModel):
    id: int
    record_id: str           # UUID serialized
    phenopacket_id: str      # public stable id, joined for convenience
    revision_number: int
    state: str
    from_state: str | None
    to_state: str
    is_head_published: bool
    change_reason: str
    actor_id: int
    actor_username: str | None
    change_patch: list[dict] | None
    created_at: datetime
    # content_jsonb returned only from GET /{id}/revisions/{revision_id}, not list
```

The frontend API client (`frontend/src/api/domain/phenopackets.js`) and type definitions update in the same PR. The state-badge column on the list view depends on `state` being present in list responses; non-curator list responses return `state: null` (schema keeps the field; value is omitted for privacy).

## 8. Filter centralization — complete audited endpoint list

Every code path that reads from `phenopackets` must route through one of two repository methods. **No raw query is allowed to hit `phenopackets` from outside the repository without a comment justifying why.**

### 8.1 Repository methods

```python
class PhenopacketRepository:
    def public_filter(self, stmt):
        """Apply invariant public visibility: deleted_at IS NULL
        AND state='published' AND head_published_revision_id IS NOT NULL."""

    def curator_filter(self, stmt, *, include_deleted=False, include_archived=False):
        """Apply invariant curator visibility: (deleted_at IS NULL OR include_deleted)
        AND (state != 'archived' OR include_archived)."""

    # content resolvers
    def resolve_public_content(self, pp) -> dict:
        """Return content_jsonb from head_published_revision_id; None if not published."""

    def resolve_curator_content(self, pp) -> dict:
        """Return phenopackets.phenopacket (working copy)."""
```

The endpoint chooses which filter + resolver to call based on the caller's role.

### 8.2 Endpoints audited in this wave

Each of the following is updated to route through the repository filters. Any raw select that currently reads `phenopackets` gets rewritten or justified inline.

**Detail / list / CRUD (required):**
- `backend/app/phenopackets/routers/crud.py` — list, detail, create, update (PUT), delete, audit-history
- `backend/app/phenopackets/routers/crud_related.py` — variant lookups, related-record queries
- `backend/app/phenopackets/routers/crud_timeline.py` — patient clinical timeline (reads phenopacket JSONB for features)

**Search / comparison:**
- `backend/app/phenopackets/routers/search.py` — full-text and facet search
- `backend/app/phenopackets/routers/comparisons/query.py` — record comparisons
- `backend/app/search/services/facet.py` — facet aggregation
- `backend/app/search/repositories.py` — search index reads

**Aggregations (every file under `aggregations/`):**
- `aggregations/publications.py`, `features.py`, `summary.py`, `demographics.py`, `diseases.py`
- `aggregations/variant_query_builder.py`
- `aggregations/sql_fragments/ctes.py`
- `aggregations/survival/handlers/{variant_type,pathogenicity,protein_domain,disease_subtype}.py`

**Cross-domain readers:**
- `backend/app/publications/endpoints/list_route.py` — publication → phenopacket counts
- `backend/app/publications/endpoints/sync_route.py` — **audit only**: probably admin-gated, may skip public filter with a comment if so
- `backend/app/seo/sitemap.py` — **must use public filter** (sitemap is public)
- `backend/app/api/admin/queries.py` — **admin** filter: `curator_filter(include_deleted=True, include_archived=True)`

**Materialized views:**
- `backend/alembic/versions/add_materialized_views_for_aggregations.py` + `44ccb14dc32b_fix_mv_summary_statistics_unique_index.py` — MV definitions need to filter by `state='published'` AND `deleted_at IS NULL` so public aggregations never include drafts. MV refresh job runs on every publish/archive transition (can piggy-back on the existing refresh schedule with added triggers).

**Tests touching schema:**
- `backend/tests/test_crud_related_and_timeline.py`
- `backend/tests/test_classification_validation.py`
- `backend/tests/test_soft_delete_global_filter.py`
- `backend/tests/test_variant_query_soft_delete.py`

Tests get companions (see §10) that assert filter application.

## 9. Minimal D.1 frontend

Only enough to exercise the API and render state. The rich GitHub-PR 3-lane review screen is D.3.

### 9.1 Components

- **`StateBadge.vue`** — colored chip, 6 state variants, WCAG AA contrast.
- **`TransitionMenu.vue`** — dropdown on the detail view; renders only transitions legal for (current state, current user role, current ownership). Each item opens the modal.
- **`TransitionModal.vue`** — reason textarea (required) + confirm/cancel; calls `POST /transitions`.
- **`EditingBanner.vue`** — shown on curator detail view when `editing_revision_id IS NOT NULL`: "Draft in progress by @{draft_owner_username} — started {relative_time}". Non-owners see a read-only variant; owner sees "Continue editing" CTA.

### 9.2 Changed views

- **`Phenopackets.vue`** (list) — state badge column visible to curators only (non-curator responses have `state=null`, column hidden).
- **`PagePhenopacket.vue`** (detail) — state badge at top; `TransitionMenu` for curators/admins; `EditingBanner` when applicable. No 3-lane UI yet.
- **`PhenopacketCreateEdit.vue`** — toast on save of a `published` record: "Draft saved — submit for review when ready." Toast on save of `draft` / `changes_requested` record: "Draft updated."

### 9.3 Store

`authStore` unchanged. New composable `usePhenopacketState(phenopacketId)`:
- `transitionTo(toState, reason)` — calls `POST /transitions`, refreshes record.
- `fetchRevisions()` — lazy-loaded (D.3 will consume the result).

### 9.4 Routing & guards

No new routes. Visibility filter is enforced server-side; router guard for `/phenopackets/:id` stays as-is.

## 10. Testing

### 10.1 Backend unit

- **Transition guard matrix:** parametrized test — every role × every current state × every attempted `to_state` (30+ cases); legal = success, illegal = correct error code.
- **Ownership checks:** withdraw/resubmit/in-place-save as owner succeed; as non-owner non-admin return 403; as admin succeed regardless.
- **Clone-to-draft atomicity:** two concurrent `PUT` calls on the same published record — second returns 409 `edit_in_progress`.
- **Head-swap atomicity:** simulated concurrent publishes on the same record — exactly one succeeds; other gets a unique-index violation mapped to 409.
- **Revision numbering gaps:** after `create → submit → <3 in-place saves> → approve → publish`, assert `revision_number` values on revision rows are `{1, 2, 6}` (or similar) — gaps reflect in-place saves.
- **Invariant I5:** `publish` clears `draft_owner_id`; `archive` clears it; `clone-to-draft` sets it.

### 10.2 Backend integration

- **Full lifecycle:** `create (draft) → submit → request_changes → resubmit → approve → publish`, asserting revision rows + state + pointers at each step.
- **Edit-published-record:** edit a published record, submit, approve, re-publish; assert old head row `is_head_published=FALSE`, new one TRUE, `phenopackets.phenopacket` updated, curator sees new content, public GET returns new content.
- **"Public sees last published while curator sees newer draft":** after clone-to-draft, same request path returns different content depending on caller role; after re-publish they converge. This is **the key I1 test**.
- **Visibility filter (centralization):** non-curator list / detail / search / aggregations / timeline / variant-lookup for records in every non-published state all return 0 or 404. Parametrized over the full endpoint list in §8.2.
- **Archive ↔ soft-delete orthogonality:** a record that is both `archived` and `deleted_at != NULL`; curator with `?include=archived` sees it; curator with `?include=deleted` sees it; curator with both sees it; public sees nothing.
- **Archive is terminal:** `archived → *` all 409 `invalid_transition`.

### 10.3 Migration test

Alembic migration 3 on a fresh DB seeded with ≥ 5 pre-D.1 phenopackets (varied `revision` values, varied `deleted_at`). Assert for every record post-migration:
- `state = 'published'`
- `draft_owner_id IS NULL` (no active drafts on historical records, per §5.3 and I5)
- Exactly one revision row with `is_head_published = TRUE`, `to_state = 'published'`, `revision_number = old phenopackets.revision`
- `head_published_revision_id` points to that row
- Public GET responses are byte-identical to pre-migration.

### 10.4 Frontend

- **Component tests:** `StateBadge` renders every variant; `TransitionMenu` role-gating (curator vs admin vs viewer); `TransitionModal` reason-required validation; `EditingBanner` owner vs non-owner variants.
- **E2E (Playwright):** login as curator → create draft → submit → login as admin → approve → publish → log out → verify public detail shows new content. Gated as a CI job.
- **E2E (dual-read I1):** login as curator, clone-to-draft-edit a published record, assert detail shows new content; open a second browser context as anonymous and verify public still sees old content; re-publish; assert both converge.

### 10.5 Regression

All 1,131 existing backend tests stay green. Frontend coverage floor unchanged (30%). Backend coverage threshold unchanged (70%).

## 11. Rollout

1. Merge all three migrations + backend endpoints + minimal UI + MV refresh in one PR (Wave 7a).
2. Run data migration on staging; verify public endpoints byte-identical (automated E2E + Playwright sniff).
3. Run on prod during low-traffic window. Rollback: `DROP TABLE phenopacket_revisions`, `ALTER TABLE phenopackets DROP COLUMN state, editing_revision_id, head_published_revision_id, draft_owner_id`. Since `phenopackets.phenopacket` is untouched by the migration, rollback is destructive only to revision history — public content remains intact.
4. Enable curator access to transitions UI. Non-curator public experience is byte-identical.

## 12. Open items deferred to D.2 / D.3

- Comment threads anchored to specific JSON Patch operations
- Soft-approval gate when unresolved comments exist
- GitHub-PR 3-lane review screen
- `json-diff-kit-vue` diff rendering
- @-mention autocomplete
- CRediT role tagging (Bundle E)

## 13. Risks

- **Visibility regression** — the whole filter-centralization premise only holds if every read path routes through the repository. New endpoints added later may forget. Mitigation: a pytest asserts every handler in `backend/app/phenopackets/routers/` and `backend/app/search/`, `backend/app/api/admin/`, `backend/app/publications/endpoints/` calls either `public_filter` or `curator_filter` (AST-level static check over `app/` paths matching `phenopackets`). This is the same defensive shape as the Wave 5b soft-delete guard, extended to state.
- **Performance** — adding a `head_published_revision_id` dereference on public list endpoints is a per-row JOIN. Mitigation: denormalize — for every published record, `phenopackets.phenopacket` already holds the current public content on migrated records because migration 3 copies them identically; the public resolver falls back to `phenopackets.phenopacket` when `head_published_revision_id.content_jsonb == phenopackets.phenopacket` (checked by a cheap digest field on the revision). If the clone-to-draft path never updates `phenopackets.phenopacket` for `published` records **without** also setting `editing_revision_id`, the public resolver can short-circuit to `phenopackets.phenopacket` when `editing_revision_id IS NULL AND state = 'published'`. This is the common case and costs zero extra queries. The join is taken only when `editing_revision_id IS NOT NULL` AND we're serving a public request — the uncommon case.
- **MV staleness** — materialized views on publication status need refresh on every publish/archive transition. Mitigation: trigger-based refresh or a background queue; measured before rollout.
- **Migration length** — 864 rows + 864 new revision rows = trivial (<1 s).

## 14. Acceptance criteria

- [ ] Invariants I1–I7 each have a dedicated test that breaks if the invariant is violated.
- [ ] All 8 transition types in §4.1 work with role + ownership gates; all 30+ illegal cases return stated errors.
- [ ] `PUT /phenopackets/{id}` on a `published` record creates a draft revision, leaves `head_published_revision_id` unchanged, sets `editing_revision_id` + `draft_owner_id`, and updates `phenopackets.phenopacket` to the new draft.
- [ ] Publishing a draft atomically sets `head_published_revision_id` to the approved row, clears `editing_revision_id` and `draft_owner_id`, advances state, bumps `revision`. Concurrent publishes: one succeeds, one 409.
- [ ] **I1 test** — after clone-to-draft, anonymous GET returns OLD head content; curator GET returns NEW draft content; after re-publish, both converge.
- [ ] Non-curator GETs return 0/404 for every state except `published` across list, detail, search, every aggregation endpoint, timeline, and variant lookups (§8.2 list exhaustively covered).
- [ ] Migration 3 seeds 864 records into `state='published'` with `draft_owner_id=NULL` and exactly one `is_head_published=TRUE` revision per record; public API responses byte-identical pre/post.
- [ ] AST-level test asserts no handler under the audited directories in §8.2 reads `phenopackets` without calling a repository filter method.
- [ ] All 1,131 existing backend tests stay green.
- [ ] Backend coverage ≥ 70%; new code ≥ 85%. Frontend coverage floor 30% unchanged; new components land with component tests.
- [ ] One Playwright E2E covering the full lifecycle + one covering the dual-read I1 scenario land and are gating jobs.
