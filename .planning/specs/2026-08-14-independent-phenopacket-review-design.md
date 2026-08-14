# Independent Phenopacket Review Design

**Date:** 2026-08-14

**Status:** User-approved design; independent review findings addressed; awaiting written-spec confirmation

**Scope:** Phenopacket curation workflow, review audit, curator-facing review queue/workspace, and publication gate

## 1. Decision

HNF1B-DB will retain its existing revisioned lifecycle and make it a real four-eyes workflow:

```text
draft -> in_review -> approved -> published
             |            |
             v            v
      changes_requested <-+
             |
             +---------> in_review
```

An authenticated curator or admin may review any open submission except a submission they own, submitted on another user's behalf, or whose candidate content they changed during the active edit cycle. One eligible reviewer signs off the exact immutable candidate revision. Only an admin may publish that approved revision. Unpublished records and candidate revisions remain curator-only; when an already-published record is revised, its old immutable public head remains visible until the replacement is approved and published.

The review queue is open to all active curators/admins. It does not use assignment, claiming, bulk approval, or a new editor role.

## 2. Why this design

### 2.1 Current system findings

The repository already has the hard parts worth preserving:

- immutable `phenopacket_revisions` snapshots with actor, reason, transition, hashes, and timestamps;
- `draft`, `in_review`, `changes_requested`, `approved`, `published`, and `archived` states;
- optimistic revision checks and a phenopacket row lock around transitions;
- separate working-copy and public-head pointers;
- public visibility that dereferences only the immutable published head;
- curator comments with resolution state and edit history.

The gaps are policy and workflow projection:

- approval and request-changes are admin-only, while an admin can submit and approve the same work;
- the frontend and backend both encode transition permissions, so they can drift;
- the main curator list exposes physical `phenopackets.state` instead of the working copy's effective state;
- there is no server-driven review queue or comparison workspace;
- comments are record-wide and approval does not distinguish or gate on review issues;
- the current end-to-end lifecycle test explicitly uses the same admin to approve and publish.

### 2.2 Community-standard alignment

CIViC permits curators to submit and reject work but does not permit them to accept their own submissions or revisions. ClinGen workflows separate in-progress/provisional work, expert approval, and publication and require review discrepancies to be reconciled or explicitly dispositioned before a final decision. A single independent sign-off is proportionate for literature-derived case-record publication; it must not be described as equivalent to ClinGen expert-panel consensus.

Relevant primary sources:

- [CIViC evidence curation and moderation](https://docs.civicdb.org/en/latest/curating/evidence.html)
- [CIViC Standard Operating Procedure](https://pmc.ncbi.nlm.nih.gov/articles/PMC6883603/)
- [ClinGen Gene-Disease Validity SOP v12](https://www.clinicalgenome.org/site/assets/files/10876/gene_disease_validity_standard_operating_procedures-_version_12.pdf)
- [ClinGen Gene Curation Expert Panel Protocol v3](https://clinicalgenome.org/docs/clingen-gene-curation-expert-panel-protocol/)
- [GA4GH Phenopackets v2 metadata](https://phenopacket-schema.readthedocs.io/en/stable/metadata.html)

The following are deliberate HNF1B-DB product policies rather than universal biomedical requirements:

- admins may act as scientific reviewers because HNF1B-DB treats its admin role as curator-capable;
- only admins perform public release;
- pending revisions remain private rather than publicly labelled as unreviewed;
- one independent approval is sufficient.

## 3. Goals and non-goals

### 3.1 Goals

1. Make self-review impossible at every API and UI entry point.
2. Let any eligible curator/admin review an open submission without assignment.
3. Canonicalize before review, freeze candidate content during review, and bind sign-off to an exact revision and full-content digest.
4. Require all blocking review issues to have a recorded disposition before approval.
5. Keep ordinary discussion separate from blocking review issues.
6. Give curators a server-driven queue and focused before/after review workspace.
7. Preserve old public content during re-review and publish the approved content byte-for-byte under the canonical JSON contract.
8. Keep the revision ledger as the sole sign-off audit source; avoid a parallel review-state model.
9. Close comment/approval races for HTTP and direct database writers.
10. Preserve pagination, filtering, sorting, accessibility, mobile behavior, and fail-closed error handling.

### 3.2 Non-goals

- reviewer assignment, claiming, workload balancing, or notifications;
- multi-reviewer voting, panel quorum, or a dedicated editor role;
- field-anchored annotation threads inside the Phenopacket form;
- public access to pending queue metadata or candidate content;
- retroactively classifying ordinary historical comments as blocking issues;
- changing the GA4GH Phenopacket v2 clinical content model;
- conflating source-data `Reviewed By` provenance with application workflow approval.

## 4. Lifecycle and transition policy

### 4.1 State meanings

| Effective state | Meaning | Content editable by |
| --- | --- | --- |
| `draft` | Private candidate not submitted | draft owner |
| `in_review` | Frozen candidate awaiting independent review | nobody |
| `changes_requested` | Reviewer returned candidate with rationale | draft owner |
| `approved` | Frozen candidate independently signed off | nobody |
| `published` | Immutable public head | nobody; editing creates a private clone |
| `archived` | Terminal internal record | nobody |

For a published record with an active edit, `phenopackets.state` remains `published` while `editing_revision.state` is the authoritative effective state. Public reads continue to use `phenopackets.state='published'` plus `head_published_revision_id`; curator workflow reads use effective state.

### 4.2 Allowed transitions

| From | To | Actor and conditions |
| --- | --- | --- |
| `draft` | `in_review` | owner, or admin acting on behalf; publish canonicalization/validation succeeds; reason required |
| `changes_requested` | `in_review` | owner, or admin acting on behalf; publish canonicalization/validation succeeds; reason required |
| `in_review` | `draft` | owner withdraws; admin emergency withdrawal remains audited |
| `in_review` | `changes_requested` | eligible independent curator/admin; reason required |
| `in_review` | `approved` | eligible independent curator/admin; exact candidate revision/digest; zero open blocking issues; attestation and reason required |
| `approved` | `changes_requested` | eligible independent curator/admin reopens before publication; reason required |
| `approved` | `published` | admin only; exact approved revision/full-content digest required; content copied unchanged |
| any active state | `archived` | admin only; reason required |

No transition bypass exists for admins when the rule concerns reviewer independence.

### 4.3 Reviewer eligibility

An actor is eligible to review a candidate only when all of the following hold:

1. The actor is active and has role `curator` or `admin`.
2. `draft_owner_id` is non-null.
3. The actor is not `draft_owner_id`.
4. The actor did not submit the active candidate revision on another user's behalf.
5. The actor did not author a content-changing `created`, `draft_created`, or `draft_saved` revision in the active edit cycle.
6. The candidate is in a reviewable effective state.

The active edit cycle begins after the current published head, or at record creation when there is no published head. State-transition events and discussion activity do not make an actor a content contributor. Contributor checks use immutable revision history, not client claims.

Missing ownership or ambiguous revision ancestry fails closed with a machine-readable error. It is never interpreted as proof that the actor is independent.

## 5. Blocking review issues

### 5.1 Discussion versus review issue

Existing comments remain ordinary discussion and never block approval. A blocking review issue is a comment whose `review_revision_id` references the exact `in_review` revision inspected by the reviewer.

Only an eligible independent reviewer can create a blocking issue while the candidate is `in_review`. The issue remains associated with that immutable snapshot through request-changes, editing, and resubmission. Approval is blocked while any live blocking issue for the record is unresolved, including an issue raised against an earlier submission in the same cycle.

The draft owner may reply in discussion but may not resolve, reopen, or delete a blocking issue. An eligible independent reviewer may resolve or reopen it while the active cycle is `in_review` or `changes_requested`, with a required rationale. Blocking issues cannot be soft-deleted to bypass the gate; retraction is a recorded resolution disposition.

### 5.2 Resolution audit

Resolution and reopening append an immutable event containing:

- issue ID;
- action (`resolved` or `reopened`);
- resolution disposition (`addressed`, `accepted_with_rationale`, `retracted`, or `superseded`) when resolving;
- disposition/rationale;
- authenticated actor ID and role snapshot;
- server timestamp.

The comment row retains `resolved_at` and `resolved_by_id` as the current-state projection. The append-only event log is the audit source.

### 5.3 Race-free invariant

Review-issue creation, resolution, reopening, approval, reopen-approved, and publication acquire the same phenopacket row lock before reading or changing review state. Locks are always acquired phenopacket-first, then comment/revision, to prevent deadlocks.

This lock protocol is enforced for every writer, not merely application services. Database triggers on blocking-issue insert/reopen/resolve and on active-revision/state changes first acquire `SELECT ... FOR UPDATE` on the owning phenopacket row, then validate the operation. Direct SQL writers therefore serialize on the same record-scoped lock. A direct writer that bypasses or disables those triggers is outside the supported write contract.

Approval under the lock verifies:

1. optimistic record revision;
2. reviewer eligibility;
3. active `in_review` revision identity and full-content digest;
4. zero live unresolved blocking issues;
5. valid attestation.

If issue creation wins the lock, approval observes it and returns `409 unresolved_review_issues`. If approval wins, the waiting issue creation observes `approved` and returns `409 review_closed`. No committed state may contain an approved active revision and a newly created unresolved blocking issue.

A deferred database constraint trigger performs a final approved-plus-unresolved check after the lock-taking triggers have serialized non-HTTP writers. The deferred check alone is not treated as concurrency protection. Application locking remains necessary to produce deterministic errors and avoid retry-only behavior.

## 6. Audit and storage changes

### 6.1 Comments

Add:

```text
comments.review_revision_id BIGINT NULL
    REFERENCES phenopacket_revisions(id) ON DELETE RESTRICT

comment_resolution_events
    id BIGINT PK
    comment_id BIGINT NOT NULL REFERENCES comments(id) ON DELETE RESTRICT
    action TEXT NOT NULL CHECK action IN ('resolved', 'reopened')
    disposition TEXT NULL
    rationale TEXT NOT NULL
    actor_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT
    actor_role TEXT NOT NULL
    created_at TIMESTAMPTZ NOT NULL
```

A check constraint requires an allowlisted disposition for `resolved` events and `NULL` disposition for `reopened` events. A partial index covers live unresolved blocking issues by record. Lock-taking triggers verify that `review_revision_id` belongs to the comment's phenopacket record and represents a review snapshot. Historical comments remain `NULL` and non-blocking.

### 6.2 Revision decision metadata

Extend revision audit with a deterministic full-content digest, versioned ledger payload, actor-role snapshot, and structured decision metadata:

```text
phenopacket_revisions.actor_role TEXT NULL
phenopacket_revisions.decision_metadata JSONB NULL
phenopacket_revisions.content_sha256 TEXT NULL
phenopacket_revisions.ledger_version INTEGER NULL
```

`content_sha256` is SHA-256 over the complete `content_jsonb` serialized by the project's versioned canonical JSON function, including `hnf1bCuration` and extension fields. It is not the existing projection-only `projection_hash`. Every new revision records `content_sha256`, `actor_role`, and `ledger_version=2`. The v2 ledger hash covers parent/revision/state/event fields, full-content digest, actor role, and a canonical digest of decision metadata. Existing v1 hashes remain valid and are never rewritten.

An approval revision stores a versioned payload equivalent to:

```json
{
  "schemaVersion": 1,
  "reviewedRevisionId": 123,
  "reviewedContentSha256": "sha256:...",
  "independentReview": true,
  "noUnmanagedConflict": true
}
```

The existing revision actor, timestamp, reason, parent, state, content, projection hash, and ledger hash remain authoritative. The full-content digest closes the extension-field gap left by `projection_hash`. No mutable `reviewed_by` column or separate sign-off table is introduced.

Historical `actor_role`, `content_sha256`, and `ledger_version` remain `NULL`/v1 unless they were captured originally. The migration does not disable append-only protection or reconstruct a historical role from a user's current role. Display falls back to the current user relationship with an explicit “role at decision not recorded” label; it never presents that fallback as an attested snapshot.

### 6.3 Canonical freeze and exact publication

Publish canonicalization and publishability validation run while transitioning `draft` or `changes_requested` to `in_review`, before the candidate becomes reviewable. The resulting `in_review` revision is the exact canonical snapshot shown to reviewers. If canonicalization changes content, that canonical content, revision ID, and digest are returned to the submitter and review workspace.

Approval requires the client-observed candidate revision ID and full-content digest, rechecks them under the row lock, and copies the candidate content unchanged into the approval revision. Publication requires the approved revision ID and digest, rechecks them under the lock, and copies approved `content_jsonb` unchanged into the new public-head revision. Publication performs validation assertions only; it must not canonicalize, default, normalize, timestamp, or otherwise mutate clinical or extension content.

Any server-derived publication metadata must therefore be deterministic and present before review, or stored outside `content_jsonb` as publication audit metadata. Tests compare canonical serialized full content—not only projection fields—across candidate, approval, and published revisions.

### 6.3 Ownership integrity

Add a local constraint that an active editing pointer requires a non-null draft owner. The migration derives missing active owners only when immutable revision ancestry identifies one actor deterministically. It reports and aborts on ambiguous rows instead of guessing. Historical published records without an active edit retain `draft_owner_id=NULL`.

## 7. Backend architecture and API

### 7.1 Boundaries

- A review-policy service owns reviewer eligibility, contributor checks, blocking-issue counts, and actor-specific capabilities.
- A review-query repository owns effective-state SQL, queue pagination, filters, counts, and consistent review-context reads.
- The state service remains the sole writer of lifecycle revisions and public-head swaps.
- The comments service owns discussion and review-issue mutations but participates in router-owned transactions; it no longer commits inside service methods.
- Routers map typed domain failures to stable HTTP error contracts.

### 7.2 Review queue

`GET /api/v2/phenopackets/review-queue` is curator/admin-only and server-driven.

Supported query state:

- `page[number]`, `page[size]`;
- `filter[state]` (`draft`, `in_review`, `changes_requested`, `approved`);
- `filter[owner]` (`mine` or a user ID);
- `filter[eligibility]` (`reviewable_by_me` or `all`);
- `filter[issues]` (`open`, `none`, or `all`);
- `q` for case/subject search;
- allowlisted sorting, defaulting to oldest submission first for `in_review`.

Each lean row includes record/public identifiers, subject label, physical and effective state, owner, submission actor/time, record revision, candidate revision, change count, open blocking-issue count, published-head presence, and actor-specific capabilities. `meta` includes pagination and state counts computed under the same visibility rules.

### 7.3 Review context

`GET /api/v2/phenopackets/{id}/review-context` is curator/admin-only and returns one coherent review snapshot:

- candidate revision metadata and exact candidate content;
- baseline published revision metadata, or `null` for a new record;
- semantic changes grouped into Subject, Phenotypes, Diseases, Variants/Interpretations, Measurements, and Metadata, with operation, path, before, and after values;
- owner, submission, contributor, approval, and publication audit metadata;
- blocking issues plus ordinary discussion summary;
- current record revision and actor-specific capabilities.

The endpoint acquires a read lock compatible with the write protocol or uses one equivalent transactionally consistent query. A new record renders all candidate content as added. A revised record always compares the candidate with the current immutable public head, not merely the preceding save.

### 7.4 Mutations

Continue using `POST /api/v2/phenopackets/{id}/transitions`. Approval additionally requires `candidate_revision_id`, `candidate_content_sha256`, and structured attestation. Publication additionally requires `approved_revision_id` and `approved_content_sha256`. The server rejects irrelevant, missing, or stale conditional fields.

The existing comment routes remain, with explicit discriminated behavior:

- `POST /api/v2/comments`: ordinary discussion keeps its existing body. A blocking issue additionally supplies `record_revision` and `review_revision_id`; the server verifies both and the reviewer's eligibility.
- `POST /api/v2/comments/{id}/resolve`: ordinary discussion keeps backward-compatible optional input. A blocking issue requires `record_revision`, an allowlisted `disposition`, and a non-empty `rationale`; it uses phenopacket-first locking and independent-reviewer checks.
- `POST /api/v2/comments/{id}/unresolve`: ordinary discussion keeps backward-compatible optional input. For a blocking issue this means reopen and requires `record_revision` plus a non-empty `rationale`; it uses the same locking and eligibility checks.
- `DELETE /api/v2/comments/{id}`: continues to soft-delete ordinary discussion. It rejects blocking issues with `409 review_issue_delete_forbidden`, including for admins and the issue author.

Blocking-issue retraction is `resolve` with `disposition='retracted'`; it is never deletion. The server loads the comment, discriminates on `review_revision_id`, and never trusts a client-nominated unrelated revision. Every legacy mutation route is covered by blocking-issue policy tests.

Conditional request fields use explicit schemas:

```text
ApprovalAttestation
    independent_review: Literal[true]
    no_unmanaged_conflict: Literal[true]

TransitionRequest additions
    candidate_revision_id: PositiveInt | null
    candidate_content_sha256: constrained sha256 string | null
    approved_revision_id: PositiveInt | null
    approved_content_sha256: constrained sha256 string | null
    attestation: ApprovalAttestation | null

CommentCreate additions
    record_revision: NonNegativeInt | null
    review_revision_id: PositiveInt | null

ReviewIssueResolveRequest
    record_revision: NonNegativeInt
    disposition: addressed | accepted_with_rationale | retracted | superseded
    rationale: string[1..500]

ReviewIssueReopenRequest
    record_revision: NonNegativeInt
    rationale: string[1..500]
```

For ordinary comments, resolve/unresolve accept no body or an ignored-compatible empty body. For blocking issues the matching typed body is mandatory after the server loads and discriminates the comment. OpenAPI documents both cases and the API contract snapshot is refreshed.

All curator-facing transition controls consume server-returned capabilities; the duplicated matrix in `TransitionMenu.vue` is removed.

### 7.5 Errors

Stable error codes include:

- `self_review_forbidden`;
- `reviewer_contributed`;
- `review_author_unknown`;
- `unresolved_review_issues` with a count;
- `review_revision_mismatch`;
- `review_closed`;
- `review_issue_delete_forbidden`;
- `attestation_required`;
- existing `revision_mismatch` and `invalid_transition`.

Authorization failures use `403`; stale/conflicting workflow state uses `409`; malformed input uses `422`. Viewer/anonymous access to private review endpoints returns `404` where required to avoid existence disclosure.

## 8. Frontend design

### 8.1 Routes and navigation

Add curator-only routes:

- `/curation/reviews` -> `ReviewQueue.vue`;
- `/curation/reviews/:phenopacket_id` -> `PhenopacketReview.vue`.

Add a `requiresCurator` route guard and “Review queue” entries beside “Create Phenopacket” in desktop and mobile Curate navigation.

### 8.2 Queue

The queue uses `AppDataTable` in its default server-driven mode and persists pagination, search, filters, and sorting in the URL. Tabs are:

- Needs review (`in_review`, default);
- Changes requested;
- Approved / awaiting publication;
- My drafts.

Core columns/cards show case/subject, state, owner, submitted time, proposed-change count, open-issue count, eligibility, and an explicit Review/Open action. There is no row-click-only interaction and no bulk approval.

Loading uses stable skeletons. API errors render an alert and Retry rather than an empty table. Empty results distinguish an empty queue from filters with no matches. Mobile cards retain state and issue count as primary signals.

### 8.3 Review workspace

The header shows case ID, state, owner, submission time, candidate revision, public-head status, eligibility, and a back-to-queue link.

The main comparison groups added, removed, and changed values semantically and uses text/icons in addition to color. Secondary views expose the complete candidate, raw JSON, and revision history. A desktop right rail contains unresolved-first review issues, discussion, and the decision panel; mobile stacks these sections and uses a safe-area-aware decision bar.

Actions are driven only by backend capabilities:

- Approve opens an exact-revision confirmation, requires rationale and independent/no-unmanaged-conflict attestation, and remains disabled if issue status is unknown.
- Request changes requires a rationale and preserves blocking issues.
- Reopen approved requires a rationale.
- Publish is admin-only and explicitly states that the approved revision will become public.
- An author/contributor sees why review actions are unavailable.

On `revision_mismatch` or `review_revision_mismatch`, controls are replaced with a reload-required conflict state; the UI never retries a decision blindly. Successful mutations refresh queue counts, context, history, and live announcements.

### 8.4 Existing detail page

The general phenopacket detail page remains a browsing/detail surface. Curators receive an “Open review workspace” affordance for active review states. Any retained transition menu consumes server capabilities so it cannot expose a bypass.

After publication, public detail may show “Independently reviewed” and the approval date. Reviewer identity and internal rationale remain curator/admin-visible, avoiding accidental conflation with source-review provenance.

## 9. Privacy, integrity, and observability

1. Public queries continue to dereference only `head_published_revision_id`.
2. Queue/context endpoints require active curator/admin role and never expose candidate data to viewers.
3. Public search, aggregates, exports, and MCP results remain pinned to published heads during re-review.
4. Canonicalization occurs before `in_review`; approval and publication assert the stored full-content digest and never alter approved clinical or extension content.
5. Reviewer identity comes from authentication, never request bodies.
6. Logs record transition/error codes and record/revision IDs but never clinical content or comment bodies.
7. Metrics cover queue depth/age by state, approval latency, request-changes rate, and gate failures without patient-identifying labels.

## 10. Migration and rollout

1. Use an expand migration for nullable columns/table/indexes and an activation migration for lock-taking triggers, constraints, and ownership enforcement, both based on the current head.
2. Preflight active edit cycles and deterministically backfill missing owners; abort with record IDs on ambiguity.
3. Leave historical comments non-blocking and historical revision audit fields unset; report their counts.
4. Deploy backend schema/API support before enabling frontend navigation.
5. Keep legacy `changes_requested` and history rendering throughout rollout.
6. Validate queue counts against direct effective-state SQL before enabling decisions.
7. Exercise the complete two-curator lifecycle in staging/local production-like configuration.

Rollback is expand/activate, not destructive schema reversal. Application code may roll back while the added schema and audit rows remain. Alembic downgrade must refuse once any blocking issue, resolution event, v2 ledger revision, or decision metadata exists. Before activation and before any such data exists, downgrade may remove the unused expansion. This matches the repository precedent for refusing unsafe audit/invariant downgrades.

No destructive data cleanup or audit erasure is part of migration or rollback.

## 11. Testing strategy

### 11.1 Backend

- pure policy matrix for every role, state, owner, contributor, and NULL-owner combination;
- non-author curator/admin approval and request-changes;
- author and content-contributor self-review rejection;
- pre-review canonicalization and full-content digest stability, including extension-only changes;
- admin-only publication and byte-for-byte canonical equality with the approved full-content snapshot;
- ordinary, blocking, resolved, reopened, retracted, and historical comments;
- required resolution rationale and approval attestation;
- request-changes/resubmission with outstanding issues;
- approved-to-changes-requested reopening;
- two-real-session service-level issue-create versus approve and issue-reopen versus approve in both lock orders;
- two-connection raw-SQL issue/approval races in both commit orders, proving lock-taking triggers prevent write skew;
- concurrent approvals/request-changes with exactly one winner;
- queue projection, counts, search, allowlisted sorting, and pagination;
- physical `published` plus effective `in_review` projection;
- new-record privacy and old-public-head visibility throughout re-review;
- migration expand/activate, guarded downgrade refusal after audit data exists, deterministic owner backfill, ambiguity failure, lock-taking/deferred triggers, and legacy comment handling;
- every legacy resolve/unresolve/delete route against a blocking issue;
- approval audit actor/role/attestation and immutable revision behavior.

### 11.2 Frontend

- curator route guard and desktop/mobile navigation;
- URL-backed server queue state;
- loading, retry, true-empty, filtered-empty, and permission states;
- effective-state and capability rendering;
- semantic diff additions/removals/changes and no-baseline behavior;
- author/contributor explanations;
- unresolved/unknown issue approval gate;
- transition payloads, attestation, and structured 403/409 handling;
- discussion/review issue counts after create, resolve, reopen, and response;
- keyboard focus, accessible names, `aria-live`, non-color cues, and mobile layout.

### 11.3 End to end

The principal Playwright scenario uses distinct accounts:

1. Curator A creates and submits a new private case.
2. Anonymous/viewer access cannot discover the candidate.
3. Curator A cannot approve it.
4. Curator B finds it through the server-driven open queue.
5. Curator B creates a blocking issue and requests changes.
6. Curator A edits, responds, and resubmits.
7. Curator B records resolution and approves the exact revision.
8. The case remains non-public until an admin publishes it.
9. Public list/detail/search expose the approved content only after publication.
10. A second cycle proves the old public head stays visible until the replacement is published.

Additional E2E coverage verifies approved reopening, stale-revision conflicts, keyboard-only decisions, and the mobile queue/workspace.

## 12. Acceptance criteria

The feature is complete only when all of the following are proven:

1. No owner, active candidate submitter, or active-cycle content contributor can approve/request changes through UI, API, or direct transition service use.
2. An eligible non-author curator and admin can review without assignment.
3. Approval cannot commit with a live unresolved blocking issue, including under concurrent writes.
4. Every approval identifies the exact candidate revision/full-content digest, reviewer, role snapshot, rationale, attestation, and time.
5. Admin publication copies only that approved full-content snapshot without publish-time mutation.
6. New candidates are private and old published heads remain public throughout re-review.
7. The review queue is server-paginated/sorted/filtered and displays effective state correctly.
8. The review workspace provides a usable before/after comparison, issues, history, and actor-correct actions on desktop and mobile.
9. Ordinary historical comments do not unexpectedly block approval.
10. Backend tests, frontend tests, lint, formatting, typing, build, focused Playwright, migration checks—including raw-SQL concurrency and guarded downgrade—and relevant GitHub Actions pass.
11. A one-pass independent high-reasoning spec review and a one-pass independent high-reasoning PR review are completed, with actionable findings resolved or explicitly documented.

## 13. Rejected alternatives

### Separate sign-off/review-round tables

They would support quorum and multiple decisions but duplicate the existing immutable revision ledger. Add them only if panel voting becomes a real requirement.

### Dedicated editor role

This mirrors CIViC more literally but conflicts with the selected curator/admin open queue and adds role-administration work without improving the requested one-reviewer invariant.

### Reusing the general registry and detail page unchanged

This keeps public browsing and workflow review tangled, forces client-side joins, and leaves race-prone permission logic in the frontend.

### Treating every unresolved comment as blocking

Historical and conversational comments would unexpectedly veto publication. Only explicitly revision-bound review issues participate in the gate.

### Collapsing `changes_requested` into `draft`

The explicit state distinguishes a reviewer return from voluntary drafting and preserves workflow metrics, queue clarity, and audit meaning.

## 14. Known trade-offs

- One independent sign-off is a local quality-control threshold, not expert-panel consensus.
- Admins count as scientific reviewers by explicit HNF1B-DB policy; actor role and attestation make that decision auditable.
- Open queues improve throughput but do not balance workload; assignment can be added later without changing the sign-off invariant.
- Revision-bound blocking issues are intentionally record-level gates across a review cycle rather than field-anchored annotations.
- Database constraint triggers add complexity, justified by the clinical-publication invariant and the existence of non-HTTP maintenance/import paths.
