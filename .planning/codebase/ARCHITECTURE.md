# Architecture

**Analysis Date:** 2026-01-19

## Pattern Overview

**Overall:** Monorepo with separate full-stack layers (FastAPI backend + Vue.js SPA frontend)

**Key Characteristics:**
- GA4GH Phenopackets v2 compliant REST API with JSON:API pagination
- PostgreSQL JSONB document storage for phenopacket data
- Async/await throughout backend with SQLAlchemy 2.0
- Vue 3 Composition API with Vuetify Material Design
- Modular router architecture in backend (domain-split routers)
- Centralized API client with auth interceptors in frontend

## Layers

**API Layer (Backend):**
- Purpose: HTTP request/response handling, validation, routing
- Location: `backend/app/api/`, `backend/app/phenopackets/routers/`
- Contains: FastAPI routers, endpoint definitions, request validation
- Depends on: Services, Database, Models
- Used by: Frontend API client

**Service Layer (Backend):**
- Purpose: Business logic, external API integration, data transformation
- Location: `backend/app/services/`, `backend/app/search/services.py`, `backend/app/reference/service.py`, `backend/app/variants/service.py`
- Contains: OntologyService, GlobalSearchService, ReferenceService, VariantService
- Depends on: Database, External APIs (VEP, OLS, PubMed)
- Used by: API routers

**Repository Layer (Backend):**
- Purpose: Data access abstraction for database operations
- Location: `backend/app/repositories/`
- Contains: `user_repository.py`, search repositories
- Depends on: Database, SQLAlchemy models
- Used by: Services, API routers

**Models Layer (Backend):**
- Purpose: SQLAlchemy ORM models and Pydantic schemas
- Location: `backend/app/models/`, `backend/app/phenopackets/models.py`
- Contains: `Phenopacket`, `PhenopacketAudit`, `User`, JSON:API response models
- Depends on: SQLAlchemy Base
- Used by: All backend layers

**Database Layer (Backend):**
- Purpose: Connection management, session factory, migrations
- Location: `backend/app/database.py`, `backend/alembic/`
- Contains: Engine config, session maker, `get_db` dependency
- Depends on: PostgreSQL, asyncpg driver
- Used by: All backend layers via dependency injection

**Views Layer (Frontend):**
- Purpose: Page-level routed components
- Location: `frontend/src/views/`
- Contains: `Home.vue`, `Phenopackets.vue`, `PagePhenopacket.vue`, `Variants.vue`, `Publications.vue`, etc.
- Depends on: Components, API, Composables, Stores
- Used by: Vue Router

**Components Layer (Frontend):**
- Purpose: Reusable UI components
- Location: `frontend/src/components/`
- Contains: Domain components (`phenopacket/`, `gene/`, `analyses/`), common components (`common/`)
- Depends on: Vuetify, Composables, Utils
- Used by: Views, other components

**API Client Layer (Frontend):**
- Purpose: Centralized HTTP client with auth handling
- Location: `frontend/src/api/index.js`
- Contains: Axios instance, request/response interceptors, API functions
- Depends on: Axios, Auth store
- Used by: Views, Composables

**Stores Layer (Frontend):**
- Purpose: Global state management
- Location: `frontend/src/stores/`
- Contains: `authStore.js`, `logStore.js`, `variantStore.js`
- Depends on: Pinia
- Used by: Views, Components, API client

**Composables Layer (Frontend):**
- Purpose: Reusable composition functions (Vue hooks)
- Location: `frontend/src/composables/`
- Contains: `useSeoMeta.js`, `useTableUrlState.js`, `useHPOAutocomplete.js`, `useNGLStructure.js`
- Depends on: Vue reactivity, API
- Used by: Views, Components

## Data Flow

**Phenopacket List Flow:**

1. User navigates to `/phenopackets` -> Vue Router loads `Phenopackets.vue`
2. View calls `getPhenopackets()` from `frontend/src/api/index.js`
3. API client sends GET to `/api/v2/phenopackets/` with JSON:API pagination params
4. FastAPI routes to `backend/app/phenopackets/routers/crud.py::list_phenopackets()`
5. Router builds SQLAlchemy query with filters, executes via async session
6. Query results transformed to JSON:API response format
7. Response returned to frontend, data rendered in `AppDataTable.vue`

**Phenopacket Detail Flow:**

1. User clicks phenopacket row -> Router navigates to `/phenopackets/:id`
2. `PagePhenopacket.vue` calls `getPhenopacket(id)`
3. Backend returns full phenopacket JSONB document
4. View renders domain cards: `SubjectCard`, `PhenotypicFeaturesCard`, `InterpretationsCard`, etc.

**Global Search Flow:**

1. User types in global search -> `AppBar.vue` debounces input
2. Autocomplete calls `/api/v2/search/autocomplete?q=...`
3. `backend/app/search/routers.py` delegates to `GlobalSearchService`
4. Service queries across phenopackets, variants, publications using trigram matching
5. Results returned with type facets

**State Management:**
- Auth state managed in `authStore.js` with JWT tokens in localStorage
- API client intercepts 401 responses for automatic token refresh
- Log service (`logStore.js`) captures sanitized logs for debugging

## Key Abstractions

**Phenopacket:**
- Purpose: Core domain entity representing a patient case
- Examples: `backend/app/phenopackets/models.py::Phenopacket`, JSONB `phenopacket` column
- Pattern: Document storage in PostgreSQL JSONB with denormalized index columns

**JSON:API Response:**
- Purpose: Standardized pagination response format
- Examples: `backend/app/models/json_api.py::JsonApiResponse`
- Pattern: `{ data: [], meta: { page: {...} }, links: {...} }`

**Aggregation Router:**
- Purpose: Statistical queries split by domain
- Examples: `backend/app/phenopackets/routers/aggregations/survival.py`, `features.py`, `demographics.py`
- Pattern: Modular sub-routers combined via `include_router()`

**Composable:**
- Purpose: Reusable reactive logic in Vue components
- Examples: `frontend/src/composables/useSeoMeta.js`, `useTableUrlState.js`
- Pattern: Functions returning reactive state and methods

## Entry Points

**Backend Main:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` or `make backend`
- Responsibilities: FastAPI app creation, CORS config, router registration, lifespan management (cache init)

**Frontend Main:**
- Location: `frontend/src/main.js`
- Triggers: Vite dev server or production bundle
- Responsibilities: Vue app creation, Pinia/Vuetify/Router setup, auth initialization

**Migration Entry:**
- Location: `backend/migration/direct_sheets_to_phenopackets.py`
- Triggers: `make phenopackets-migrate`
- Responsibilities: Import phenopackets from Google Sheets to database

**Alembic Migrations:**
- Location: `backend/alembic/versions/`
- Triggers: `make db-upgrade`
- Responsibilities: Database schema evolution

## Error Handling

**Strategy:** Layer-appropriate error handling with HTTP status codes

**Patterns:**
- FastAPI HTTPException for API errors with detail messages
- SQLAlchemy rollback on transaction failures in `get_db` dependency
- Axios interceptor catches 401, triggers token refresh or redirect
- Frontend uses `window.logService.error()` for sanitized error logging
- Pydantic validators raise ValueError for config validation (e.g., missing JWT_SECRET)

## Cross-Cutting Concerns

**Logging:**
- Backend: Python `logging` module configured per-module
- Frontend: `window.logService` with automatic PII sanitization via `logSanitizer.js`

**Validation:**
- Backend: Pydantic models for request/response validation
- Backend: `PhenopacketValidator` and `PhenopacketSanitizer` for domain validation
- Frontend: Vuetify form validation rules

**Authentication:**
- JWT tokens with access/refresh pattern
- Backend: `backend/app/auth/` module (dependencies, tokens, permissions)
- Frontend: `authStore.js` manages tokens, API client adds Bearer header
- Protected routes use `require_curator` dependency or route meta guards

**Caching:**
- Redis for backend cache (with in-memory fallback)
- Materialized views for aggregation queries (`mv_feature_aggregation`, etc.)
- VEP API responses cached locally

**Configuration:**
- Backend: `.env` for secrets, `config.yaml` for behavior settings
- Frontend: `.env` for build-time config (VITE_API_URL)
- Centralized in `backend/app/core/config.py` with Pydantic Settings

---

*Architecture analysis: 2026-01-19*
