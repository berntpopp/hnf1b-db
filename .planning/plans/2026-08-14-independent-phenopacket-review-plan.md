# Independent Phenopacket Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an end-to-end four-eyes Phenopacket workflow with an open curator review queue, revision-bound blocking issues, exact immutable sign-off, admin publication, and private pre-publication content.

**Architecture:** Preserve the existing dual-head revision state machine and add a focused review domain (`policy`, `queries`, `schemas`, `router`) rather than a second workflow model. Canonicalize before review, hash the complete candidate, serialize application and direct-SQL writers on the phenopacket row, and make backend capabilities authoritative. Add a server-driven Vue review queue/workspace that consumes the new DTOs and reuses existing Phenopacket, history, comment, and table primitives.

**Tech Stack:** FastAPI, Python 3.10+ (CI Python 3.12), async SQLAlchemy/asyncpg, PostgreSQL JSONB/triggers, Alembic, Pydantic, pytest; Vue 3 Composition API with `<script setup>`, Vuetify 4, Pinia/Axios, Vitest, Playwright, npm.

## Global Constraints

- The approved design is `.planning/specs/2026-08-14-independent-phenopacket-review-design.md`; its one-pass review is `.planning/reviews/2026-08-14-independent-phenopacket-review-spec-review.md`.
- Preserve `draft -> in_review -> changes_requested -> in_review -> approved -> published`; do not collapse `changes_requested` into `draft`.
- The open queue is visible only to active curators/admins; there is no assignment, claiming, bulk approval, new editor role, or panel quorum.
- Owner, active candidate submitter, and active-cycle content contributors cannot approve or request changes; admins never bypass independence.
- Only revision-bound blocking issues gate approval; ordinary and historical comments remain non-blocking.
- Canonicalize and validate before `in_review`; approval and publication copy canonical content unchanged and verify the complete `content_jsonb` digest.
- Public reads stay pinned to `head_published_revision_id`; an old public head remains public during re-review.
- All backend code remains async-first and routers/services/repositories stay separated.
- All queue pagination, filtering, and sorting is server-driven; `AppDataTable` remains in server mode.
- Frontend local imports use `@/`; no `console.log`; use `window.logService`.
- New production-sensitive paths fail closed with stable structured errors.
- Existing append-only revision rows are never rewritten to reconstruct historical roles or v2 hashes.
- Schema rollback preserves audit data and refuses destructive downgrade after activation data exists.
- Use TDD for every implementation task, small intentional commits, and relevant verification before integration.

## File and ownership map

| Area | Files | Responsibility |
| --- | --- | --- |
| Schema | `backend/app/phenopackets/models.py`, `backend/app/comments/models.py`, two new Alembic revisions | Nullable expansion, resolution-event ledger, lock/constraint activation |
| Revision integrity | `backend/app/phenopackets/services/revision_ledger.py`, `state_service.py`, `phenopacket_service.py` | Full-content digest, v2 ledger hash, canonical freeze, exact approval/publication |
| Review policy | `backend/app/phenopackets/review/policy.py`, `schemas.py` | Independence, capabilities, typed errors and DTOs |
| Review queries/API | `backend/app/phenopackets/review/repository.py`, `service.py`, `backend/app/phenopackets/routers/review.py` | Queue, coherent review context, semantic changes |
| Review issues | `backend/app/comments/service.py`, `schemas.py`, `routers.py` | Blocking issue create/resolve/reopen/retract semantics and transaction boundaries |
| Frontend transport | `frontend/src/api/domain/reviews.js`, `phenopackets.js`, `comments.js`, review composables | DTO calls, mutation payloads, state refresh/error handling |
| Frontend queue | `frontend/src/views/ReviewQueue.vue` | URL-backed server table, filters, loading/error/empty/mobile states |
| Frontend workspace | `frontend/src/views/PhenopacketReview.vue`, `frontend/src/components/review/*` | Semantic diff, issues, audit, actions, responsive/a11y behavior |
| Navigation/policy consumers | router, app bar, drawer, state menu, Phenopacket detail | Curator guards/links and server-authoritative capabilities |
| End-to-end contract | backend OpenAPI snapshot/tests, frontend Playwright | Two-user lifecycle, visibility, concurrency/conflict, public-head invariants |

## Acceptance coverage map

| Design criterion | Planned proof |
| --- | --- |
| 1. Owner/submitter/contributor cannot decide | Tasks 3-5 policy/service/API tests; Tasks 10-12 UI and distinct-actor E2E |
| 2. Eligible curator/admin can review without assignment | Tasks 3 and 6 policy/queue tests; Task 12 E2E |
| 3. Unresolved issue blocks approval under races | Task 5 service, migration, and four-order raw-SQL tests |
| 4. Exact approval audit | Tasks 1-4 schema, digest, snapshot, and ledger tests |
| 5. Exact mutation-free publication | Task 4 canonicalizer-spy/content-equality tests; Task 12 E2E |
| 6. Candidate privacy and old public head | Tasks 4 and 6 visibility tests; Task 12 two-cycle E2E |
| 7. Server-driven effective-state queue | Tasks 6 and 8 query/count/URL/table tests |
| 8. Complete responsive workspace | Tasks 9-10 component, accessibility, build, and mobile tests |
| 9. Historical comments remain non-blocking | Tasks 1 and 5 migration/backward-compatibility tests |
| 10. All verification layers pass | Tasks 12-13 focused/full/migration/E2E/Actions checks |
| 11. Independent reviews adjudicated | Existing spec-review artifact and Task 13 one-pass PR review artifact |

---

### Task 1: Expand the persistence model without activating workflow constraints

**Files:**

- Create: `backend/alembic/versions/d0f422b00005_expand_independent_review_audit.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/app/phenopackets/models.py`
- Modify: `backend/app/comments/models.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/migration/test_independent_review_expand_migration.py`
- Create: `backend/tests/test_review_models.py`
- Modify: `backend/tests/test_alembic_env_autogenerate.py`

**Interfaces:**

- Produces `PhenopacketRevision.actor_role: str | None`, `decision_metadata: dict[str, Any] | None`, `content_sha256: str | None`, and `ledger_version: int | None`.
- Produces `Comment.review_revision_id: int | None` and relationship `review_revision`.
- Produces `CommentResolutionEvent` with `action`, `disposition`, `rationale`, `actor_id`, `actor_role`, and `created_at`.
- Migration revision is `d0f422b00005`, down revision `c0f422b00004`.
- Does not add lock-taking triggers or the active-owner constraint; Task 5 activates those after application support exists.

- [x] **Step 1: Write failing ORM and migration-contract tests**

```python
def test_revision_exposes_v2_audit_columns():
    columns = PhenopacketRevision.__table__.c
    assert {"actor_role", "decision_metadata", "content_sha256", "ledger_version"} <= set(columns)


def test_review_issue_and_resolution_event_models_are_linked():
    assert Comment.__table__.c.review_revision_id.foreign_keys
    assert CommentResolutionEvent.__table__.c.comment_id.foreign_keys
```

The migration test must import the revision module, assert its revision chain, upgrade a temporary/test schema, inspect nullability/FKs/check constraints/indexes, and verify downgrade succeeds while all new tables/columns are empty.

- [x] **Step 2: Run the focused tests and confirm the schema is absent**

Run: `cd backend && uv run pytest tests/migration/test_independent_review_expand_migration.py tests/test_review_models.py tests/test_alembic_env_autogenerate.py -q`

Expected: FAIL because the migration, columns, and model do not exist.

- [x] **Step 3: Implement the nullable expansion**

Add the four nullable revision columns; add nullable `comments.review_revision_id` with `ON DELETE RESTRICT`; create `comment_resolution_events` with:

```python
CheckConstraint(
    "(action = 'reopened' AND disposition IS NULL) OR "
    "(action = 'resolved' AND disposition IN "
    "('addressed','accepted_with_rationale','retracted','superseded'))",
    name="ck_comment_resolution_event_action_disposition",
)
```

Add database checks for `content_sha256 ~ '^sha256:[0-9a-f]{64}$'`, `ledger_version IS NULL OR ledger_version = 2`, `decision_metadata IS NULL OR ledger_version = 2`, allowlisted actor-role snapshots where present, trimmed resolution rationale length `1..500`, and resolution-event actor role `curator|admin`. Create a partial index for live unresolved phenopacket blocking issues on `(record_id, review_revision_id)` where `record_type = 'phenopacket' AND review_revision_id IS NOT NULL AND resolved_at IS NULL AND deleted_at IS NULL`. Leave existing rows null and do not disable the revision immutability trigger. Import both new ORM models in `alembic/env.py` so autogenerate sees the complete metadata graph.

- [x] **Step 4: Register cleanup order and verify upgrade/downgrade**

Add `comment_resolution_events` before `comments` in `_MUTABLE_TABLES`. Run:

`cd backend && uv run pytest tests/migration/test_independent_review_expand_migration.py tests/test_review_models.py tests/test_alembic_env_autogenerate.py tests/test_comments_ast_immutable.py tests/test_revision_immutability.py -q`

Expected: PASS.

- [x] **Step 5: Commit the expansion**

```bash
git add backend/alembic/versions/d0f422b00005_expand_independent_review_audit.py \
  backend/alembic/env.py backend/app/phenopackets/models.py backend/app/comments/models.py \
  backend/tests/conftest.py backend/tests/migration/test_independent_review_expand_migration.py \
  backend/tests/test_review_models.py backend/tests/test_alembic_env_autogenerate.py
git commit -m "feat(backend): expand independent review schema"
```

### Task 2: Centralize full-content and v2 ledger hashing

**Files:**

- Create: `backend/app/phenopackets/services/revision_ledger.py`
- Create: `backend/tests/test_revision_ledger_v2.py`

**Interfaces:**

- Produces `content_sha256(content: Mapping[str, Any]) -> str` using the existing canonical JSON contract and returning `sha256:<64 lowercase hex>`.
- Produces `build_ledger_v2_payload(...) -> dict[str, Any]` and `ledger_sha256(payload: Mapping[str, Any]) -> str`.
- The v2 payload includes parent revision, revision number, state/event/from/to, reason, patch, full-content digest, projection hash, actor ID, actor role, and canonical decision metadata.
- Task 4 integrates these pure functions into all new revision writes; this task does not modify `state_service.py`.

- [x] **Step 1: Write failing digest and tamper-evidence tests**

```python
def test_content_digest_covers_extension_fields_and_ignores_key_order():
    left = {"subject": {"id": "1"}, "hnf1bCuration": {"flag": True}}
    reordered = {"hnf1bCuration": {"flag": True}, "subject": {"id": "1"}}
    changed = {"subject": {"id": "1"}, "hnf1bCuration": {"flag": False}}
    assert content_sha256(left) == content_sha256(reordered)
    assert content_sha256(left) != content_sha256(changed)


def test_v2_ledger_hash_changes_with_role_or_decision_metadata():
    base = build_fixture_payload()
    assert ledger_sha256(base) != ledger_sha256({**base, "actor_role": "admin"})
    assert ledger_sha256(base) != ledger_sha256({**base, "decision_metadata": {"independentReview": True}})
```

- [x] **Step 2: Run the tests and confirm imports fail**

Run: `cd backend && uv run pytest tests/test_revision_ledger_v2.py -q`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement deterministic hashing**

Reuse `app.phenopackets.curation.hashing.canonical_json`/`sha256_digest`; do not introduce a second serializer. Normalize only the explicit ledger payload, never remove `hnf1bCuration` or unknown extension keys from content.

- [x] **Step 4: Run focused hashing and projection tests**

Run: `cd backend && uv run pytest tests/test_revision_ledger_v2.py tests/curation/test_projection_properties.py -q`

Expected: PASS.

- [x] **Step 5: Commit the ledger utility**

```bash
git add backend/app/phenopackets/services/revision_ledger.py backend/tests/test_revision_ledger_v2.py
git commit -m "feat(backend): add full-content revision digests"
```

### Task 3: Implement independent-review policy and server capabilities

**Files:**

- Create: `backend/app/phenopackets/review/__init__.py`
- Create: `backend/app/phenopackets/review/policy.py`
- Create: `backend/app/phenopackets/review/schemas.py`
- Modify: `backend/app/phenopackets/services/transitions.py`
- Modify: `backend/app/phenopackets/services/state_service.py`
- Create: `backend/tests/test_review_policy.py`
- Modify: `backend/tests/test_state_transitions.py`
- Modify: `backend/tests/test_state_flows.py`

**Interfaces:**

- Produces `ReviewBlockCode = Literal['self_review_forbidden','reviewer_submitted','reviewer_contributed','review_author_unknown','unresolved_review_issues','review_closed']`.
- Produces immutable `ActionCapability(action: str, allowed: bool, blocked_by: list[str])`.
- Produces `ReviewPolicy.evaluate(db, phenopacket, candidate_revision, actor, unresolved_count) -> ReviewCapabilities`.
- Produces `ReviewPolicy.require_independent_reviewer(...) -> None`, raising typed `ReviewPolicyError(code, message, context)`.
- Contributor scope is content events `created|draft_created|draft_saved` after the current published-head revision number, or all such events for a never-published record.
- Pure transition rules allow curator/admin review transitions, but the state service must call policy checks before mutation; publish remains admin-only.

- [ ] **Step 1: Write the failing role/owner/submitter/contributor matrix**

```python
@pytest.mark.parametrize(
    ("role", "is_owner", "submitted", "contributed", "allowed", "code"),
    [
        ("curator", False, False, False, True, None),
        ("admin", False, False, False, True, None),
        ("curator", True, False, True, False, "self_review_forbidden"),
        ("admin", False, True, False, False, "reviewer_submitted"),
        ("admin", False, False, True, False, "reviewer_contributed"),
    ],
)
async def test_review_eligibility_matrix(...):
    ...
```

Also test NULL owner fails closed, viewer has no actions, unresolved issues block only approval, request-changes is available to an eligible curator, approved may reopen to changes requested, only admins may publish, and direct state-service calls cannot bypass actor-specific policy.

- [ ] **Step 2: Run policy and transition tests to prove current admin-only behavior fails**

Run: `cd backend && uv run pytest tests/test_review_policy.py tests/test_state_transitions.py tests/test_state_flows.py -q`

Expected: FAIL because curator review and independent-review errors are absent.

- [ ] **Step 3: Implement the review policy and adjust the pure matrix**

Keep structural state/role rules in `services/transitions.py`; move actor-specific owner/submitter/contributor/issue decisions into `ReviewPolicy`. Integrate the policy in `state_service.py` after the phenopacket row lock and candidate lookup but before any revision mutation. Add `approved -> changes_requested`. Do not allow `admin` to bypass independence in either layer.

- [ ] **Step 4: Verify policy tests and mypy**

Run: `cd backend && uv run pytest tests/test_review_policy.py tests/test_state_transitions.py tests/test_state_flows.py -q && uv run mypy app/phenopackets/review app/phenopackets/services/transitions.py app/phenopackets/services/state_service.py`

Expected: PASS.

- [ ] **Step 5: Commit the policy layer**

```bash
git add backend/app/phenopackets/review backend/app/phenopackets/services/transitions.py \
  backend/app/phenopackets/services/state_service.py backend/tests/test_review_policy.py \
  backend/tests/test_state_transitions.py backend/tests/test_state_flows.py
git commit -m "feat(backend): enforce independent review policy"
```

### Task 4: Freeze canonical candidates and publish the exact approved snapshot

**Files:**

- Modify: `backend/app/phenopackets/models.py` (`TransitionRequest`, `RevisionResponse`)
- Modify: `backend/app/phenopackets/services/state_service.py`
- Modify: `backend/app/phenopackets/services/phenopacket_service.py`
- Modify: `backend/app/phenopackets/routers/transitions.py`
- Create: `backend/tests/test_exact_review_snapshot.py`
- Modify: `backend/tests/test_state_flows.py`
- Modify: `backend/tests/test_revision_immutability.py`
- Modify: `backend/tests/test_api_transitions.py`

**Interfaces:**

- `TransitionRequest` adds optional conditional fields:
  `candidate_revision_id`, `candidate_content_sha256`, `approved_revision_id`, `approved_content_sha256`, and `attestation`.
- `ApprovalAttestation` requires literal `True` for `independent_review` and `no_unmanaged_conflict`.
- `_append_revision(...)` accepts `decision_metadata: dict[str, Any] | None`, records actor role/content digest/ledger version, and uses Task 2 hashing.
- `RevisionResponse` exposes actor role, decision metadata, content digest, ledger version, and `actor_role_at_decision_recorded`; old rows remain explicitly labeled as lacking a recorded role snapshot rather than inferring one from the user's current role.
- Submit/resubmit canonicalizes with `publish=True` before writing `in_review`.
- Approval calls Task 3 policy under the existing row lock and copies the `in_review` snapshot unchanged.
- Publication validates expected approved ID/digest and copies approved content unchanged; `_canonicalize_for_persistence(..., publish=True)` must not run in `_publish`.

- [ ] **Step 1: Write failing exact-snapshot service tests**

```python
async def test_submit_freezes_publish_canonical_content(db_session, draft_record, curator_user):
    record, submitted = await service.transition(..., to_state="in_review", actor=curator_user)
    assert submitted.content_sha256 == content_sha256(submitted.content_jsonb)
    assert record.phenopacket == submitted.content_jsonb


async def test_publish_copies_approved_extension_content_unchanged(...):
    assert content_sha256(published.content_jsonb) == approved.content_sha256
    assert published.content_jsonb == approved.content_jsonb
    assert published.content_jsonb["hnf1bCuration"] == approved.content_jsonb["hnf1bCuration"]
```

Cover stale candidate ID, stale digest, missing/false attestation, publish-time canonicalizer mutation (must never be called), stale approved ID/digest, actor role and decision metadata in the v2 hash, and exact public-head pointer swap.

- [ ] **Step 2: Run focused tests and observe current publish-time mutation behavior**

Run: `cd backend && uv run pytest tests/test_exact_review_snapshot.py tests/test_state_flows.py tests/test_revision_immutability.py -q`

Expected: FAIL because current approval has no conditional digest/attestation and `_publish` canonicalizes.

- [ ] **Step 3: Implement conditional schemas and service behavior**

Use Pydantic model validation so approval requires only candidate fields/attestation and publication requires only approved fields. Translate `ReviewPolicyError` to stable structured router errors. Preserve optimistic record `revision` checks in addition to candidate/approved identity checks.

- [ ] **Step 4: Update creation writes to v2 audit without rewriting history**

Newly created records and all new revision events record actor role, full digest, and ledger v2. Existing rows with null v2 fields remain readable and immutable. Add response fields so review clients can echo exact IDs/digests.

- [ ] **Step 5: Run lifecycle/API/visibility regression tests**

Run: `cd backend && uv run pytest tests/test_exact_review_snapshot.py tests/test_state_flows.py tests/test_revision_immutability.py tests/test_api_transitions.py tests/test_visibility_endpoints.py tests/test_state_service_canonicalization_hook.py -q`

Expected: PASS.

- [ ] **Step 6: Commit exact review semantics**

```bash
git add backend/app/phenopackets/models.py backend/app/phenopackets/services/state_service.py \
  backend/app/phenopackets/services/phenopacket_service.py backend/app/phenopackets/routers/transitions.py \
  backend/tests/test_exact_review_snapshot.py backend/tests/test_state_flows.py \
  backend/tests/test_revision_immutability.py backend/tests/test_api_transitions.py
git commit -m "feat(backend): bind approval to exact candidate snapshot"
```

### Task 5: Add blocking review-issue semantics and activate database invariants

**Files:**

- Modify: `backend/app/comments/schemas.py`
- Modify: `backend/app/comments/service.py`
- Modify: `backend/app/comments/routers.py`
- Create: `backend/alembic/versions/e0f422b00006_activate_independent_review_invariants.py`
- Create: `backend/tests/test_blocking_review_issues.py`
- Create: `backend/tests/migration/test_independent_review_sql_races.py`
- Create: `backend/tests/migration/test_independent_review_activation_migration.py`
- Modify: `backend/tests/test_comments_service_mutations.py`
- Modify: `backend/tests/test_comments_router.py`
- Modify: `backend/tests/test_comments_permissions.py`
- Modify: `backend/tests/test_comments_soft_delete.py`

**Interfaces:**

- `CommentCreate` adds optional `record_revision` and `review_revision_id`.
- `ReviewIssueResolveRequest(record_revision, disposition, rationale)` and `ReviewIssueReopenRequest(record_revision, rationale)` implement the conditional bodies in the spec.
- `CommentsService` mutation methods flush but never commit; routers own commit/rollback.
- Blocking issue operations acquire the owning phenopacket `FOR UPDATE` before locking/loading the comment.
- Expansion activation revision is `e0f422b00006`, down revision `d0f422b00005`.
- Database functions/triggers lock the phenopacket row for blocking issue insert/resolve/reopen and active revision/state changes, then validate ownership/state/revision linkage; a deferred constraint trigger checks approved-plus-unresolved final state.

- [ ] **Step 1: Write failing blocking-issue API/service tests**

```python
async def test_owner_cannot_resolve_or_delete_blocking_issue(...):
    resolved = await client.post(f"/api/v2/comments/{issue.id}/resolve", headers=owner_headers, json={...})
    deleted = await client.delete(f"/api/v2/comments/{issue.id}", headers=owner_headers)
    assert resolved.status_code == 403
    assert deleted.status_code == 409
    assert deleted.json()["detail"]["code"] == "review_issue_delete_forbidden"


async def test_ordinary_comment_routes_remain_backward_compatible(...):
    assert (await client.post(f"/api/v2/comments/{comment.id}/resolve", headers=curator_headers)).status_code == 200
```

Cover unrelated revision nomination, non-review state creation, missing rationale/disposition, retraction as resolution, append-only resolution/reopen events, all legacy resolve/unresolve/delete routes, admin-owner bypass attempts, and router rollback on failures.

- [ ] **Step 2: Run focused comment tests and confirm bypasses**

Run: `cd backend && uv run pytest tests/test_blocking_review_issues.py tests/test_comments_service_mutations.py tests/test_comments_router.py -q`

Expected: FAIL because current routes allow any curator resolve/unresolve and author/admin delete.

- [ ] **Step 3: Implement phenopacket-first comment mutations**

Load comment identity, acquire the phenopacket row lock by `record_id`, reload/lock the comment, then discriminate `review_revision_id`. Use Task 3 policy for blocking operations. Write a `CommentResolutionEvent` before updating the current projection. Reject DELETE on a blocking issue; do not soft-delete it.

- [ ] **Step 4: Write failing raw-SQL race and activation-migration tests**

Use two independent async connections/transactions and explicit barriers, not sleeps. Test all four orderings:

```text
Tx A: insert/reopen unresolved blocking issue -> hold -> commit
Tx B: advance active revision to approved -> blocks -> rejects after A commit

Tx A: approve/lock -> hold -> commit
Tx B: insert/reopen issue -> blocks -> rejects review_closed after A commit
```

Also assert active `editing_revision_id` requires `draft_owner_id`, review revision belongs to the comment record, ambiguous owner preflight aborts, and downgrade refuses after a resolution event or v2 revision exists.

- [ ] **Step 5: Implement activation migration and guarded downgrade**

Create lock-taking trigger functions with one global order: `phenopackets FOR UPDATE` before revision/comment checks. Augment the existing pointer-state trigger rather than replacing it. Backfill missing active owners from recursive deterministic active-cycle ancestry; run a preflight that raises with record IDs when ancestry is ambiguous. Guard downgrade before dropping any audit/invariant object: it succeeds only when no blocking issue, resolution event, v2 ledger revision, or decision metadata exists. Do not modify existing revision rows to reconstruct roles/hashes.

- [ ] **Step 6: Run migration, race, comment, and state tests**

Run: `cd backend && uv run pytest tests/migration/test_independent_review_activation_migration.py tests/migration/test_independent_review_sql_races.py tests/test_blocking_review_issues.py tests/test_comments_service_mutations.py tests/test_comments_router.py tests/test_comments_permissions.py tests/test_comments_soft_delete.py tests/test_state_invariants.py -q`

Expected: PASS with both raw-SQL commit orders proven.

- [ ] **Step 7: Commit review issues and invariant activation**

```bash
git add backend/app/comments/schemas.py backend/app/comments/service.py backend/app/comments/routers.py \
  backend/alembic/versions/e0f422b00006_activate_independent_review_invariants.py \
  backend/tests/test_blocking_review_issues.py \
  backend/tests/migration/test_independent_review_sql_races.py \
  backend/tests/migration/test_independent_review_activation_migration.py \
  backend/tests/test_comments_service_mutations.py backend/tests/test_comments_router.py \
  backend/tests/test_comments_permissions.py backend/tests/test_comments_soft_delete.py
git commit -m "feat(backend): gate approval on blocking review issues"
```

### Task 6: Build the server-driven review queue and coherent review context

**Files:**

- Create: `backend/app/phenopackets/review/repository.py`
- Create: `backend/app/phenopackets/review/service.py`
- Extend: `backend/app/phenopackets/review/schemas.py`
- Create: `backend/app/phenopackets/routers/review.py`
- Modify: `backend/app/phenopackets/routers/__init__.py`
- Fix: `backend/app/phenopackets/routers/crud.py` effective-state projection
- Create: `backend/tests/test_review_queue.py`
- Create: `backend/tests/test_review_context.py`
- Modify: `backend/tests/test_crud_state_branching.py`
- Modify: `backend/tests/test_openapi_contract.py`

**Interfaces:**

- `ReviewRepository.list_queue(actor, query) -> tuple[list[ReviewQueueRow], int, StateCounts]` uses one centralized SQL effective-state expression for data/count filters.
- `ReviewRepository.get_context(record_id, actor) -> ReviewContext | None` reads candidate, public baseline, issues, audit, contributors, and capability inputs coherently.
- `ReviewService.semantic_changes(baseline, candidate) -> list[SemanticChange]` returns `section`, `operation`, JSON pointer `path`, `before`, and `after`.
- `GET /api/v2/phenopackets/review-queue` and `GET /api/v2/phenopackets/{id}/review-context` implement the approved DTO/query contract.
- Queue rows return both `physical_state` and `effective_state`; context and each blocking issue return actor-specific `ActionCapability` objects shaped as `{action, allowed, blocked_by}`.
- Comment responses expose `review_revision_id`, `is_blocking_issue`, and append-only resolution events without changing the ordinary-comment contract.
- Public CRUD filtering remains physical-head based; curator CRUD rows now include correct `effective_state`.

- [ ] **Step 1: Write failing queue projection and authorization tests**

```python
async def test_queue_filters_published_record_by_in_review_effective_state(...):
    response = await client.get(
        "/api/v2/phenopackets/review-queue?filter[state]=in_review&page[number]=1&page[size]=10",
        headers=reviewer_headers,
    )
    row = response.json()["data"][0]
    assert row["physical_state"] == "published"
    assert row["effective_state"] == "in_review"


async def test_viewer_review_queue_is_not_discoverable(...):
    assert response.status_code == 404
```

Cover pagination/count parity, allowlisted sorting, oldest-submission default, state/owner/eligibility/issues filters, search, state counts, own-row visibility with disabled capabilities, and old public-head retention.

- [ ] **Step 2: Write failing coherent-context and semantic-change tests**

Test new records (no baseline/all added), revised records (public head baseline), nested add/remove/replace, arrays, unknown extension fields, unresolved-first issues, contributor/submission audit, and actor-specific capability blockers.

- [ ] **Step 3: Run queue/context tests and confirm endpoints are absent**

Run: `cd backend && uv run pytest tests/test_review_queue.py tests/test_review_context.py tests/test_crud_state_branching.py -q`

Expected: FAIL with 404/import errors.

- [ ] **Step 4: Implement repository/service/router boundaries**

Register the review router before the CRUD catch-all. Keep SQL expressions shared between row and count queries. Avoid per-row queries by joining/aggregating owner, submitted revision, blocking issue count, and contributors. Return typed Pydantic response models rather than ad hoc dicts.

- [ ] **Step 5: Verify API, visibility, query-count, and OpenAPI tests**

Run: `cd backend && uv run pytest tests/test_review_queue.py tests/test_review_context.py tests/test_crud_state_branching.py tests/test_visibility_endpoints.py tests/test_openapi_contract.py -q`

Expected before snapshot refresh: only the snapshot equality test may fail due intentional API additions; vocabulary contract must pass. Snapshot refresh belongs to Task 12.

- [ ] **Step 6: Commit the review API**

```bash
git add backend/app/phenopackets/review backend/app/phenopackets/routers/review.py \
  backend/app/phenopackets/routers/__init__.py backend/app/phenopackets/routers/crud.py \
  backend/tests/test_review_queue.py backend/tests/test_review_context.py \
  backend/tests/test_crud_state_branching.py
git commit -m "feat(backend): expose review queue and context"
```

### Task 7: Add frontend review transport, route guard, and navigation

**Files:**

- Create: `frontend/src/api/domain/reviews.js`
- Modify: `frontend/src/api/domain/comments.js`
- Modify: `frontend/src/api/domain/phenopackets.js`
- Modify: `frontend/src/api/index.js`
- Create: `frontend/tests/unit/api/reviews.spec.js`
- Create: `frontend/tests/unit/api/comments.spec.js`
- Modify: `frontend/tests/unit/api/phenopackets.spec.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/AppBar.vue`
- Modify: `frontend/src/components/MobileDrawer.vue`
- Create: `frontend/src/views/ReviewQueue.vue`
- Create: `frontend/src/views/PhenopacketReview.vue`
- Create: `frontend/tests/unit/router/reviewRoutes.spec.js`
- Create: `frontend/tests/unit/components/ReviewNavigation.spec.js`

**Interfaces:**

```javascript
getReviewQueue(params)
getReviewContext(phenopacketId)
transitionPhenopacket(id, toState, reason, recordRevision, conditional = {})
createComment({ recordType, recordId, bodyMarkdown, mentionUserIds, recordRevision, reviewRevisionId })
resolveComment(commentId, request?)
unresolveComment(commentId, request?)
```

Routes `ReviewQueue` and `PhenopacketReview` use `requiresAuth: true, requiresCurator: true`. Export a testable `resolveRouteAccess(to, from, authStore)` and return `NotFound` for authenticated viewers. API modules serialize snake_case HTTP contracts and never infer policy.

- [ ] **Step 1: Write failing transport serialization tests**

Assert every queue parameter alias, encoded context ID, candidate ID/digest/attestation approval payload, approved ID/digest publication payload, omission of irrelevant fields, revision-bound issue creation, typed resolve/reopen bodies, and ordinary bodyless resolution.

- [ ] **Step 2: Write failing guard/navigation tests**

```javascript
it('returns NotFound for a viewer without disclosing the review record', async () => {
  expect(await resolveRouteAccess(reviewRoute, from, viewerStore)).toEqual({ name: 'NotFound' });
});
```

Cover anonymous return URL, curator/admin access, desktop/mobile menu visibility, and drawer close.

- [ ] **Step 3: Run focused frontend tests and confirm missing modules/routes**

Run: `cd frontend && npm test -- tests/unit/api/reviews.spec.js tests/unit/api/comments.spec.js tests/unit/api/phenopackets.spec.js tests/unit/router/reviewRoutes.spec.js tests/unit/components/ReviewNavigation.spec.js`

Expected: FAIL.

- [ ] **Step 4: Implement transport, guards, and lazy routes**

Use lazy route imports and create accessible loading shells for both route components so this commit remains buildable. Tasks 8 and 10 replace the shells with the queue and workspace. Preserve existing login initialization and admin guards.

- [ ] **Step 5: Verify focused tests and lint**

Run: `cd frontend && npm test -- tests/unit/api/reviews.spec.js tests/unit/api/comments.spec.js tests/unit/api/phenopackets.spec.js tests/unit/router/reviewRoutes.spec.js tests/unit/components/ReviewNavigation.spec.js && npm run lint:check`

Expected: PASS.

- [ ] **Step 6: Commit transport/navigation**

```bash
git add frontend/src/api frontend/src/router/index.js frontend/src/components/AppBar.vue \
  frontend/src/components/MobileDrawer.vue frontend/src/views/ReviewQueue.vue \
  frontend/src/views/PhenopacketReview.vue frontend/tests/unit/api \
  frontend/tests/unit/router/reviewRoutes.spec.js frontend/tests/unit/components/ReviewNavigation.spec.js
git commit -m "feat(frontend): add curator review routes and transport"
```

### Task 8: Implement URL-backed server review queue

**Files:**

- Create: `frontend/src/composables/useReviewQueue.js`
- Modify: `frontend/src/views/ReviewQueue.vue`
- Create: `frontend/tests/unit/composables/useReviewQueue.spec.js`
- Create: `frontend/tests/unit/views/ReviewQueue.spec.js`

**Interfaces:**

```javascript
useReviewQueue() => {
  items, meta, loading, error,
  page, pageSize, sort, search, tab, eligibility, issues,
  load, retry, clearFilters, setTab
}
```

Tab mapping is exact: `needs-review -> in_review`, `changes-requested -> changes_requested`, `approved -> approved`, and `my-drafts -> draft + owner=mine`. Queue DTO rows use `physical_state` and `effective_state`; the view always displays effective state.

- [ ] **Step 1: Write failing composable tests**

Cover URL hydration, exact tab filters, page reset on filter/search/tab changes, backend totals, stale-response suppression, and preserved error for retry.

- [ ] **Step 2: Run composable tests and observe missing implementation**

Run: `cd frontend && npm test -- tests/unit/composables/useReviewQueue.spec.js`

Expected: FAIL.

- [ ] **Step 3: Implement queue state against `getReviewQueue`**

Reuse `useTableUrlState` semantics. Track a monotonically increasing request token or AbortController so an older response cannot overwrite a newer one. Do no client sorting/pagination.

- [ ] **Step 4: Write failing queue-view tests**

Assert server totals, effective state, explicit focusable Review link, retry, true-empty versus filtered-empty messages, mobile state/issue count, and absence of bulk approval or row-click-only navigation.

- [ ] **Step 5: Implement `ReviewQueue.vue`**

Use `AppDataTable`, standard toolbar/pagination components, `StateBadge`, skeletons, alert/retry, and mobile slots. Keep query state shareable.

- [ ] **Step 6: Verify queue tests and accessibility lint**

Run: `cd frontend && npm test -- tests/unit/composables/useReviewQueue.spec.js tests/unit/views/ReviewQueue.spec.js && npm run lint:check`

Expected: PASS.

- [ ] **Step 7: Commit the queue**

```bash
git add frontend/src/composables/useReviewQueue.js frontend/src/views/ReviewQueue.vue \
  frontend/tests/unit/composables/useReviewQueue.spec.js frontend/tests/unit/views/ReviewQueue.spec.js
git commit -m "feat(frontend): add server-driven review queue"
```

### Task 9: Implement review context, semantic comparison, and blocking issues

**Files:**

- Create: `frontend/src/composables/useReviewContext.js`
- Create: `frontend/src/composables/useReviewIssues.js`
- Create: `frontend/src/components/review/SemanticDiff.vue`
- Create: `frontend/src/components/review/CandidateSnapshot.vue`
- Create: `frontend/src/components/review/ReviewIssuesPanel.vue`
- Create: `frontend/src/components/review/ReviewIssueDialog.vue`
- Create: `frontend/tests/unit/composables/useReviewContext.spec.js`
- Create: `frontend/tests/unit/composables/useReviewIssues.spec.js`
- Create: `frontend/tests/unit/components/review/SemanticDiff.spec.js`
- Create: `frontend/tests/unit/components/review/CandidateSnapshot.spec.js`
- Create: `frontend/tests/unit/components/review/ReviewIssuesPanel.spec.js`
- Create: `frontend/tests/unit/components/review/ReviewIssueDialog.spec.js`

**Interfaces:**

```javascript
useReviewContext(id) => {
  context, loading, error, conflict, liveMessage,
  load, reload, markConflict, clearConflict
}

useReviewIssues({ recordId, recordRevision, candidateRevisionId, reload }) => {
  submitting, error, createIssue, resolveIssue, reopenIssue
}
```

The backend semantic diff is authoritative. `CandidateSnapshot` reuses existing subject, phenotype, disease, interpretation, measurement, and metadata cards. Each blocking issue consumes its own backend-returned capabilities; it never inherits ordinary comment author/admin deletion rules.

- [ ] **Step 1: Write failing context/diff tests**

Cover one coherent load, unavailable issue status failing closed, add/remove/change text plus icons, before/after rendering without color dependence, null baseline “New phenopacket”, complete candidate cards, and raw extension content.

- [ ] **Step 2: Implement the context composable and display components**

Do not compute a client diff. Sanitize rendered values through existing utilities and provide accessible labels for JSON pointers/operations.

- [ ] **Step 3: Write failing blocking-issue tests**

Cover exact candidate binding, disposition allowlist, rationale, unresolved-first ordering, server capabilities, no Delete action, reload after mutation, and issue-count live announcement.

- [ ] **Step 4: Implement issue composable/panel/dialog**

Use Task 7 transport. Preserve ordinary `DiscussionTab` unchanged except for shared response-field compatibility.

- [ ] **Step 5: Verify focused tests, format, and lint**

Run: `cd frontend && npm test -- tests/unit/composables/useReviewContext.spec.js tests/unit/composables/useReviewIssues.spec.js tests/unit/components/review && npm run format:check && npm run lint:check`

Expected: PASS.

- [ ] **Step 6: Commit comparison/issues**

```bash
git add frontend/src/composables/useReviewContext.js frontend/src/composables/useReviewIssues.js \
  frontend/src/components/review frontend/tests/unit/composables/useReviewContext.spec.js \
  frontend/tests/unit/composables/useReviewIssues.spec.js frontend/tests/unit/components/review
git commit -m "feat(frontend): add review comparison and issues"
```

### Task 10: Implement exact-revision decisions and assemble the responsive workspace

**Files:**

- Create: `frontend/src/composables/useReviewActions.js`
- Create: `frontend/src/components/review/ReviewActionPanel.vue`
- Create: `frontend/src/components/review/ReviewDecisionDialog.vue`
- Create: `frontend/src/components/review/ReviewHeader.vue`
- Modify: `frontend/src/views/PhenopacketReview.vue`
- Create: `frontend/tests/unit/composables/useReviewActions.spec.js`
- Create: `frontend/tests/unit/components/review/ReviewActionPanel.spec.js`
- Create: `frontend/tests/unit/components/review/ReviewDecisionDialog.spec.js`
- Create: `frontend/tests/unit/components/review/ReviewHeader.spec.js`
- Create: `frontend/tests/unit/views/PhenopacketReview.spec.js`

**Interfaces:**

```javascript
useReviewActions(id, contextRef, { reload, onCompleted }) => {
  pendingAction, submitting, error, conflict,
  approve, requestChanges, reopenApproved, publish, withdraw
}
```

Approval payloads originate only from loaded candidate ID/digest; publication originates only from loaded approval ID/digest. Backend capabilities drive every action and denial reason.

- [ ] **Step 1: Write failing action tests**

Cover unknown/open issue disabling, both attestations and rationale, server self-review/contributor explanations, publish capability, structured conflict mapping, no retry after conflict, unresolved count copy, and focus restoration.

- [ ] **Step 2: Implement action composable and dialogs**

Map `revision_mismatch` and `review_revision_mismatch` to a reload-required state. Never synthesize an approval/publication identity from route or current record state.

- [ ] **Step 3: Write failing workspace/header tests**

Cover audit metadata, preserved back-to-queue query, skeleton/retry/private-404 states, refresh after mutation, conflict replacement, candidate/raw JSON/history views, right rail desktop layout, and single-column mobile order/sticky safe-area controls.

- [ ] **Step 4: Assemble `PhenopacketReview.vue`**

Desktop main column contains changes/candidate/JSON/history; the right rail contains review issues, discussion summary, and decisions. Mobile order is header, content tabs, issues, decisions. Use `aria-live="polite"`, one `h1`, 44px targets, focus trap/return, and text plus icons.

- [ ] **Step 5: Verify workspace tests and build**

Run: `cd frontend && npm test -- tests/unit/composables/useReviewActions.spec.js tests/unit/components/review tests/unit/views/PhenopacketReview.spec.js && npm run lint:check && npm run build`

Expected: PASS.

- [ ] **Step 6: Commit the workspace**

```bash
git add frontend/src/composables/useReviewActions.js frontend/src/components/review \
  frontend/src/views/PhenopacketReview.vue frontend/tests/unit/composables/useReviewActions.spec.js \
  frontend/tests/unit/components/review frontend/tests/unit/views/PhenopacketReview.spec.js
git commit -m "feat(frontend): add exact-revision review workspace"
```

### Task 11: Remove local transition policy and close legacy UI/API bypasses

**Files:**

- Modify: `frontend/src/components/state/TransitionMenu.vue`
- Modify: `frontend/src/components/state/TransitionModal.vue`
- Modify: `frontend/src/composables/usePhenopacketState.js`
- Modify: `frontend/src/views/PagePhenopacket.vue`
- Modify: `frontend/src/components/curation/reports/ReportObservationWorkspace.vue`
- Modify their existing Vitest files

**Interfaces:**

- `TransitionMenu` accepts only backend `capabilities` and emits a selected simple transition.
- Approval, approved reopening, and publication route to the focused workspace because the generic dialog cannot safely construct exact revision/digest/attestation payloads.
- `PagePhenopacket` exposes “Open review workspace” in active review states.
- Direct publication in `ReportObservationWorkspace` is removed and replaced with an open-review affordance.

- [ ] **Step 1: Replace local-matrix tests with capability tests**

Assert only server capabilities render, denial reasons display, conditional actions route to review workspace, and no `RULES`, `role`, or `isOwner` props remain.

- [ ] **Step 2: Write failing detail/report-workspace bypass tests**

Assert active review records link to the workspace and report curation can no longer call publication without approved ID/digest.

- [ ] **Step 3: Implement server-authoritative consumers**

Preserve legacy state labels/history. Do not recreate policy in computed properties.

- [ ] **Step 4: Run focused and full affected unit tests**

Run: `cd frontend && npm test -- tests/unit/components/state tests/unit/views/PagePhenopacket.spec.js tests/unit/components/curation/ReportObservationWorkspace.spec.js`

Expected: PASS.

- [ ] **Step 5: Commit bypass removal**

```bash
git add frontend/src/components/state frontend/src/composables/usePhenopacketState.js \
  frontend/src/views/PagePhenopacket.vue frontend/src/components/curation/reports/ReportObservationWorkspace.vue \
  frontend/tests/unit/components/state frontend/tests/unit/views/PagePhenopacket.spec.js \
  frontend/tests/unit/components/curation/ReportObservationWorkspace.spec.js
git commit -m "refactor(frontend): consume server review capabilities"
```

### Task 12: Update contracts, seed distinct actors, and prove the lifecycle end to end

**Files:**

- Modify: `backend/scripts/seed_dev_users.py`
- Modify: `backend/tests/test_seed_dev_users.py`
- Refresh: `mcp/contract/openapi.snapshot.json`
- Modify: `backend/tests/test_openapi_contract.py`
- Modify: `frontend/tests/e2e/helpers/auth.js`
- Create: `frontend/tests/e2e/independent-review.spec.js`
- Create: `frontend/tests/e2e/review-workspace-accessibility.spec.js`
- Modify: `frontend/tests/e2e/state-lifecycle.spec.js`
- Modify: `frontend/tests/e2e/comments.spec.js`
- Modify: `frontend/tests/e2e/dual-read-invariant.spec.js`
- Modify: `frontend/tests/e2e/README.md`

**Interfaces:**

- Seed two distinct active verified curator fixtures plus an admin without weakening production authentication.
- Add `loginAsCuratorA` and `loginAsCuratorB`, using `E2E_CURATOR_A_*`/`E2E_CURATOR_B_*` with deterministic development-only fallbacks.
- OpenAPI documents queue/context DTOs, conditional transition fields, ordinary/bodyless and blocking/typed comment mutations, structured errors, and actor capabilities.

- [ ] **Step 1: Write/update seeder and OpenAPI contract tests**

Assert both curators are distinct/active/verified and snapshot exposes the new request/response/error contracts. Run focused backend tests and confirm intentional snapshot drift.

- [ ] **Step 2: Refresh the deterministic OpenAPI snapshot under CI Python 3.12**

Run: `cd backend && uv run python scripts/dump_openapi.py > ../mcp/contract/openapi.snapshot.json` only after the live schema tests are correct. Inspect the diff and verify only intentional review-contract changes.

- [ ] **Step 3: Replace same-admin lifecycle assumptions**

Update existing backend/E2E fixtures so owner, reviewer, and publisher are distinct where policy requires. Do not weaken assertions to accept both old and new workflows.

- [ ] **Step 4: Write the principal Playwright lifecycle**

Prove: curator A creates/submits; anonymous/viewer cannot discover; A cannot decide; curator B finds through server filters, raises an issue, requests changes, resolves with disposition/rationale, approves exact revision/digest; content stays private until admin publication; a second cycle retains the old public head until replacement publication.

- [ ] **Step 5: Add conflicts, reopening, keyboard, and mobile E2E coverage**

Cover approved-to-changes-requested, stale revision/digest reload-required state, keyboard-only queue/issue/decision path, 375×812 layout/no overflow, named controls, focus behavior, and non-color diff cues.

- [ ] **Step 6: Run focused backend and E2E contracts**

Run:

```bash
cd backend && uv run pytest tests/test_openapi_contract.py tests/test_seed_dev_users.py tests/test_api_transitions.py -q
cd frontend && npm run e2e -- tests/e2e/independent-review.spec.js tests/e2e/review-workspace-accessibility.spec.js tests/e2e/state-lifecycle.spec.js tests/e2e/dual-read-invariant.spec.js
```

Expected: PASS with genuinely distinct authenticated actors.

- [ ] **Step 7: Commit contracts and E2E proof**

```bash
git add backend/scripts/seed_dev_users.py backend/tests/test_seed_dev_users.py \
  backend/tests/test_openapi_contract.py mcp/contract/openapi.snapshot.json \
  frontend/tests/e2e/helpers/auth.js frontend/tests/e2e/independent-review.spec.js \
  frontend/tests/e2e/review-workspace-accessibility.spec.js \
  frontend/tests/e2e/state-lifecycle.spec.js frontend/tests/e2e/comments.spec.js \
  frontend/tests/e2e/dual-read-invariant.spec.js frontend/tests/e2e/README.md
git commit -m "test(review): prove independent curation lifecycle"
```

### Task 13: Verify, document, adversarially review, and prepare the PR

**Files:**

- Update: `.planning/plans/2026-08-14-independent-phenopacket-review-plan.md` checkboxes
- Create: `.planning/reviews/2026-08-14-independent-phenopacket-review-pr-review.md`
- Create: `docs/curation-review-workflow.md`

**Interfaces:**

- Verification evidence maps every acceptance criterion in the design spec to a test, runtime check, migration check, or rendered behavior.
- One independent `gpt-5.6-sol` xhigh reviewer performs the requested one-pass adversarial PR review; it reports only and does not edit.
- The primary agent adjudicates every finding, fixes accepted findings with TDD, reruns relevant/full checks, and records dispositions once; there is no second independent review pass.

- [ ] **Step 1: Run backend formatting, lint, typing, migrations, and full tests**

```bash
make lint
make typecheck
make test
cd backend && uv run alembic heads
```

Exercise expand -> backend-compatible -> activation -> head and guarded downgrade behavior against a disposable/test database. Expected head is the activation revision.

The rollout order is exact: apply `d0f422b00005`, deploy the v2-writing backend, then apply `e0f422b00006`. The migration proof must also demonstrate empty-data downgrade success and post-audit downgrade refusal.

- [ ] **Step 2: Run frontend formatting, lint, tests, build, and focused E2E**

```bash
cd frontend
npm run format:check
npm run lint:check
npm test
npm run build
npm run e2e -- tests/e2e/independent-review.spec.js tests/e2e/review-workspace-accessibility.spec.js
```

- [ ] **Step 3: Perform runtime smoke checks**

Start the isolated backend/frontend against migrated dev services. Verify queue loading, distinct-user decisions, issue gate, public privacy before publication, old-head behavior during re-review, exact digest/approval/publication equality, desktop/mobile rendering, and structured conflicts. Capture only non-sensitive evidence.

- [ ] **Step 4: Run the requirement-by-requirement completion audit**

For every design acceptance criterion, record authoritative evidence and mark proven/missing/contradicted. Continue implementation for every missing or indirect item; do not infer completion from broad green suites.

Write `docs/curation-review-workflow.md` with the operator-visible state lifecycle, independent-review exclusions, blocking-issue dispositions, exact-revision sign-off contract, publication boundary, rollout order, and guarded rollback behavior.

- [ ] **Step 5: Dispatch the one-pass adversarial PR reviewer**

Give the reviewer the design, spec-review artifact, implementation plan, complete diff, test evidence, and current code. Save its report and primary-agent dispositions in `.planning/reviews/2026-08-14-independent-phenopacket-review-pr-review.md`.

- [ ] **Step 6: Address accepted review findings with focused failing tests and rerun all impacted checks**

Commit fixes intentionally. Document any rejected finding with code/test evidence, not preference.

- [ ] **Step 7: Publish the branch and open a draft PR**

Use the repository's GitHub publication workflow: inspect status/diff, commit remaining intentional changes, push `feat/peer-review-workflow`, open a draft PR with design/verification/review links, and never include secrets or local environment symlinks.

- [ ] **Step 8: Inspect GitHub Actions and drive the PR green**

Inspect every required check. For any failure, use systematic debugging, fix with a regression test, push, and re-run until all required Actions are green or a deliberate external blocker is documented.

- [ ] **Step 9: Final commit of planning/review evidence**

```bash
git add .planning/plans/2026-08-14-independent-phenopacket-review-plan.md \
  .planning/reviews/2026-08-14-independent-phenopacket-review-pr-review.md \
  docs/curation-review-workflow.md
git commit -m "docs(planning): record independent review delivery"
```
