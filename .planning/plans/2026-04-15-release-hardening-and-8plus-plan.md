# Release Hardening And >8.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the fastest credible path to a stable release candidate by closing the remaining security, workflow-integrity, and verification gaps that currently keep HNF1B-DB below a defensible `>8.0/10` platform score.

**Architecture:** This plan treats release readiness as a hardening program, not a feature wave. Work proceeds in four gates: security/session hardening, workflow integrity, verification stabilization, and release-doc/runtime cleanup. Collaboration enrichments such as D.2 comments remain secondary unless they directly help release readiness.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Alembic, Redis, Pydantic 2, Vue 3, Vuetify 4, Axios, Vitest, Playwright, pytest.

---

## Status

This is the **single current planning document** for the next release-hardening steps.

Audit update: as of 2026-04-23, most auth/workflow hardening slices from this
plan are implemented on `main`. The remaining live blockers are:

- production email must fail closed instead of defaulting to console delivery
- durable docs still link to `.planning/` implementation plans as reference docs
- release-facing docs and ADRs still lag the live auth/session model
- the April 17 UI review still has medium/low follow-up items

It consolidates and supersedes as the active execution driver:

- `.planning/archive/reviews/2026-04-15-senior-codebase-platform-review.md`
- `.planning/archive/reviews/2026-04-15-path-to-8plus-and-pr-254-review.md`
- `.planning/archive/plans/2026-04-14-wave-7-d2-comments-and-clone-advancement.md`

Those archived documents remain useful as historical analysis and feature-specific references, but this file is the source of truth for sequencing and go/no-go release decisions.

## Release Goal

Reach a release candidate that is:

- secure enough for controlled multi-user rollout
- stable under normal editorial workflow concurrency
- backed by trustworthy backend and frontend verification
- documented clearly enough that planning artifacts are not acting as production docs

## Explicit Non-Goals For This Release

Do not expand scope into these until the release gates below are green:

- ORCID link/unlink
- attribution preferences
- contributor dashboard
- broader workflow enrichment beyond hardening follow-ups

## Release Gates

The release is not ready until all four gates are green.

### Gate 1: Security

- no auth or refresh token persistence in frontend `localStorage`
- locked and inactive users cannot mint new tokens on any issuance path
- password reset and password change invalidate refresh capability
- refresh-token persistence is no longer raw-token-on-user-row only
- production email delivery fails closed instead of silently degrading to console delivery

### Gate 2: Workflow Integrity

- timeline/detail access obey the same visibility model
- soft-delete and state-changing mutations are atomic under concurrency
- publication edit/save preserves PMIDs correctly
- duplicate-email admin updates fail as clean `409` conflicts

### Gate 3: Verification

- targeted backend auth slice passes
- targeted backend workflow slice passes
- frontend auth/admin/edit regression slices pass
- reruns are stable enough to trust red/green signals

### Gate 4: Release Hygiene

- durable docs no longer point at active planning files as developer guides
- `AGENTS.md` is the canonical instruction source everywhere current docs reference repository instructions
- release-facing docs match live behavior and configuration rules

## Recommended Order Of Work

1. Security/session hardening
2. Workflow integrity fixes
3. Verification stabilization
4. Release docs/runtime cleanup
5. Reassess D.2 / PR `#254` merge only after the first four are materially complete

## Workstreams

### Workstream A: Security And Session Hardening

This is the highest-leverage work. It should start before any additional collaboration features.

- [x] Enforce account state on every token issuance path.
  Files:
  `backend/app/api/auth_endpoints.py`
  `backend/app/auth/dependencies.py`
  `backend/app/repositories/user_repository.py`
  Tests:
  add locked-login, inactive-refresh, and unlock-follow-up regression coverage under `backend/tests/`.

- [x] Replace frontend long-lived token persistence.
  Files:
  `frontend/src/stores/authStore.js`
  `frontend/src/api/session.js`
  `frontend/src/api/transport.js`
  Goal:
  move to HttpOnly refresh cookie plus short-lived in-memory access token.

- [x] Add CSRF protection for refresh/logout/mutation routes if cookie refresh is introduced.
  Files:
  backend auth/router and frontend transport/auth plumbing.

- [x] Rework refresh-token invalidation semantics.
  Minimum:
  password change and password reset revoke existing refresh capability.
  Prefer:
  hashed refresh token material or token-version / JTI invalidation instead of raw token storage.

- [ ] Make production email delivery fail closed.
  Files:
  `backend/app/core/config.py`
  `backend/config.yaml`
  Goal:
  production startup must reject console backend unless explicitly allowed for non-prod.

### Workstream B: Workflow Integrity

- [x] Lock down the timeline endpoint to the same visibility rules as detail/list routes.
  Files:
  `backend/app/phenopackets/routers/crud_timeline.py`
  related detail/list visibility helpers and tests.

- [x] Make delete/state mutations atomic.
  Files:
  `backend/app/phenopackets/services/phenopacket_service.py`
  related state/transition services.
  Goal:
  final mutation guarded by revision predicate or row lock, not only pre-read checks.

- [x] Fix the phenopacket publication binding regression.
  Files:
  `frontend/src/views/PhenopacketCreateEdit.vue`
  Goal:
  one source of truth for publication editing and save payload generation.

- [x] Normalize duplicate-email update handling to explicit conflict responses.
  Files:
  backend admin/auth update paths and repository methods.

### Workstream C: Verification Stabilization

- [x] Define the required release verification slices and keep them small enough to run often.
  Backend target groups:
  auth/session lifecycle
  state workflow
  delete/concurrency
  Frontend target groups:
  auth store/transport
  admin user management
  phenopacket edit regression

- [x] Fix fixture/session-boundary defects that make targeted backend slices unreliable.
  Focus:
  async SQLAlchemy session isolation and fixture cleanup discipline.

- [ ] Add at least one real concurrent integration test for edit/delete or state/delete races.

- [x] Add frontend regression coverage for existing-record PMID preservation.

- [x] Add one release-candidate command list and use it consistently before merge.
  Candidate commands:
  `cd backend && make test`
  `cd backend && uv run pytest tests/test_dev_endpoints.py tests/test_pwdlib_rehash.py -v`
  `cd backend && uv run pytest tests/test_state_flows.py tests/test_api_transitions.py tests/test_phenopackets_delete_revision.py tests/test_crud_related_and_timeline.py -v`
  `cd frontend && npm test`

### Workstream D: Release Hygiene And Planning Cleanup

- [ ] Remove durable doc links that treat `.planning/` files as end-user or developer reference docs.
  Files:
  `docs/api/README.md`
  `docs/api/variant-annotation.md`
  `docs/user-guide/README.md`
  `docs/user-guide/variant-annotation.md`
  `backend/README.md`

- [x] Keep `AGENTS.md` as canonical and reduce current references to `CLAUDE.md` in live docs/plans.
  Status:
  canonicalization is complete in the active planning/docs surface; remaining
  `CLAUDE.md` references are historical or archived.

- [x] Update planning indexes so this file is the current active release plan and older documents are clearly historical/supporting.

## PR #254 Position

PR `#254` is not the current release driver.

Treat it as:

- acceptable to merge after the hardening work if it does not reintroduce verification instability
- acceptable to mine for already-completed D.2 code and tests where they help release readiness
- not sufficient evidence on its own for a `>8.0` or release-ready claim

## Exit Criteria

The next release candidate can be called credible only when:

1. Gate 1 through Gate 4 are all green.
2. Fresh verification evidence exists for the required backend and frontend slices.
3. No known critical or high-severity auth/visibility/concurrency bug remains open.
4. Durable docs no longer depend on internal planning files for operational guidance.

## Immediate Next Step

Finish the remaining hardening/doc cleanup in this order:

1. production email fail-closed
2. durable doc link cleanup out of `.planning/`
3. ADR and release-facing auth/session docs refresh
4. remaining release-candidate verification reruns
5. medium/low UI follow-up work from the 2026-04-17 review

Only after those are in place should the codebase be rescored for `>8.0` and considered for release-candidate signoff.
