# End-to-end tests (Playwright)

Critical user-flow tests that drive a real browser against a running frontend +
backend. They mirror what CI runs (`.github/workflows/ci.yml` → `e2e` job).

## Prerequisites

1. **Backend on `:8000`** with a migrated DB and a seeded admin user. From the
   repo root:
   ```bash
   make backend            # uvicorn on :8000 (needs DATABASE_URL, JWT_SECRET, REDIS_URL)
   make db-create-admin     # or: make dev-seed-users  (seeds dev-admin / dev-curator / dev-viewer)
   ```
2. **A frontend** Playwright can reach (see _Ports_ below).

## Credentials

Authenticated specs log in through `helpers/auth.js` → `loginAsAdmin()`, which
tries credentials in this order:

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

## CI parity

CI seeds `admin` with `ADMIN_PASSWORD=ci_test_admin_password_2026` and exports
the matching `E2E_ADMIN_*` env, runs the backend on `:8000`, and lets
Playwright start Vite on `:5173`. Because the explicit env pair is tried first,
CI is deterministic; the local-dev fallbacks above never change CI behavior.
