# Wave 7 / D.2 — Comments, Discussion, @-mentions + D.1 Clone-Cycle Advancement

**Date:** 2026-04-14
**Follows:** Wave 7 / D.1 (2026-04-12; PR #238, merged `26ee961`). Dep-bump wave (PR #252, `d518642`) is the baseline package set.
**Source review:** [docs/reviews/2026-04-11-platform-readiness-review.md](../../reviews/2026-04-11-platform-readiness-review.md) §3.8 and Bundle D items 14.
**Relation to D.1 spec:** [docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md](./2026-04-12-wave-7-d1-state-machine-design.md). This spec amends §3 of the D.1 spec with two new invariants (I8, I9) and rewires the routing inside `PhenopacketStateService`; it does NOT change the schema shipped by D.1.

This spec covers two things in a single PR:

- **Part A — D.1 clone-cycle advancement fix.** After a clone-to-draft edit of a published record, the state machine has no path forward (no `(published, in_review)` rule), cannot iterate (second PUT returns 409 `edit_in_progress`), and cannot withdraw. Part A resolves all three by introducing an "effective state" read-through on the `editing_revision_id` revision row, and locks `phenopackets.state` to `'published'` / `'archived'` after first publish.

- **Part B — D.2 comments + edits + mentions.** Generic `comments` table scoped by `(record_type, record_id)`, immutable `comment_edits` log, thin `comment_mentions` join table. Markdown-only body storage, client-side Tiptap editor, @-mention autocomplete. No threading, no anchored comments (D.3), no resolution-gate on `approve`, no notification delivery. Resolution **columns** are schema-ready; the gate is deferred.

D.3 (GitHub-PR 3-lane `PhenopacketReviewView.vue` + `json-diff-kit-vue` diff rendering + anchored comments) remains out of scope.

---

## 1. Purpose

Two bugs and one feature, shipped together because they touch the same curation workflow and it is cheaper to rewire the state machine once than twice.

**Bugs (Part A):** after a curator clones a published record to edit it, there is no mechanism to move that draft through review, iterate on it, or withdraw it. The Phase 6 E2E test `dual-read-invariant.spec.js` was deliberately truncated at re-publish convergence because of this (file:line ~244–258). This ships the fix and un-truncates that test.

**Feature (Part B):** curators need a place to discuss a record during review — disagreements about HPO terms, clarifications about pedigree, flags on variant pathogenicity. The review (§3.8) models this as the GitHub PR comments shape: one generic `comments` table, immutable edit log, mentions. v1 is the minimum that makes that usable on `PagePhenopacket.vue`.

---

## 2. Goals & non-goals

### Goals

- A curator who clones a published record can iteratively save, submit for review, be asked for changes, resubmit, and have the record re-published — all while the public continues to see the prior published copy (invariant I1 from D.1 preserved).
- `phenopackets.state` becomes a strict record-level lifecycle field: `'draft'`/`'in_review'`/`'changes_requested'`/`'approved'`/`'published'` only while a record has never been published, then `'published'` or `'archived'` for its remaining lifetime. All in-flight edit state lives on the revision row at `editing_revision_id`.
- Curators can post, edit, resolve, and soft-delete comments on any phenopacket. Edits are append-only audit-logged. Mentions are captured to a join table for future "mentions inbox" work.
- Tab-based UX on the existing detail view. No new routes.

### Non-goals (explicitly out of scope)

- **Threading** — no `parent_id` or `thread_root_id` in v1 comments; columns added later when the thread UI ships.
- **Anchored comments** — no `anchor` JSONB column in v1. D.3 will add it with the RFC 6902 pointer plumbing.
- **Approve-gate on unresolved comments** — §3.8 proposes a soft gate; v1 ships resolution columns but no gate. Wiring is a one-line future addition inside `state_service.transition()`.
- **Notification delivery** — no email, no inbox view, no `notifications` table. Mentions persist to `comment_mentions` and render highlighted in-place only.
- **`PhenopacketReviewView.vue` 3-lane layout + `json-diff-kit-vue`** — D.3.
- **Real-time updates** — the Discussion tab refetches on mount and manual refresh.
- **Viewer-role read access to comments** — viewers see no tab, no comments. Permissions matrix in §Permissions.
- **Rate-limiting on comment write endpoints** — accepted risk for v1; the existing middleware stack can add slowapi later with zero schema change.
- **`vuetify-pro-tiptap`** — bare Tiptap core + mention extension is sufficient; the pre-skinned variant is a later ergonomic tweak.
- **`body_rendered` column** — markdown-only storage (Q5 A); renderers live on the client.
- **Pagination modes beyond JSON:API offset** — cursor isn't worth it at expected comment volumes (<100 per record).

---

## 3. Invariants

### Part A additions to the D.1 invariants (§3 of D.1 spec)

#### I8 — `phenopackets.state` is sticky post-first-publish

Once `phenopackets.head_published_revision_id IS NOT NULL`, `phenopackets.state ∈ {'published', 'archived'}` for the rest of the record's lifetime. No transition, no write path, no migration may leave `pp.state` in `{'draft', 'in_review', 'changes_requested', 'approved'}` after the first publish has occurred.

Consequence: all edit-cycle progress on a previously-published record is reflected on the `editing_revision_id` revision row's `state` column, not on `pp.state`.

Enforced by: (a) a gated assignment in `PhenopacketStateService._simple_transition` (`pp.state = to_state` only fires when `head_published_revision_id IS NULL OR to_state == 'archived'`); (b) a dedicated parametrized test iterating every transition type after a first publish has landed.

#### I9 — Effective-state determinism

The function `PhenopacketStateService._effective_state(pp)` is pure over `(pp.state, pp.editing_revision_id, phenopacket_revisions[editing_revision_id].state)`. It depends on nothing else — not on caller role, request time, transaction isolation level, or cached data. Two calls within one transaction return the same value.

Consequence: `_effective_state` is safe to call from anywhere inside a service method, and the value it returns is the single authoritative "what state is this edit currently in" answer.

Enforced by: unit tests exercising every `(pp.state, editing_revision_id set?, revision.state)` triple.

### Part B invariants (new)

#### C1 — `comment_edits` is append-only

No application code path issues `UPDATE` or `DELETE` against `comment_edits`. Rows are inserted on each comment body update and never mutated. The editor_id, prev_body, and edited_at form a permanent record of what a given comment said at any historical point.

Enforced by: an AST-level test scanning `backend/app/` for any SQLAlchemy `update()` or `delete()` call targeting `comment_edits`, failing on match. Same defensive shape as the D.1 handler-audit test.

#### C2 — `comment_mentions` rows match the current body's mentions

After any write path (create or update_body), the set of `(comment_id, user_id)` rows in `comment_mentions` equals exactly the de-duplicated `mention_user_ids` list supplied in the most recent write for that comment. No stale rows survive an edit; no duplicates are possible (primary key enforces).

Historical mention state (what was mentioned in an old body) is recoverable by re-parsing `comment_edits.prev_body` if future code needs it. v1 does not re-parse.

Enforced by: the `update_body` service method uses a single-transaction "DELETE WHERE comment_id=?" + "INSERT ..." sequence, and a dedicated test asserts row-set equality after N successive edits.

#### C3 — Record reference integrity

On every comment create, the service resolves `(record_type, record_id)` to an actual record and rejects the write with 404 if the target does not exist. For v1 this means a `SELECT 1 FROM phenopackets WHERE id = record_id LIMIT 1` check. Soft-deleted records (`deleted_at IS NOT NULL`) are acceptable targets — a comment may outlive a soft-delete, and curators may want to discuss a record even as it is being removed.

No FK constraint is added on `comments.record_id` because `record_type` is polymorphic and Postgres does not support cross-table polymorphic FKs cleanly. Reference integrity is an app-layer contract, not a DB invariant.

Enforced by: the `create` service method's existence check plus a dedicated test covering the not-exists and soft-deleted cases.

#### C4 — Author is always curator-or-admin at write time

Every row in `comments`, `comment_edits`, and `comment_mentions` was produced by a caller whose role at the time of the write was `'curator'` or `'admin'`. Viewer role cannot produce any row directly or transitively.

Enforced by: `require_curator` dependency on all write endpoints, plus parametrized permissions tests.

#### C5 — Resolved/deleted consistency

`comments.resolved_at IS NULL ⇔ comments.resolved_by_id IS NULL`. Same for `deleted_at ⇔ deleted_by_id`. A comment is either resolved with an actor or not resolved at all; the actor is never anonymous. Deleted with an actor or not deleted at all.

Enforced by: CHECK constraints in the migration (DDL given in §5.1).

---

## 4. Part A — Effective-state routing (D.1 follow-up)

### 4.1 Contract

`phenopackets.state` is the **record-level** lifecycle:
- For a never-published record: tracks the in-flight state (`draft → in_review → ...`). Unchanged from D.1.
- For a record that has reached `'published'` at least once: locked at `'published'` or `'archived'`. Never moves through draft-side states.

The **in-flight edit state** on a previously-published record lives on the `editing_revision_id` revision row. As the clone-cycle progresses, that pointer moves forward through new revision rows with increasing state (draft → in_review → approved), while `pp.state` stays `'published'`.

The function `_effective_state(pp)` returns the one "what state is this edit at right now" answer, whichever axis owns it.

### 4.2 Code changes — file by file

#### 4.2.1 `backend/app/phenopackets/services/state_service.py`

Add:

```python
async def _effective_state(self, pp: Phenopacket) -> State:
    """Return the state governing edit-cycle decisions for this phenopacket.

    If an edit is in flight (editing_revision_id set), the in-flight
    revision row's state is authoritative. Otherwise pp.state.
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

Modify `edit_record`:
- Dispatch on `await self._effective_state(pp)`, not `pp.state`.
- `effective == 'published'` → `_clone_to_draft` (only hit when `editing_revision_id IS NULL`).
- `effective IN {'draft', 'changes_requested'}` → `_inplace_save`.
- `effective IN {'in_review', 'approved'}` → `InvalidTransition("edit_forbidden: withdraw or resubmit first")`.
- `effective == 'archived'` → `InvalidTransition("cannot edit archived record")`.

Modify `_simple_transition`:
- Read `from_state = await self._effective_state(pp)` BEFORE any mutation.
- Pass `from_state` to `check_transition` (not `pp.state`).
- Store that same `from_state` on the new revision row's `from_state` column.
- Gate the `pp.state = to_state` assignment:
  ```python
  if pp.head_published_revision_id is None or to_state == "archived":
      pp.state = to_state
  # else: pp.state is sticky (I8) — only the revision row's state advances
  ```
- `editing_revision_id := rev.id` (except on archive, where it is cleared).
- On archive, also clear `pp.draft_owner_id` (unchanged from current code).

Modify `transition`:
- Pass `await self._effective_state(pp)` as `from_state` to `check_transition`.
- Error messages that reference `pp.state` now reference the effective state.

`_publish`: **no change needed**. The head-swap logic searches `phenopacket_revisions WHERE state='approved'` and works for both never-published and clone-cycle paths. `pp.state = 'published'` on the last line is a no-op for clone-cycle (was already `'published'`).

`_clone_to_draft` and `_inplace_save`: **no changes**.

#### 4.2.2 `backend/app/phenopackets/services/transitions.py`

**No changes.** The `_RULES` dict already covers every `(from, to)` pair the effective-state routing needs.

#### 4.2.3 `backend/app/phenopackets/routers/transitions.py`

Response builder additions in `post_transition` (and wherever `build_phenopacket_response` is called in ways the frontend will read):

```python
pp_dict["effective_state"] = await svc._effective_state(pp_reloaded)
```

Add `effective_state: str | None` to `PhenopacketResponse` (backend schema).

#### 4.2.4 Frontend

- `frontend/src/components/StateBadge.vue` — rebind to `phenopacket.effective_state`.
- `frontend/src/components/TransitionMenu.vue` — call `allowed_transitions(effective_state, role, is_owner)` (already pure; no backend change).
- `frontend/src/composables/usePhenopacketState.js` — expose `effective_state`.
- `frontend/src/components/EditingBanner.vue` — verify it uses `editing_revision_id != null` as the condition (already does; no change).

### 4.3 Mutation sequences under the clone-cycle

Starting state after `_clone_to_draft`: `pp.state='published'`, `editing_revision_id → DRAFT_ROW` (state=`'draft'`), `head_published_revision_id → ORIGINAL_ROW`, `draft_owner_id = curator.id`.

| Action | `check_transition` args | New / mutated revision row | `pp.state` | `editing_revision_id` | `head_published_revision_id` | `draft_owner_id` |
|---|---|---|---|---|---|---|
| submit | `(draft → in_review)` | INSERT REVIEW_ROW (`from='draft'`, `to='in_review'`) | published (unchanged, I8) | → REVIEW_ROW | unchanged | unchanged |
| withdraw | `(in_review → draft)` | INSERT DRAFT2_ROW | unchanged | → DRAFT2_ROW | unchanged | unchanged |
| request_changes | `(in_review → changes_requested)` | INSERT CR_ROW | unchanged | → CR_ROW | unchanged | unchanged |
| inplace save (draft/CR) | — | UPDATE editing row's `content_jsonb` + `change_reason` | unchanged | unchanged | unchanged | unchanged |
| resubmit | `(changes_requested → in_review)` | INSERT REVIEW2_ROW | unchanged | → REVIEW2_ROW | unchanged | unchanged |
| approve | `(in_review → approved)` | INSERT APPROVED_ROW | unchanged | → APPROVED_ROW | unchanged | unchanged |
| **publish** | `(approved → published)` | UPDATE APPROVED_ROW: `state='published'`, `to_state='published'`, `is_head_published=TRUE`; UPDATE prev head: `is_head_published=FALSE` | published (no-op, already) | **NULL** | → APPROVED_ROW | **NULL** |
| archive | `(effective → archived)` | INSERT archive row | **'archived'** | **NULL** | unchanged (preserved for audit per I3) | **NULL** |

Never-published path is unchanged from D.1 §6.

### 4.4 Tests (Part A)

- `test_state_service_effective_state.py` — unit tests over every `(pp.state, editing_revision_id set?, rev.state)` triple.
- `test_state_service_clone_cycle.py` — full cycle (clone → submit → request_changes → inplace → resubmit → approve → publish), asserting `pp.state`, `pp.head_published_revision_id`, `pp.editing_revision_id`, `pp.draft_owner_id`, and the chain of revision rows at every step.
- `test_state_service_clone_iteration.py` — N consecutive PUTs in a clone-cycle all succeed as inplace-saves.
- `test_state_service_clone_withdraw.py` — withdraw after submit returns effective state to `'draft'`; `pp.state` remains `'published'`.
- `test_state_service_invariant_i8.py` — parametrized over every transition type after the first publish. `pp.state` never exits `{'published','archived'}`.
- `frontend/tests/e2e/dual-read-invariant.spec.js` — the truncated "re-publish convergence" phase is implemented. After full cycle republish, anon and curator GETs converge on the new content. The NOTE comment (file lines ~244–258) is removed.

---

## 5. Part B — Comments, Edits, Mentions

### 5.1 Schema

Three Alembic migrations, applied in order after Part A code lands (no data migration; both features operate on empty tables or non-disruptive routing).

#### Migration B1 — `comments`

```sql
CREATE TABLE comments (
  id              BIGSERIAL PRIMARY KEY,
  record_type     TEXT NOT NULL,
  record_id       UUID NOT NULL,
  author_id       BIGINT NOT NULL REFERENCES users(id),
  body_markdown   TEXT NOT NULL CHECK (char_length(body_markdown) BETWEEN 1 AND 10000),
  resolved_at     TIMESTAMPTZ NULL,
  resolved_by_id  BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ NULL,
  deleted_by_id   BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT chk_resolved_consistency
    CHECK ((resolved_at IS NULL) = (resolved_by_id IS NULL)),
  CONSTRAINT chk_deleted_consistency
    CHECK ((deleted_at IS NULL) = (deleted_by_id IS NULL))
);

CREATE INDEX ix_comments_record
  ON comments (record_type, record_id, created_at ASC)
  WHERE deleted_at IS NULL;

CREATE INDEX ix_comments_author ON comments (author_id);

CREATE INDEX ix_comments_unresolved
  ON comments (record_type, record_id)
  WHERE resolved_at IS NULL AND deleted_at IS NULL;
```

**Schema deviations from §3.8:**
- No `parent_id`, `thread_root_id` — threading deferred.
- No `body_rendered` — markdown-only (Q5 A).
- No `anchor jsonb` — D.3.

No FK on `record_id` — polymorphic, enforced at app layer (C3).

#### Migration B2 — `comment_edits`

```sql
CREATE TABLE comment_edits (
  id           BIGSERIAL PRIMARY KEY,
  comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
  editor_id    BIGINT NOT NULL REFERENCES users(id),
  prev_body    TEXT NOT NULL,
  edited_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_comment_edits_comment
  ON comment_edits (comment_id, edited_at DESC);
```

`comments.body_markdown` holds the CURRENT body. On edit: the OLD body snapshots to `comment_edits.prev_body` BEFORE the UPDATE overwrites `comments.body_markdown`. History reconstruction = walk `comment_edits` reverse-chronologically + append current body.

Immutability of `comment_edits` (C1) is a service-layer contract enforced by the AST test.

#### Migration B3 — `comment_mentions`

```sql
CREATE TABLE comment_mentions (
  comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
  user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (comment_id, user_id)
);

CREATE INDEX ix_comment_mentions_user ON comment_mentions (user_id);
```

Replace-atomic on edit (C2). `ON DELETE CASCADE` on user_id so hard-deleted users (if it ever happens) don't leak orphan mention rows; the `@username` text in the body stays as historical record.

### 5.2 Permissions matrix

| Action | viewer | curator | admin |
|---|---|---|---|
| read comments on a record | 403 | ✓ | ✓ |
| create | 403 | ✓ | ✓ |
| edit own body *(writes `comment_edits` row with `prev_body`)* | — | ✓ | ✓ |
| edit others' body | — | 403 | **403** |
| soft-delete own | — | ✓ | ✓ |
| soft-delete others | — | 403 | ✓ |
| resolve / unresolve (any) | — | ✓ | ✓ |
| list edit history (`GET /comments/{id}/edits`) | 403 | ✓ | ✓ |
| `?include=deleted` | 403 | ✓ | ✓ |

Admin cannot edit other users' comment bodies — the review (§3.8) requires edit history to be immutable, and "admin can silently rewrite another curator's assertion" undermines that even if the old body is logged. Admins soft-delete; they do not rewrite.

Viewer role: no access anywhere. Viewers cannot see records in non-published states per D.1, so they have no context for curation discussions and granting read-only access creates an awkward asymmetry.

### 5.3 API surface

All endpoints under `/api/v2/comments`. JSON:API v1.1 pagination per CLAUDE.md.

```
POST   /api/v2/comments
       auth: curator or admin
       body: {
         record_type: "phenopacket",
         record_id: "<uuid>",
         body_markdown: string (1–10000 chars),
         mention_user_ids: int[]        # optional, deduped server-side, max 50
       }
       201:  CommentResponse
       400:  validation_error
       403:  forbidden_role (viewer)
       404:  record_not_found           # C3 failure
       422:  mention_unknown_user       # any id not resolvable to active curator/admin

GET    /api/v2/comments
       auth: curator or admin
       query:
         filter[record_type]  = "phenopacket"
         filter[record_id]    = <uuid>
         filter[resolved]     = "true" | "false"   # optional
         include              = "deleted"           # curator or admin; soft-deleted comments included with full body
         page[number], page[size]  (default 50, max 200)
       200:  { data: CommentResponse[], meta: { total } }
       sort: fixed, created_at ASC (not user-configurable)

GET    /api/v2/comments/{id}
       auth: curator or admin
       200:  CommentResponse
       404:  not_found or soft-deleted (unless curator/admin + include=deleted)

PATCH  /api/v2/comments/{id}
       auth: author only (admin CANNOT edit others' body — matrix)
       body: { body_markdown: string, mention_user_ids: int[] }
       side effects (single transaction):
         1. INSERT comment_edits(comment_id, editor_id=current_user.id, prev_body=<current body>)
         2. UPDATE comments SET body_markdown=?, updated_at=now()
         3. DELETE comment_mentions WHERE comment_id=?
         4. INSERT comment_mentions FROM new id list
       200:  CommentResponse
       403:  forbidden_not_author
       404:  not_found
       422:  mention_unknown_user

POST   /api/v2/comments/{id}/resolve
       auth: curator or admin
       200:  CommentResponse (resolved_at=now(), resolved_by_id=current_user.id)
       409:  already_resolved

POST   /api/v2/comments/{id}/unresolve
       auth: curator or admin
       200:  CommentResponse (both resolved_* fields cleared)
       409:  not_resolved

DELETE /api/v2/comments/{id}
       auth: author (any curator) OR admin
       side effect: soft-delete (deleted_at=now(), deleted_by_id=current_user.id)
       comment_edits and comment_mentions are NOT deleted
       204:  no content
       403:  forbidden (curator who isn't the author)

GET    /api/v2/comments/{id}/edits
       auth: curator or admin
       200:  { data: CommentEditResponse[] }    # reverse-chronological
```

### 5.4 Pydantic schemas

```python
class CommentMentionOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    is_active: bool           # UI dims deactivated mentioned users

class CommentResponse(BaseModel):
    id: int
    record_type: str
    record_id: str            # UUID serialized
    author_id: int
    author_username: str
    author_display_name: str | None
    body_markdown: str
    mentions: list[CommentMentionOut]
    edited: bool              # derived: EXISTS(comment_edits WHERE comment_id=id)
    resolved_at: datetime | None
    resolved_by_id: int | None
    resolved_by_username: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    deleted_by_id: int | None

class CommentCreate(BaseModel):
    record_type: Literal["phenopacket"]
    record_id: UUID
    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: list[int] = Field(default_factory=list, max_length=50)

class CommentUpdate(BaseModel):
    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: list[int] = Field(default_factory=list, max_length=50)

class CommentEditResponse(BaseModel):
    id: int
    editor_id: int
    editor_username: str
    prev_body: str
    edited_at: datetime
```

### 5.5 Service layer

New module `backend/app/comments/` with:

- `backend/app/comments/models.py` — SQLAlchemy ORM for `Comment`, `CommentEdit`, `CommentMention`.
- `backend/app/comments/service.py` — `CommentsService(db)` with methods `create`, `update_body`, `resolve`, `unresolve`, `soft_delete`, `list_for_record`, `list_edits`.
- `backend/app/comments/routers.py` — FastAPI router with the eight endpoints.
- `backend/app/comments/schemas.py` — the Pydantic models above.

Each module ≤ 500 lines per CLAUDE.md §Code Quality Principles. Every mutating service method opens a single async transaction and commits at the end; the `update_body` method performs the three-step atomic sequence (edit log INSERT → body UPDATE → mentions replace).

### 5.6 Authorization helpers

`backend/app/auth/dependencies.py` gains:

- `require_comment_author_or_admin(comment_id: int)` — dependency factory for PATCH (author only) and DELETE (author or admin). The body-edit path additionally rejects admin-when-not-author with 403 even though the generic dependency would pass, because the matrix forbids admin body edits.

### 5.7 Mentionable-users endpoint

Autocomplete backing: reuse the existing `GET /api/v2/auth/users` admin-only endpoint is wrong (too privileged). Add:

```
GET /api/v2/comments/mentionable-users?q=<prefix>
    auth: curator or admin
    query: q (required, min 2 chars)
    200: { data: [{id, username, display_name}] }
    limit: 20 results, sorted by username ASC
    filter: role IN ('curator','admin') AND is_active=TRUE
```

`q ≥ 2 chars` defends against list-scraping (risk #1 in §8).

### 5.8 Frontend

#### 5.8.1 New dependencies (all MIT)

- `@tiptap/core`, `@tiptap/vue-3`, `@tiptap/starter-kit`, `@tiptap/extension-mention` — editor + autocomplete.
- `markdown-it` — server responses ship raw markdown; client renders to HTML.
- `@tiptap/extension-markdown` (or `tiptap-markdown`) — markdown round-trip for the composer.

Lazy-loaded via dynamic import inside the `DiscussionTab.vue` component. Approximate bundle delta: 80 KB gzipped; only paid by users who open the tab.

`vuetify-pro-tiptap` is **not** adopted v1. Bare Tiptap is sufficient; the pre-skinned variant can be a later ergonomic tweak.

#### 5.8.2 API client

`frontend/src/api/domain/comments.js`:

```js
export async function listComments({ recordType, recordId, page, size, includeDeleted, resolved })
export async function getComment(id)
export async function createComment({ recordType, recordId, bodyMarkdown, mentionUserIds })
export async function updateComment(id, { bodyMarkdown, mentionUserIds })
export async function resolveComment(id)
export async function unresolveComment(id)
export async function deleteComment(id)
export async function listCommentEdits(id)
export async function searchMentionableUsers(q)
```

Composable `frontend/src/composables/useComments.js` returns `{ comments, total, loading, load(), post(), edit(), resolve(), unresolve(), remove() }`. State is local to the detail page; leaving the page discards it.

#### 5.8.3 Components

```
frontend/src/components/comments/
  DiscussionTab.vue          — top-level, mounted in PagePhenopacket tab
  CommentList.vue            — chronological list
  CommentItem.vue            — single comment card
  CommentEditHistory.vue     — collapsible "edited" expander, lazy-loads GET /edits
  CommentComposer.vue        — Tiptap editor + mention autocomplete + submit
  CommentBody.vue            — markdown-it render → HTML, @mention hover-link, v-html sanitized
```

Six files, each ≤ 300 lines.

#### 5.8.4 Changed views

- `frontend/src/views/PagePhenopacket.vue` — adds fourth tab `DISCUSSION`, conditionally rendered when `user.role in ['curator','admin']`. Tab label: `Discussion (N)` where N is the total comment count; when unresolved_count > 0 the label becomes `Discussion (N, M open)`. Badge data comes from two cheap queries in the composable on mount: `filter[record_id]=?&page[size]=1` for total, and `filter[resolved]=false&page[size]=1` for open count; cached 30s.

#### 5.8.5 Logging

Every mutation logs through `window.logService.info/warn/error` per CLAUDE.md. Comment body is NOT logged (could contain clinical free-text). Logs include `{comment_id, record_id, action}` only.

#### 5.8.6 Routing and guards

No new routes. No router-guard changes. Tab visibility is client-side; backend is the source of truth and returns 403 for viewer-role reads.

---

## 6. Combined mutation sequences (reference)

### 6.1 Creating a comment

```
POST /api/v2/comments
Transaction:
  1. SELECT 1 FROM phenopackets WHERE id=record_id      -- C3
  2. For each mention_user_id:
     SELECT id FROM users WHERE id=? AND is_active=TRUE AND role IN ('curator','admin')
     422 on any miss
  3. INSERT INTO comments (...)
  4. For each mention_user_id:
     INSERT INTO comment_mentions (comment_id, user_id)
  5. COMMIT
Response: CommentResponse (201)
```

### 6.2 Editing a comment body

```
PATCH /api/v2/comments/{id}
Transaction:
  1. SELECT * FROM comments WHERE id=? FOR UPDATE
  2. 403 forbidden_not_author if author_id != current_user.id
  3. Validate mention_user_ids (same check as create)
  4. INSERT INTO comment_edits (comment_id, editor_id, prev_body=<current body>)
  5. UPDATE comments SET body_markdown=?, updated_at=now() WHERE id=?
  6. DELETE FROM comment_mentions WHERE comment_id=?
  7. INSERT INTO comment_mentions (...)
  8. COMMIT
Response: CommentResponse (200)
```

### 6.3 Resolving / unresolving

```
POST /api/v2/comments/{id}/resolve
Transaction:
  1. SELECT * FROM comments WHERE id=? FOR UPDATE
  2. 409 already_resolved if resolved_at IS NOT NULL
  3. UPDATE comments SET resolved_at=now(), resolved_by_id=current_user.id, updated_at=now() WHERE id=?
  4. COMMIT
```

### 6.4 Soft-deleting

```
DELETE /api/v2/comments/{id}
Transaction:
  1. SELECT * FROM comments WHERE id=? FOR UPDATE
  2. Permissions: author OR admin (403 otherwise)
  3. UPDATE comments SET deleted_at=now(), deleted_by_id=current_user.id, updated_at=now() WHERE id=?
  4. COMMIT
```

---

## 7. Testing

### 7.1 Backend — Part A

- `test_state_service_effective_state.py` — unit over every `(pp.state, editing_revision_id set?, rev.state)` triple.
- `test_state_service_clone_cycle.py` — create → submit → approve → publish, then edit → submit → request_changes → inplace → resubmit → approve → publish; assert pointers, state, revision chain at every step.
- `test_state_service_clone_iteration.py` — N consecutive PUTs route to inplace-save after first clone.
- `test_state_service_clone_withdraw.py` — withdraw in clone-cycle preserves `pp.state='published'`.
- `test_state_service_invariant_i8.py` — parametrized sticky-state check.

### 7.2 Backend — Part B

- `test_comments_crud.py` — create, list, detail, update, soft-delete happy paths.
- `test_comments_permissions.py` — parametrized over 4 roles × 8 actions.
- `test_comments_edit_log.py` — edit creates a `comment_edits` row with the correct `prev_body`.
- `test_comments_mentions_replace.py` — C2 test: row-set equality after N successive edits.
- `test_comments_record_integrity.py` — C3 test: non-existent record_id → 404; soft-deleted record → 201.
- `test_comments_resolve.py` — resolve, unresolve, 409 on double-resolve.
- `test_comments_soft_delete.py` — deleted comment hidden by default; body redacted to "[deleted]" for curators with `?include=deleted`, full body for admins.
- `test_comments_mention_unknown_user.py` — 422 on unknown / deactivated / non-curator mention.
- `test_comments_ast_immutable.py` — AST scan: no `update()`/`delete()` against `comment_edits`.
- `test_comments_mentionable_users.py` — q < 2 chars → 400; role and is_active filters applied.

### 7.3 Frontend tests

- Component tests: `CommentItem` (renders author, body, edited badge, resolve chip), `CommentComposer` (mention autocomplete triggers on `@`, submit disabled on empty), `CommentEditHistory` (lazy-loads on expand), `CommentBody` (markdown-it output sanitized; `<script>`, `<img onerror>` inert).
- E2E Playwright: login as curator → open phenopacket → post comment → edit → verify edited label + history → login as admin → soft-delete → verify list state. One spec.

### 7.4 Regression

All existing backend and frontend tests stay green. Backend coverage ≥ 70%; new code ≥ 85%. Frontend floor 30%.

---

## 8. Risks

1. **Mention autocomplete user-enum leak.** Curator sees the username list of other curators and admins. They're trusted; admins are already publicly visible via author bylines. Mitigation: `q ≥ 2` chars requirement; limit 20 results. Severity: low.

2. **XSS via markdown body.** `markdown-it` rendering user input to HTML. Mitigation: `markdown-it` instantiated with `html: false`; output passes through `frontend/src/utils/sanitize.js` before `v-html`. Dedicated test that `<script>`, `<img onerror>` in a comment body do not execute.

3. **Immutability bypass.** Someone later adds a "fix typo" endpoint that UPDATEs `comment_edits`. Mitigation: C1 AST test.

4. **Effective-state regression.** Future code reads `pp.state` directly and assumes it reflects the edit cycle. Mitigation: the I8 test plus a grep-level lint (same shape as the D.1 handler-audit AST check) flagging direct reads of `pp.state` outside `state_service.py` and `phenopackets/repositories.py`.

5. **Tiptap bundle weight.** 80 KB gzip on a tab most users won't open. Mitigation: lazy-load; measured before merge.

6. **Mention race: user deactivated between autocomplete and save.** POST validates active status at save time → 422; user retries without the offender. Acceptable.

7. **No rate-limit on comment writes.** A compromised curator account could flood a record with comments. Mitigation: accepted risk for v1; slowapi can land later with no schema change. Every write is authenticated + role-gated.

---

## 9. Rollout

1. Single PR titled `feat(wave-7-d2): effective-state routing + comments/edits/mentions`.
2. Order within the PR: Part A code changes (no migration); then Part B migrations B1 → B2 → B3; then Part B backend + frontend.
3. CI (`make check` in both backend and frontend) must pass.
4. Deploy during a low-traffic window. The Part A change is behaviorally invisible to the public; Part B is additive.
5. Rollback: the Part A change reverts via `git revert`; the Part B migrations drop cleanly in reverse (B3 → B2 → B1). No data migration means no rollback data hazard.

---

## 10. Acceptance criteria

### Part A

- [ ] `backend/app/phenopackets/services/state_service.py` has `_effective_state(pp)`; `edit_record`, `_simple_transition`, and `transition` all route on it.
- [ ] `PhenopacketResponse.effective_state` field populated in router responses.
- [ ] Frontend `StateBadge`, `TransitionMenu`, `usePhenopacketState` read `effective_state`.
- [ ] After clone-to-draft, a curator can iteratively save (no 409 `edit_in_progress`), submit, request_changes, resubmit, approve, and publish without DB intervention.
- [ ] After clone-to-draft, withdraw returns effective state to `'draft'` with `pp.state='published'`.
- [ ] Invariants I8 and I9 each have a dedicated failing-on-regression test.
- [ ] All D.1 acceptance criteria from the 2026-04-12 spec remain satisfied.
- [ ] `frontend/tests/e2e/dual-read-invariant.spec.js` phase 5 (re-publish convergence) is implemented, green, and the NOTE comment at lines ~244–258 is removed.

### Part B

- [ ] All eight endpoints in §5.3 plus the mentionable-users endpoint (§5.7) implemented, OpenAPI-documented, and parametrized-tested.
- [ ] Permissions matrix enforced: viewer 403 on every endpoint; admin 403 on PATCH when not author; every other matrix cell passes its test.
- [ ] C1 (append-only edit log) enforced by AST test.
- [ ] C2 (mention row-set equality) test green after N iterations.
- [ ] C3 (record reference integrity) test green for not-exists (404) and soft-deleted (201) cases.
- [ ] CHECK constraints from C5 present in the migration; a test attempts violating inserts at the DB level and asserts `IntegrityError` is raised.
- [ ] Discussion tab hidden for viewers; curator+ sees it; comment-count badge renders; open-count badge renders when any unresolved comment exists.
- [ ] E2E flow (curator posts → edits → admin soft-deletes) green in one Playwright spec.
- [ ] XSS sanitization test green: `<script>` / `<img onerror>` in a body render inert.

### Combined

- [ ] All existing backend tests (≥ 1,131 post-D.1) stay green.
- [ ] `make check` green in `backend/` and `frontend/`.
- [ ] Backend coverage ≥ 70%; new code ≥ 85%. Frontend coverage floor 30% unchanged.
- [ ] One PR covers both parts; commits inside the PR atomic per logical unit (Part A code, B1, B2, B3, services, routers, frontend).

---

## 11. Deferred to future bundles

- **D.3** — anchored comments (RFC 6902 `anchor jsonb`), `json-diff-kit-vue` diff rendering, `PhenopacketReviewView.vue` 3-lane layout, tiptap-based anchor pinning UI.
- **Threading** — `parent_id` + `thread_root_id` columns nullable-added when the thread UI ships.
- **Approve-gate on unresolved comments** — one-line addition in `state_service.transition()` plus a parametrized test when product signals it's needed.
- **Notifications** — `GET /me/mentions` list endpoint + optional email pipeline + inbox view.
- **Rate-limiting** — slowapi on `/comments` POST/PATCH endpoints if abuse surfaces.
- **`vuetify-pro-tiptap`** — migrate the composer for ergonomic polish if the bare Tiptap UX proves rough.
- **Full-text search on comments** — generated `tsvector` column from `body_markdown`; GIN index; optional search endpoint.
- **"My mentions" dashboard card** — trivial query over `comment_mentions WHERE user_id = me`.
