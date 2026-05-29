# CI/CD Pipeline Optimization — Design

**Date:** 2026-05-29
**Branch:** `chore/ci-cd-optimization`
**Status:** Approved design → implementation

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
| `test` (backend) | PG+Redis, `uv sync`, migrations, ruff, mypy, **serial pytest** (120 files / 29k LOC) + coverage | 20m | serial pytest |
| `frontend` | npm ci, vitest (59 specs), eslint, prettier, build, 4 grep guards | 15m | install + build |
| `e2e-tests` | `needs: frontend`; full stack; **re-installs both stacks**; `playwright install`; 9 specs | 25m | full re-bootstrap |
| `mcp` | uv sync, ruff, mypy, pytest (100 tests), contract drift | 15m | — |
| `pre-commit` | **re-installs backend + frontend deps + pip pre-commit**; runs ruff/mypy/eslint/prettier on all files | 15m | ~90% duplicates `test`+`frontend` |

Triggers: `push: [main, develop, refactor--*]` + `pull_request: [main, develop]`
→ duplicate runs on branches matching both. Concurrency cancels in-progress for
all refs.

### Key findings
1. **No path filtering** — every change runs all 5 jobs.
2. **`pre-commit` job ~90% redundant** — re-bootstraps both stacks to re-run
   lint/typecheck already covered by `test` + `frontend`.
3. **`pytest` serial** — `pytest-xdist` typically 2–3× faster.
4. **Missing caches** — Playwright browsers re-downloaded; ruff/mypy cold; no
   pytest cache. (uv + npm caches already enabled.)
5. **`e2e` over-serialized** — `needs: frontend` adds an ordering barrier and
   re-installs everything instead of running in parallel.
6. **Double runs** — `push: refactor--*` + `pull_request` on the same commit
   land in different concurrency groups → two runs.
7. **No Docker image builds at all** — images are deploy/local-time only.

## Decisions (locked)

- **Triggers:** PR-only for feature branches. `push` triggers only on `main`
  (+ `v*` tags for Docker). Feature branches get CI through their open PR.
- **Gating:** `dorny/paths-filter@v4` boolean outputs gate downstream jobs.
- **xdist:** Included. Per-worker DB + Redis isolation added to backend tests.
- **Required check:** a single `ci-gate` aggregator (`if: always()`), never the
  individual conditional jobs.
- **Docker:** matrix build of all three images; PR = build-validate, main/tags =
  build + push to `ghcr.io`; per-image `type=gha,mode=max` layer cache.
- **Hardening:** all actions pinned to commit SHA (Dependabot already bumps the
  `github-actions` ecosystem); runners pinned to `ubuntu-24.04`.

## Target architecture

### File layout
- `.github/actions/setup-uv-python/action.yml` — **new** composite action:
  `astral-sh/setup-uv` (cache, `cache-dependency-glob` = both `uv.lock`s) +
  Python pin + `uv sync`. Reused by `backend`, `mcp`, `e2e` jobs.
- `.github/workflows/ci.yml` — **rewritten**: gated jobs + `ci-gate`.
- `.github/workflows/docker.yml` — **new**: build/push matrix.

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
   `mcp`, `docker`, `ci`. The `ci` filter (`.github/**`) forces all jobs when
   workflows/actions change. `permissions: pull-requests: read`.
   Filters:
   - `backend: ['backend/**']`
   - `frontend: ['frontend/**']`
   - `mcp: ['mcp/**']`
   - `docker: ['**/Dockerfile', 'docker/**']`
   - `ci: ['.github/workflows/**', '.github/actions/**']`

2. **`backend`** — `if: backend || ci`. Composite setup → migrations → ruff →
   mypy (optional `.mypy_cache` with isolated key) → `pytest -n auto` (per-worker
   isolation) → Codecov.

3. **`frontend`** — `if: frontend || ci`. setup-node npm cache → `npm ci` →
   vitest (`pool: threads`) → eslint → prettier → build → 4 grep guards.

4. **`mcp`** — `if: mcp || ci`. Composite setup → ruff → mypy → `pytest -n auto`
   (isolated, free win) → contract-drift guard.

5. **`e2e`** — `if: frontend || backend || ci`. Full PG+Redis+backend+frontend
   stack + Playwright. **`needs: changes` only** (drop `needs: frontend`
   barrier). No browser caching (Playwright advises against for chromium-only).

6. **`hygiene`** — always runs. Slimmed ex-`pre-commit`: installs **only**
   `pre-commit` (no uv/node bootstrap) and runs with
   `SKIP=backend-ruff-check,backend-ruff-format,backend-mypy,frontend-eslint,frontend-prettier`
   so it executes only the `pre-commit-hooks` (yaml/json/toml/merge-conflict/
   large-files/case-conflict/private-key) + grep guards
   (`check-test-imports`, `detect-non-deterministic-hash`). Removes the single
   most redundant ~10-min job.

7. **`ci-gate`** — `if: always()`, `needs: [changes, backend, frontend, mcp,
   e2e, hygiene]`. The **only** required status check. Fails if any need is
   `failure`/`cancelled`; passes when jobs are `skipped`. Resolves the
   "required check + skipped job = hung PR" trap.

### pytest-xdist + per-worker isolation

Root `backend/conftest.py` already derives a test DB URL and honors
`TEST_DATABASE_URL`. Extend `_derive_test_database_url()` to append the worker
id when running under xdist:

- Read `PYTEST_XDIST_WORKER` (e.g. `gw0`, `gw1`); when set, suffix the DB name
  (`..._test_gw0`) so each worker owns an isolated database.
- Ensure each worker's database exists (create-if-missing in a worker-scoped
  fixture; session create_all/drop_all then operate per-worker DB).
- Redis: derive a per-worker logical DB index from the worker id
  (`redis://.../{index}`), within Redis's 16-DB default.
- CI command: `uv run pytest -n auto --dist loadgroup -m "not benchmark"
  --cov=app --cov=migration --cov-report=xml`. pytest-cov auto-combines xdist
  worker data — no extra flags.
- **Validation gate:** must pass locally with `-n 2` (and the existing serial
  run) before relying on CI. `mcp` tests are already isolated → `-n auto`
  directly.

### `docker.yml`

```yaml
on:
  push:
    branches: [main]
    tags: ['v*.*.*']
  pull_request:
permissions:
  contents: read
  packages: write
```

- `changes` job (paths-filter) for per-image gating; on `v*` tags build all
  three for a coherent release set.
- Matrix `include`: `backend` / `frontend` / `mcp` (context, dockerfile).
  `fail-fast: false`.
- Per image: `docker/login-action` (GHCR, `GITHUB_TOKEN`) →
  `docker/metadata-action` (tags: `sha`, branch, `pr`, `semver`, `latest` on
  default branch) → `docker/setup-buildx-action` → `docker/build-push-action`
  with `push: ${{ github.event_name != 'pull_request' }}`,
  `cache-from: type=gha,scope=<image>`,
  `cache-to: type=gha,mode=max,scope=<image>`.

### Dockerfile hardening (caching + image size)
- `backend/Dockerfile`: single-stage, `uv:latest`, no cache mount → split
  builder/runtime, pin uv version, add
  `--mount=type=cache,target=/root/.cache/uv`, manifest-before-source,
  `--no-dev` runtime, drop the dev/`migration` toolchain from the shipped image.
- `mcp/Dockerfile`: already cache-friendly (pinned uv, cache mount) → add a
  runtime stage that excludes the `dev` group.
- `frontend/Dockerfile`: add `--mount=type=cache,target=/root/.npm` to the
  `npm ci` layer; keep `VITE_API_URL` as a `build-arg` passed from the workflow.

## Implementation sequencing (one branch, one PR)

1. **Foundation** — composite action; rewrite `ci.yml` triggers + concurrency +
   `changes` gating + `ci-gate`; slim `hygiene`; SHA-pin + `ubuntu-24.04`.
   *Largest compute win, lowest risk.*
2. **xdist** — conftest per-worker DB/Redis isolation; verify `-n 2` locally,
   then enable `-n auto` for backend + mcp.
3. **Docker** — `docker.yml` build/push matrix + Dockerfile hardening.

Each step verified green before the next. Final: full CI green on the PR,
Playwright-verified per repo convention.

## Expected impact
- Docs/mcp-only PRs: ~25 min → ~2–4 min (skip backend/frontend/e2e).
- Redundant `pre-commit` job removed: ~−10 min compute per run.
- Backend tests: ~2–3× faster (xdist).
- Docker builds: minutes → seconds on warm layer cache.
- No more duplicate push+PR runs.

## Risks & mitigations
- **xdist DB isolation** (medium) — contained to `conftest.py`; gated on local
  `-n 2` pass + unchanged serial behavior before CI reliance.
- **Required-check migration** — branch protection must switch the required
  check to `ci-gate` (one repo-settings change; documented in the PR).
- **GHA cache eviction** (7-day idle / LRU) — low-traffic repo may see cold
  Docker caches; acceptable, registry cache is the documented fallback if churn
  appears.
- **PR-only triggers** — bare pushes without a PR no longer run CI (intended;
  confirmed with user).

## Out of scope
- Larger/self-hosted runners (chose free hosted).
- Vitest sharding (overkill at 59 specs).
- ruff cache (sub-second cold; not worth it).
- Caching Playwright browsers (Playwright advises against for chromium-only).
