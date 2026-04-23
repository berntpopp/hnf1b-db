# Workstream B Slices: Publication Binding And Duplicate-Email Conflicts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the next two Workstream B slices by fixing the phenopacket publication edit/save regression in the frontend and normalizing duplicate-email update failures to explicit `409` conflicts in backend update paths.

**Architecture:** The frontend fix keeps publication edit state and payload generation on a single backend-aligned source of truth so edit-mode load, form binding, and save all operate on the same structure. The backend fix introduces explicit duplicate-email conflict handling in the user update path so admin/auth user updates fail predictably with API-level `409` semantics instead of leaking lower-level integrity behavior.

**Tech Stack:** Vue 3, Vuetify 3, Vitest, FastAPI, SQLAlchemy async, pytest.

---

## Context

Source of truth: `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`

This execution slice covers:

- Workstream B: fix the phenopacket publication binding regression
- Workstream B: normalize duplicate-email update handling to explicit conflict responses

## File Map

Frontend track:

- Modify: `frontend/src/views/PhenopacketCreateEdit.vue`
- Add/modify test: `frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`

Backend track:

- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/api/auth_endpoints.py`
- Modify/add tests: `backend/tests/test_auth_user_management_endpoints.py`

## Task 1: Frontend Publication Binding Regression

**Files:**
- Modify: `frontend/src/views/PhenopacketCreateEdit.vue`
- Test: `frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`

- [ ] **Step 1: Write the failing regression test**

Create a unit test that mounts the edit view with a fetched phenopacket whose `metaData.externalReferences` contains PMID references, verifies the input binds to those PMIDs, edits one PMID, submits, and asserts the `updatePhenopacket()` payload contains the updated PMID in `phenopacket.metaData.externalReferences`.

- [ ] **Step 2: Run the test to verify it fails for the right reason**

Run: `cd frontend && npm test -- frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`
Expected: FAIL because edit-mode load stores publications on a different property than the template/save path uses.

- [ ] **Step 3: Implement the minimal fix**

Update `PhenopacketCreateEdit.vue` so publication editing and payload generation use one source of truth. Keep the editable collection on the phenopacket object that is actually submitted, and normalize to/from `metaData.externalReferences` in one place.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`
Expected: PASS

- [ ] **Step 5: Run nearby regression coverage**

Run: `cd frontend && npm test -- frontend/tests/unit/api/phenopackets.spec.js frontend/tests/unit/views/PhenopacketCreateEdit.spec.js`
Expected: PASS

## Task 2: Backend Duplicate-Email Conflict Normalization

**Files:**
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/api/auth_endpoints.py`
- Test: `backend/tests/test_auth_user_management_endpoints.py`

- [ ] **Step 1: Write the failing regression tests**

Add tests that create two users, attempt to update one user’s email to the other user’s email through `PUT /api/v2/auth/users/{id}`, and assert a clean `409` response with a duplicate-email message. Add a second test that exercises the repository update path directly and asserts it raises an explicit domain conflict instead of surfacing a raw SQLAlchemy integrity exception.

- [ ] **Step 2: Run the tests to verify they fail for the right reason**

Run: `cd backend && uv run pytest tests/test_auth_user_management_endpoints.py -k "duplicate_email or duplicate email" -v`
Expected: FAIL because the current update path does not preflight or normalize duplicate-email conflicts.

- [ ] **Step 3: Implement the minimal fix**

Add explicit duplicate-email detection/normalization in the repository update path and convert that conflict to an HTTP `409` in the admin/auth update endpoint.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_auth_user_management_endpoints.py -k "duplicate_email or duplicate email" -v`
Expected: PASS

- [ ] **Step 5: Run nearby regression coverage**

Run: `cd backend && uv run pytest tests/test_auth_user_management_endpoints.py tests/test_auth.py tests/test_auth_tokens.py -v`
Expected: PASS

## Task 3: Combined Verification And PR

**Files:**
- Review scoped git diff only

- [ ] **Step 1: Run frontend verification**

Run: `cd frontend && npm test -- frontend/tests/unit/views/PhenopacketCreateEdit.spec.js frontend/tests/unit/api/phenopackets.spec.js`
Expected: PASS

- [ ] **Step 2: Run backend verification**

Run: `cd backend && uv run pytest tests/test_auth_user_management_endpoints.py -v`
Expected: PASS

- [ ] **Step 3: Run relevant lint and typecheck**

Run: `cd frontend && npm run lint && npm run typecheck`
Expected: PASS

Run: `cd backend && uv run ruff check app tests && uv run mypy app`
Expected: PASS

- [ ] **Step 4: Inspect scoped diff and create one branch/PR**

Run:
`git status --short`
`git diff -- frontend/src/views/PhenopacketCreateEdit.vue frontend/tests/unit/views/PhenopacketCreateEdit.spec.js backend/app/repositories/user_repository.py backend/app/api/auth_endpoints.py backend/tests/test_auth_user_management_endpoints.py`

Expected: only the intended slice files are included in the scoped change set.

- [ ] **Step 5: Push and open one PR**

Push the combined branch and open one PR covering both slices. Inspect GitHub Actions for that PR and keep iterating until green or until a concrete blocker is identified.
