# AGENTS.md

## Trust Order

- Trust current code and config over older prose when they conflict.
- Prefer `backend/pyproject.toml`, `frontend/package.json`, project configs, and source conventions over narrative docs.
- Treat `.planning/` as the home for active specs, plans, reviews, and archives.
- Treat `docs/` as durable reference documentation only.

## Stack

- Monorepo with `backend/` and `frontend/`.
- Backend: FastAPI, Python 3.10+, async SQLAlchemy, asyncpg, Alembic, PostgreSQL JSONB, Redis, Pydantic, JWT, uv.
- Frontend: Vue 3, Vuetify 3, Vite, Pinia, Axios, Vitest, Playwright, npm.
- Domain standards: GA4GH Phenopackets v2 and VRS-aware variant handling.

## Architecture

- Keep backend code async-first.
- Prefer clear router/service/model boundaries over large mixed-responsibility modules.
- Use centralized frontend API utilities rather than ad hoc fetch logic.
- Preserve server-driven pagination, sorting, and filtering for data tables.
- Use `.planning/` for planning artifacts and `docs/` for stable documentation; do not blur the boundary again.

## Workflow

- Prefer root `make` targets first for setup, running, and verification.
- Keep git worktrees as sibling directories, never nested inside the repo.
- Before committing or merging, run the relevant repo checks for the code you changed.
- Before calling work complete or opening/updating a PR, verify the relevant local checks pass and inspect the PR's GitHub Actions status; if Actions fail, investigate, fix, and re-run until the PR is green or a deliberate blocker is documented.
- Do not ignore failing tests, lint errors, or type errors; fix them or document a deliberate exception.

## Backend Conventions

- Use snake_case for modules and functions, PascalCase for classes.
- Use `ruff` for formatting/linting and `mypy` for type checking.
- Keep imports ordered: standard library, third-party, local.
- Use Google-style docstrings where docstrings are needed.
- Prefer explicit validation and conflict handling over raw database errors leaking outward.

## Frontend Conventions

- Use Vue Composition API and `<script setup>` patterns.
- Keep SFC block order as `template`, `script`, `style`.
- Use `@/` aliases for local imports.
- Never use `console.log()` in frontend code; use `window.logService`.
- Keep pagination and sorting server-side; do not reintroduce client-side table sorting/pagination.
- `AppDataTable` is the standard table wrapper and should remain server-driven by default.

## Testing

- Backend tests use `pytest` and `test_*.py`.
- Frontend tests use Vitest and Playwright with `*.spec.js`.
- Prefer testing public behavior over implementation details.
- Prefer fixtures, mocks, and deterministic inputs over live external dependencies.

## Environment Constraints

- Backend requires correct local environment configuration, especially `DATABASE_URL` and `JWT_SECRET`.
- Frontend API configuration should target the backend `/api/v2` base path.
- Production-sensitive behavior should fail closed rather than silently degrade.

## Documentation Discipline

- If implementation details need to be durable, promote them into `docs/`.
- If a file is an active plan, review, or roadmap, keep it in `.planning/`.
- Archive finished or superseded planning material promptly by type.
