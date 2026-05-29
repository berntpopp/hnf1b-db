# CI/CD Pipeline Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure CI into path-gated jobs behind a single `ci-gate`, add a slim composite uv/python setup action, parallelize backend tests with Alembic-migrated per-worker databases, and add a Docker→GHCR build/publish workflow — all SHA-pinned and PR-only-triggered.

**Architecture:** One branch (`chore/ci-cd-optimization`), one PR. Three sequential phases (Foundation → xdist → Docker), each verified green before the next. `dorny/paths-filter` produces boolean outputs that gate conditional jobs; `ci-gate` (`if: always()`) aggregates them so branch protection depends on exactly one check. xdist isolation is contained entirely to `backend/conftest.py` (worker DB bootstrap) — the existing migration-seeded, mutable-table-truncation model is preserved untouched.

**Tech Stack:** GitHub Actions, `dorny/paths-filter@v4`, `astral-sh/setup-uv`, `pytest-xdist`, `docker/build-push-action` + GHCR, Alembic, FastAPI/async SQLAlchemy.

**Working directory:** sibling worktree `/home/bernt-popp/development/hnf1b-db-ci-cd-optimization` on branch `chore/ci-cd-optimization`.

---

## Safety invariants (must hold across every phase)

These are the spec's non-negotiable corrections. Re-check them before each commit:

1. Active planning files stay in `.planning/` (never `docs/`).
2. Backend xdist uses `pytest-xdist` + Alembic-migrated per-worker DBs. **Never** `metadata.create_all()`/`drop_all()` as a migration replacement.
3. Backend coverage run excludes network tests (`-m "not benchmark and not network"`); the HPO network guard runs separately and serially (`-m network`).
4. Backend keeps `ruff format --check`.
5. Frontend keeps Prettier coverage for **both** `src` and `tests`.
6. Docker/prod-config changes run the production guards (`prod-config-guards` job + compose grep guards).
7. Frontend Dockerfile changes trigger the frontend job (which owns the production bundle dev-auth leak guard).
8. Docker image builds use the `*.Dockerfile.prod` variants, not the dev Dockerfiles.
9. PR Docker validation is read-only (`build`, no push, no `packages: write`); `packages: write` is granted only on the publish job.
10. Every `uses:` is full-commit-SHA pinned with a same-line `# vX.Y.Z` version comment.

---

## File structure

**Created:**
- `.planning/plans/2026-05-29-ci-cd-optimization.md` — this plan.
- `.planning/specs/2026-05-29-ci-cd-optimization-design.md` — moved from `docs/superpowers/specs/` (Phase 0).
- `.github/actions/setup-uv-python/action.yml` — composite action: setup-uv (cache) + setup-python + `uv sync`.
- `.github/workflows/docker.yml` — production image build/publish matrix.

**Modified:**
- `.github/workflows/ci.yml` — full rewrite (triggers, concurrency, `changes` gating, gated jobs, `prod-config-guards`, slim `hygiene`, `ci-gate`).
- `.pre-commit-config.yaml` — unchanged content, but `hygiene` job invokes it with `SKIP=...` so the heavy lint/typecheck hooks are not re-run.
- `backend/conftest.py` — add xdist per-worker DB suffix + Alembic bootstrap + per-worker Redis index. Preserve serial behavior.
- `backend/pyproject.toml` — add `pytest-xdist` to the `test` group.
- `backend/uv.lock` — refreshed.
- `mcp/pyproject.toml` — add `pytest-xdist` to the `dev` group.
- `mcp/uv.lock` — refreshed.

**Deleted:**
- `docs/superpowers/specs/2026-05-29-ci-cd-optimization-design.md` — moved to `.planning/specs/` (git rm).

---

## Phase 0 — Spec relocation

### Task 0: Move active spec into `.planning/` and remove the docs copy

**Files:**
- Create: `.planning/specs/2026-05-29-ci-cd-optimization-design.md` (already copied into the worktree as untracked)
- Delete: `docs/superpowers/specs/2026-05-29-ci-cd-optimization-design.md`

- [ ] **Step 1: Confirm the two files are byte-identical** (the `.planning/` copy must equal the committed docs copy, so the move is a pure relocation)

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
diff docs/superpowers/specs/2026-05-29-ci-cd-optimization-design.md \
     .planning/specs/2026-05-29-ci-cd-optimization-design.md && echo "IDENTICAL"
```
Expected: `IDENTICAL`. If they differ, STOP — the `.planning/` copy is the authority (it is the revised spec); inspect the diff before proceeding.

- [ ] **Step 2: Stage the move**

Run:
```bash
git rm docs/superpowers/specs/2026-05-29-ci-cd-optimization-design.md
git add .planning/specs/2026-05-29-ci-cd-optimization-design.md .planning/plans/2026-05-29-ci-cd-optimization.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(planning): relocate CI/CD optimization spec to .planning/ + add plan"
```

---

## Phase 1 — Foundation (gating + composite action + hygiene slim + SHA-pin)

> Largest compute win, lowest risk. No test-runner behavior changes yet (xdist is Phase 2).

### Task 1: Resolve and record full-SHA pins for every action

**Files:**
- Create (scratch, not committed): note the SHA table in the PR description / commit body.

- [ ] **Step 1: Resolve commit SHAs for each action tag**

Run (each command prints `<sha>\trefs/tags/<tag>^{}` — the `^{}` dereferences annotated tags to the commit):
```bash
for spec in \
  "actions/checkout v6" \
  "astral-sh/setup-uv v7" \
  "actions/setup-python v6" \
  "actions/setup-node v6" \
  "codecov/codecov-action v6" \
  "actions/upload-artifact v7" \
  "dorny/paths-filter v4" \
  "docker/metadata-action v5" \
  "docker/setup-buildx-action v3" \
  "docker/login-action v3" \
  "docker/build-push-action v6" ; do
  repo=${spec% *}; tag=${spec#* }
  sha=$(git ls-remote "https://github.com/${repo}.git" "refs/tags/${tag}^{}" | awk '{print $1}')
  [ -z "$sha" ] && sha=$(git ls-remote "https://github.com/${repo}.git" "refs/tags/${tag}" | awk '{print $1}')
  printf '%-32s %s  # %s\n' "$repo" "$sha" "$tag"
done
```
Expected: one 40-hex SHA per action. Record the exact `owner/repo@<sha> # <tag>` mapping; every `uses:` in Tasks 2–4 and Phase 3 uses these resolved SHAs. **Do not invent SHAs** — use only what this command prints. If `dorny/paths-filter` exposes a newer patch tag than `v4`, pin to the resolved `v4` commit and comment `# v4`.

> Wherever the YAML below shows `<SHA:owner/repo@vX>`, substitute the resolved 40-hex SHA from this step and keep the trailing `# vX` comment.

### Task 2: Add the composite uv/python setup action

**Files:**
- Create: `.github/actions/setup-uv-python/action.yml`

- [ ] **Step 1: Write the composite action**

```yaml
name: Setup uv + Python
description: >-
  Install uv with caching, pin Python, and run uv sync for a given working
  directory and dependency groups. Reused by the backend, mcp, and e2e jobs.

inputs:
  working-directory:
    description: Directory containing pyproject.toml / uv.lock
    required: true
  python-version:
    description: Python version to pin
    required: false
    default: '3.12'
  groups:
    description: Space-separated dependency groups passed as repeated --group flags
    required: false
    default: ''

runs:
  using: composite
  steps:
    - name: Install uv
      uses: astral-sh/setup-uv@<SHA:astral-sh/setup-uv@v7>  # v7
      with:
        enable-cache: true
        cache-dependency-glob: |
          backend/uv.lock
          mcp/uv.lock

    - name: Set up Python
      uses: actions/setup-python@<SHA:actions/setup-python@v6>  # v6
      with:
        python-version: ${{ inputs.python-version }}

    - name: uv sync
      shell: bash
      working-directory: ${{ inputs.working-directory }}
      run: |
        groups=""
        for g in ${{ inputs.groups }}; do
          groups="$groups --group $g"
        done
        uv sync --frozen $groups
```

> Note: `--frozen` matches the lockfile-pinned dev workflow. If a clean checkout lacks an up-to-date lock the job fails loudly (correct — lockfiles are committed). The original CI used bare `uv sync`; `--frozen` is stricter and safe because `uv.lock` is committed.

- [ ] **Step 2: Lint the action YAML**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
python -c "import yaml,sys; yaml.safe_load(open('.github/actions/setup-uv-python/action.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/actions/setup-uv-python/action.yml
git commit -m "ci: add composite setup-uv-python action"
```

### Task 3: Rewrite `ci.yml` — triggers, concurrency, `changes`, gated jobs, `prod-config-guards`, slim `hygiene`, `ci-gate`

**Files:**
- Modify (full rewrite): `.github/workflows/ci.yml`

This is the largest task. Backend keeps its **serial** pytest command for now (Phase 1 does not enable xdist). Phase 2 swaps only the pytest line.

- [ ] **Step 1: Write the new `ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

permissions:
  contents: read

jobs:
  changes:
    name: Detect changed paths
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: read
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
      mcp: ${{ steps.filter.outputs.mcp }}
      docker_backend: ${{ steps.filter.outputs.docker_backend }}
      docker_frontend: ${{ steps.filter.outputs.docker_frontend }}
      docker_mcp: ${{ steps.filter.outputs.docker_mcp }}
      docker_config: ${{ steps.filter.outputs.docker_config }}
      ci: ${{ steps.filter.outputs.ci }}
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6
      - uses: dorny/paths-filter@<SHA:dorny/paths-filter@v4>  # v4
        id: filter
        with:
          filters: |
            backend:
              - 'backend/**'
            frontend:
              - 'frontend/**'
            mcp:
              - 'mcp/**'
            docker_backend:
              - 'backend/Dockerfile*'
              - 'backend/.dockerignore'
            docker_frontend:
              - 'frontend/Dockerfile*'
              - 'frontend/.dockerignore'
            docker_mcp:
              - 'mcp/Dockerfile*'
              - 'mcp/.dockerignore'
            docker_config:
              - 'docker/**'
              - '.env.docker.example'
            ci:
              - '.github/workflows/**'
              - '.github/actions/**'

  backend:
    name: Backend (lint / typecheck / tests)
    needs: changes
    if: ${{ needs.changes.outputs.backend == 'true' || needs.changes.outputs.ci == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 20

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: hnf1b_user
          POSTGRES_PASSWORD: hnf1b_pass
          POSTGRES_DB: hnf1b_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U hnf1b_user -d hnf1b_test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Setup uv + Python
        uses: ./.github/actions/setup-uv-python
        with:
          working-directory: backend
          groups: dev test

      - name: Run database migrations
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_test
          JWT_SECRET: test-secret-key-for-ci
          ADMIN_PASSWORD: test-admin-password-ci-2026
        working-directory: backend
        run: uv run alembic upgrade head

      - name: Run linting (ruff check)
        working-directory: backend
        run: uv run ruff check .

      - name: Run format check (ruff format)
        working-directory: backend
        run: uv run ruff format --check .

      - name: Run type checking (mypy)
        working-directory: backend
        run: uv run mypy app/ migration/

      - name: Run tests (pytest, coverage, no network)
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_test
          JWT_SECRET: test-secret-key-for-ci
          ADMIN_PASSWORD: test-admin-password-ci-2026
        working-directory: backend
        run: uv run pytest -m "not benchmark and not network" --cov=app --cov=migration --cov-report=xml --cov-report=term-missing

      - name: Validate curated HPO labels against live ontology (network)
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_test
          JWT_SECRET: test-secret-key-for-ci
          ADMIN_PASSWORD: test-admin-password-ci-2026
        working-directory: backend
        run: uv run pytest -m network -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@<SHA:codecov/codecov-action@v6>  # v6
        with:
          files: ./backend/coverage.xml
          fail_ci_if_error: false

  frontend:
    name: Frontend (test / lint / format / build)
    needs: changes
    if: ${{ needs.changes.outputs.frontend == 'true' || needs.changes.outputs.docker_frontend == 'true' || needs.changes.outputs.ci == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Setup Node.js
        uses: actions/setup-node@<SHA:actions/setup-node@v6>  # v6
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Run tests (vitest)
        working-directory: frontend
        run: npm test

      - name: Run linting (eslint)
        working-directory: frontend
        run: npm run lint:check

      - name: Run format check (prettier, src + tests)
        working-directory: frontend
        run: npx prettier --check "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"

      - name: Build production bundle
        working-directory: frontend
        run: npm run build

      - name: Verify no dev-auth strings in production bundle
        working-directory: frontend
        run: |
          if grep -rqE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/ --include='*.js' --include='*.css' 2>/dev/null; then
            echo "::error::dev-auth strings leaked into production bundle"
            grep -rnE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/ --include='*.js' --include='*.css' || true
            exit 1
          fi
          echo "dev-auth strings are NOT in the production bundle"

  mcp:
    name: MCP server (lint / typecheck / unit tests / contract drift)
    needs: changes
    if: ${{ needs.changes.outputs.mcp == 'true' || needs.changes.outputs.ci == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Setup uv + Python
        uses: ./.github/actions/setup-uv-python
        with:
          working-directory: mcp
          groups: dev

      - name: Run linting (ruff check)
        working-directory: mcp
        run: uv run ruff check .

      - name: Run type checking (mypy)
        working-directory: mcp
        run: uv run mypy src/

      - name: Run unit tests (pytest, no smoke/live)
        working-directory: mcp
        run: uv run pytest --cov=hnf1b_mcp -m "not smoke and not live"

      - name: Contract drift guard (paths + enums)
        working-directory: mcp
        run: |
          uv run python scripts/gen_contract.py
          git diff --exit-code -- src/hnf1b_mcp/contract/_generated_paths.py src/hnf1b_mcp/contract/_generated_enums.py

  e2e:
    name: E2E tests (Playwright)
    needs: changes
    if: ${{ needs.changes.outputs.frontend == 'true' || needs.changes.outputs.backend == 'true' || needs.changes.outputs.ci == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 25

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: hnf1b_user
          POSTGRES_PASSWORD: hnf1b_pass
          POSTGRES_DB: hnf1b_phenopackets_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U hnf1b_user -d hnf1b_phenopackets_test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Setup Node.js
        uses: actions/setup-node@<SHA:actions/setup-node@v6>  # v6
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Setup uv + Python
        uses: ./.github/actions/setup-uv-python
        with:
          working-directory: backend
          groups: dev test

      - name: Run backend migrations
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_phenopackets_test
          JWT_SECRET: ${{ secrets.JWT_SECRET || 'CI_TEST_ONLY_NOT_A_REAL_SECRET_DO_NOT_REUSE_0000000000000000' }}
          ADMIN_PASSWORD: ci_test_admin_password_2026
        working-directory: backend
        run: uv run alembic upgrade head

      - name: Seed admin user (required for E2E auth)
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_phenopackets_test
          JWT_SECRET: ${{ secrets.JWT_SECRET || 'CI_TEST_ONLY_NOT_A_REAL_SECRET_DO_NOT_REUSE_0000000000000000' }}
          ADMIN_USERNAME: admin
          ADMIN_EMAIL: admin@hnf1b-db.local
          ADMIN_PASSWORD: ci_test_admin_password_2026
        working-directory: backend
        run: uv run python scripts/create_admin_user.py

      - name: Start backend
        env:
          ENVIRONMENT: development
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5432/hnf1b_phenopackets_test
          JWT_SECRET: ${{ secrets.JWT_SECRET || 'CI_TEST_ONLY_NOT_A_REAL_SECRET_DO_NOT_REUSE_0000000000000000' }}
          ADMIN_PASSWORD: ci_test_admin_password_2026
          REDIS_URL: redis://localhost:6379/0
        working-directory: backend
        run: |
          nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
          for i in $(seq 1 30); do
            if curl -fsS http://localhost:8000/health >/dev/null 2>&1 || \
               curl -fsS http://localhost:8000/ >/dev/null 2>&1; then
              echo "backend is up"; break
            fi
            echo "waiting for backend... ($i)"; sleep 2
          done

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Install Playwright browsers
        working-directory: frontend
        run: npx playwright install --with-deps chromium

      - name: Run E2E tests
        env:
          VITE_API_URL: http://localhost:8000/api/v2
          CI: "true"
          E2E_ADMIN_USERNAME: admin
          E2E_ADMIN_PASSWORD: ci_test_admin_password_2026
        working-directory: frontend
        run: npx playwright test

      - name: Upload backend log on failure
        if: failure()
        uses: actions/upload-artifact@<SHA:actions/upload-artifact@v7>  # v7
        with:
          name: backend-log
          path: /tmp/backend.log
          if-no-files-found: ignore

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@<SHA:actions/upload-artifact@v7>  # v7
        with:
          name: playwright-report
          path: frontend/playwright-report/
          if-no-files-found: ignore
          retention-days: 7

  prod-config-guards:
    name: Production config guards
    needs: changes
    if: ${{ needs.changes.outputs.docker_config == 'true' || needs.changes.outputs.ci == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Verify ENABLE_DEV_AUTH not truthy in prod compose
        run: |
          if grep -Eq "^[[:space:]]*(-[[:space:]]*)?ENABLE_DEV_AUTH[[:space:]]*[:=][[:space:]]*['\"]?(true|True|TRUE|yes|Yes|YES|on|On|ON|1)['\"]?[[:space:]]*$" docker/docker-compose.npm.yml; then
            echo "::error::ENABLE_DEV_AUTH must not be truthy in docker/docker-compose.npm.yml"
            grep -nE "^[[:space:]]*(-[[:space:]]*)?ENABLE_DEV_AUTH" docker/docker-compose.npm.yml || true
            exit 1
          fi
          echo "ENABLE_DEV_AUTH is not truthy in docker/docker-compose.npm.yml"

      - name: Verify ENVIRONMENT=production in prod compose
        run: |
          if ! grep -Eq "^\s*(-\s*)?ENVIRONMENT\s*[:=]\s*production" docker/docker-compose.npm.yml; then
            echo "::error::docker/docker-compose.npm.yml must set ENVIRONMENT=production explicitly"
            exit 1
          fi
          echo "ENVIRONMENT=production is pinned in docker/docker-compose.npm.yml"

  hygiene:
    name: Hygiene (pre-commit upstream hooks + grep guards)
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Set up Python
        uses: actions/setup-python@<SHA:actions/setup-python@v6>  # v6
        with:
          python-version: '3.12'

      - name: Install pre-commit
        run: pip install pre-commit

      - name: Run pre-commit (skip heavy lint/typecheck — covered by backend/frontend jobs)
        env:
          SKIP: backend-ruff-check,backend-ruff-format,backend-mypy,frontend-eslint,frontend-prettier
        run: pre-commit run --all-files --show-diff-on-failure --config .pre-commit-config.yaml

  ci-gate:
    name: CI gate
    if: always()
    needs: [changes, backend, frontend, mcp, e2e, prod-config-guards, hygiene]
    runs-on: ubuntu-24.04
    steps:
      - name: Verify no required job failed or was cancelled
        run: |
          results='${{ join(needs.*.result, ',') }}'
          echo "Job results: $results"
          IFS=',' read -ra arr <<< "$results"
          for r in "${arr[@]}"; do
            if [ "$r" = "failure" ] || [ "$r" = "cancelled" ]; then
              echo "::error::A required job reported '$r'"
              exit 1
            fi
          done
          echo "All required jobs succeeded or were skipped."
```

> Rationale notes for reviewers (do not paste into YAML):
> - `hygiene` no longer bootstraps uv/node; the `SKIP` env disables the five `language: system` hooks (`backend-ruff-check`, `backend-ruff-format`, `backend-mypy`, `frontend-eslint`, `frontend-prettier`) that need those toolchains. Equivalent coverage now lives in `backend` (ruff check, **ruff format --check**, mypy) and `frontend` (eslint, prettier over src+tests). The upstream `pre-commit-hooks` (yaml/json/toml/merge-conflict/large-files/case-conflict/private-key) and the local grep guards (`check-test-imports`, `detect-non-deterministic-hash`) still run because they are not in SKIP and use no project toolchain.
> - The two compose grep guards moved out of `frontend` into `prod-config-guards` so docker/compose-only PRs still get them; the bundle dev-auth leak guard stays in `frontend` because it needs the `dist/` build artifact.
> - `e2e` dropped `needs: frontend` → `needs: changes` only (parallel with frontend/backend).

- [ ] **Step 2: Validate YAML + GitHub Actions syntax**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
# If actionlint is available, prefer it (catches expression + context errors):
command -v actionlint >/dev/null && actionlint .github/workflows/ci.yml || echo "actionlint not installed — relying on yaml parse"
```
Expected: `YAML OK` (and clean actionlint if present).

- [ ] **Step 3: Confirm no remaining `<SHA:...>` placeholders**

Run:
```bash
! grep -n "<SHA:" .github/workflows/ci.yml .github/actions/setup-uv-python/action.yml && echo "all SHAs substituted"
```
Expected: `all SHAs substituted`. If any placeholder remains, substitute the resolved SHA from Task 1.

- [ ] **Step 4: Confirm every `uses:` has a SHA + version comment**

Run:
```bash
grep -nE "uses: .*@[0-9a-f]{40}" .github/workflows/ci.yml | grep -v "#" && echo "WARNING: SHA without version comment" || echo "all third-party uses pinned with version comment"
grep -nE "uses: \./" .github/workflows/ci.yml && echo "(local composite action — no SHA needed)"
```
Expected: no SHA-without-comment warnings; the only un-SHA'd `uses:` is the local `./.github/actions/setup-uv-python`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: gate jobs behind paths-filter + ci-gate, slim hygiene, SHA-pin actions"
```

### Task 4: Push branch and verify Phase 1 CI is green

- [ ] **Step 1: Push and open the PR**

Run:
```bash
git push -u origin chore/ci-cd-optimization
gh pr create --fill --title "chore: CI/CD pipeline optimization" \
  --body "Implements .planning/specs/2026-05-29-ci-cd-optimization-design.md. Phase 1 (foundation) first; xdist + Docker land in follow-up commits on this branch. Branch protection must switch the required check to 'ci-gate' (see PR notes)."
```

- [ ] **Step 2: Watch the run and confirm gating behaves**

Run:
```bash
gh pr checks --watch
gh run list --branch chore/ci-cd-optimization --limit 1
```
Expected: This PR touches `.github/**` → `ci` filter true → all gated jobs run. `ci-gate` is green. If any job fails, STOP and use `superpowers:systematic-debugging`.

---

## Phase 2 — pytest-xdist with Alembic-migrated per-worker databases

> Highest-risk phase. Isolation is contained to `backend/conftest.py`. Validate locally with `-n 2` AND unchanged serial behavior BEFORE enabling `-n auto` in CI.

### Task 5: Add `pytest-xdist` dependencies and refresh lockfiles

**Files:**
- Modify: `backend/pyproject.toml` (add to `test` group)
- Modify: `mcp/pyproject.toml` (add to `dev` group)
- Modify: `backend/uv.lock`, `mcp/uv.lock`

- [ ] **Step 1: Add xdist to backend `test` group**

In `backend/pyproject.toml`, inside `[dependency-groups]` `test = [...]`, add after the `pytest-cov` line:
```toml
    "pytest-xdist>=3.6.0",
```

- [ ] **Step 2: Add xdist to mcp `dev` group**

In `mcp/pyproject.toml`, inside `[dependency-groups]` `dev = [...]`, add after the `pytest-cov` line:
```toml
    "pytest-xdist>=3.6.0",
```

- [ ] **Step 3: Refresh lockfiles**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend && uv lock
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/mcp && uv lock
```
Expected: both `uv.lock` files updated to include `pytest-xdist` (and its `execnet` dep).

- [ ] **Step 4: Sync and confirm xdist importable**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend
uv sync --group dev --group test
uv run python -c "import xdist; print('xdist', xdist.__version__)"
```
Expected: prints an xdist version (no ImportError).

- [ ] **Step 5: Commit**

```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
git add backend/pyproject.toml backend/uv.lock mcp/pyproject.toml mcp/uv.lock
git commit -m "test: add pytest-xdist to backend test group and mcp dev group"
```

### Task 6: Implement per-worker DB bootstrap in `backend/conftest.py`

**Files:**
- Modify: `backend/conftest.py`

**Design:** `backend/conftest.py` runs at import, before `tests/conftest.py` imports `app` and builds the engine. Under xdist each worker is a separate process that imports this conftest with `PYTEST_XDIST_WORKER` set (`gw0`, `gw1`, …). For a worker we (a) suffix the DB name with the worker id, (b) create that database if missing, (c) run `alembic upgrade head` against it via subprocess (matches `backend/Makefile` `db-test-init`; a fresh process reads `DATABASE_URL` from env, sidestepping any cached `settings`), and (d) derive a per-worker Redis logical-DB index. Serial runs (`PYTEST_XDIST_WORKER` unset) are untouched and continue to rely on the externally-migrated base DB. **No `metadata.create_all`/`drop_all`.**

- [ ] **Step 1: Read `alembic/env.py` to confirm it reads `DATABASE_URL` from env/settings**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
sed -n '1,80p' backend/alembic/env.py | grep -nE "DATABASE_URL|settings|get_main_option|sqlalchemy.url|os.environ" || true
```
Expected: confirm the URL comes from `settings`/`DATABASE_URL` env (not a hardcoded ini value). If alembic reads `alembic.ini`'s `sqlalchemy.url` literally instead of env, the subprocess approach still works because we pass `DATABASE_URL` and the project's `env.py` is known to derive from settings — but VERIFY here. If it does NOT read env, STOP and reassess (the subprocess env override would be ineffective).

- [ ] **Step 2: Replace the bootstrap logic in `backend/conftest.py`**

Replace the current file body (the `_DEFAULT_TEST_URL` constant through the final `_ensure_test_database_url()` call) with the version below. The docstring at the top of the file is preserved; only the implementation functions change/extend.

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_DEFAULT_TEST_URL = (
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test"
)

_BACKEND_DIR = Path(__file__).resolve().parent


def _xdist_worker_id() -> str | None:
    """Return the xdist worker id (e.g. ``gw0``) or ``None`` when serial."""
    return os.environ.get("PYTEST_XDIST_WORKER")


def _derive_test_database_url() -> str:
    """Compute the database URL to use for the test suite.

    Honors ``TEST_DATABASE_URL``, then a ``test``-named ``DATABASE_URL`` (CI),
    then rewrites a dev ``DATABASE_URL`` to a sibling ``_test`` database. When
    running under pytest-xdist, the resolved database name is further suffixed
    with the worker id so each worker owns an isolated, separately-migrated
    database (e.g. ``hnf1b_test`` -> ``hnf1b_test_gw0``).
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        base = explicit
    else:
        base = os.environ.get("DATABASE_URL")
        if not base:
            base = _DEFAULT_TEST_URL
        else:
            parsed = urlparse(base)
            db_path = parsed.path.lstrip("/")
            if "test" not in db_path.lower():
                new_path = f"/{db_path}_test" if db_path else "/hnf1b_phenopackets_test"
                base = urlunparse(parsed._replace(path=new_path))

    worker = _xdist_worker_id()
    if worker:
        parsed = urlparse(base)
        db_path = parsed.path.lstrip("/")
        base = urlunparse(parsed._replace(path=f"/{db_path}_{worker}"))
    return base


def _sync_dsn_for_admin(async_url: str, database: str) -> str:
    """Build a synchronous psycopg2 DSN pointing at ``database``.

    Used to issue ``CREATE DATABASE`` against the ``postgres`` maintenance DB.
    """
    parsed = urlparse(async_url)
    # Strip the +asyncpg driver suffix -> plain postgresql:// for psycopg2.
    scheme = parsed.scheme.split("+", 1)[0]
    return urlunparse(parsed._replace(scheme=scheme, path=f"/{database}"))


def _create_worker_database_if_missing(worker_url: str) -> None:
    """Create the per-worker database if it does not already exist.

    Connects to the ``postgres`` maintenance database with psycopg2 in
    autocommit mode (``CREATE DATABASE`` cannot run inside a transaction).
    """
    import psycopg2  # psycopg2-binary is a project dependency.

    target_db = urlparse(worker_url).path.lstrip("/")
    admin_dsn = _sync_dsn_for_admin(worker_url, "postgres")

    conn = psycopg2.connect(admin_dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if cur.fetchone() is None:
                # Identifier is derived from our own worker id + the CI-provided
                # base name, not user input; quote defensively all the same.
                cur.execute(f'CREATE DATABASE "{target_db}"')
    finally:
        conn.close()


def _alembic_upgrade(worker_url: str) -> None:
    """Run ``alembic upgrade head`` against ``worker_url`` in a subprocess.

    A subprocess gets a fresh interpreter that reads ``DATABASE_URL`` from the
    environment, so it is unaffected by any already-imported, cached
    ``app.core.config.settings`` in the worker process. Mirrors the
    ``backend/Makefile`` ``db-test-init`` target.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = worker_url
    env["TEST_DATABASE_URL"] = worker_url
    env.setdefault("JWT_SECRET", "test-secret-key-for-local-pytest")
    env.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")
    env.setdefault("ENVIRONMENT", "development")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env=env,
        check=True,
    )


def _maybe_set_worker_redis_url() -> None:
    """Give each xdist worker its own Redis logical DB to avoid cross-talk.

    Derives an index from the numeric part of the worker id and keeps it within
    Redis's default 16 logical databases.
    """
    worker = _xdist_worker_id()
    if not worker:
        return
    digits = "".join(ch for ch in worker if ch.isdigit())
    index = (int(digits) if digits else 0) % 16
    base = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(base)
    os.environ["REDIS_URL"] = urlunparse(parsed._replace(path=f"/{index}"))


def _ensure_test_database_url() -> None:
    """Install the resolved test DB URL, bootstrap worker DBs, verify safety."""
    resolved = _derive_test_database_url()

    parsed = urlparse(resolved)
    db_name = parsed.path.lstrip("/").lower()
    if "test" not in db_name:
        raise RuntimeError(
            "Refusing to run backend tests: resolved DATABASE_URL "
            f"database name {db_name!r} does not contain 'test'. "
            "Set TEST_DATABASE_URL to a dedicated test database "
            "(e.g. hnf1b_phenopackets_test) or run `make db-test-init`."
        )

    # Under xdist, each worker creates + Alembic-migrates its own database
    # BEFORE app.database builds the engine in tests/conftest.py.
    if _xdist_worker_id():
        _create_worker_database_if_missing(resolved)
        _alembic_upgrade(resolved)
        _maybe_set_worker_redis_url()

    os.environ["DATABASE_URL"] = resolved
    os.environ.setdefault("TEST_DATABASE_URL", resolved)
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-local-pytest")
    os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")
    os.environ.setdefault("ENVIRONMENT", "development")


_ensure_test_database_url()
```

- [ ] **Step 3: Ensure the local test Postgres has the base DB + a clean slate**

Run (uses the repo's existing local test DB helper; the worker DBs are created on demand):
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend
make db-test-init || echo "db-test-init requires the docker hnf1b_db container; ensure local test PG is reachable per backend/conftest.py default (localhost:5433)"
```
Expected: base test DB exists + migrated. (If the local environment differs, ensure a Postgres reachable at the `TEST_DATABASE_URL`/default used by `backend/conftest.py`.)

- [ ] **Step 4: Verify SERIAL behavior is unchanged**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend
uv run pytest -m "not benchmark and not network" -q
```
Expected: same pass/fail outcome as before this task (all pass). Serial path must not touch the new worker code (`PYTEST_XDIST_WORKER` unset).

- [ ] **Step 5: Verify `-n 2` works with isolated worker DBs**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend
uv run pytest -n 2 --dist loadgroup -m "not benchmark and not network" -q
```
Expected: PASS. Confirm two worker DBs were created:
```bash
PGPASSWORD=hnf1b_pass psql -h localhost -p 5433 -U hnf1b_user -d postgres \
  -tc "SELECT datname FROM pg_database WHERE datname LIKE '%_gw%'" || true
```
Expected: `..._gw0` and `..._gw1` listed. If `-n 2` fails on DB/lookup-data errors, use `superpowers:systematic-debugging` — likely the worker DB was not migrated before the engine was built (ordering) or alembic did not pick up `DATABASE_URL`.

- [ ] **Step 6: Verify the network guard still runs serially**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/backend
uv run pytest -m network -v
```
Expected: PASS or network-skip (transient outage). Must NOT error on DB isolation (this path is serial → base DB).

- [ ] **Step 7: Commit**

```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
git add backend/conftest.py
git commit -m "test(backend): Alembic-migrated per-worker DB + Redis isolation for pytest-xdist"
```

### Task 7: Enable xdist in the `backend` and `mcp` CI jobs

**Files:**
- Modify: `.github/workflows/ci.yml` (backend pytest line, mcp pytest line)

- [ ] **Step 1: Verify MCP passes under `-n auto` locally first**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization/mcp
uv sync --group dev
uv run pytest -n auto --cov=hnf1b_mcp -m "not smoke and not live" -q
```
Expected: PASS. (MCP tests are isolated/no shared DB, so xdist needs no bootstrap.) If FAIL, use `superpowers:systematic-debugging`.

- [ ] **Step 2: Update the backend pytest step**

In `.github/workflows/ci.yml`, replace the backend coverage command:
```yaml
        run: uv run pytest -m "not benchmark and not network" --cov=app --cov=migration --cov-report=xml --cov-report=term-missing
```
with:
```yaml
        run: uv run pytest -n auto --dist loadgroup -m "not benchmark and not network" --cov=app --cov=migration --cov-report=xml --cov-report=term-missing
```
Leave the separate `-m network -v` step (serial) unchanged.

- [ ] **Step 3: Update the MCP pytest step**

In `.github/workflows/ci.yml`, replace the mcp unit-test command:
```yaml
        run: uv run pytest --cov=hnf1b_mcp -m "not smoke and not live"
```
with:
```yaml
        run: uv run pytest -n auto --cov=hnf1b_mcp -m "not smoke and not live"
```

- [ ] **Step 4: Validate YAML**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 5: Commit, push, verify CI**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run backend + mcp tests under pytest-xdist (-n auto)"
git push
gh pr checks --watch
```
Expected: backend + mcp green; coverage uploaded (pytest-cov auto-combines xdist worker data). If a worker DB error appears in CI but not locally, debug ordering/migration in `backend/conftest.py`.

---

## Phase 3 — Docker → GHCR build/publish workflow

### Task 8: Add `docker.yml` build/publish matrix

**Files:**
- Create: `.github/workflows/docker.yml`

- [ ] **Step 1: Write `docker.yml`**

```yaml
name: Docker

on:
  push:
    branches: [main]
    tags: ['v*.*.*']
  pull_request:

permissions:
  contents: read

env:
  REGISTRY: ghcr.io

jobs:
  changes:
    name: Detect changed images
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: read
    outputs:
      docker_backend: ${{ steps.filter.outputs.docker_backend }}
      docker_frontend: ${{ steps.filter.outputs.docker_frontend }}
      docker_mcp: ${{ steps.filter.outputs.docker_mcp }}
      docker_config: ${{ steps.filter.outputs.docker_config }}
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6
      - uses: dorny/paths-filter@<SHA:dorny/paths-filter@v4>  # v4
        id: filter
        with:
          filters: |
            docker_backend:
              - 'backend/**'
            docker_frontend:
              - 'frontend/**'
            docker_mcp:
              - 'mcp/**'
            docker_config:
              - 'docker/**'
              - '.env.docker.example'

  build:
    name: Build ${{ matrix.image }} image
    needs: changes
    # On tags, build all three for a coherent release set. Otherwise gate per
    # image (or when shared docker config changes).
    if: >-
      startsWith(github.ref, 'refs/tags/v') ||
      needs.changes.outputs.docker_config == 'true' ||
      (matrix.image == 'backend'  && needs.changes.outputs.docker_backend  == 'true') ||
      (matrix.image == 'frontend' && needs.changes.outputs.docker_frontend == 'true') ||
      (matrix.image == 'mcp'      && needs.changes.outputs.docker_mcp      == 'true')
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      # packages: write is granted ONLY for publishing (push/tag), never on PRs.
      packages: ${{ (github.event_name != 'pull_request') && 'write' || 'read' }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - image: backend
            context: backend
            dockerfile: backend/Dockerfile.prod
          - image: frontend
            context: frontend
            dockerfile: frontend/Dockerfile.prod
          - image: mcp
            context: mcp
            dockerfile: mcp/Dockerfile.prod
    steps:
      - uses: actions/checkout@<SHA:actions/checkout@v6>  # v6

      - name: Log in to GHCR
        if: ${{ github.event_name != 'pull_request' }}
        uses: docker/login-action@<SHA:docker/login-action@v3>  # v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@<SHA:docker/metadata-action@v5>  # v5
        with:
          images: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.image }}
          tags: |
            type=sha
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Set up Buildx
        uses: docker/setup-buildx-action@<SHA:docker/setup-buildx-action@v3>  # v3

      - name: Build and push
        uses: docker/build-push-action@<SHA:docker/build-push-action@v6>  # v6
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha,scope=${{ matrix.image }}
          cache-to: type=gha,mode=max,scope=${{ matrix.image }}
          build-args: |
            VITE_API_URL=/api/v2
```

> Notes for reviewers (do not paste into YAML):
> - `VITE_API_URL=/api/v2` is harmless for backend/mcp (their Dockerfiles ignore unknown build-args) and supplies the production value the frontend `Dockerfile.prod` expects.
> - PR builds: no GHCR login, `push: false`, `packages: read` → fully read-only validation.
> - Publishing (push to main / `v*` tags): `packages: write`, login, push.

- [ ] **Step 2: Substitute SHAs and validate**

Run:
```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
# substitute every <SHA:...> using the Task 1 table, then:
python -c "import yaml; yaml.safe_load(open('.github/workflows/docker.yml')); print('YAML OK')"
! grep -n "<SHA:" .github/workflows/docker.yml && echo "all SHAs substituted"
command -v actionlint >/dev/null && actionlint .github/workflows/docker.yml || echo "actionlint not installed"
```
Expected: `YAML OK`, `all SHAs substituted`, clean actionlint if present.

- [ ] **Step 3: Confirm permissions posture**

Run:
```bash
grep -n "packages:" .github/workflows/docker.yml
```
Expected: only the conditional `packages: ${{ ... 'write' || 'read' }}` on the build job — no unconditional `packages: write`.

- [ ] **Step 4: Commit, push, verify PR Docker validation is read-only**

```bash
git add .github/workflows/docker.yml
git commit -m "ci: add Docker GHCR build/publish matrix (PR build-validate, push/tag publish)"
git push
gh pr checks --watch
```
Expected: the Docker workflow runs on this PR, builds all three prod images (because this PR touches workflow files → but note `docker.yml`'s `changes` filters do not include `.github/**`; on this PR the image source dirs are unchanged, so per-image gates may all be false and `build` jobs skip). Verify the run is green and that NO push to GHCR occurred (PR event). If you want to force a build-validate on this PR, confirm by checking the run logs show `push: false`.

> If verifying the build on the PR is desired but gating skips it (no image source changed), that is expected and acceptable — the build path is exercised on the first `main` push. Document this in the PR.

---

## Phase 4 — Finalization

### Task 9: Full verification sweep + PR notes for branch-protection change

- [ ] **Step 1: Re-run the safety-invariant checklist** (top of this plan) against the final diff:

```bash
cd /home/bernt-popp/development/hnf1b-db-ci-cd-optimization
git diff --stat main...HEAD
# 1 planning files in .planning only:
git diff --name-only main...HEAD | grep -E "^docs/" && echo "CHECK: docs changes (expected only the spec deletion)" || true
# 3 network exclusion preserved:
grep -n 'not benchmark and not network' .github/workflows/ci.yml
grep -n '\-m network -v' .github/workflows/ci.yml
# 4 ruff format check present:
grep -n 'ruff format --check' .github/workflows/ci.yml
# 5 prettier covers src+tests:
grep -n 'prettier --check "{src,tests}' .github/workflows/ci.yml
# 8 prod Dockerfiles used:
grep -n 'Dockerfile.prod' .github/workflows/docker.yml
# 10 no unpinned third-party uses:
grep -nE "uses: [^.].*@(v[0-9]|main|master)$" .github/workflows/*.yml .github/actions/*/action.yml && echo "FAIL: unpinned action" || echo "all third-party actions SHA-pinned"
```
Expected: all checks consistent with the invariants; the only `docs/` change is the spec deletion; no unpinned third-party actions.

- [ ] **Step 2: Confirm the whole PR is green**

Run:
```bash
gh pr checks
```
Expected: `ci-gate` and the Docker workflow green.

- [ ] **Step 3: Add the required-check migration note to the PR body**

Run:
```bash
gh pr comment --body "**Required manual repo-settings change:** switch branch protection on \`main\` so the single required status check is **\`ci-gate\`** (Settings → Branches → branch protection rule → Require status checks → select \`ci-gate\`, remove the old per-job checks: \`test\`, \`frontend\`, \`e2e-tests\`, \`mcp\`, \`pre-commit hygiene gate\`). The conditional jobs are intentionally skippable; gating on them directly would block docs/MCP-only PRs."
```

- [ ] **Step 4: Use `superpowers:verification-before-completion` before claiming done.**

---

## Self-review notes

- **Spec coverage:** triggers/concurrency (Task 3), composite action (Task 2), `changes`+filters incl. `ci` force-all (Task 3), backend job incl. ruff-format + separate network guard (Task 3/7), frontend prettier src+tests + bundle leak guard (Task 3), mcp incl. xdist + contract drift (Task 3/7), e2e drop `needs: frontend` (Task 3), `prod-config-guards` (Task 3), slim `hygiene` with SKIP (Task 3), `ci-gate` (Task 3), xdist deps+lock (Task 5), per-worker Alembic DB + Redis (Task 6), enable xdist in CI (Task 7), `docker.yml` matrix on prod Dockerfiles with PR read-only / publish-only write (Task 8), SHA-pin everything (Task 1 + each task), ubuntu-24.04 pin (Task 3/8), spec relocation (Task 0), branch-protection note (Task 9).
- **Open verification item flagged for execution:** Task 6 Step 1 must confirm `alembic/env.py` reads `DATABASE_URL` from env/settings; the subprocess-migration design depends on it. This is the one place to STOP-and-ask if the assumption breaks.
