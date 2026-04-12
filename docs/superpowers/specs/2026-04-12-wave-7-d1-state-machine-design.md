# Wave 7 / D.1 — Phenopacket State Machine & Revisions

**Date:** 2026-04-12
**Source review:** [docs/reviews/2026-04-11-platform-readiness-review.md](../../reviews/2026-04-11-platform-readiness-review.md) Bundle D.1
**Follows:** Wave 6 (2026-04-10 refactor roadmap exit at 8.1/10)
**Scope:** Bundle D is split into three sub-waves. This spec covers D.1 only (state machine + immutable revisions). D.2 (comments) and D.3 (GitHub-PR review UI) are separate specs.

## 1. Purpose

Add a curation workflow state machine and immutable revision history to phenopackets. Replaces the current "every saved record is immediately public and overwrite-in-place" model with a `draft → in_review → changes_requested → approved → published` pipeline plus `archived` terminal state. Keeps the previously published copy live and publicly visible while curators edit a new draft revision, so fixing a typo never blinks a record out of public view.

## 2. Goals & non-goals

**Goals**
- Record-level lifecycle state that gates public visibility.
- Immutable per-transition snapshot rows (`phenopacket_revisions`) suitable as the substrate for D.3 diff rendering.
- Clone-to-draft semantics for editing published records.
- One-shot data migration that seeds existing 864 rows into `published` with a single revision row, no public regression.
- Role-based transition guards on top of the existing `curator` / `admin` roles.

**Non-goals (explicitly out of D.1 scope)**
- Comments, discussion threads, @-mentions — D.2
- `PhenopacketReviewView.vue` GitHub-PR 3-lane UI — D.3
- RFC 6902 diff *rendering* — D.3 (the `change_patch` **data** is captured in D.1)
- CRediT role tagging on transition events — deferred to Bundle E per review §7
- Separate ClinGen VCEP-style specialist role — review §7 decision: stay with `curator` / `admin`
- `superseded` state — review §7 decision: deferred; new publishes replace, not supplement
- Draft visibility to non-curators — review §7 decision: drafts + `in_review` + `changes_requested` + `approved` are curator-only; public sees `published` only

## 3. State model

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

### 3.1 Transition guard matrix

| From state | Transition | To state | Required role | Notes |
|---|---|---|---|---|
| `draft` | `submit` | `in_review` | `curator` (author) or `admin` | |
| `in_review` | `withdraw` | `draft` | `curator` (author) or `admin` | Author is whoever last set state to `draft` |
| `in_review` | `request_changes` | `changes_requested` | `admin` | Curator cannot self-approve / self-request-changes |
| `in_review` | `approve` | `approved` | `admin` | Same |
| `changes_requested` | `resubmit` | `in_review` | `curator` (author) or `admin` | |
| `approved` | `publish` | `published` | `admin` | |
| `published` | `edit` | *(clone to new `draft` revision, head stays `published`)* | `curator` or `admin` | Creates new revision row; `phenopackets.state` stays `published`; `editing_revision_id` set |
| *(any non-archived)* | `archive` | `archived` | `admin` | Terminal |

No other transitions are legal. The backend rejects all unknown `{from_state, to_state}` pairs with `HTTP 409 {"error_code": "invalid_transition"}`.

### 3.2 Authorship

Authorship of a draft revision is `phenopacket_revisions.actor_id` on the most recent row with `to_state='draft'`. This determines who can `submit` / `withdraw` / `resubmit` the record. Admin overrides apply universally.

## 4. Schema

Two Alembic migrations, in order.

### 4.1 Migration 1 — `phenopackets.state` + `editing_revision_id`

```sql
ALTER TABLE phenopackets
  ADD COLUMN state TEXT NOT NULL DEFAULT 'draft'
    CHECK (state IN ('draft','in_review','changes_requested','approved','published','archived')),
  ADD COLUMN editing_revision_id BIGINT NULL;
CREATE INDEX ix_phenopackets_state ON phenopackets (state);
-- FK on editing_revision_id added in migration 2 (revisions table must exist first)
```

### 4.2 Migration 2 — `phenopacket_revisions`

```sql
CREATE TABLE phenopacket_revisions (
  id BIGSERIAL PRIMARY KEY,
  phenopacket_id TEXT NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
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
  UNIQUE (phenopacket_id, revision_number)
);

-- At most one "head published" row per phenopacket. Partial unique index
-- enforces the atomicity of the head swap (§5.2).
CREATE UNIQUE INDEX ux_head_published_per_record
  ON phenopacket_revisions (phenopacket_id)
  WHERE is_head_published = TRUE;

-- Activity lookups (latest revisions per phenopacket)
CREATE INDEX ix_revisions_phenopacket_created
  ON phenopacket_revisions (phenopacket_id, created_at DESC);

-- Add the FK from phenopackets.editing_revision_id deferred from migration 1
ALTER TABLE phenopackets
  ADD CONSTRAINT fk_phenopackets_editing_revision
    FOREIGN KEY (editing_revision_id)
    REFERENCES phenopacket_revisions(id)
    ON DELETE SET NULL;
```

### 4.3 Migration 3 — data migration for existing 864 rows

One-shot, idempotent:

1. Ensure a `system` user exists (create with role=`admin`, `is_active=FALSE`, `is_verified=TRUE`, username=`system`, random hashed password; used only as an audit actor).
2. For every existing phenopacket row:
   - Set `state = 'published'`
   - Insert one `phenopacket_revisions` row: `revision_number=phenopackets.revision`, `state='published'`, `content_jsonb=<current JSONB content>`, `change_patch=NULL`, `change_reason='Migrated from pre-D.1 data model'`, `actor_id=<system user id>`, `from_state=NULL`, `to_state='published'`, `is_head_published=TRUE`

After migration, every existing record is publicly visible exactly as before. **No public regression.**

## 5. Clone-to-draft edit flow

### 5.1 Editing a `published` record (clone path)

Triggered by `PUT /api/v2/phenopackets/{id}` when `phenopackets.state = 'published'`:

1. Open a `BEGIN` transaction.
2. If `phenopackets.editing_revision_id IS NOT NULL`, return `409 {"error_code": "edit_in_progress", "editing_revision_id": …, "editing_actor_id": …}`. One active edit per record at a time.
3. Insert new `phenopacket_revisions` row:
   - `revision_number = phenopackets.revision + 1`
   - `state = 'draft'`
   - `content_jsonb = <edited payload>`
   - `change_patch = jsonpatch(prev_head.content_jsonb, new_content)` (reuses existing `backend/app/utils/audit.py` helper)
   - `change_reason = <from request body>`
   - `actor_id = current_user.id`
   - `from_state = 'published'`
   - `to_state = 'draft'`
   - `is_head_published = FALSE`
4. Set `phenopackets.editing_revision_id = <new row id>`.
5. `phenopackets.state` and `phenopackets.content` stay unchanged — public GETs continue serving the old copy.
6. `COMMIT`.

### 5.2 Publishing a draft (head-swap path)

Triggered by `POST /api/v2/phenopackets/{id}/transitions` with `to_state='published'` from `approved`:

1. Open a `BEGIN` transaction.
2. Find the revision row to publish: it is the single revision with `state='approved'` for this phenopacket (the flow only approves one revision at a time — `approved` never coexists with another `approved` because subsequent edits re-enter `draft`). If `phenopackets.editing_revision_id` is set it must point to this row; otherwise 409.
3. Set all prior rows for this phenopacket to `is_head_published=FALSE` (idempotent — only one can ever be TRUE per partial unique index).
4. Set the new row's `is_head_published = TRUE`.
5. Copy the new row's `content_jsonb` into `phenopackets.content` (or equivalent — the existing "current content" columns).
6. Set `phenopackets.state = 'published'`, `phenopackets.editing_revision_id = NULL`, `phenopackets.revision = <new row's revision_number>`.
7. `COMMIT`.

The partial unique index ux_head_published_per_record guarantees two concurrent publishes cannot both set `is_head_published=TRUE` — the second `COMMIT` fails with a unique violation and the client retries.

### 5.3 Editing a non-published record (in-place path)

For `draft` / `changes_requested`: `PUT /api/v2/phenopackets/{id}` overwrites `content_jsonb` and `change_reason` on the existing in-progress draft revision. `revision_number` does **not** increment — it only increments when a transition creates a new revision row. State stays the same; no new revision row is created. This matches the "save draft → keep editing → eventually submit" mental model and keeps revision history focused on transition events rather than every keystroke-save.

## 6. API surface

### 6.1 New endpoints

```
POST   /api/v2/phenopackets/{id}/transitions
       auth: curator or admin (per guard matrix §3.1)
       body: { to_state: string, reason: string (min_length=1), revision: int (optimistic lock) }
       200:  { phenopacket: PhenopacketResponse, revision: RevisionResponse }
       409:  invalid_transition | revision_mismatch | edit_in_progress | forbidden_role
       400:  validation errors

GET    /api/v2/phenopackets/{id}/revisions
       auth: curator or admin (non-curators: 404)
       query: page[size], page[number], sort=-created_at
       200:  { data: RevisionResponse[], meta: { total } }

GET    /api/v2/phenopackets/{id}/revisions/{revision_id}
       auth: curator or admin
       200:  RevisionResponse (full content_jsonb + change_patch)
```

### 6.2 Changed semantics

```
PUT    /api/v2/phenopackets/{id}
       body unchanged
       new behavior:
         - if phenopackets.state == 'published': clone-to-draft path (§5.1)
         - otherwise: in-place path (§5.3)
         - 409 edit_in_progress if editing_revision_id is already set

GET    /api/v2/phenopackets/
GET    /api/v2/phenopackets/{id}
       new visibility filter:
         - non-curator callers see only state='published' records; the returned
           content is the content of the `is_head_published=TRUE` revision row.
         - curator/admin callers see all non-archived records; returned content
           is phenopackets.content as today.
         - archived records 404 for everyone except admin list queries with
           ?include=archived.

POST   /api/v2/phenopackets/
       default new record state = 'draft' (was implicitly "published" under pre-D.1 model)
       non-curator callers continue to 403 (unchanged)

DELETE /api/v2/phenopackets/{id}
       unchanged — soft-delete remains orthogonal to state; archived != deleted.
```

### 6.3 Pydantic schemas

```python
class TransitionRequest(BaseModel):
    to_state: Literal["draft","in_review","changes_requested","approved","published","archived"]
    reason: str = Field(min_length=1, max_length=500)
    revision: int

class RevisionResponse(BaseModel):
    id: int
    phenopacket_id: str
    revision_number: int
    state: str
    from_state: str | None
    to_state: str
    is_head_published: bool
    change_reason: str
    actor_id: int
    actor_username: str | None  # joined for display
    change_patch: list[dict] | None
    created_at: datetime
    # content_jsonb returned only from GET /{id}/revisions/{revision_id}, not list
```

## 7. Minimal D.1 frontend

Only enough to exercise the API. The rich GitHub-PR 3-lane review screen is D.3.

### 7.1 Components

- **`StateBadge.vue`** — colored chip component, 6 state variants, WCAG AA contrast
- **`TransitionMenu.vue`** — dropdown on the detail view, renders only transitions legal for (current state, current user role); each item opens a reason-required modal
- **`TransitionModal.vue`** — reason textarea (required, min 1 char) + confirm/cancel; calls `POST /transitions`
- **`EditingBanner.vue`** — shows on published records when `editing_revision_id IS NOT NULL`: "Draft in progress by @{actor_username} — started {relative_time}"

### 7.2 Changed views

- **`Phenopackets.vue`** (list) — adds state badge column (curators only; non-curators don't see state)
- **`PagePhenopacket.vue`** (detail) — adds state badge at top, `TransitionMenu` button group for curators/admins, `EditingBanner` conditional
- **`PhenopacketCreateEdit.vue`** — no new UI, but on save of a `published` record the backend now returns the new draft revision; surface a toast: "Draft saved — submit for review when ready"

### 7.3 Store

`authStore` unchanged. Phenopacket detail composable (`useSyncTask` pattern or a fresh `usePhenopacketState` composable) adds:
- `transitionTo(toState, reason)` — calls `POST /transitions`, refreshes record
- `fetchRevisions()` — lazy-loaded when a History tab opens (D.3 will consume this)

### 7.4 Routing & guards

No new routes. Visibility filter is enforced server-side; the router guard for `/phenopackets/:id` stays the same (visitor hits the detail URL, gets `published` content or 404).

## 8. Testing

### 8.1 Backend

- **Unit (transition guard matrix):** parametrized test — every role × every state × every attempted `to_state` (~30 cases); legal transitions succeed, illegal return `409 invalid_transition` or `403 forbidden_role`
- **Unit (clone-to-draft atomicity):** two concurrent `PUT /phenopackets/{id}` calls on the same published record — second returns `409 edit_in_progress`
- **Unit (head-swap atomicity):** simulated concurrent publishes on the same record — exactly one succeeds; the loser retries cleanly
- **Integration (full lifecycle):** `create (draft) → submit → request_changes → resubmit → approve → publish` end-to-end, asserting revision rows at each step
- **Integration (edit-published-record):** edit a published record, submit, approve, re-publish; assert old `is_head_published=FALSE`, new one `TRUE`, public GET returns new content, non-curator never saw the in-flight draft
- **Integration (visibility):** non-curator list / detail of records in every state except `published` returns 0 results / 404
- **Integration (archive is terminal):** `archived → *` all 409
- **Regression:** all 1,131 existing backend tests stay green (pytest + coverage ≥ 70%)

### 8.2 Frontend

- **Component:** `StateBadge.vue` renders every state variant
- **Component:** `TransitionMenu.vue` role-gating (curator sees subset, admin sees superset, viewer sees none)
- **Component:** `TransitionModal.vue` reason-required validation
- **E2E (Playwright):** login as curator → create draft → submit for review → login as admin → approve → publish → log out → verify public detail page shows new content

### 8.3 Test-data migration fixture

- Test that Alembic migration 3 on a fresh DB seeded with ≥ 5 pre-D.1 phenopackets results in: `phenopackets.state = 'published'` for all, one `phenopacket_revisions` row per record with `is_head_published=TRUE`, and public GET responses identical to pre-migration.

## 9. Rollout

1. Merge migrations + backend endpoints + minimal UI in one PR (Wave 7a).
2. Run data migration on staging; verify public endpoints unchanged (automated E2E + manual Playwright sniff).
3. Run data migration on prod during a low-traffic window; `deleted_at` and audit tables are untouched so rollback is `ALTER TABLE … DROP COLUMN state, editing_revision_id` + `DROP TABLE phenopacket_revisions` (destructive but safe — the `phenopackets.content` column is the fall-back truth).
4. Enable curator access to the new transitions UI. Non-curator public experience is byte-identical.

## 10. Open items deferred to D.2 / D.3

- Comment threads anchored to specific JSON Patch operations (`comments.anchor` JSONB per review §3.8)
- Soft-approval gate when unresolved comments exist
- GitHub-PR 3-lane review screen with Conversation / Changes / History tabs
- `json-diff-kit-vue` integration for rendering `change_patch` in the UI
- @-mention autocomplete from user directory
- CRediT role tagging on transition events (Bundle E)

## 11. Risks

- **Visibility filter regression** — if the non-curator filter is ever bypassed (e.g., a new aggregation endpoint forgets the `state='published'` guard), an in-progress draft could leak. Mitigation: mirror the `deleted_at IS NULL` global-filter pattern from Wave 5b — add a `state = 'published'` filter to `PhenopacketRepository.list_for_public()` and forbid any public-facing code path from using the raw repository. Add a pytest asserting every `GET /api/v2/phenopackets` shape filters by state when the caller is anonymous.
- **Performance** — adding state + revision join to the list endpoint could regress the cursor-pagination SLOs. Mitigation: the list endpoint already serves `phenopackets.content`; the only extra work is a state filter (indexed). Revisions are fetched separately (detail view / History tab). Measure before/after with the existing pgbench fixture.
- **Migration length** — seeding 864 revision rows is trivial; the one-shot migration is ≪ 1 s. Low risk.

## 12. Acceptance criteria

- [ ] All 8 transition types in §3.1 work with the stated role gates; 24 illegal cases return the stated errors.
- [ ] `PUT /phenopackets/{id}` on a `published` record creates a draft revision, does not mutate the public copy, sets `editing_revision_id`.
- [ ] Publishing a draft atomically swaps `is_head_published` and updates public content; concurrent publishes: one succeeds, one 409.
- [ ] Non-curator list/detail GETs return 0 records for every state except `published`.
- [ ] Data migration seeds existing 864 records into `state='published'` with a single `is_head_published=TRUE` revision each; public API responses byte-identical pre/post.
- [ ] Backend coverage ≥ 70%, new code ≥ 85%.
- [ ] Frontend coverage floor unchanged (30%); new components land with component tests.
- [ ] One Playwright E2E covering the full lifecycle lands and is a gating job.
- [ ] All 1,131 existing backend tests stay green.
