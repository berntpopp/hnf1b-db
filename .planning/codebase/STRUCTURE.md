# Codebase Structure

**Analysis Date:** 2026-01-19

## Directory Layout

```
hnf1b-db/
├── backend/                    # FastAPI Python backend
│   ├── app/                    # Application code
│   │   ├── api/                # Admin and auth endpoints
│   │   ├── auth/               # Authentication module
│   │   ├── core/               # Config, cache, settings
│   │   ├── middleware/         # Request middleware
│   │   ├── models/             # Shared SQLAlchemy models
│   │   ├── ontology/           # HPO ontology routers
│   │   ├── phenopackets/       # Core phenopacket domain
│   │   │   ├── routers/        # CRUD, search, aggregations
│   │   │   │   └── aggregations/  # Domain-split agg endpoints
│   │   │   └── validation/     # Phenopacket validators
│   │   ├── publications/       # Publication endpoints
│   │   ├── reference/          # Gene/transcript reference data
│   │   ├── repositories/       # Data access layer
│   │   ├── schemas/            # Shared Pydantic schemas
│   │   ├── search/             # Global search service
│   │   ├── seo/                # SEO metadata endpoints
│   │   ├── services/           # Business logic services
│   │   ├── utils/              # Utilities (audit, pagination)
│   │   └── variants/           # Variant annotation service
│   ├── alembic/                # Database migrations
│   │   └── versions/           # Migration files
│   ├── migration/              # Data import scripts
│   │   ├── data_sources/       # Google Sheets connectors
│   │   ├── phenopackets/       # Phenopacket builders
│   │   └── vrs/                # VRS variant helpers
│   ├── scripts/                # Utility scripts
│   └── tests/                  # Pytest test suite
├── frontend/                   # Vue.js frontend
│   ├── src/
│   │   ├── api/                # Centralized API client
│   │   ├── assets/             # Static assets, JS mixins
│   │   ├── components/         # Vue components
│   │   │   ├── common/         # Shared UI components
│   │   │   ├── phenopacket/    # Phenopacket detail cards
│   │   │   ├── gene/           # Gene visualization
│   │   │   ├── analyses/       # Charts and analysis components
│   │   │   └── timeline/       # Timeline components
│   │   ├── composables/        # Vue composition functions
│   │   ├── config/             # App configuration
│   │   ├── plugins/            # Vuetify plugins
│   │   ├── router/             # Vue Router config
│   │   ├── schemas/            # JSON schemas
│   │   ├── services/           # Frontend services
│   │   ├── stores/             # Pinia stores
│   │   ├── utils/              # Utility functions
│   │   └── views/              # Page components
│   ├── public/                 # Static public assets
│   │   └── config/             # Runtime config
│   ├── tests/                  # Test suites
│   │   ├── unit/               # Unit tests
│   │   └── e2e/                # End-to-end tests
│   └── nginx/                  # Nginx config for production
├── docs/                       # Documentation
│   ├── api/                    # API documentation
│   ├── database/               # DB schema docs
│   ├── deployment/             # Deployment guides
│   ├── frontend/               # Frontend docs
│   └── adr/                    # Architecture Decision Records
├── docker/                     # Docker compose files
├── .github/                    # GitHub Actions CI/CD
│   └── workflows/              # Workflow definitions
└── .planning/                  # GSD planning documents
    └── codebase/               # Codebase analysis docs
```

## Directory Purposes

**`backend/app/`:**
- Purpose: Main FastAPI application code
- Contains: Routers, models, services, utilities
- Key files: `main.py`, `database.py`, `hpo_proxy.py`

**`backend/app/phenopackets/`:**
- Purpose: Core phenopacket domain logic
- Contains: Models, validators, routers (CRUD, search, aggregations)
- Key files: `models.py`, `clinical_endpoints.py`, `query_builders.py`

**`backend/app/phenopackets/routers/`:**
- Purpose: API endpoints split by concern
- Contains: CRUD, search, comparisons, aggregations sub-routers
- Key files: `crud.py`, `search.py`, `comparisons.py`

**`backend/app/phenopackets/routers/aggregations/`:**
- Purpose: Statistical aggregation endpoints by domain
- Contains: Features, diseases, demographics, variants, survival, publications
- Key files: `survival.py`, `features.py`, `all_variants.py`, `sql_fragments.py`

**`backend/app/core/`:**
- Purpose: Application configuration and caching
- Contains: Settings, cache management, materialized view cache
- Key files: `config.py`, `cache.py`, `mv_cache.py`

**`backend/app/auth/`:**
- Purpose: Authentication and authorization
- Contains: JWT tokens, password hashing, permission decorators
- Key files: `dependencies.py`, `tokens.py`, `permissions.py`

**`backend/app/search/`:**
- Purpose: Global search across entity types
- Contains: Search service, repositories, schemas
- Key files: `services.py`, `repositories.py`, `routers.py`

**`backend/app/reference/`:**
- Purpose: Gene and transcript reference data
- Contains: HNF1B gene data, protein domains, GRCh38 reference
- Key files: `service.py`, `router.py`, `models.py`

**`backend/app/variants/`:**
- Purpose: Variant annotation via Ensembl VEP
- Contains: VEP service, CNV handling
- Key files: `service.py`

**`backend/alembic/versions/`:**
- Purpose: Database migration scripts
- Contains: Schema changes, index additions, materialized views
- Key files: `001_initial_phenopackets_v2_schema.py`, migration files by feature

**`backend/migration/`:**
- Purpose: Data import from Google Sheets
- Contains: Sheet readers, phenopacket builders, VRS helpers
- Key files: `direct_sheets_to_phenopackets.py`

**`frontend/src/api/`:**
- Purpose: Centralized axios API client
- Contains: Request/response interceptors, all API functions
- Key files: `index.js`, `auth.js`

**`frontend/src/views/`:**
- Purpose: Page-level routed components
- Contains: All top-level pages
- Key files: `Phenopackets.vue`, `PagePhenopacket.vue`, `Variants.vue`, `Home.vue`, `AggregationsDashboard.vue`

**`frontend/src/components/`:**
- Purpose: Reusable UI components organized by domain
- Contains: Domain-specific and common components
- Key files: Organized in subdirectories

**`frontend/src/components/common/`:**
- Purpose: Shared data display components
- Contains: Tables, pagination, search filters
- Key files: `AppDataTable.vue`, `AppPagination.vue`, `AppSearchFilters.vue`

**`frontend/src/components/phenopacket/`:**
- Purpose: Phenopacket detail view cards
- Contains: Cards for each phenopacket section
- Key files: `SubjectCard.vue`, `PhenotypicFeaturesCard.vue`, `InterpretationsCard.vue`, `DiseasesCard.vue`

**`frontend/src/components/gene/`:**
- Purpose: Gene and protein visualizations
- Contains: Interactive D3/NGL visualizations
- Key files: `HNF1BGeneVisualization.vue`, `HNF1BProteinVisualization.vue`, `ProteinStructure3D.vue`

**`frontend/src/components/analyses/`:**
- Purpose: Statistical analysis and chart components
- Contains: D3-based charts, survival analysis
- Key files: `KaplanMeierChart.vue`, `DonutChart.vue`, `StackedBarChart.vue`, `BoxPlotChart.vue`

**`frontend/src/composables/`:**
- Purpose: Reusable Vue composition functions
- Contains: SEO, URL state, HPO autocomplete, visualization hooks
- Key files: `useSeoMeta.js`, `useTableUrlState.js`, `useHPOAutocomplete.js`

**`frontend/src/stores/`:**
- Purpose: Pinia global state stores
- Contains: Auth, logging, variant state
- Key files: `authStore.js`, `logStore.js`, `variantStore.js`

**`frontend/src/utils/`:**
- Purpose: Utility functions
- Contains: Pagination, colors, age parsing, variant formatting
- Key files: `pagination.js`, `colors.js`, `ageParser.js`, `variants.js`

**`frontend/src/services/`:**
- Purpose: Frontend service layer
- Contains: Logging, health checks
- Key files: `logService.js`, `healthService.js`

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app creation and router registration
- `frontend/src/main.js`: Vue app bootstrap
- `frontend/index.html`: HTML entry point

**Configuration:**
- `backend/.env`: Backend secrets (DATABASE_URL, JWT_SECRET)
- `backend/config.yaml`: Backend behavior config (timeouts, limits)
- `frontend/.env`: Frontend config (VITE_API_URL)
- `backend/app/core/config.py`: Unified settings with Pydantic

**Core Logic:**
- `backend/app/phenopackets/models.py`: Phenopacket SQLAlchemy model
- `backend/app/phenopackets/routers/crud.py`: Main CRUD operations
- `backend/app/database.py`: Database connection and session management
- `frontend/src/api/index.js`: All API call functions

**Testing:**
- `backend/tests/`: Pytest test files
- `backend/tests/conftest.py`: Test fixtures
- `frontend/tests/unit/`: Vitest unit tests
- `frontend/tests/e2e/`: E2E test files

**Build/Deploy:**
- `Makefile`: Root make commands
- `backend/Makefile`: Backend-specific commands
- `frontend/Makefile`: Frontend-specific commands
- `docker/docker-compose.yml`: Docker orchestration

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `clinical_endpoints.py`, `query_builders.py`)
- Vue components: `PascalCase.vue` (e.g., `AppDataTable.vue`, `SubjectCard.vue`)
- JavaScript utilities: `camelCase.js` (e.g., `pagination.js`, `ageParser.js`)
- Tests: `test_*.py` (backend), `*.test.js` or `*.spec.js` (frontend)

**Directories:**
- Python: `snake_case` (e.g., `phenopackets`, `data_sources`)
- Frontend: `camelCase` (e.g., `composables`, `stores`)
- Domain groupings: singular noun (e.g., `phenopacket/`, `gene/`, `timeline/`)

**Vue Components:**
- Page views: Single word or description (e.g., `Home.vue`, `PagePhenopacket.vue`)
- Reusable components: `App` prefix for app-wide (e.g., `AppBar.vue`, `AppDataTable.vue`)
- Domain components: Domain + Purpose (e.g., `SubjectCard.vue`, `KaplanMeierChart.vue`)

**Python Modules:**
- Routers: `*_endpoints.py` or just function name (e.g., `clinical_endpoints.py`, `crud.py`)
- Services: `*_service.py` or `service.py` in domain folder
- Models: `models.py` in domain folder

## Where to Add New Code

**New API Endpoint:**
- Backend route: Add to existing router in `backend/app/phenopackets/routers/` or create new router
- Register in `backend/app/main.py` if new router file
- Add frontend function in `frontend/src/api/index.js`

**New Page/View:**
- Create `frontend/src/views/NewPage.vue`
- Add route in `frontend/src/router/index.js`
- Use lazy loading: `component: () => import('../views/NewPage.vue')`

**New Reusable Component:**
- Common UI: `frontend/src/components/common/`
- Domain-specific: `frontend/src/components/{domain}/`
- Analysis/chart: `frontend/src/components/analyses/`

**New Composable:**
- Location: `frontend/src/composables/use{Feature}.js`
- Pattern: Export function returning reactive state and methods

**New Database Table:**
- Create Alembic migration: `cd backend && uv run alembic revision -m "description"`
- Add SQLAlchemy model in appropriate `models.py`
- Run migration: `make db-upgrade`

**New Aggregation Endpoint:**
- Add file in `backend/app/phenopackets/routers/aggregations/`
- Register in `backend/app/phenopackets/routers/aggregations/__init__.py`

**New Utility Function:**
- Backend: `backend/app/utils/` or domain-specific utils
- Frontend: `frontend/src/utils/`

**New Test:**
- Backend: `backend/tests/test_{feature}.py`
- Frontend unit: `frontend/tests/unit/{domain}/`
- Frontend component: `frontend/tests/unit/components/`

## Special Directories

**`backend/.venv/`:**
- Purpose: Python virtual environment (uv managed)
- Generated: Yes
- Committed: No

**`frontend/node_modules/`:**
- Purpose: Node.js dependencies
- Generated: Yes
- Committed: No

**`backend/alembic/versions/`:**
- Purpose: Database migration scripts
- Generated: Partially (templates generated, then edited)
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: By GSD commands
- Committed: Optional (project preference)

**`backend/.ontology_cache/`:**
- Purpose: Cached HPO ontology data
- Generated: Yes (on first HPO lookup)
- Committed: No

**`backend/.mypy_cache/`, `backend/.pytest_cache/`, `backend/.ruff_cache/`:**
- Purpose: Tool caches
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-01-19*
