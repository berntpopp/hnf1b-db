# Codebase Structure

**Analysis Date:** 2026-01-19

## Directory Layout

```
hnf1b-db/
├── backend/                    # FastAPI REST API (Python 3.10+)
│   ├── app/                    # Main application code
│   │   ├── api/                # Auth and admin endpoints
│   │   ├── auth/               # JWT authentication module
│   │   ├── core/               # Config, cache, patterns
│   │   ├── middleware/         # Rate limiting
│   │   ├── models/             # Shared Pydantic models
│   │   ├── ontology/           # HPO term routers
│   │   ├── phenopackets/       # Core phenopackets domain
│   │   │   ├── routers/        # CRUD, search, aggregations
│   │   │   │   └── aggregations/  # Statistical endpoints
│   │   │   └── validation/     # Schema validators
│   │   ├── publications/       # Publication endpoints/services
│   │   ├── reference/          # Reference genome endpoints
│   │   ├── repositories/       # Data access patterns
│   │   ├── schemas/            # Additional Pydantic schemas
│   │   ├── search/             # Global search functionality
│   │   ├── seo/                # Sitemap generation
│   │   ├── services/           # Business logic services
│   │   ├── utils/              # Shared utilities
│   │   └── variants/           # Variant annotation service
│   ├── alembic/                # Database migrations
│   │   └── versions/           # Migration files
│   ├── migration/              # Data import from Google Sheets
│   │   ├── data_sources/       # Google Sheets client
│   │   ├── database/           # Storage utilities
│   │   ├── phenopackets/       # Phenopacket builders/mappers
│   │   └── vrs/                # VRS variant builders
│   ├── scripts/                # CLI utility scripts
│   └── tests/                  # Pytest test files
├── frontend/                   # Vue.js 3 application
│   ├── src/
│   │   ├── api/                # Axios API client
│   │   ├── assets/             # Static assets, mixins
│   │   ├── components/         # Reusable Vue components
│   │   │   ├── analyses/       # Visualization charts
│   │   │   ├── common/         # Shared UI components
│   │   │   ├── gene/           # Gene visualization
│   │   │   ├── phenopacket/    # Phenopacket detail cards
│   │   │   └── timeline/       # Timeline visualization
│   │   ├── composables/        # Vue 3 composition utilities
│   │   ├── config/             # App configuration
│   │   ├── plugins/            # Vuetify plugin setup
│   │   ├── router/             # Vue Router config
│   │   ├── schemas/            # Form validation schemas
│   │   ├── services/           # Frontend services (logging)
│   │   ├── stores/             # Pinia state stores
│   │   ├── utils/              # Helper functions
│   │   └── views/              # Page-level components
│   ├── tests/                  # Test files
│   │   ├── unit/               # Unit tests
│   │   └── e2e/                # End-to-end tests
│   ├── public/                 # Static public assets
│   └── nginx/                  # Nginx config for Docker
├── docs/                       # Project documentation
│   ├── api/                    # API documentation
│   ├── adr/                    # Architecture Decision Records
│   ├── database/               # Database schema docs
│   ├── frontend/               # Frontend-specific docs
│   └── issues/                 # Issue implementation plans
├── docker/                     # Docker configuration
├── .planning/                  # GSD planning documents
│   └── codebase/               # Codebase analysis docs
├── plan/                       # Project planning files
├── .github/                    # GitHub Actions workflows
├── Makefile                    # Root-level build commands
├── CLAUDE.md                   # Claude Code instructions
└── docker-compose.*.yml        # Docker orchestration
```

## Directory Purposes

**`backend/app/`:**
- Purpose: Core backend application code
- Contains: FastAPI application, routers, models, services
- Key files: `main.py` (entry point), `database.py` (session management), `schemas.py` (shared Pydantic models)

**`backend/app/phenopackets/`:**
- Purpose: Primary domain - phenopacket data management
- Contains: Models, routers, validators, query builders
- Key files: `models.py` (SQLAlchemy + Pydantic), `routers/__init__.py` (router composition)

**`backend/app/phenopackets/routers/`:**
- Purpose: API endpoints organized by functionality
- Contains: CRUD operations, search, aggregations, comparisons
- Key files: `crud.py` (list/get/create/update/delete), `search.py` (full-text search), `aggregations/__init__.py` (stats endpoints)

**`backend/app/core/`:**
- Purpose: Infrastructure and configuration
- Contains: Settings, caching, retry patterns
- Key files: `config.py` (unified settings), `cache.py` (Redis wrapper), `mv_cache.py` (materialized view cache)

**`backend/app/auth/`:**
- Purpose: Authentication and authorization
- Contains: JWT tokens, password hashing, permission decorators
- Key files: `tokens.py` (JWT creation/verification), `dependencies.py` (FastAPI Depends), `permissions.py` (role checks)

**`backend/migration/`:**
- Purpose: Data import from external sources (Google Sheets)
- Contains: ETL pipeline for phenopacket creation
- Key files: `direct_sheets_to_phenopackets.py` (main migration script), `phenopackets/builder_simple.py` (phenopacket builder)

**`backend/alembic/`:**
- Purpose: Database schema migrations
- Contains: Alembic configuration and migration files
- Key files: `env.py` (migration environment), `versions/*.py` (individual migrations)

**`frontend/src/api/`:**
- Purpose: Backend API integration
- Contains: Axios client with interceptors, all API functions
- Key files: `index.js` (API client and all endpoints), `auth.js` (auth-specific calls)

**`frontend/src/components/`:**
- Purpose: Reusable Vue components
- Contains: UI building blocks organized by feature
- Key files: `common/AppDataTable.vue` (data table), `HPOAutocomplete.vue` (term search), `analyses/*.vue` (charts)

**`frontend/src/views/`:**
- Purpose: Page-level routed components
- Contains: Full pages mounted by Vue Router
- Key files: `Phenopackets.vue` (list view), `PagePhenopacket.vue` (detail view), `AggregationsDashboard.vue` (stats)

**`frontend/src/composables/`:**
- Purpose: Reusable stateful logic (Composition API)
- Contains: Hooks for common patterns
- Key files: `useVEPAnnotation.js` (variant annotation), `useTableUrlState.js` (URL state sync), `useHPOAutocomplete.js` (HPO search)

**`frontend/src/stores/`:**
- Purpose: Global state management (Pinia)
- Contains: Reactive stores for shared state
- Key files: `authStore.js` (authentication state), `logStore.js` (log entries), `variantStore.js` (variant data)

**`frontend/src/utils/`:**
- Purpose: Pure utility functions
- Contains: Helpers for data transformation, formatting
- Key files: `pagination.js` (JSON:API helpers), `logSanitizer.js` (PII redaction), `auth.js` (token management)

**`docs/`:**
- Purpose: Project documentation
- Contains: API docs, ADRs, implementation plans
- Key files: `adr/001-json-api-pagination.md`, `database/reference-schema.md`, `COLOR_STYLE_GUIDE.md`

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI application entry point
- `frontend/src/main.js`: Vue application entry point
- `Makefile`: Root-level make targets for development

**Configuration:**
- `backend/app/core/config.py`: Unified settings (Pydantic + YAML)
- `backend/config.yaml`: Behavior configuration (timeouts, limits, URLs)
- `backend/.env`: Secrets (DATABASE_URL, JWT_SECRET)
- `frontend/.env`: Frontend config (VITE_API_URL)
- `frontend/vite.config.js`: Vite build configuration

**Core Logic:**
- `backend/app/phenopackets/models.py`: Phenopacket SQLAlchemy + Pydantic models
- `backend/app/database.py`: Async database session management
- `backend/app/phenopackets/routers/crud.py`: CRUD operations with pagination
- `frontend/src/api/index.js`: All API endpoint functions

**Testing:**
- `backend/tests/`: Pytest test files
- `backend/pytest.ini`: Pytest configuration
- `frontend/tests/unit/`: Vitest unit tests
- `frontend/vitest.config.js`: Vitest configuration

**Database:**
- `backend/alembic/versions/`: Migration files
- `backend/migration/phenopackets_schema.sql`: Raw SQL schema reference

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `phenopacket_validator.py`)
- Vue components: `PascalCase.vue` (e.g., `AppDataTable.vue`)
- JavaScript utilities: `camelCase.js` (e.g., `logSanitizer.js`)
- Tests: `test_<module>.py` (backend), `<Component>.test.js` (frontend)

**Directories:**
- Python packages: `snake_case` (e.g., `phenopackets`, `data_sources`)
- Vue feature folders: `kebab-case` or `camelCase` (e.g., `common`, `analyses`)

**API Endpoints:**
- Path: `/api/v2/<resource>/` (e.g., `/api/v2/phenopackets/`)
- Aggregations: `/api/v2/phenopackets/aggregate/<metric>` (e.g., `/aggregate/sex-distribution`)
- Actions: Verb in URL for non-CRUD (e.g., `/search`, `/annotate`)

**Database:**
- Tables: `snake_case` plural (e.g., `phenopackets`, `publication_metadata`)
- Columns: `snake_case` (e.g., `phenopacket_id`, `created_at`)
- Indexes: `idx_<table>_<column>` (e.g., `idx_phenopackets_cursor_pagination`)
- Materialized views: `mv_<purpose>` (e.g., `mv_feature_aggregation`)

## Where to Add New Code

**New API Endpoint:**
1. For phenopacket-related: Add to appropriate router in `backend/app/phenopackets/routers/`
2. For new domain: Create new module in `backend/app/<domain>/` with `__init__.py`, `router.py`, `models.py`
3. Register router in `backend/app/main.py` with `app.include_router()`
4. Add API function in `frontend/src/api/index.js`

**New Vue Page:**
1. Create component in `frontend/src/views/<PageName>.vue`
2. Add route in `frontend/src/router/index.js` with lazy import
3. Add navigation item in `frontend/src/config/navigationItems.js` if needed

**New Vue Component:**
1. Feature-specific: `frontend/src/components/<feature>/<ComponentName>.vue`
2. Shared/common: `frontend/src/components/common/<ComponentName>.vue`
3. Analysis/chart: `frontend/src/components/analyses/<ChartName>.vue`

**New Utility Function:**
- Backend: `backend/app/utils/<module>.py` or domain-specific utils
- Frontend: `frontend/src/utils/<module>.js`

**New Composable:**
- Location: `frontend/src/composables/use<FeatureName>.js`
- Pattern: Export function returning reactive state and methods

**New Pinia Store:**
- Location: `frontend/src/stores/<domain>Store.js`
- Pattern: `defineStore` with state, getters, actions

**New Database Table:**
1. Create Alembic migration: `cd backend && alembic revision -m "Add <table> table"`
2. Add SQLAlchemy model in appropriate module
3. Run migration: `make db-upgrade`

**New Test:**
- Backend: `backend/tests/test_<module>.py`
- Frontend unit: `frontend/tests/unit/<path>/<Component>.test.js`
- Frontend E2E: `frontend/tests/e2e/<feature>.spec.js`

## Special Directories

**`backend/.venv/`:**
- Purpose: Python virtual environment (uv managed)
- Generated: Yes (by `uv sync`)
- Committed: No (in .gitignore)

**`frontend/node_modules/`:**
- Purpose: npm dependencies
- Generated: Yes (by `npm install`)
- Committed: No (in .gitignore)

**`backend/alembic/versions/`:**
- Purpose: Database migration history
- Generated: Yes (by `alembic revision`)
- Committed: Yes (tracks schema evolution)

**`backend/.ontology_cache/`:**
- Purpose: Cached HPO ontology data
- Generated: Yes (runtime)
- Committed: No (in .gitignore)

**`frontend/dist/`:**
- Purpose: Production build output
- Generated: Yes (by `npm run build`)
- Committed: No (in .gitignore)

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents
- Generated: Yes (by Claude Code)
- Committed: Yes (documentation)

**`docs/adr/`:**
- Purpose: Architecture Decision Records
- Generated: No (manual documentation)
- Committed: Yes (architectural history)

---

*Structure analysis: 2026-01-19*
