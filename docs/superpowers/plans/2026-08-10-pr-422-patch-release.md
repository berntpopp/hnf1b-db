# PR #422 Patch Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the PR #422 remediation as a coordinated patch release and merge the existing PR only after fresh required Actions checks pass.

**Architecture:** Each independently versioned deliverable receives a patch increment in its canonical manifest. Generated metadata is regenerated through the repository's package tooling, then CI validates the exact merged candidate before the PR is merged.

**Tech Stack:** Python/uv, npm, FastAPI OpenAPI generation, GitHub Actions, GitHub CLI.

## Global Constraints

- API version: `0.2.1` → `0.2.2`.
- MCP version: `0.1.1` → `0.1.2`.
- Frontend version: `0.0.5` → `0.0.6`.
- Do not change dependency versions or generate unrelated lock churn.
- Merge the existing PR #422 only after its fresh required Actions checks pass.

---

### Task 1: Align canonical release metadata

**Files:**
- Modify: `backend/pyproject.toml:3`
- Modify: `mcp/pyproject.toml:3`
- Modify: `frontend/package.json:4`
- Modify: `frontend/package-lock.json:3-9`

**Interfaces:**
- Consumes: package metadata read by uv, npm, and FastAPI OpenAPI generation.
- Produces: coordinated manifest versions consumed by CI and release artifacts.

- [ ] **Step 1: Record current canonical versions**

Run: `rg -n '^(version = "0\.2\.1"|version = "0\.1\.1")|"version": "0\.0\.5"' backend/pyproject.toml mcp/pyproject.toml frontend/package.json frontend/package-lock.json`

Expected: API `0.2.1`, MCP `0.1.1`, and matching frontend root/package-lock `0.0.5` entries.

- [ ] **Step 2: Apply the minimal patch bump**

Update only the canonical API, MCP, frontend package, and frontend lock root versions to `0.2.2`, `0.1.2`, and `0.0.6` respectively.

- [ ] **Step 3: Verify manifest/lock consistency**

Run: `cd frontend && npm run check:dependencies`

Expected: dependency graph consistency passes with the unchanged dependency graph.

- [ ] **Step 4: Commit**

Run: `git add backend/pyproject.toml mcp/pyproject.toml frontend/package.json frontend/package-lock.json && git commit -m "chore: release PR 422 patch versions"`

### Task 2: Regenerate and validate API metadata

**Files:**
- Modify when generated metadata changes: `mcp/contract/openapi.snapshot.json`

**Interfaces:**
- Consumes: `backend/pyproject.toml` FastAPI version metadata.
- Produces: committed OpenAPI contract version synchronized with the API manifest.

- [ ] **Step 1: Run the contract drift guard**

Run: `cd mcp && make contract-verify`

Expected: the guard either passes unchanged or identifies only the API version metadata delta.

- [ ] **Step 2: Regenerate the authoritative snapshot if required**

Run: `cd backend && uv run --group dev --group test python scripts/dump_openapi.py`

Expected: `mcp/contract/openapi.snapshot.json` receives only the API version update if regeneration is required.

- [ ] **Step 3: Re-run contract verification**

Run: `cd mcp && make contract-verify`

Expected: success with no contract drift.

- [ ] **Step 4: Commit generated metadata if changed**

Run: `git add mcp/contract/openapi.snapshot.json && git commit -m "chore: refresh API release metadata"`

### Task 3: Verify, publish, and merge

**Files:**
- No source files.

**Interfaces:**
- Consumes: committed release metadata and GitHub Actions status for PR #422.
- Produces: merged existing PR and documented branch cleanup scope.

- [ ] **Step 1: Run release-scope local checks**

Run: `cd frontend && npm ci && npm run check:dependencies && npm run build`; `cd mcp && make contract-verify`; `cd backend && uv run --group dev --group test ruff check . && uv run --group dev --group test mypy app/ migration/`

Expected: all commands succeed.

- [ ] **Step 2: Push the existing PR branch**

Run: `git push origin fix/ontology-defects-and-curation-specs`

Expected: GitHub starts a fresh CI workflow for the new head.

- [ ] **Step 3: Inspect required Actions to a terminal green state**

Run: `gh pr checks 422 --repo berntpopp/hnf1b-db --watch --interval 10`

Expected: backend, frontend, MCP, E2E, hygiene, production guards, and Docker validation pass; publish jobs may remain skipped.

- [ ] **Step 4: Merge the existing PR**

Run: `gh pr merge 422 --repo berntpopp/hnf1b-db --merge --delete-branch=false`

Expected: PR state becomes `MERGED` with a merge commit on the default branch.

- [ ] **Step 5: Inventory stale branches before deletion**

Run: `git fetch --prune origin && git branch -r --merged origin/main`

Expected: a concrete, reviewable set of remote branches already merged into the default branch; delete only those branches, excluding protected/default branches and active PR branches.

- [ ] **Step 6: Verify post-merge state**

Run: `gh pr view 422 --repo berntpopp/hnf1b-db --json state,mergedAt,mergeCommit,url`

Expected: `state` is `MERGED` and `mergeCommit` is populated.
