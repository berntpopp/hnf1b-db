# Dependency and Security Consolidation Plan

> **For implementers:** execute in an isolated sibling worktree with `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Use `superpowers:systematic-debugging` for any install/CI failure and `superpowers:verification-before-completion` before updating/closing Dependabot PRs.

**Goal:** Integrate the intent of Dependabot PRs #423-#434 as coherent lockfile updates, close all alerts in scope (or record an owner-approved time-bounded exception), and avoid the broken/split dependency graphs found in #428, #430, and #431.

**Architecture:** Treat each package manager's authoritative manifest and lock as one atomic unit. Frontend package changes are one manifest edit plus one `package-lock.json` regeneration. Backend/MCP use `pyproject.toml` plus `uv.lock`; requirements are generated artifacts. Workflow actions are one reviewed workflow change.

## Baseline facts

The versions, alert counts, PR states, action SHAs, and fixed-version thresholds below were observed on 2026-08-09 at PR #422 SHA `1539b196107e960004dd382a2ee9ea0625c899d3`. Task 1 refreshes all volatile evidence before edits; refreshed advisory metadata is authoritative.

- PR #422 does not itself change workflow or dependency manifests/locks.
- Open alert groups at review time: Undici (five alerts, including one high), backend cryptography (high), MCP cryptography (high), and DOMPurify (medium).
- PR #430 fails install because `@tiptap/vue-3@3.29.2` requires exact peer `@tiptap/core@3.29.2` while the root stays 3.27.1.
- PR #428 alone nests a second 3.29.2 Tiptap stack, producing a split graph.
- PR #431 changes requirements pins that are not backed by `backend/uv.lock`; its `pydantic==2.13.4` / `pydantic-core==2.47.0` pairing is incompatible because that Pydantic release requires core 2.46.4.
- Backend cryptography is not covered by the current MCP cryptography PR.
- The observed GitHub-hosted runner is compatible with Node 24 actions; any self-hosted runner must meet the official minimum before action v7 is adopted.

## Task 1: Capture a reproducible baseline

**Read/record, do not edit yet**

- `frontend/package.json`, `frontend/package-lock.json`
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.txt`, `backend/requirements-dev.txt`
- `mcp/pyproject.toml`, `mcp/uv.lock`
- `.github/workflows/**/*.yml` and `.github/actions/**/action.yml`

**Steps**

1. Record branch SHA, Node/npm/uv versions, `npm ls`, `uv lock --check` for backend/MCP, current GitHub alert/check state, advisory fixed versions, peer metadata, action SHAs, and runner requirements.
2. Save no generated reports containing tokens or environment secrets.
3. Run baseline package-manager checks so pre-existing failures are distinguishable from update failures.

```bash
cd frontend && npm ci && npm ls --all
cd ../backend && uv lock --check
cd ../mcp && uv lock --check
```

## Task 2: Consolidate the frontend updates into one dependency graph

**Modify together**

- `frontend/package.json`
- `frontend/package-lock.json`

**Target manifest intent**

- `@playwright/test`: `^1.62.1`
- `lint-staged`: `^17.3.0`
- `vuetify`: `~4.1.7`
- `vue-router`: `^5.2.0`
- `dompurify`: `^3.4.13`
- all direct Tiptap packages pinned exactly to `3.29.2` because their peers are exact:
  - `@tiptap/core`
  - `@tiptap/extension-link`
  - `@tiptap/extension-mention`
  - `@tiptap/starter-kit`
  - `@tiptap/vue-3`

The regenerated graph must resolve Undici to at least 7.29.0. Do not hand-edit lockfile package nodes.

**Steps**

1. Write/adjust a small dependency-consistency check if the repository lacks one: all five direct `@tiptap/*` manifest values and resolved root versions must be identical, and `npm ls @tiptap/core` must not report conflicting stacks.
2. Edit `package.json` once.
3. Run one npm install to regenerate the lock.
4. Inspect the Tiptap graph, Undici resolution, DOMPurify resolution, and peer warnings.

```bash
cd frontend
npm install
npm ls @tiptap/core @tiptap/vue-3 @tiptap/starter-kit undici dompurify
npm audit
npm audit --omit=dev
npm test -- \
  tests/unit/components/PhenotypicFeaturesSection.spec.js \
  tests/unit/components/VariantAnnotationForm.spec.js \
  tests/unit/views/PhenopacketCreateEdit.spec.js
npm test
npm run lint:check
npx prettier --check "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run build
npx playwright install --with-deps chromium
npx playwright test tests/e2e/curation-console.spec.js --project=chromium
```

5. Run focused editor/router/Vuetify/Playwright tests plus the full frontend unit suite. Do not accept `--legacy-peer-deps`, `--force`, nested duplicate stacks, or audit suppression as a fix.

## Task 3: Regenerate the backend dependency set from authoritative inputs

**Modify**

- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`

**Policy**

- Change the direct ruff pin to `0.16.1` if its release remains the approved target.
- Upgrade compatible locked versions for annotated-doc, Redis, Uvicorn, and cryptography through uv resolution using Task 1's refreshed compatible/fixed versions (0.0.5, 8.1.0, 0.52.0, and 50.x at review time).
- Keep `pydantic-core` paired with the exact Pydantic metadata requirement. For Pydantic 2.13.4, keep core 2.46.4. Upgrade both only if an actual Pydantic release officially requires/supports the newer core and the full suite passes.
- `backend/uv.lock` is authoritative. Do not patch only exported requirements.

**Steps**

1. Update the direct ruff pin in `pyproject.toml`.
2. Use targeted uv upgrades rather than editing transitive lock entries:

```bash
cd backend
uv lock --upgrade-package ruff \
  --upgrade-package annotated-doc \
  --upgrade-package redis \
  --upgrade-package uvicorn \
  --upgrade-package cryptography
uv lock --check
uv sync --all-groups
```

3. Verify resolved versions and Pydantic/core metadata before exporting.
4. Regenerate base requirements exactly as its header documents:

```bash
uv export --format requirements.txt --no-dev --no-hashes --no-emit-project --output-file requirements.txt
```

5. Add a deterministic `backend/Makefile` export target and CI drift check, then generate the dev/test export from uv rather than hand-maintaining a partial list:

```bash
uv export --format requirements.txt --group dev --group test --no-hashes --no-emit-project --output-file requirements-dev.txt
```

6. Prove both exported files are reproducible and pins equal lock resolutions for ruff, annotated-doc, Pydantic/core, Redis, Uvicorn, and cryptography.
7. Run a pinned Python advisory scanner against the complete exported locked graph for backend; sanitize its report before retaining it.

**Gate**

Run the CI-parity pgvector PostgreSQL 15 and Redis services, `alembic upgrade head`, and the exact lint/format/mypy/pytest environment from `.github/workflows/ci.yml`. For a local equivalent, start the repository services, initialize the dedicated test DB, set `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET`, and `ADMIN_PASSWORD`, then run `cd backend && make check`. The GitHub backend job remains the authoritative clean-checkout gate.

## Task 4: Upgrade MCP cryptography through uv

**Modify**

- `mcp/uv.lock`
- `mcp/pyproject.toml` only if a direct constraint is actually required

**Steps**

1. Run `uv lock --upgrade-package cryptography` in `mcp/`.
2. Confirm all cryptography lock entries meet the refreshed advisory's fixed version (50.x at review time) and no incompatible transitive package is forced.
3. Run a pinned Python advisory scanner against the complete MCP locked graph.
4. Run MCP checks. Contract verification is needed only if the OpenAPI/generated contract changes in the combined branch.

```bash
cd mcp
uv lock --upgrade-package cryptography
uv lock --check
uv sync --all-groups
make check
```

## Task 5: Integrate workflow action updates as one reviewed change

**Modify**

- every matching file under `.github/workflows/**/*.yml` and `.github/actions/**/action.yml`, discovered with `rg`

**Intent from PRs #423-#425**

- docker/login-action 4.6.0
- actions/setup-node 7.0.0
- actions/checkout 7.0.1

At execution time, verify the exact full commit SHAs against the official action repositories/Dependabot PR heads. Do not copy a tag-only reference. Update every occurrence and its version comment together; the current setup-node `# v6` comments must not remain beside a v7 SHA.

**Steps**

1. Confirm hosted/self-hosted runner inventory. Node 24 action runtimes require the official minimum runner; keep the tested application Node version at 22 unless a separate application migration is approved.
2. Inventory/update all occurrences with exact SHAs and matching comments.
3. Parse/lint workflow YAML and inspect the diff for missed occurrences.
4. Push and require every CI/Docker job to start successfully; an install-time failure is not an acceptable partial success.

## Task 6: Verify alerts, PR coverage, and close superseded PRs

**Steps**

1. Run local frontend/backend/MCP checks from Tasks 2-4 and Docker builds relevant to changed dependency graphs.
2. Push the consolidated branch and wait for all required GitHub checks.
3. Merge the consolidated PR only when checks pass, then re-query Dependabot alerts on the default branch. Expected: Undici, both cryptography alerts, and DOMPurify alerts are closed by the resolved graph.
4. If an alert remains, inspect its ecosystem/manifest/path. Do not assume an MCP lock change covers the backend lock.
5. Compare consolidated changes against PRs #423-#434 and record each as integrated, superseded, intentionally rejected, or still needed.
6. Close superseded Dependabot PRs only after the consolidated PR is merged and alert state is verified.

## Final verification matrix

| Area                 | Required evidence                                                                                                                             |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend install     | `npm ci` succeeds without peer overrides.                                                                                                     |
| Tiptap               | All direct packages aligned; no split 3.27/3.29 root graph.                                                                                   |
| Frontend security    | Undici and DOMPurify meet refreshed fixed versions (7.29.0 and 3.4.13 at review); alerts close.                                               |
| Frontend runtime     | unit/lint/format/build and editor/router/Vuetify/Playwright smoke tests pass.                                                                 |
| Backend lock         | `uv lock --check`; cryptography meets refreshed fixed version; advertised upgrades are locked.                                                |
| Pydantic             | Pydantic/core exact metadata requirement satisfied.                                                                                           |
| Requirements exports | generated pins match uv lock; no requirements-only phantom upgrade.                                                                           |
| MCP lock             | cryptography meets refreshed fixed version; `make check` and relevant contract checks pass.                                                   |
| Actions              | exact SHA pins, matching comments, compatible runners, all jobs start/pass.                                                                   |
| GitHub               | required checks green; alerts in scope closed or an owner-approved exception records advisory ID, exposure, compensating control, and expiry. |

## Merge strategy

Use one consolidated dependency PR or a short ordered stack with non-overlapping locks. Do not cherry-pick #428, #430, or #431 independently. Generate and verify authoritative locks on Lane G, merge Lane G first, then rebase clinical branches onto updated main. Clinical branches regenerate locks only if they also change manifests.
