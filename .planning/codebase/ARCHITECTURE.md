# Architecture

**Analysis Date:** 2026-01-19

## Pattern Overview

**Overall:** Layered Monorepo Architecture

The HNF1B Database is a full-stack monorepo implementing a layered architecture with clear separation between:
- **Frontend (Vue.js 3):** Client-side SPA with Material Design UI
- **Backend (FastAPI):** GA4GH Phenopackets v2 compliant REST API
- **Database (PostgreSQL):** Document-oriented storage using JSONB

**Key Characteristics:**
- Monorepo with independent frontend/backend packages
- Async-first backend design (asyncio, asyncpg)
- Document-oriented data model (GA4GH Phenopackets in JSONB)
- JSON:API v1.1 compliant pagination
- VRS 2.0 compliant variant identifiers
- Centralized configuration (YAML for behavior, .env for secrets)

## Layers

**Presentation Layer (Frontend):**
- Purpose: User interface and client-side state management
- Location: `frontend/src/`
- Contains: Vue components, views, routing, Pinia stores
- Depends on: Backend API via Axios client
- Used by: End users via browser

**API Layer (Backend Routers):**
- Purpose: HTTP request handling, validation, response formatting
- Location: `backend/app/api/`, `backend/app/phenopackets/routers/`
- Contains: FastAPI routers, endpoint definitions, Pydantic schemas
- Depends on: Service layer, database layer, auth dependencies
- Used by: Frontend API client, external consumers

**Service Layer (Backend Services):**
- Purpose: Business logic, external API integration, data transformation
- Location: `backend/app/services/`, `backend/app/variants/service.py`, `backend/app/publications/service.py`
- Contains: Ontology services, VEP annotation, PubMed fetching
- Depends on: External APIs (Ensembl, PubMed, OLS), cache layer
- Used by: API routers

**Data Access Layer (Backend Repositories/Models):**
- Purpose: Database operations, query building, ORM models
- Location: `backend/app/phenopackets/models.py`, `backend/app/database.py`, `backend/app/repositories/`
- Contains: SQLAlchemy models, async session management, query builders
- Depends on: PostgreSQL database
- Used by: Service layer, API routers

**Core/Infrastructure Layer:**
- Purpose: Cross-cutting concerns (config, auth, caching, middleware)
- Location: `backend/app/core/`, `backend/app/auth/`, `backend/app/middleware/`
- Contains: Settings, JWT auth, rate limiting, Redis cache
- Depends on: External services (Redis)
- Used by: All other layers

## Data Flow

**Read Flow (GET /api/v2/phenopackets):**

1. Frontend calls `getPhenopackets()` from `frontend/src/api/index.js`
2. Axios client adds JWT token via request interceptor
3. FastAPI router in `backend/app/phenopackets/routers/crud.py` receives request
4. Query builder constructs SQLAlchemy query with filters/sort/pagination
5. Async database session executes query against PostgreSQL
6. Response formatted as JSON:API v1.1 with pagination links
7. Frontend extracts `data`, `meta.page`, `links` from response

**Write Flow (POST /api/v2/phenopackets):**

1. Frontend calls `createPhenopacket()` with phenopacket data
2. `require_curator` dependency validates JWT and role
3. `PhenopacketSanitizer` cleans input data
4. `PhenopacketValidator` validates against GA4GH schema
5. SQLAlchemy model created and committed to database
6. Audit entry created in `phenopacket_audit` table
7. Response returns created phenopacket with metadata

**Search Flow (GET /api/v2/search/global):**

1. Frontend calls `searchGlobal()` with query string
2. Backend search router queries materialized views if available
3. Full-text search uses PostgreSQL `tsvector` column
4. Results aggregated across phenopackets, variants, publications
5. Ranked results returned with type indicators

**State Management:**
- Frontend uses Pinia stores for auth (`authStore.js`), logs (`logStore.js`), variants (`variantStore.js`)
- Backend uses Redis for caching (with in-memory fallback)
- PostgreSQL materialized views cache expensive aggregations

## Key Abstractions

**Phenopacket (Core Domain Entity):**
- Purpose: Represents clinical/genetic patient data per GA4GH standard
- Examples: `backend/app/phenopackets/models.py::Phenopacket`, `backend/app/phenopackets/models.py::PhenopacketSchema`
- Pattern: Document model stored as JSONB with denormalized columns for fast queries

**API Client (Frontend-Backend Communication):**
- Purpose: Centralized HTTP client with auth interceptors
- Examples: `frontend/src/api/index.js::apiClient`
- Pattern: Axios instance with request/response interceptors for JWT handling

**Settings (Configuration):**
- Purpose: Unified configuration combining .env secrets and YAML behavior config
- Examples: `backend/app/core/config.py::Settings`, `backend/config.yaml`
- Pattern: Pydantic settings with lazy-loaded YAML config

**Router (API Endpoint Organization):**
- Purpose: Group related endpoints with shared prefix/tags
- Examples: `backend/app/phenopackets/routers/__init__.py::router`
- Pattern: FastAPI APIRouter composition with include_router()

**Composable (Vue Reusable Logic):**
- Purpose: Share stateful logic between Vue components
- Examples: `frontend/src/composables/useVEPAnnotation.js`, `frontend/src/composables/useTableUrlState.js`
- Pattern: Vue 3 Composition API with reactive state

## Entry Points

**Backend Application:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` or `make backend`
- Responsibilities: FastAPI app initialization, lifespan management, router registration, CORS middleware

**Frontend Application:**
- Location: `frontend/src/main.js`
- Triggers: Vite dev server or production build
- Responsibilities: Vue app creation, Pinia/Vuetify plugin registration, router initialization

**Database Migrations:**
- Location: `backend/alembic/env.py`
- Triggers: `alembic upgrade head` or `make db-upgrade`
- Responsibilities: Schema migrations, table creation, index management

**Data Migration (Import):**
- Location: `backend/migration/direct_sheets_to_phenopackets.py`
- Triggers: `make phenopackets-migrate`
- Responsibilities: Google Sheets to GA4GH Phenopackets conversion, database insertion

**CLI Scripts:**
- Location: `backend/scripts/`
- Triggers: Various make targets
- Responsibilities: Admin user creation, publication sync, variant annotation

## Error Handling

**Strategy:** Fail-fast with structured error responses

**Backend Patterns:**
- FastAPI HTTPException for API errors with status codes
- Pydantic validation errors auto-converted to 422 responses
- Database errors caught and wrapped with user-friendly messages
- Optimistic locking via revision field returns 409 on conflict
- Soft delete pattern preserves data for audit trail

**Frontend Patterns:**
- Axios interceptors handle 401 with automatic token refresh
- Try/catch blocks in API calls with logService logging
- User-friendly error messages via Vuetify snackbars
- Graceful degradation when optional data unavailable

**Example (Backend Optimistic Locking):**
```python
# backend/app/phenopackets/routers/crud.py
if phenopacket_data.revision is not None and existing.revision != phenopacket_data.revision:
    raise HTTPException(
        status_code=409,
        detail={
            "error": "Conflict detected",
            "current_revision": existing.revision,
            "expected_revision": phenopacket_data.revision,
        },
    )
```

**Example (Frontend Token Refresh):**
```javascript
// frontend/src/api/index.js
if (error.response?.status === 401 && !originalRequest._retry) {
    const newAccessToken = await authStore.refreshAccessToken();
    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
    return apiClient(originalRequest);
}
```

## Cross-Cutting Concerns

**Logging:**
- Backend: Python `logging` module with structured output
- Frontend: Custom `logService` with PII/PHI redaction (`frontend/src/services/logService.js`)
- Pattern: Never use `console.log()` in frontend - always use `window.logService`

**Validation:**
- Backend: Pydantic models for request/response validation
- Backend: Custom `PhenopacketValidator` for GA4GH schema compliance
- Frontend: Vee-validate with Yup schemas (`frontend/src/schemas/phenopacketSchema.js`)

**Authentication:**
- JWT-based with access/refresh token pattern
- Backend: `backend/app/auth/` module with tokens, dependencies, permissions
- Frontend: `authStore` manages tokens in localStorage
- Protected routes use `requiresAuth` meta in Vue Router

**Caching:**
- Redis cache for expensive operations (with in-memory fallback)
- PostgreSQL materialized views for aggregation queries
- VEP annotation cache (configurable TTL)
- Publication metadata cache (90-day TTL)

**Pagination:**
- JSON:API v1.1 standard with dual modes (offset and cursor)
- Offset: `page[number]`, `page[size]` for page numbers display
- Cursor: `page[after]`, `page[before]` for stable browsing
- Database index: `(created_at DESC, id DESC)` for efficient cursor queries

**Rate Limiting:**
- External API rate limits (VEP: 15/s, PubMed: 3/s or 10/s with API key)
- Configurable via `backend/config.yaml`

---

*Architecture analysis: 2026-01-19*
