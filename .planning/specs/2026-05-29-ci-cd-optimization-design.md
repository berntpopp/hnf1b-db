# CI/CD Pipeline Optimization — Design

**Date:** 2026-05-29
**Branch:** `chore/ci-cd-optimization`
**Status:** Revised design → implementation

## Motivation

HNF1B-db's CI runs five jobs on **every** push/PR with **no path filtering**, a
heavily redundant `pre-commit` job, serial `pytest`, and missing caches.
Touching only `mcp/` or `docs/` still pays for the full backend + frontend +
e2e suites. This wastes wall-clock (slow PR feedback) and runner minutes
(compute). Faster, leaner CI ships curated HNF1B data and tooling to clinicians
and researchers sooner.

**Optimize for:** both wall-clock and compute (balanced). **Runners:** free
GitHub-hosted (`ubuntu-24.04`). **Scope:** full restructure, including
Docker→GHCR builds.

## Current state (baseline)

`/.github/workflows/ci.yml` — 5 jobs, all unconditional:

| Job | Work | Timeout | Main cost |
|-----|------|---------|-----------|
| `test` (backend) | PG+Redis, `uv sync`, migrations, ruff, mypy, **serial pytest** (120 files / 29k LOC) + coverage + separate network HPO guard | 20m | serial pytest |
| `frontend` | npm ci, vitest (59 specs), eslint, prettier, build, production guards | 15m | install + build |
| `e2e-tests` | `needs: frontend`; full stack; **re-installs both stacks**; `playwright install`; 9 specs | 25m | full re-bootstrap |
| `mcp` | uv sync, ruff, mypy, pytest (100 tests), contract drift | 15m | — |
| `pre-commit` | **re-installs backend + frontend deps + pip pre-commit**; runs ruff/mypy/eslint/prettier on all files | 15m | duplicates most `test`+`frontend` work |

Triggers: `push: [main, develop, refactor--*]` + `pull_request: [main, develop]`
→ duplicate runs on branches matching both. Concurrency cancels in-progress for
all refs.

### Key findings
1. **No path filtering** — every change runs all 5 jobs.
2. **`pre-commit` job mostly redundant** — re-bootstraps both stacks to re-run
   lint/typecheck already covered by `test` + `frontend`, but it also owns
   backend `ruff format --check` and frontend tests Prettier coverage today.
3. **`pytest` serial** — `pytest-xdist` typically 2-3x faster, but this repo
   needs migration-seeded per-worker databases.
4. **Missing caches** — Playwright browsers re-downloaded; mypy/pytest cold.
   (uv + npm caches already enabled.)
5. **`e2e` over-serialized** — `needs: frontend` adds an ordering barrier and
   re-installs everything instead of running in parallel.
6. **Double runs** — `push: refactor--*` + `pull_request` on the same commit
   land in different concurrency groups → two runs.
7. **No Docker image builds at all** — images are deploy/local-time only.

## Decisions

- **Spec location:** active implementation design lives in `.planning/specs/`;
  durable post-implementation docs belong under `docs/`.
- **Triggers:** PR-only for feature branches. `push` triggers only on `main`
  (+ `v*` tags for Docker). Feature branches get CI through their open PR.
- **Gating:** `dorny/paths-filter@v4` boolean outputs gate downstream jobs.
  Docker and production-config changes must still run production guards.
- **xdist:** Included only after adding `pytest-xdist` to the backend test group
  and MCP dev group. Backend workers must use Alembic-migrated DBs, not
  `metadata.create_all()`.
- **Required check:** a single `ci-gate` aggregator (`if: always()`), never the
  individual conditional jobs.
- **Docker:** matrix build of all three production images; PR = build-validate,
  main/tags = build + push to `ghcr.io`; per-image `type=gha,mode=max` layer
  cache.
- **Hardening:** every `uses:` action pinned to full commit SHA with a same-line
  version comment for Dependabot visibility; runners pinned to `ubuntu-24.04`.

## Target architecture

### File layout
- `.github/actions/setup-uv-python/action.yml` — **new** composite action with
  inputs for `working-directory`, dependency groups, and Python version:
  `astral-sh/setup-uv` (cache, `cache-dependency-glob` = both `uv.lock`s) +
  Python pin + `uv sync`. Reused by `backend`, `mcp`, `e2e` jobs.
- `.github/workflows/ci.yml` — **rewritten**: gated jobs + `ci-gate`.
- `.github/workflows/docker.yml` — **new**: production image build/push matrix.

### `ci.yml`

```yaml
on:
  push: { branches: [main] }
  pull_request:
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
permissions:
  contents: read
```

**Jobs:**

1. **`changes`** — `dorny/paths-filter@v4`. Outputs: `backend`, `frontend`,
   `mcp`, `docker_backend`, `docker_frontend`, `docker_mcp`, `docker_config`,
   `ci`. The `ci` filter (`.github/**`) forces all jobs when workflows/actions
   change. `permissions: pull-requests: read`.
   Filters:
   - `backend: ['backend/**']`
   - `frontend: ['frontend/**']`
   - `mcp: ['mcp/**']`
   - `docker_backend: ['backend/Dockerfile*', 'backend/.dockerignore']`
   - `docker_frontend: ['frontend/Dockerfile*', 'frontend/.dockerignore']`
   - `docker_mcp: ['mcp/Dockerfile*', 'mcp/.dockerignore']`
   - `docker_config: ['docker/**', '.env.docker.example']`
   - `ci: ['.github/workflows/**', '.github/actions/**']`

2. **`backend`** — `if: backend || ci`. Composite setup → migrations → ruff
   check → ruff format check → mypy → xdist unit coverage →
   separate serial network HPO guard → Codecov.
   Commands:
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy app/ migration/`
   - `uv run pytest -n auto --dist loadgroup -m "not benchmark and not network" --cov=app --cov=migration --cov-report=xml --cov-report=term-missing`
   - `uv run pytest -m network -v`

3. **`frontend`** — `if: frontend || docker_frontend || ci`. setup-node npm
   cache → `npm ci` → vitest → eslint → Prettier coverage for `src` and
   `tests` → build → production bundle dev-auth leak guard.
   Implementation may either widen `npm run format:check` to cover
   `src`+`tests`, or run the existing `format:check` plus an explicit tests
   Prettier command.

4. **`mcp`** — `if: mcp || ci`. Composite setup → ruff → mypy →
   `uv run pytest -n auto --cov=hnf1b_mcp -m "not smoke and not live"` →
   contract-drift guard. Add `pytest-xdist` before enabling this command.

5. **`e2e`** — `if: frontend || backend || ci`. Full PG+Redis+backend+frontend
   stack + Playwright. **`needs: changes` only** (drop `needs: frontend`
   barrier). No browser caching for the current chromium-only suite.

6. **`prod-config-guards`** — `if: docker_config || ci`. Checkout-only job for
   cheap production config checks that must run on Docker/compose-only PRs:
   - `ENABLE_DEV_AUTH` must not be YAML-truthy in `docker/docker-compose.npm.yml`.
   - `ENVIRONMENT=production` must be pinned in `docker/docker-compose.npm.yml`.
   Keep grep guards here if they do not require a frontend build artifact.

7. **`hygiene`** — always runs. Slimmed ex-`pre-commit`: installs **only**
   `pre-commit` (no uv/node bootstrap) and runs with
   `SKIP=backend-ruff-check,backend-ruff-format,backend-mypy,frontend-eslint,frontend-prettier`
   after the backend/frontend jobs gain equivalent coverage. It still executes
   the upstream `pre-commit-hooks` checks (yaml/json/toml/merge-conflict/
   large-files/case-conflict/private-key) plus local grep guards
   (`check-test-imports`, `detect-non-deterministic-hash`).

8. **`ci-gate`** — `if: always()`, `needs: [changes, backend, frontend, mcp,
   e2e, prod-config-guards, hygiene]`. The **only** required status check.
   Fails if any need is `failure`/`cancelled`; passes when conditional jobs are
   `skipped`. This avoids branch protection depending on many conditional job
   names and keeps failures visible even when dependencies were skipped.

### pytest-xdist + per-worker isolation

Root `backend/conftest.py` already derives a test DB URL and honors
`TEST_DATABASE_URL`. Extend this path carefully for xdist:

- Add `pytest-xdist` to `backend`'s `test` group and `mcp`'s `dev` group, then
  refresh the corresponding `uv.lock` files.
- Read `PYTEST_XDIST_WORKER` (e.g. `gw0`, `gw1`); when set, suffix the DB name
  (`..._test_gw0`) so each worker owns an isolated database.
- Each worker database must be created and migrated with Alembic before tests
  touch static lookup tables. Do **not** replace migrations with
  `metadata.create_all()` / `drop_all()` because the suite relies on
  migration-seeded reference data and migration behavior.
- Preserve serial behavior when `PYTEST_XDIST_WORKER` is absent.
- Ensure session-start cleanup fixtures run only after worker DB creation and
  Alembic upgrade. Keep the existing mutable-table truncation model so static
  lookup tables survive inside each migrated worker DB.
- Redis: derive a per-worker logical DB index from the worker id
  (`redis://.../{index}`) or cap CI workers so the index stays within Redis's
  default 16 logical DBs.
- CI command for coverage stays network-free:
  `uv run pytest -n auto --dist loadgroup -m "not benchmark and not network" --cov=app --cov=migration --cov-report=xml --cov-report=term-missing`.
  `pytest-cov` auto-combines xdist worker data.
- Run the HPO live-network guard separately and serially:
  `uv run pytest -m network -v`.
- **Validation gate:** backend must pass locally with `-n 2` and the existing
  serial run before relying on CI. MCP must pass with
  `uv run pytest -n auto --cov=hnf1b_mcp -m "not smoke and not live"`.

### `docker.yml`

```yaml
on:
  push:
    branches: [main]
    tags: ['v*.*.*']
  pull_request:
permissions:
  contents: read
```

- `changes` job (paths-filter) for per-image gating; on `v*` tags build all
  three production images for a coherent release set. Reuse the `docker_backend`,
  `docker_frontend`, `docker_mcp`, and `docker_config` filters from `ci.yml`.
- Matrix `include` must use production Dockerfiles:
  - `backend`: context `backend`, dockerfile `backend/Dockerfile.prod`
  - `frontend`: context `frontend`, dockerfile `frontend/Dockerfile.prod`
  - `mcp`: context `mcp`, dockerfile `mcp/Dockerfile.prod`
  Use `fail-fast: false`.
- PRs build-validate only: no GHCR login and no `packages: write` permission.
- Pushes/tags publish: grant `packages: write` only on the publishing job,
  then run `docker/login-action` (GHCR, `GITHUB_TOKEN`).
- Per image: `docker/metadata-action` (tags: `sha`, branch, `pr`, `semver`,
  `latest` on default branch) → `docker/setup-buildx-action` →
  `docker/build-push-action` with
  `push: ${{ github.event_name != 'pull_request' }}`,
  `cache-from: type=gha,scope=<image>`,
  `cache-to: type=gha,mode=max,scope=<image>`.

### Dockerfile hardening (caching + image size)

GHCR builds should use the existing production Dockerfiles, not the development
Dockerfiles currently used by base local compose.

- `backend/Dockerfile.prod` already has a builder/runtime split, pinned uv, cache
  mounts, and manifest-before-source install. Do not remove the `migration`
  dependency group unless the deploy-time Alembic/data-import entrypoint
  contract is changed at the same time.
- `mcp/Dockerfile.prod` already excludes the dev group and uses a runtime stage.
- `frontend/Dockerfile.prod` already has an npm cache mount and keeps
  `VITE_API_URL` as a build arg. Pass the production value from the workflow.
- Dev Dockerfile cleanup is optional and should not block the CI/GHCR work.

## Implementation sequencing (one branch, one PR)

1. **Foundation** — move active spec to `.planning/`; composite action; rewrite
   `ci.yml` triggers + concurrency + `changes` gating + `prod-config-guards` +
   `ci-gate`; move missing backend/frontend formatting coverage out of
   `pre-commit`; slim `hygiene`; SHA-pin with version comments; pin
   `ubuntu-24.04`.
   *Largest compute win, lowest risk.*
2. **xdist** — add dependencies; implement Alembic-migrated per-worker DB/Redis
   isolation; verify backend serial + `-n 2`; verify MCP `-n auto`; then enable
   xdist in CI.
3. **Docker** — add `docker.yml` build/push matrix against production
   Dockerfiles; keep PR permissions read-only and publishing permissions
   push/tag-only.

Each step verified green before the next. Final: relevant local checks pass and
the PR's GitHub Actions status is green per repo convention.

## Expected impact
- Docs-only PRs: full backend/frontend/e2e skipped; only cheap hygiene/gate work.
- MCP-only PRs: backend/frontend/e2e skipped; MCP + hygiene/gate run.
- Redundant `pre-commit` bootstrapping removed.
- Backend tests: 2-3x faster if xdist validation holds.
- Docker builds: minutes → seconds on warm layer cache.
- No more duplicate push+PR runs.

## Risks & mitigations
- **Path-filter false negatives** (high) — filters must include Dockerfile
  variants, `.dockerignore`, compose files, `.env.docker.example`, and workflow
  changes. `ci` changes force all jobs.
- **xdist DB isolation** (medium) — contained to test bootstrap, but each worker
  must run Alembic migrations and preserve static lookup tables; gated on local
  `-n 2` pass + unchanged serial behavior before CI reliance.
- **Network HPO guard accidentally folded into coverage run** (medium) — keep
  `not network` in the coverage command and run the network marker separately.
- **Required-check migration** — branch protection must switch the required
  check to `ci-gate` (one repo-settings change; documented in the PR).
- **GHA cache eviction** (7-day idle / LRU) — low-traffic repo may see cold
  Docker caches; acceptable, registry cache is the fallback if churn appears.
- **PR-only triggers** — bare pushes without a PR no longer run CI (intended;
  confirmed with user).

## Out of scope
- Larger/self-hosted runners (chose free hosted).
- Vitest sharding (overkill at 59 specs).
- ruff cache (sub-second cold; not worth it).
- Caching Playwright browsers for the current chromium-only suite.
