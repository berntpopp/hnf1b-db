# Technology Stack

**Analysis Date:** 2026-01-19

## Languages

**Primary:**
- Python 3.10+ - Backend API, migrations, data processing
- JavaScript (ES6+) - Frontend application

**Secondary:**
- SQL - Database queries, migrations (PostgreSQL dialect)
- YAML - Configuration files (`backend/config.yaml`)

## Runtime

**Environment:**
- Python 3.10+ (via uv package manager)
- Node.js (latest LTS, via npm)

**Package Manager:**
- Backend: uv (fast Python dependency resolution)
  - Lockfile: `backend/uv.lock` (present)
- Frontend: npm
  - Lockfile: `frontend/package-lock.json` (present)

## Frameworks

**Core:**
- FastAPI 0.116.1+ - Backend REST API framework with async support
- Vue 3.5.26 - Frontend SPA framework (Composition API)
- Vuetify 3 - Material Design UI component library

**ORM/Database:**
- SQLAlchemy 2.0+ (async) - ORM with asyncpg driver
- Alembic 1.13.1+ - Database migrations

**Testing:**
- Backend: pytest 9.0.2 with pytest-asyncio, pytest-cov
- Frontend: Vitest 4.0.7 with @vue/test-utils 2.4.6
- E2E: Playwright 1.57.0

**Build/Dev:**
- Backend: uvicorn (ASGI server with hot reload)
- Frontend: Vite 7.3.1 (build tool, dev server)
- Linting: ruff (Python), ESLint 9.x (JavaScript)
- Formatting: ruff (Python), Prettier 3.7.4 (JavaScript)
- Type Checking: mypy 1.19.1 (Python only)

## Key Dependencies

**Critical (Backend):**
- `fastapi>=0.116.1` - Web framework with automatic OpenAPI docs
- `sqlalchemy[asyncio]>=2.0.25` - Async ORM
- `asyncpg>=0.29.0` - PostgreSQL async driver
- `pydantic>=2.11.7` - Data validation and serialization
- `pydantic-settings>=2.10.1` - Environment configuration
- `pyjwt>=2.10.1` - JWT authentication
- `passlib[bcrypt]>=1.7.4` - Password hashing
- `phenopackets>=2.0.0` - GA4GH Phenopackets v2 schema
- `ga4gh.vrs>=2.1.3` - GA4GH Variant Representation Standard
- `pronto>=2.5.0` - OBO ontology parsing (HPO, MONDO)

**Infrastructure (Backend):**
- `redis>=5.0.0` - Distributed caching
- `httpx>=0.28.1` - Async HTTP client (VEP API calls)
- `aiohttp>=3.13.1` - Async HTTP client (PubMed API calls)
- `requests>=2.31.0` - Sync HTTP client (ontology APIs)
- `pandas>=2.3.2` - Data processing (Google Sheets import)

**Critical (Frontend):**
- `vue@3.5.26` - Reactive UI framework
- `vue-router@4.6.4` - Client-side routing
- `vuetify` - Material Design components (via vite-plugin-vuetify)
- `axios@1.13.2` - HTTP client for API calls
- `d3@7.9.0` - Data visualization
- `chart.js@4.5.1` - Charting library
- `pinia@3.0.4` - State management

**Infrastructure (Frontend):**
- `ngl@2.4.0` - Protein structure visualization
- `date-fns@4.1.0` - Date utilities
- `yup@1.7.1` - Form validation
- `file-saver@2.0.5` - File download utility

## Configuration

**Environment (Secrets - `.env` files):**
- `backend/.env` - Backend secrets (required)
  - `DATABASE_URL` - PostgreSQL connection string (required)
  - `JWT_SECRET` - JWT signing key (required, app exits if empty)
  - `REDIS_URL` - Redis connection (default: `redis://localhost:6379/0`)
  - `PUBMED_API_KEY` - PubMed API key (optional, increases rate limit)
  - `ADMIN_USERNAME/EMAIL/PASSWORD` - Initial admin credentials
  - `CORS_ORIGINS` - Allowed CORS origins
  - `DEBUG` - Debug mode flag
- `frontend/.env` - Frontend configuration
  - `VITE_API_URL` - Backend API URL (default: `/api/v2`)

**Behavior (YAML - `backend/config.yaml`):**
- `pagination` - Page sizes and limits
- `rate_limiting` - API, VEP, PubMed rate limits
- `external_apis` - VEP, OLS, PubMed endpoints and timeouts
- `database` - Connection pool settings
- `security` - JWT algorithm, token expiration
- `materialized_views` - Aggregation optimization settings
- `hpo_terms` - HPO term constants for survival analysis

**Build:**
- `backend/pyproject.toml` - Python project config, dependencies, ruff/mypy settings
- `frontend/vite.config.js` - Vite build config, chunk splitting, compression
- `frontend/vitest.config.js` - Test configuration
- `frontend/eslint.config.js` - Linting rules

## Platform Requirements

**Development:**
- Docker and Docker Compose (for PostgreSQL + Redis)
- Python 3.10+ with uv
- Node.js LTS with npm
- Make (for unified commands)

**Production:**
- Docker with docker-compose
- PostgreSQL 15 (Alpine image)
- Redis 7 (Alpine image)
- Nginx (via Nginx Proxy Manager for SSL termination)

**Docker Services:**
- `hnf1b_db` - PostgreSQL 15-alpine on port 5433
- `hnf1b_cache` - Redis 7-alpine on port 6380
- `hnf1b_api` - FastAPI backend on port 8000
- `hnf1b_frontend` - Vue.js frontend on port 3000

---

*Stack analysis: 2026-01-19*
