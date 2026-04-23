# Docs And Release Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make durable docs, ADRs, READMEs, and deployment guidance match the live platform so reviewers and operators no longer have to reverse-engineer reality from code.

**Architecture:** Update durable docs to reflect the already-shipped auth/session/runtime model, eliminate links from `docs/` into `.planning`, and leave planning content where it belongs. Prefer exact truth over aspirational prose.

**Tech Stack:** Markdown docs, repository READMEs, ADRs.

---

## Task 1: Remove durable `.planning` references from stable docs

**Files:**
- Modify: `backend/README.md`
- Modify: `docs/api/README.md`
- Modify: `docs/api/variant-annotation.md`
- Modify: `docs/user-guide/README.md`
- Modify: `docs/user-guide/variant-annotation.md`

- [ ] Remove the current “Developer Guide” links pointing at `.planning/plans/variant-annotation-implementation-plan.md`.

- [ ] Replace with one of:
  - durable `docs/` reference if enough content already exists
  - nothing, if the planning file should remain internal only

- [ ] Run:

```bash
rg -n "\.planning/plans/variant-annotation-implementation-plan" backend/README.md docs
```

Expected:
- no matches

- [ ] Commit:

```bash
git add backend/README.md docs/api/README.md docs/api/variant-annotation.md docs/user-guide/README.md docs/user-guide/variant-annotation.md
git commit -m "docs: remove durable references into planning files"
```

## Task 2: Supersede ADR 0001 and align auth/session docs

**Files:**
- Modify: `frontend/README.md`
- Modify: `README.md`
- Modify: `docs/adr/0001-jwt-storage.md`
- Create if preferred: `docs/adr/0002-cookie-refresh-and-memory-access-token.md`

- [ ] Update auth/session documentation to the live model:
  - short-lived access token in memory
  - refresh token in HttpOnly cookie
  - CSRF token header/cookie for cookie-auth flows

- [ ] Mark ADR 0001 as superseded if creating ADR 0002.

- [ ] Remove stale claims that JWTs live in `localStorage`.

- [ ] Run:

```bash
rg -n "localStorage|HttpOnly|refresh token|csrf" README.md frontend/README.md docs/adr
```

- [ ] Commit:

```bash
git add README.md frontend/README.md docs/adr/0001-jwt-storage.md docs/adr/0002-cookie-refresh-and-memory-access-token.md
git commit -m "docs(auth): align durable docs with cookie-backed session model"
```

## Task 3: Align API docs URLs and deployment references

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `docs/README.md`
- Modify: `docs/deployment/docker.md`
- Modify any doc file still claiming `http://localhost:8000/docs` when `/api/v2/docs` is correct

- [ ] Update all durable docs to use the live API docs URL:
  - `http://localhost:8000/api/v2/docs`

- [ ] Fix deployment doc env-file references to the live repo setup:
  - root `.env.docker`
  - root `.env.docker.example`
  - current compose commands

- [ ] Run:

```bash
rg -n "http://localhost:8000/docs|docker/\.env\.docker|docker/\.env\.example" README.md backend/README.md docs
```

Expected:
- no stale matches

- [ ] Commit:

```bash
git add README.md backend/README.md docs/README.md docs/deployment/docker.md
git commit -m "docs: align api docs urls and deployment env references"
```

## Task 4: Update frontend and stack version references

**Files:**
- Modify: `README.md`
- Modify: `frontend/README.md`

- [ ] Align version references to the live stack from:
  - `frontend/package.json`
  - `backend/pyproject.toml`

- [ ] Correct at minimum:
  - Vuetify version family
  - Vue Router version family
  - current auth description

- [ ] Run:

```bash
sed -n '1,120p' frontend/package.json
sed -n '1,90p' frontend/README.md
sed -n '1,40p' README.md
```

- [ ] Commit:

```bash
git add README.md frontend/README.md
git commit -m "docs: align stack version references with current repo"
```

## Task 5: Final docs hygiene verification

**Files:**
- No code changes required unless fixes are needed

- [ ] Run:

```bash
rg -n "\.planning/plans/variant-annotation-implementation-plan|localStorage|http://localhost:8000/docs|docker/\.env\.docker" \
  README.md backend/README.md frontend/README.md docs
```

Expected:
- no stale durable references

- [ ] Run:

```bash
git diff -- README.md backend/README.md frontend/README.md docs
```

- [ ] Commit any final lane-only follow-up:

```bash
git add README.md backend/README.md frontend/README.md docs
git commit -m "docs: finalize release hygiene cleanup"
```
