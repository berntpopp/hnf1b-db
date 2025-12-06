# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B Database is a full-stack monorepo for clinical and genetic data management. Backend is a GA4GH Phenopackets v2 compliant FastAPI REST API, frontend is a Vue.js 3 application with Material Design (Vuetify 3).

**Monorepo Structure:**
```
hnf1b-db/
├── backend/              # FastAPI REST API (Python 3.10+)
├── frontend/             # Vue.js 3 application
├── docs/                 # Documentation
├── Makefile              # Unified root commands
└── docker-compose.*.yml  # Docker orchestration
```

## Quick Start

```bash
# From project root
make dev           # Install all dependencies (backend + frontend)
make hybrid-up     # Start PostgreSQL + Redis in Docker

# Terminal 1: Backend (http://localhost:8000)
make backend

# Terminal 2: Frontend (http://localhost:5173)
make frontend
```

## Essential Commands

### Development
```bash
make help          # Show all available commands
make status        # Show system status
make backend       # Start backend dev server
make frontend      # Start frontend dev server
make hybrid-up     # Start services (PostgreSQL + Redis)
make hybrid-down   # Stop services
```

### Code Quality (REQUIRED before commits)
```bash
# Backend
cd backend
make check         # Run all checks (lint + typecheck + test)
make test          # Run pytest
make lint          # Run ruff linting
make typecheck     # Run mypy
make format        # Format with ruff

# Frontend
cd frontend
make check         # Run all checks (test + lint + format)
make test          # Run vitest
make lint          # Lint with ESLint
make format        # Format with Prettier
```

### Database
```bash
make db-init       # Initialize database (migrations + admin user)
make db-upgrade    # Apply migrations
make db-reset      # Reset database (drop + recreate + migrations)
make db-create-admin  # Create/update admin user
make phenopackets-migrate  # Import all data (864 phenopackets)
make phenopackets-migrate-test  # Import test data (20 phenopackets)
```

### Run Single Test
```bash
# Backend
cd backend
uv run pytest tests/test_specific.py -v
uv run pytest tests/test_specific.py::TestClass::test_method -v

# Frontend
cd frontend
npm test -- tests/specific.test.js
```

## Tech Stack

### Backend (Python 3.10+)
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL with SQLAlchemy + asyncpg
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Auth**: JWT tokens with PyJWT
- **Standards**: GA4GH Phenopackets v2, VRS 2.0
- **Package Manager**: uv (fast dependency resolution)
- **Linting**: ruff (replaces black, isort, flake8)
- **Type Checking**: mypy
- **Testing**: pytest with pytest-asyncio

**Key Dependencies:**
- `fastapi>=0.116.1` - Web framework
- `sqlalchemy[asyncio]>=2.0.25` - ORM
- `asyncpg>=0.29.0` - PostgreSQL driver
- `pydantic>=2.11.7` - Data validation
- `ga4gh.vrs>=2.0.0` - Variant representation
- `phenopackets>=2.0.0` - GA4GH standard

### Frontend
- **Framework**: Vue 3 with Composition API
- **UI Library**: Vuetify 3 (Material Design)
- **Build Tool**: Vite 7
- **Router**: Vue Router 4
- **HTTP Client**: Axios
- **State**: Pinia (optional)
- **Visualization**: D3.js
- **Testing**: Vitest + @vue/test-utils
- **Linting**: ESLint
- **Formatting**: Prettier

## Architecture Essentials

### Backend Architecture

**API Structure (GA4GH Phenopackets v2):**
- `/api/v2/phenopackets/` - CRUD operations with JSON:API v1.1 pagination
- `/api/v2/phenopackets/search` - Full-text search with HPO autocomplete
- `/api/v2/phenopackets/aggregate/*` - Statistics and aggregations
- `/api/v2/clinical/*` - Clinical feature queries
- `/api/v2/variants/*` - Variant validation and VEP annotation
- `/api/v2/auth/*` - JWT authentication
- `/api/v2/ontology/hpo/*` - HPO term autocomplete

**Database Schema:**
- PostgreSQL with JSONB storage for phenopackets
- Generated columns: `subject_id`, `subject_sex` for fast queries
- GIN indexes for JSONB full-text search
- Composite B-tree index for cursor pagination: `(created_at DESC, id DESC)`

**Key Patterns:**
1. **JSONB Storage**: Document-oriented with PostgreSQL JSONB
2. **Async Everything**: All database operations use async/await
3. **Pydantic Models**: Data validation and serialization
4. **Dependency Injection**: FastAPI's DI system for database sessions
5. **VRS 2.0 Compliance**: Deterministic variant identifiers with proper digests

### Frontend Architecture

**Project Structure:**
- `frontend/src/api/` - API service layer (centralized axios client)
- `frontend/src/components/` - Reusable components
- `frontend/src/views/` - Page-level routed components
- `frontend/src/router/` - Route definitions (lazy-loaded)
- `frontend/src/utils/` - Utilities (auth, pagination, logging)

**Key Features:**
- HPO term autocomplete with fuzzy matching
- Global phenopacket search with faceted filtering
- JSON:API v1.1 compliant pagination (offset + cursor modes)
- Privacy-first logging with automatic PII/PHI redaction
- Material Design responsive UI

**Logging Requirements:**
- ❌ NEVER use `console.log()` in frontend code
- ✅ ALWAYS use `window.logService.debug/info/warn/error()`
- Automatic redaction of sensitive data (HPO terms, emails, variants, tokens)

**Pagination/Sorting Requirements:**
- ❌ NEVER use client-side pagination or sorting
- ✅ ALWAYS use server-side pagination with cursor-based JSON:API
- ✅ ALWAYS send sort parameters to the backend API
- All data tables must use `server-side="true"` with AppDataTable
- Use `buildSortParameter()` from `@/utils/pagination` to convert Vuetify sortBy to JSON:API sort

## Development Workflow

### Environment Setup

**Backend (`backend/.env`):**
```bash
cp backend/.env.example backend/.env

# REQUIRED variables:
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
JWT_SECRET=$(openssl rand -hex 32)  # Generate secure secret

# Application will EXIT on startup if JWT_SECRET is empty
```

**Frontend (`frontend/.env`):**
```bash
cp frontend/.env.example frontend/.env

# Optional (has fallback):
VITE_API_URL=http://localhost:8000/api/v2
```

### Hybrid Mode (Recommended)

Best for development with hot reload:
```bash
make hybrid-up     # Services in Docker (PostgreSQL + Redis)
make backend       # Backend runs locally (hot reload)
make frontend      # Frontend runs locally (hot reload)
```

### Full Docker Mode

Everything containerized:
```bash
make dev-up        # Start full stack
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

## Testing & Code Quality

### Critical Rules

**⚠️ ABSOLUTE REQUIREMENTS:**
1. **NEVER skip failing tests** - Always fix them properly
2. **NEVER ignore linting errors** - Fix or document exceptions
3. **NEVER ignore type checking errors** - Fix code or add documented type ignores
4. **ALWAYS run `make check` before committing**
5. **Use modern best practices** - e.g., pytest `caplog` for logging tests, not mocking
6. **Quality gates are mandatory** - All checks must pass before merge

### Pre-Commit Checklist

```bash
# Backend
cd backend
make check         # ✅ Lint + typecheck + test must pass

# Frontend
cd frontend
make check         # ✅ Test + lint + format must pass

# Commit
git add .
git commit -m "feat(scope): description"  # Conventional commits
```

### Test-Before-Refactor Protocol

```bash
# 1. Verify tests pass BEFORE refactoring
make test

# 2. Make changes
# ... edit code ...

# 3. Run tests IMMEDIATELY after
make test

# 4. Update tests if API changed
# ... fix tests ...

# 5. Only commit when tests pass
git commit
```

### Testing Best Practices

**Rule 1: Tests use PUBLIC APIs only**
- ❌ `migration._build_subject(row)` - private method may not exist
- ✅ `builder.build_phenopacket(id, rows)` - public API guaranteed

**Rule 2: Deterministic code only**
- ❌ `abs(hash(data))` - randomized per Python instance
- ✅ `hashlib.sha256(data.encode()).digest()` - deterministic

**Rule 3: Fix broken tests immediately**
- Don't commit failing tests
- Update tests when refactoring APIs
- Remove tests for deleted functionality

### Code Quality Principles

**DRY (Don't Repeat Yourself):**
- Extract reusable code into utilities when copying >10 lines
- Check for similar patterns before adding new code

**YAGNI (You Aren't Gonna Need It):**
- Don't write code for future "what if" scenarios
- Remove unused code, imports, modules immediately
- Only implement current requirements

**Single Responsibility:**
- Keep modules under 500 lines
- One class/function = one responsibility

## API Standards

### JSON:API v1.1 Pagination

The `/api/v2/phenopackets/` endpoint supports dual-mode pagination:

**Offset Pagination (Page Numbers):**
```bash
GET /api/v2/phenopackets/?page[number]=1&page[size]=20&sort=-created_at
```

**Cursor Pagination (Stable Results):**
```bash
# First page
GET /api/v2/phenopackets/?page[size]=20

# Next page using cursor from response
GET /api/v2/phenopackets/?page[after]=CURSOR&page[size]=20
```

**Query Parameters:**
- `page[number]` - Page number (1-indexed)
- `page[size]` - Items per page (default: 100, max: 1000)
- `page[after]` / `page[before]` - Cursor tokens
- `filter[sex]` - Filter by sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
- `filter[has_variants]` - Filter by variant presence (true/false)
- `sort` - Comma-separated fields, `-` prefix for descending

**Performance:**
- Offset: O(n) with COUNT query (~150ms)
- Cursor: O(log n) with B-tree index (~120ms)

### Variant Annotation (VEP)

New endpoints for variant validation and annotation:

**Annotate Variant:**
```bash
POST /api/v2/variants/annotate?variant=17-36459258-A-G
POST /api/v2/variants/annotate?variant=NM_000458.4:c.544+1G>A
```

Returns: CADD scores, gnomAD frequencies, consequence predictions, impact severity

**Recode Variant:**
```bash
POST /api/v2/variants/recode?variant=rs56116432
```

Returns: All representations (HGVS c./p./g., VCF, SPDI, rsID)

**Configuration (backend/app/config.py):**
- `VEP_API_BASE_URL` - Ensembl REST API base (default: https://rest.ensembl.org)
- `VEP_RATE_LIMIT_REQUESTS_PER_SECOND` - Rate limit (default: 15)
- `VEP_MAX_RETRIES` - Max retry attempts (default: 3)
- `VEP_CACHE_SIZE_LIMIT` - Max cached variants (default: 1000)

## Git Commit Conventions

All commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format:** `<type>(<scope>): <description>`

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `refactor` - Code restructuring (no behavior change)
- `perf` - Performance improvement
- `test` - Adding/updating tests
- `docs` - Documentation only
- `chore` - Build/tooling changes
- `style` - Code formatting (no logic change)

**Scopes:**
- `frontend` - Vue.js changes
- `backend` - FastAPI changes
- `api` - API endpoint changes
- `db` - Database schema/migrations
- `ci` - CI/CD changes

**Examples:**
```bash
feat(api): add VEP annotation endpoint with CADD scores
fix(frontend): resolve pagination reset on filter change
refactor(backend): extract variant parsing to dedicated module
perf(db): add composite index for cursor pagination
test(backend): add unit tests for VEP annotation
docs: update API migration guide
```

**Breaking Changes:**
```bash
feat(api): migrate all endpoints to v2 format

BREAKING CHANGE: All API endpoints now require /api/v2/ prefix.
Frontend must update VITE_API_URL to include /api/v2 suffix.
```

## CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):
- Runs on push/PR
- Backend: ruff lint, mypy typecheck, pytest
- Frontend: ESLint, Prettier, Vitest
- Detects non-deterministic `abs(hash(` usage
- Detects broken imports

**Pre-commit Hooks:**
```bash
# Install
uv pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push

# What it checks:
- Code formatting (ruff/prettier)
- Type checking (mypy)
- No large files, private keys
- No non-deterministic hash() usage
- Pytest on pre-push
```

## Common Patterns

### Backend

**Database Session:**
```python
from app.database import get_db

@router.get("/example")
async def example(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Phenopacket))
    return result.scalars().all()
```

**Pydantic Models:**
```python
from pydantic import BaseModel, Field

class PhenopacketCreate(BaseModel):
    subject_id: str = Field(..., min_length=1)
    phenotypic_features: list[PhenotypicFeature] = []
```

**Async Operations:**
```python
# Always use async/await for database operations
async with async_session() as session:
    result = await session.execute(query)
    await session.commit()
```

### Frontend

**API Calls:**
```javascript
// Use centralized API client
import { getPhenopackets, searchPhenopackets } from '@/api';

const phenopackets = await getPhenopackets({ page: 1, size: 20 });
```

**Logging:**
```javascript
// ❌ NEVER use console.log()
console.log('User data:', userData);

// ✅ ALWAYS use logService
window.logService.info('User logged in', { username: user.value?.user });
window.logService.error('API error', { error: err.message });
```

**Pagination:**
```javascript
import { buildPaginationParameters } from '@/utils/pagination';

const params = buildPaginationParameters(page, pageSize, sort);
const response = await getPhenopackets(params);
```

## Data Migration

**Import Phenopackets from Google Sheets:**
```bash
# Full import (864 phenopackets)
make phenopackets-migrate

# Test import (20 phenopackets, faster for development)
make phenopackets-migrate-test

# Dry run (outputs to JSON file, no database changes)
make phenopackets-migrate-dry
```

**Migration System** (`backend/migration/`):
- Direct conversion: Google Sheets → GA4GH Phenopackets v2
- Modular architecture with focused components (<500 lines each)
- HPO term mapping with special onset terms (prenatal, congenital)
- MONDO disease classification
- VRS 2.0 compliant variant identifiers
- Publication references with PMID/DOI

## Admin User Management

```bash
# Initialize database with admin user
make db-init

# Or create/update admin user separately
make db-create-admin
```

**Default Credentials** (set in `backend/.env`):
```bash
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@hnf1b-db.local
ADMIN_PASSWORD=ChangeMe!Admin2025
```

⚠️ **Change admin password immediately after first login!**

## Troubleshooting

### Backend Issues
```bash
# Database connection failed
make hybrid-up          # Ensure services running
docker ps               # Verify containers

# Tests failing
make test               # Run to see errors
uv sync --group test    # Ensure test dependencies installed

# Linting errors
make lint               # See errors
make format             # Auto-fix formatting
```

### Frontend Issues
```bash
# Environment variable not updating
# Vite doesn't hot-reload .env files - restart dev server
npm run dev

# API calls failing
# Check VITE_API_URL in frontend/.env includes /api/v2 suffix
curl http://localhost:8000/api/v2/phenopackets/
```

### Common Errors

**"Address already in use":**
```bash
# Backend port 8000 or frontend port 5173 already in use
lsof -i :8000
lsof -i :5173
kill -9 <PID>
```

**"JWT_SECRET is empty":**
```bash
# Application exits on startup if JWT_SECRET not set
openssl rand -hex 32 >> backend/.env  # Add to .env file
```

**"Module not found":**
```bash
# Backend
cd backend && uv sync

# Frontend
cd frontend && npm install
```

## Additional Resources

- API Documentation: http://localhost:8000/docs (when running)
- README.md: Project setup and overview
- backend/README.md: Backend-specific details
- frontend/README.md: Frontend-specific details
- docs/COLOR_STYLE_GUIDE.md: UI color standards
