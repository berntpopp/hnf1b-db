# Curation review workflow

This guide describes the operator-facing four-eyes review workflow for Phenopackets,
the audit guarantees behind it, and the required database rollout and rollback order.

## Roles and access

- Curators and administrators can open the review queue and review workspace.
- Viewers and anonymous users cannot discover private candidates through the queue,
  detail, search, aggregate, export, or MCP surfaces.
- Administrators can publish an approved revision and archive records, but they do not
  bypass reviewer-independence rules.
- There is no assignment or claim step. Any eligible curator or administrator may take
  the next review action from the open queue.

The backend returns actor-specific capabilities. The frontend displays those
capabilities; it does not infer permission from role or state.

## Lifecycle

The review lifecycle is:

```text
draft -> in_review -> changes_requested -> in_review -> approved -> published
             |                                  |
             +--------------> draft             +-> changes_requested
```

An administrator may archive an active record. While a published record has a private
replacement cycle, its physical state remains `published` and its editing revision
holds the effective workflow state.

### Submit for review

The draft owner, or an administrator acting on the owner's behalf, submits a `draft`
or `changes_requested` record. Submission canonicalizes and validates the complete
Phenopacket before creating the immutable `in_review` candidate. The candidate revision
ID and its `sha256:` full-content digest identify exactly what reviewers inspect.

### Request changes and resubmit

An eligible independent reviewer may request changes with a rationale. The owner edits
the private draft, may add ordinary discussion replies, and resubmits. Blocking issues
from an earlier submission remain part of the active edit cycle until explicitly
resolved or retracted.

### Approve

Approval requires all of the following under the record lock:

1. The optimistic record revision is current.
2. The actor is an eligible independent reviewer.
3. The candidate revision ID and full-content digest match the active candidate.
4. No active-cycle blocking issue is open.
5. The actor supplies a rationale and attests that the review is independent and has no
   unmanaged conflict.

The approval revision records the reviewer ID, reviewer role at decision time, server
time, rationale, attestation, reviewed revision ID, and reviewed full-content digest.
Changing any identity or content field requires a reload and a new decision.

### Publish

Only an administrator may publish. Publication requires the exact approved revision ID
and digest and copies that revision's complete `content_jsonb` unchanged. It does not
canonicalize, default, normalize, or add timestamps at publish time.

Until publication commits, a new record is absent from public reads. During a
replacement cycle, public list, detail, search, aggregate, export, and MCP reads stay
pinned to `head_published_revision_id`, so the old published head remains visible.

## Reviewer independence

A reviewer must be an active curator or administrator and must not be any of the
following in the active edit cycle:

- the draft owner;
- the actor who submitted the active candidate; or
- an actor who authored a content-changing `created`, `draft_created`, or `draft_saved`
  revision.

The active cycle starts after the current published head, or at record creation for a
never-published record. State transitions, review decisions, and discussion activity do
not make an actor a content contributor. Missing ownership or ambiguous authorship fails
closed. Administrators are subject to the same exclusions.

## Discussion and blocking issues

Ordinary comments have no `review_revision_id`. They remain non-blocking, including
historical comments created before this workflow was activated.

A blocking review issue identifies the immutable `in_review` revision inspected by its
author. Only an eligible independent reviewer can create one. The owner may reply in
ordinary discussion but cannot resolve, reopen, delete, or silently erase an issue.

An eligible reviewer resolves an issue with one disposition and a rationale:

- `addressed`;
- `accepted_with_rationale`;
- `retracted`; or
- `superseded`.

Reopening also requires a rationale. Each resolve or reopen action appends an immutable
event containing the actor and role snapshot, disposition, rationale, and server time.
The comment's resolution fields are only a current-state projection of that event log.
Retraction is a recorded resolution disposition, never deletion.

Approval and issue writers take the phenopacket lock first. If issue creation commits
first, approval returns `409 unresolved_review_issues`; if approval commits first, the
waiting issue creation returns `409 review_closed`. Database triggers apply the same
lock order and final invariant to supported direct-SQL writers.

## Queue and workspace operations

The review queue is server-paginated, sorted, searched, and filtered. URL state can be
shared without switching to client-side slicing or sorting. Queue rows show physical and
effective state, owner, submission, change count, open issue count, and actor-specific
eligibility.

The review workspace compares the candidate with the immutable public baseline and
provides:

- sectioned semantic changes with before and after values;
- the complete candidate rendered in cards and as raw JSON;
- owner, submission, contributor, approval, and publication audit history;
- active-cycle issues and record-wide discussion totals; and
- server-authoritative actions and structured conflict recovery.

The workspace supports keyboard operation and its single-column mobile layout. After a
stale revision, digest, or record-version conflict, reload the authoritative context
before making another decision.

## Database rollout

Apply the rollout in this exact order:

1. Upgrade to `d0f422b00005` (nullable expansion and audit storage).
2. Deploy the backend that writes v2 revision digests/decision metadata and maintains
   the resolution projection while only the expansion schema is present.
3. Upgrade to `e0f422b00006` (ownership, locks, constraints, and activation triggers).
4. Upgrade to `f0f422b00007` (forward reconciliation and final trigger definitions).
5. Confirm `alembic current` and `alembic heads` both report `f0f422b00007` before
   enabling the frontend navigation.

The `f0` step is required even for a database already stamped at `e0`; it reconciles safe
resolution-projection drift and installs the final trigger definitions. It preserves a
later legitimate comment `updated_at` while repairing older event projections.

Before enabling review decisions, compare queue state/counts with direct effective-state
SQL and exercise the distinct-curator lifecycle in the deployed environment.

## Guarded rollback

Rollback is non-destructive and audit-preserving:

- Application code may be rolled back while the expanded schema and audit rows remain.
- An empty, unused activation/expansion can be downgraded.
- Alembic refuses the destructive activation/expansion downgrade after any blocking
  issue, resolution event, v2 ledger revision, actor-role snapshot, content digest, or
  decision metadata exists.
- Do not delete review audit data, rewrite immutable revisions, disable the invariant
  triggers, or force the Alembic stamp to bypass the guard.

If a guarded downgrade refuses, keep the database at the forward head, restore a
compatible backend, and investigate the specific audit-evidence count reported by the
migration.

## Operational checks

After deployment, verify:

- the health endpoint reports database and Redis connectivity;
- the database revision matches `f0f422b00007`;
- anonymous and viewer requests do not disclose candidates;
- two distinct curators can complete issue, request-changes, resubmission, resolution,
  and exact approval steps;
- publication exposes only the approved snapshot; and
- a replacement cycle leaves the old public head visible until the new publication.

Stable failures include `self_review_forbidden`, `reviewer_submitted`,
`reviewer_contributed`, `review_author_unknown`, `unresolved_review_issues`,
`review_revision_mismatch`, `revision_mismatch`, `review_closed`,
`review_issue_delete_forbidden`, and `attestation_required`. Treat these as actionable
workflow outcomes; do not retry them as transient transport errors.
