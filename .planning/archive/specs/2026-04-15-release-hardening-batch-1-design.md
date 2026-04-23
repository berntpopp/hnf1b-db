# Release Hardening Batch 1 Design

Date: 2026-04-15
Status: Draft for review

## Goal

Define the first high-gain release-hardening milestone that maximizes speed, accuracy, and visible progress through parallel execution, while reducing the largest current release blockers on `main`.

This batch is intentionally limited to three parallel workstreams:

1. auth core hardening
2. verification stabilization
3. workflow guardrails

## Why This Batch

Current `main` after PR `#254` still has four categories of blocking risk:

- token issuance and refresh semantics are not strict enough
- frontend auth still persists tokens in `localStorage`
- timeline and delete/state workflow protections are still incomplete
- backend/frontend verification is not stable enough to trust as a release gate

The first release-hardening batch should reduce those risks without broadening scope into lower-priority product work such as ORCID, dashboard work, or general workflow enrichment.

## Scope

### In Scope

#### Track A: Auth Core

- enforce inactive/locked-account checks on all token issuance paths
- tighten refresh-token invalidation semantics
- define the backend/frontend transport contract for moving away from long-lived frontend token persistence
- implement the minimum frontend auth transport changes required by the chosen backend auth model
- add targeted regression coverage for login, refresh, logout, and password-change/reset-related invalidation

#### Track B: Verification Stability

- fix test isolation and async session-boundary problems currently causing flaky or invalid backend failures
- fix frontend test/dependency breakage introduced by merged comments components
- define a small, repeatable release-verification command set for this batch
- make auth/workflow test results trustworthy enough to gate merge decisions

#### Track C: Workflow Guardrails

- apply the visibility model to the timeline endpoint
- harden delete/state mutation behavior against concurrent race windows
- add targeted tests for unauthorized timeline access and concurrent delete/state edge cases

### Out Of Scope

- ORCID and attribution preferences
- contributor dashboard
- general comments/discussion polish
- full curation-history UI
- broad documentation cleanup beyond what is required to execute this batch safely
- unrelated tech-debt cleanup

## Architecture

This batch is a coordination design, not a feature architecture. The key architecture decision is to split work by ownership and merge-risk, not by subsystem completeness.

### Parallel Structure

#### Track A: Auth Core

Primary ownership:

- `backend/app/api/auth_endpoints.py`
- `backend/app/auth/*`
- `backend/app/repositories/user_repository.py`
- `frontend/src/stores/authStore.js`
- `frontend/src/api/session.js`
- `frontend/src/api/transport.js`
- auth-related backend/frontend tests

Purpose:

- remove broken-authentication gaps
- define the durable auth flow the release candidate will use

Constraints:

- avoid unnecessary changes to unrelated user-management or identity-lifecycle flows
- keep backend/frontend auth contract explicit
- do not rely on verification fixes being completed before writing the intended behavior tests

#### Track B: Verification Stability

Primary ownership:

- `backend/tests/conftest.py`
- failing backend auth/workflow test files
- frontend test config and dependency fixes required to run current tests

Purpose:

- remove deadlocks, fixture collisions, duplicate seeded-user issues, and session-boundary failures
- restore confidence in targeted checks

Constraints:

- this track should not redefine business rules
- if a failure is clearly a product defect rather than a harness defect, hand ownership back to Track A or C

#### Track C: Workflow Guardrails

Primary ownership:

- `backend/app/phenopackets/routers/crud_timeline.py`
- `backend/app/phenopackets/services/phenopacket_service.py`
- related repositories/helpers only if required
- related workflow tests

Purpose:

- close the most serious non-auth data exposure and concurrency risks

Constraints:

- do not expand into full workflow/history redesign
- keep the scope on visibility and atomicity only

## Worktree And Agent Model

Execution should use sibling git worktrees, one per track:

- `hnf1b-db.worktrees/release-hardening-auth-core`
- `hnf1b-db.worktrees/release-hardening-verification`
- `hnf1b-db.worktrees/release-hardening-workflow`

One worker agent should own each track. The main thread should not duplicate track work. Its role is:

- create the master plan
- dispatch workers with explicit file ownership
- review outputs and integrate decisions
- resolve cross-track contract questions
- run final verification

## Coordination Rules

### Cross-Track Dependencies

- Track B can start immediately because it fixes existing failures and dependency issues.
- Track A can start immediately on backend auth semantics and transport design.
- Track C can start immediately because its write scope is mostly independent.

Expected coordination points:

- Track A and Track B must agree on the auth regression command set.
- Track C and Track B must agree on the concurrency/visibility verification slice.
- If Track A changes auth endpoint contracts, Track B updates tests rather than blocking Track A from progressing.

### Merge Order

Preferred order:

1. Track B dependency/harness fixes that unblock trustworthy checks
2. Track A and Track C in either order, depending on which reaches verification-ready state first
3. final integration pass

If Track B cannot fully land first, it must at least establish enough stability that Track A and Track C can validate their own slices reliably.

## Approach Options Considered

### Option 1: Auth only

Pros:

- simplest coordination
- fastest narrow milestone

Cons:

- leaves known workflow leaks open
- leaves test instability as a persistent drag on every follow-up step

### Option 2: Auth + Verification + Workflow Guardrails

Pros:

- best balance of parallelism and release-risk reduction
- keeps write scopes mostly separable
- produces visible progress on all highest-severity areas

Cons:

- requires tighter coordination than a single-track plan

Recommendation:

Choose this option.

### Option 3: Broad hardening sweep

Pros:

- may reduce total elapsed time if coordination is perfect

Cons:

- higher merge conflict risk
- more token and review overhead
- easier to blur critical-path ownership

## Success Criteria

Batch 1 is successful when:

- locked and inactive users cannot mint fresh tokens on login or refresh
- refresh invalidation semantics are explicitly enforced after credential rotation
- frontend auth no longer depends on the old long-lived persistence model selected for replacement
- timeline reads obey the intended visibility rules
- delete/state race protection is materially stronger and regression-tested
- targeted backend auth/workflow slices run without current isolation/setup failures
- frontend tests no longer fail from missing merged dependencies/config for current components

## Verification Requirements

Before calling this batch complete, run fresh verification evidence for:

- targeted backend auth slice
- targeted backend workflow slice
- targeted frontend unit slice
- any new regression tests added by the three tracks

The exact commands belong in the implementation plan, not this design, but the design requires that verification stay small, repeatable, and track-aligned.

## Risks

### Risk: Auth transport migration spills into too much frontend refactoring

Mitigation:

- define the minimum release-safe transport shape first
- postpone non-essential auth UX cleanup

### Risk: Verification track spends time masking real product defects

Mitigation:

- classify each failure as harness defect or product defect before assigning ownership
- push product defects back to Track A or C explicitly

### Risk: Workflow atomicity fix becomes a broad state-machine redesign

Mitigation:

- constrain scope to final-mutation guarding and tests
- reject broader refactors in this batch

## Next Step

Write one implementation plan that decomposes this design into three parallel tracks with explicit file ownership, verification checkpoints, and worker handoff instructions.
