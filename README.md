# HNF1B Database

Full-stack monorepo for clinical and genetic data management, implementing the
GA4GH Phenopackets v2 standard.

- **Backend:** FastAPI REST API (Python 3.10+)
- **Frontend:** Vue.js 3 with Vuetify 3 (Material Design)
- **Database:** PostgreSQL with JSONB storage

## Quick Start

```bash
# Install all dependencies (backend + frontend)
make dev

# Start PostgreSQL + Redis in Docker
make hybrid-up

# Terminal 1 — Backend (http://localhost:8000)
make backend

# Terminal 2 — Frontend (http://localhost:5173)
make frontend
```

See [docs/deployment/docker.md](docs/deployment/docker.md) for full Docker
deployment instructions (including production with Nginx Proxy Manager).

## Dev-mode quick-login (local development only)

For faster iteration on features that need to switch between admin, curator, and
viewer roles, Wave 5a adds a dev-only quick-login feature guarded by five layers
of defense.

To enable it locally:

```bash
# Add to backend/.env:
ENVIRONMENT=development
ENABLE_DEV_AUTH=true

# Seed three fixture users (dev-admin / dev-curator / dev-viewer):
make dev-seed-users

# Start the backend; the login page will show the three dev buttons.
make backend
```

Passwords: `DevAdmin!2026`, `DevCurator!2026`, `DevViewer!2026`.

The feature is structurally impossible to ship to production:

1. Backend config refuses to start with `ENABLE_DEV_AUTH=true` if
   `ENVIRONMENT != development`
2. The dev router module has a load-time `assert` that crashes on import
3. The `is_fixture_user` column gates which users can be targeted
4. The frontend component is tree-shaken out of production builds
5. CI grep jobs fail the build if any dev-mode string leaks into `dist/`

## Documentation

- [docs/deployment/docker.md](docs/deployment/docker.md) — Docker deployment guide
- [docs/api/README.md](docs/api/README.md) — API endpoint overview
- [.planning/README.md](.planning/README.md) — internal plans, specs, reviews, and archives
- [CLAUDE.md](CLAUDE.md) — Developer commands and architecture reference
- API docs: http://localhost:8000/docs (when backend is running)
