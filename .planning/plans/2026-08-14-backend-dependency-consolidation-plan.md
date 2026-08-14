# Backend Dependency Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate Dependabot PRs #447 through #451 into one resolver-consistent, verified draft PR.

**Architecture:** Treat `backend/pyproject.toml` as the direct-constraint source and `backend/uv.lock` as the resolved source of truth. Generate both requirements exports from the lock and retain compatible transitive versions when Dependabot's standalone proposals cannot satisfy the graph.

**Tech Stack:** Python 3.10+, uv, FastAPI backend, Ruff, mypy, pytest, Alembic, GitHub Actions

## Global Constraints

- Request `pydantic-settings>=2.15.0`, `deepdiff>=9.1.0`, `oaklib>=0.7.4`, `types-pyyaml>=6.0.12.20260724`, `sqlalchemy[asyncio]>=2.0.51`, and `uvicorn[standard]>=0.52.1`.
- Keep `chardet==5.2.0` while `pronto==2.7.3` requires `chardet<6`.
- Keep `pydantic-core==2.46.4` while stable `pydantic==2.13.4` requires it.
- Do not hand-edit generated requirements exports.
- Do not introduce pre-release dependencies or resolver overrides.

---

### Task 1: Regenerate the unified dependency graph

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`

**Interfaces:**
- Consumes: Direct dependency constraints declared in `backend/pyproject.toml`.
- Produces: One lock graph and two deterministic requirements exports.

- [ ] **Step 1: Confirm the clean baseline**

Run `uv sync --directory backend --group dev --group test`, `make -C backend check-requirements-drift`, and `uv lock --directory backend --check`.

- [ ] **Step 2: Apply the six valid direct dependency floors**

Edit only the matching constraints in `backend/pyproject.toml` to the exact versions in Global Constraints.

- [ ] **Step 3: Resolve the dependency graph once**

Run `uv lock --directory backend --upgrade-package pydantic-settings --upgrade-package deepdiff --upgrade-package oaklib --upgrade-package types-pyyaml --upgrade-package sqlalchemy --upgrade-package uvicorn`.

- [ ] **Step 4: Regenerate requirements exports**

Run `make -C backend export-requirements` followed by `make -C backend check-requirements-drift`.

- [ ] **Step 5: Audit the dependency diff**

Use `git diff -- backend/pyproject.toml backend/uv.lock backend/requirements.txt backend/requirements-dev.txt` and `uv tree --directory backend` to confirm all requested direct floors and the two compatible transitive versions.

### Task 2: Verify backend behavior

**Files:**
- Verify: `backend/pyproject.toml`
- Verify: `backend/uv.lock`
- Verify: `backend/requirements.txt`
- Verify: `backend/requirements-dev.txt`

**Interfaces:**
- Consumes: The unified dependency graph from Task 1.
- Produces: Local evidence matching the backend GitHub Actions job.

- [ ] **Step 1: Verify lock and generated exports**

Run `uv lock --directory backend --check` and `make -C backend check-requirements-drift`.

- [ ] **Step 2: Run static checks**

Run `uv run --directory backend ruff check .`, `uv run --directory backend ruff format --check .`, and `uv run --directory backend mypy app/ migration/`.

- [ ] **Step 3: Run migrations and tests**

With CI-equivalent `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET`, and `ADMIN_PASSWORD`, run `uv run --directory backend alembic upgrade head` and `uv run --directory backend pytest -n auto --dist loadgroup -m "not benchmark and not network" --cov=app --cov=migration --cov-report=term-missing`.

### Task 3: Publish and supersede Dependabot PRs

**Files:**
- Commit: the two planning files and four dependency files.

**Interfaces:**
- Consumes: The verified dependency diff.
- Produces: One draft pull request against `main` and five closed superseded PRs.

- [ ] **Step 1: Review and commit the intended diff**

Run `git status -sb`, inspect `git diff`, stage only the six scoped files, and commit with a concise dependency-consolidation message.

- [ ] **Step 2: Push and open the draft PR**

Push `agent/consolidate-backend-dependency-updates`, then open a draft PR against `main` describing changes, resolver corrections, impact, and validation.

- [ ] **Step 3: Wait for GitHub Actions**

Run `gh pr checks --watch` for the consolidated PR. Inspect and fix any failing GitHub Actions job before continuing.

- [ ] **Step 4: Close superseded PRs**

Close #447, #448, #449, #450, and #451 with comments linking to the green consolidated PR.
