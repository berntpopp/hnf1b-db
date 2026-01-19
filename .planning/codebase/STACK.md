# Technology Stack

**Analysis Date:** 2026-01-19

## Languages

**Primary:**
- Python 3.10+ - Backend API, migration scripts, data processing
- JavaScript (ES2020+) - Frontend application

**Secondary:**
- SQL (PostgreSQL) - Database queries, migrations, materialized views
- YAML - Configuration files (`backend/config.yaml`)

## Runtime

**Environment:**
- Python 3.11 (Docker) / 3.10+ (local development)
- Node.js 20 LTS

**Package Manager:**
- Backend: uv (fast dependency resolution)
- Frontend: npm
- Lockfiles: `backend/uv.lock`, `frontend/package-lock.json`

## Frameworks

**Core:**
- FastAPI 0.116.1+ - Backend web framework with async support
- Vue 3.5+ - Frontend framework (Composition API)
- Vuetify 3 - Material Design UI component library

**Testing:**
- pytest 9.0.2 - Backend testing with pytest-asyncio
- Vitest 4.0.7 - Frontend testing with @vue/test-utils

**Build/Dev:**
- Vite 7.3+ - Frontend build tool and dev server
- Alembic 1.13+ - Database migrations
- uvicorn 0.35+ - ASGI server

## Key Dependencies

### Backend Critical (`backend/pyproject.toml`)

**Web Framework:**
- `fastapi>=0.116.1` - REST API framework
- `uvicorn[standard]>=0.35.0` - ASGI server
- `pydantic>=2.11.7` - Data validation and serialization
- `pydantic-settings>=2.10.1` - Settings management

**Database:**
- `sqlalchemy[asyncio]>=2.0.25` - Async ORM
- `asyncpg>=0.29.0` - PostgreSQL async driver
- `alembic>=1.13.1` - Database migrations
- `psycopg2-binary>=2.9.9` - PostgreSQL adapter (for Alembic)

**Authentication:**
- `pyjwt>=2.10.1` - JWT token handling
- `passlib[bcrypt]>=1.7.4` - Password hashing
- `bcrypt>=3.2.0,<6.0.0` - BCrypt algorithm (pinned for passlib compatibility)

**GA4GH Standards:**
- `phenopackets>=2.0.0` - GA4GH Phenopackets v2 schema
- `ga4gh.vrs>=2.1.3` - Variant Representation Standard
- `protobuf>=4.25.0` - Protocol buffers for phenopackets

**HTTP Clients:**
- `httpx>=0.28.1` - Async HTTP client (VEP, Ensembl)
- `aiohttp>=3.13.1` - Async HTTP (PubMed, OLS)
- `requests>=2.31.0` - Sync HTTP client

**Data Processing:**
- `pandas>=2.3.2` - Data manipulation
- `jsonschema>=4.20.0` - Phenopacket validation
- `jsonpatch>=1.33` - RFC 6902 JSON Patch (audit trail)
- `jsonpath-ng>=1.6.0` - Complex JSON queries
- `pronto>=2.5.0` - OBO ontology parsing (HPO, MONDO)

**Caching:**
- `redis>=5.0.0` - Distributed caching

**Configuration:**
- `pyyaml>=6.0.2` - YAML config file parsing
- `python-dotenv>=1.1.1` - Environment variable loading

### Frontend Critical (`frontend/package.json`)

**Core:**
- `vue@^3.5.26` - Vue 3 framework
- `vue-router@^4.6.4` - Client-side routing
- `pinia@^3.0.4` - State management (devDependency)

**UI:**
- `vuetify` - Material Design components (via vite-plugin-vuetify)
- `@mdi/font@^7.4.47` - Material Design Icons

**Data Fetching:**
- `axios@^1.13.2` - HTTP client with interceptors

**Visualization:**
- `d3@^7.9.0` - Data visualization (gene plots, charts)
- `chart.js@^4.5.1` - Charts and graphs
- `ngl@^2.4.0` - 3D protein structure viewer

**Utilities:**
- `date-fns@^4.1.0` - Date formatting
- `file-saver@^2.0.5` - File downloads
- `yup@^1.7.1` - Form validation
- `just-debounce-it@^3.2.0` - Debounce utility

## Development Dependencies

### Backend (`[dependency-groups]` in pyproject.toml)

**dev:**
- `ruff==0.14.10` - Linting and formatting (replaces black, isort, flake8)
- `mypy==1.19.1` - Static type checking
- `types-jsonschema`, `types-pyyaml`, `types-redis` - Type stubs

**test:**
- `pytest==9.0.2` - Test framework
- `pytest-asyncio>=1.2.0` - Async test support
- `pytest-cov==7.0.0` - Coverage reporting

**migration:**
- `tqdm>=4.66.0` - Progress bars
- `rich>=13.7.0` - Rich console output
- `deepdiff>=6.7.0` - Data comparison

### Frontend (`devDependencies`)

**Testing:**
- `vitest@^4.0.7` - Unit test framework
- `@vue/test-utils@^2.4.6` - Vue component testing
- `happy-dom@^20.1.0` - DOM environment for tests
- `@vitest/coverage-v8` - Coverage reporting
- `@playwright/test@^1.57.0` - E2E testing

**Code Quality:**
- `eslint@^9.39.2` - JavaScript/Vue linting
- `eslint-plugin-vue@^10.6.2` - Vue-specific rules
- `prettier@^3.7.4` - Code formatting

**Build:**
- `@vitejs/plugin-vue@^6.0.3` - Vite Vue plugin
- `vite-plugin-vuetify@^2.1.2` - Vuetify tree-shaking
- `vite-plugin-compression@^0.5.1` - Brotli/gzip compression
- `rollup-plugin-visualizer@^6.0.5` - Bundle analysis
- `terser@^5.44.1` - JavaScript minification

## Configuration

### Environment Variables

**Backend (`backend/.env`):**
```bash
# REQUIRED
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/db
JWT_SECRET=<32-byte-hex-string>

# Optional
REDIS_URL=redis://localhost:6379/0
PUBMED_API_KEY=<ncbi-api-key>
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<secure-password>
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DEBUG=true
```

**Frontend (`frontend/.env`):**
```bash
VITE_API_URL=http://localhost:8000/api/v2
```

### Behavior Configuration

**YAML Config (`backend/config.yaml`):**
- Pagination limits
- Rate limiting settings
- External API URLs and timeouts
- Database pool settings
- Security parameters (non-secrets)
- HPO term constants for survival analysis

### Build Configuration

**Backend:**
- `backend/pyproject.toml` - Dependencies, ruff, mypy settings
- `backend/alembic.ini` - Migration configuration

**Frontend:**
- `frontend/vite.config.js` - Build, plugins, chunking
- `frontend/vitest.config.js` - Test configuration
- `frontend/eslint.config.js` - Linting rules

## Platform Requirements

### Development

**Prerequisites:**
- Python 3.10+
- Node.js 20+
- Docker and Docker Compose
- uv package manager (`pip install uv`)

**Commands:**
```bash
make hybrid-up      # Start PostgreSQL + Redis in Docker
make backend        # Run backend locally (port 8000)
make frontend       # Run frontend locally (port 5173)
```

### Production

**Deployment:**
- Docker Compose orchestration
- PostgreSQL 15-alpine
- Redis 7-alpine
- Nginx for frontend static serving

**Docker Images:**
- `python:3.11-slim` - Backend base
- `node:20-alpine` - Frontend build stage
- `nginx:alpine` - Frontend serving

**Ports:**
- Frontend: 3000 (or 80 behind proxy)
- Backend: 8000
- PostgreSQL: 5432 (internal), 5433 (exposed for dev)
- Redis: 6379 (internal), 6380 (exposed for dev)

## CI/CD

**GitHub Actions (`.github/workflows/ci.yml`):**
- Triggers: push/PR to main, develop
- Services: PostgreSQL 15, Redis 7-alpine
- Backend: ruff lint, mypy typecheck, pytest with coverage
- Frontend: vitest, eslint, prettier
- Coverage: Codecov integration

---

*Stack analysis: 2026-01-19*
