# Concurrent Remediation Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the live 2026-04-23 review findings as fast as possible by executing backend hardening, frontend correctness, and docs hygiene in parallel without cross-lane conflicts.

**Architecture:** This program is split into three mostly independent implementation lanes plus one integration lane. Backend lane owns runtime safety and fail-closed behavior. Frontend lane owns user-visible workflow correctness and UI infrastructure. Docs lane owns durable references and release-facing truth. Integration happens only after all three lanes pass their lane-local checks.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Redis, Pydantic 2, Vue 3, Vuetify 4, Axios, Vitest, Playwright, pytest, Markdown docs.

---

## Program Structure

### Lane A: Backend hardening

Plan file:
- `.planning/plans/2026-04-23-backend-hardening-plan.md`

Owns:
- production email fail-closed
- production cookie secure fail-closed
- Redis production contract
- readiness/health semantics
- blocking sync ontology I/O removal
- transaction-boundary cleanup

Primary write set:
- `backend/app/core/config.py`
- `backend/config.yaml`
- `backend/app/main.py`
- `backend/app/core/cache.py`
- `backend/app/hpo_proxy.py`
- `backend/app/services/ontology_service.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/auth/credential_tokens.py`
- backend tests only

### Lane B: Frontend workflow and UX correctness

Plan file:
- `.planning/plans/2026-04-23-frontend-workflow-hardening-plan.md`

Owns:
- SearchCard variant routing mismatch
- session-expiry return intent
- Vuetify plugin mounting
- history/revisions tab
- accessibility/test hardening follow-ups

Primary write set:
- `frontend/src/main.js`
- `frontend/src/plugins/vuetify.js`
- `frontend/src/components/SearchCard.vue`
- `frontend/src/api/transport.js`
- `frontend/src/router/index.js`
- `frontend/src/views/PagePhenopacket.vue`
- new revision/history components if needed
- frontend tests only

### Lane C: Durable docs and release hygiene

Plan file:
- `.planning/plans/2026-04-23-docs-release-hygiene-plan.md`

Owns:
- remove durable links into `.planning`
- supersede ADR 0001
- align auth/session docs
- align docs URLs to `/api/v2/docs`
- align deployment/env-file docs

Primary write set:
- `README.md`
- `backend/README.md`
- `frontend/README.md`
- `docs/README.md`
- `docs/adr/0001-jwt-storage.md` or successor ADR
- `docs/api/README.md`
- `docs/api/variant-annotation.md`
- `docs/user-guide/README.md`
- `docs/user-guide/variant-annotation.md`
- `docs/deployment/docker.md`

### Lane D: Final integration and release verification

Owns:
- lane merge order
- final verification
- final score reassessment against `.planning/reviews/2026-04-23-senior-codebase-review.md`

Primary write set:
- none unless follow-up fixes are required

---

## Maximum-Concurrency Rules

- [ ] Run Lane A, Lane B, and Lane C in parallel from the start.
- [ ] Use a fresh worktree for the remediation program before execution starts.
- [ ] Use one implementer subagent per task, not one subagent per lane, so failures stay isolated.
- [ ] Keep write sets disjoint. If a task touches files owned by another lane, split that task before dispatch.
- [ ] Do not start Lane D until Lane A, Lane B, and Lane C all report green lane-local verification.
- [ ] Treat any shared-file collision as a planning bug and re-split before coding.

---

## Recommended Dispatch Order

### Phase 1: Parallel kickoff

- [ ] Dispatch Lane A Task 1 from `.planning/plans/2026-04-23-backend-hardening-plan.md`
- [ ] Dispatch Lane B Task 1 from `.planning/plans/2026-04-23-frontend-workflow-hardening-plan.md`
- [ ] Dispatch Lane C Task 1 from `.planning/plans/2026-04-23-docs-release-hygiene-plan.md`

Expected result:
- three active subagents
- no shared write set
- all three lanes progressing independently

### Phase 2: Keep each lane saturated

- [ ] As soon as a lane task clears spec review and code-quality review, dispatch that lane’s next task immediately.
- [ ] Keep at most one active implementer per write set.
- [ ] Prefer pairing low-risk doc tasks with backend/frontend coding tasks so reviewer time is not idle.

### Phase 3: Integration gate

- [ ] After all lane tasks are complete, run the full verification bundle below from the main controller session.
- [ ] Only if verification is green, update the release assessment and prepare the branch for merge/PR.

---

## Final Verification Bundle

- [ ] Run backend targeted hardening checks:

```bash
cd backend && uv run pytest \
  tests/test_core_config.py \
  tests/test_auth_csrf.py \
  tests/test_email_sender.py \
  tests/test_auth_password_reset.py \
  tests/test_auth_refresh_sessions.py \
  tests/test_dev_endpoints.py -v
```

- [ ] Run backend operability / ontology / auth transaction checks added by Lane A:

```bash
cd backend && uv run pytest \
  tests/test_security_headers.py \
  tests/test_ontology_service.py \
  tests/test_request_id.py -v
```

- [ ] Run frontend targeted unit checks:

```bash
cd frontend && npm test -- \
  tests/unit/components/SearchCard.spec.js \
  tests/unit/api/transport.spec.js \
  tests/unit/views/AdminUsers.spec.js \
  tests/unit/views/ForgotPassword.spec.js \
  tests/unit/views/PagePhenopacket*.spec.js
```

- [ ] Run frontend production build:

```bash
cd frontend && npm run build
```

- [ ] Run frontend key Playwright flows:

```bash
cd frontend && npx playwright test \
  tests/e2e/ui-hardening-a11y.spec.js \
  tests/e2e/comments.spec.js \
  tests/e2e/table-url-state.spec.js
```

- [ ] Spot-check durable docs:

```bash
rg -n "\.planning/plans/variant-annotation-implementation-plan|localStorage|http://localhost:8000/docs" \
  README.md backend/README.md frontend/README.md docs
```

Expected:
- no durable `.planning` references in docs
- no stale localStorage auth claims
- no stale `/docs` references where `/api/v2/docs` is correct

---

## Merge Order

- [ ] Merge Lane A first if it changes runtime startup behavior.
- [ ] Merge Lane B second.
- [ ] Merge Lane C third, rebased onto the post-Lane-B branch if doc examples changed.
- [ ] Run Lane D verification after the final merge order is assembled, not before.

---

## Success Criteria

- [ ] Production startup rejects console email backend.
- [ ] Production startup rejects insecure auth cookies.
- [ ] Redis production contract is explicit and enforced.
- [ ] `/health` reflects real readiness/liveness semantics.
- [ ] SearchCard variant selection lands on a filtered variants experience.
- [ ] The app mounts the actual Vuetify configuration.
- [ ] Durable docs match the live auth/session/runtime model.
- [ ] The remaining score blockers in `.planning/reviews/2026-04-23-senior-codebase-review.md` are resolved or intentionally downgraded with evidence.

