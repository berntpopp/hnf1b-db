# End-to-end tests (Playwright)

Critical user-flow tests that drive a real browser against a running frontend +
backend. They mirror what CI runs (`.github/workflows/ci.yml` → `e2e` job).

## Prerequisites

1. **Backend on `:8000`** with a migrated DB and seeded admin + two independent
   curator users. From the
   repo root:
   ```bash
   make backend            # uvicorn on :8000 (needs DATABASE_URL, JWT_SECRET, REDIS_URL)
   make dev-seed-users      # seeds dev-admin, curator A/B, legacy curator, viewer
   ```
   `make db-create-admin` alone is insufficient for specs that exercise
   independent approval unless you separately seed two distinct curators and
   export both credential pairs described below.
2. **A frontend** Playwright can reach (see _Ports_ below).

## Credentials

Authenticated specs use separate author/publisher and reviewer identities.
`helpers/auth.js` → `loginAsAdmin()` tries admin credentials in this order:

1. `E2E_ADMIN_USERNAME` + `E2E_ADMIN_PASSWORD` (if **both** are set) — used by CI.
2. `admin` / `ChangeMe!Admin2025` — the `backend/.env.example` default.
3. `dev-admin` / `DevAdmin!2026` — seeded by `make dev-seed-users`.

So a fresh local checkout that ran `make dev-seed-users` needs **no env vars**.
If your seeded admin uses a different password, export it:

```bash
export E2E_ADMIN_USERNAME=admin
export E2E_ADMIN_PASSWORD='<the password you seeded>'
```

If none of the candidates authenticate, `loginAsAdmin()` throws a single,
explicit error telling you what it tried and how to fix it — rather than an
opaque per-credential failure.

Independent-review specs use two deliberately distinct fixture principals:

```text
curator A (owner/submitter): dev-curator-a / DevCuratorA!2026
curator B (reviewer):        dev-curator-b / DevCuratorB!2026
```

Override either actor only with its complete paired variables:

```bash
export E2E_CURATOR_A_USERNAME='<owner curator username>'
export E2E_CURATOR_A_PASSWORD='<owner curator password>'
export E2E_CURATOR_B_USERNAME='<reviewer curator username>'
export E2E_CURATOR_B_PASSWORD='<reviewer curator password>'
```

A half-configured pair is an error; helpers never mix an explicit username with
a fallback password (or vice versa). `E2E_REVIEWER_USERNAME` /
`E2E_REVIEWER_PASSWORD` remain a compatibility alias for older specs and jobs,
but the independent-review lifecycle does not use that alias.

## Ports (important)

- Playwright's `webServer` (see `playwright.config.js`) starts Vite with
  `--port 5173 --strictPort`. The project's dev convention is `:3000`
  (`make dev`), so the two are intentionally decoupled.
- The backend allows CORS for both `:3000` and `:5173`, and the Vite dev server
  proxies `/api` + `/health` to the backend — so the browser port does not
  cause CORS issues.
- If `:5173` is already taken by an **unrelated** server, either free it or run
  against your own frontend and skip the built-in `webServer`:
  ```bash
  # point the suite at an already-running frontend (e.g. make dev on :3000)
  E2E_BASE_URL=http://localhost:3000 npm run e2e
  ```
- To leave an unrelated `:5173` service untouched, run this worktree's Vite on
  `:5174`, allow that exact development origin on the backend, and point
  Playwright at it explicitly:
  ```bash
  CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:5174 \
    make backend
  VITE_API_URL=http://localhost:8000/api/v2 npm run dev -- --port 5174 --strictPort
  E2E_BASE_URL=http://localhost:5174 \
    VITE_API_URL=http://localhost:8000/api/v2 \
    npm run e2e -- tests/e2e/independent-review.spec.js
  ```

## Running

```bash
cd frontend

npm run e2e                                   # full suite (starts Vite on :5173)
npm run e2e -- tests/e2e/comments.spec.js     # a single spec
npm run e2e:ui                                # interactive UI mode
npm run e2e:debug                             # step-through debugger
npm run e2e:report                            # open the last HTML report
```

Useful env vars: `E2E_BASE_URL` (frontend URL), `VITE_API_URL` /
`E2E_API_BASE` (backend API base, default `http://localhost:8000/api/v2`),
`E2E_ADMIN_USERNAME` / `E2E_ADMIN_PASSWORD`.
`E2E_CURATOR_A_*` / `E2E_CURATOR_B_*` select the distinct owner and reviewer.
`E2E_REVIEWER_*` is legacy-only compatibility.

## CI parity

CI seeds `admin` with `ADMIN_PASSWORD=ci_test_admin_password_2026`, runs the
development fixture seeder for curator A/B, and exports matching
`E2E_ADMIN_*`, `E2E_CURATOR_A_*`, and `E2E_CURATOR_B_*` pairs. It runs the
backend on `:8000` and lets Playwright start Vite on `:5173`. Explicit env pairs
keep CI deterministic; the local-development fallbacks never change CI actor
selection.

## Independent-review coverage

- `independent-review.spec.js` proves private discovery controls, server-filtered
  queue discovery, self-review denial, typed blocking issues, exact revision and
  digest decisions, admin-only publication, reopening, and old-public-head
  retention through a second cycle.
- `review-workspace-accessibility.spec.js` proves keyboard queue/issue/decision
  operation, named controls, cancel/success/conflict focus, non-color diff cues,
  stale-snapshot recovery, and the 375×812 safe-area/no-overflow layout.
- Most runtime records use unique `e2e-` identifiers. The principal lifecycle
  deliberately uses `review-lifecycle-*` because public list/search excludes
  synthetic `e2e-*` fixtures; a `finally` block archives that discoverable
  record through the normal transition API even when a later assertion fails.
  Interrupted processes may still leave identifiable fixtures for diagnosis;
  archive them through the same transition API rather than deleting rows.
