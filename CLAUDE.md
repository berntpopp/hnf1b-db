# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B Database is a full-stack monorepo for managing clinical and genetic data for individuals with HNF1B disease. The backend is a GA4GH Phenopackets v2 compliant REST API, and the frontend is a Vue.js application for data visualization and management.

## Project Structure

**Monorepo with backend and frontend:**

```
hnf1b-db/
├── backend/              # FastAPI REST API
│   ├── app/             # FastAPI application
│   ├── migration/       # Data migration scripts
│   ├── tests/           # Backend tests
│   ├── alembic/         # Database migrations
│   ├── pyproject.toml   # Python dependencies
│   ├── Makefile         # Backend commands
│   └── .env             # Environment config (not in git)
├── frontend/            # Vue.js application
│   ├── src/            # Vue components & views
│   ├── public/         # Static assets
│   ├── package.json    # Node dependencies
│   ├── vite.config.js  # Vite configuration
│   ├── Makefile        # Frontend commands
│   └── .env            # Frontend environment (not in git)
├── docs/               # Shared documentation
├── Makefile            # Unified root commands
├── docker-compose.yml  # Full stack (development)
└── docker-compose.services.yml  # Services only (hybrid mode)
```

**IMPORTANT:**
- **Backend code**: All Python code is in `backend/`
- **Frontend code**: All Vue.js code is in `frontend/`
- **Root Makefile**: Orchestrates both backend and frontend commands
- **Component Makefiles**: Each component has its own Makefile for specific tasks
- **Environment files**: `backend/.env` and `frontend/.env` (both in .gitignore)

## Essential Commands

### Quick Start with Make (from project root)
```bash
make help          # Show all available commands
make dev           # Install all dependencies (backend + frontend)

# Hybrid Development (Recommended):
make hybrid-up     # Start PostgreSQL and Redis
make backend       # Start backend server (Terminal 1)
make frontend      # Start frontend dev server (Terminal 2)
make hybrid-down   # Stop services

# Full Docker Development:
make dev-up        # Start full stack in Docker
make dev-down      # Stop all Docker services
make dev-logs      # Show Docker logs

# Testing & Quality:
make test          # Run backend tests
make check         # Run all checks (lint + typecheck + tests)
make status        # Show system status
```

### Development Workflows

**Hybrid Mode (Recommended)**:
```bash
# Services in Docker, apps run locally for hot reload
make hybrid-up     # Start PostgreSQL + Redis

# Terminal 1: Backend (http://localhost:8000)
make backend

# Terminal 2: Frontend (http://localhost:5173)
make frontend
```

**Full Docker Mode**:
```bash
# Everything in Docker
make dev-up        # Frontend: http://localhost:3000
                   # Backend: http://localhost:8000
```

### Environment Setup

**Backend Configuration:**
```bash
# Create backend/.env file with REQUIRED variables:
cp backend/.env.example backend/.env

# Generate secure JWT_SECRET (REQUIRED)
openssl rand -hex 32  # Copy output to backend/.env

# Edit backend/.env and set:
# DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
# JWT_SECRET=<paste-generated-secret-here>
```

**Frontend Configuration:**
```bash
# Create frontend/.env file:
cp frontend/.env.example frontend/.env

# Edit frontend/.env and set:
# VITE_API_URL=http://localhost:8000/api/v2
```

**⚠️ Security: JWT_SECRET is REQUIRED**
- Application will **exit on startup** if JWT_SECRET is empty
- Never commit .env files (both in .gitignore)
- Use different secrets for dev/staging/production

---

## Environment Configuration & Deployment

### Overview

Both backend and frontend use environment variables for configuration. This follows the [12-Factor App](https://12factor.net/config) methodology, allowing the same codebase to run in different environments (development, staging, production) with different configurations.

### Frontend Environment Variables

**Configuration File:** `frontend/.env`

**Key Variables:**
- `VITE_API_URL` - Backend API base URL (REQUIRED)

**Setup:**
```bash
# 1. Copy example file
cd frontend
cp .env.example .env

# 2. Edit .env file
# For development (default):
VITE_API_URL=http://localhost:8000/api/v2

# For staging:
VITE_API_URL=https://staging-api.hnf1b.example.com/api/v2

# For production:
VITE_API_URL=https://api.hnf1b.example.com/api/v2
```

**How It Works:**
```javascript
// frontend/src/api/index.js
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v2',
  timeout: 10000,
});
```

- If `VITE_API_URL` is set: Uses that value
- If not set: Falls back to `http://localhost:8000/api/v2` (local development)

**Important Notes:**
- ⚠️ **Always include `/api/v2` suffix** in `VITE_API_URL`
- ✅ Environment variables must start with `VITE_` to be exposed to frontend code
- ✅ Variables are embedded at **build time** (not runtime)

### Backend Environment Variables

**Configuration File:** `backend/.env`

**Key Variables:**
- `DATABASE_URL` - PostgreSQL connection string (REQUIRED)
- `JWT_SECRET` - Secret for JWT token signing (REQUIRED)
- `ENVIRONMENT` - Runtime environment (dev/staging/prod)
- `REDIS_URL` - Redis connection string (optional)

**Setup:**
```bash
# 1. Copy example file
cd backend
cp .env.example .env

# 2. Generate JWT secret
openssl rand -hex 32

# 3. Edit .env file
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
JWT_SECRET=<paste-generated-secret-here>
ENVIRONMENT=development
```

### Testing Environment Configuration

#### Test 1: Default Fallback (No .env)

**Purpose:** Verify application works without .env file (uses defaults)

```bash
# Remove .env file
cd frontend
rm .env

# Start dev server
npm run dev

# Open browser console at http://localhost:5173
console.log(import.meta.env.VITE_API_URL)
// Output: undefined (uses fallback: http://localhost:8000/api/v2)

# Navigate to /phenopackets
# Should work correctly if backend is running on localhost:8000
```

**Expected Behavior:**
- Frontend uses fallback URL: `http://localhost:8000/api/v2`
- API calls succeed if backend is running locally
- No errors in console

#### Test 2: Development Configuration

**Purpose:** Verify .env file is loaded correctly

```bash
# Create .env with development settings
cd frontend
cat > .env << EOF
VITE_API_URL=http://localhost:8000/api/v2
EOF

# Start dev server
npm run dev

# Open browser console
console.log(import.meta.env.VITE_API_URL)
// Output: "http://localhost:8000/api/v2"
```

**Expected Behavior:**
- Environment variable loaded correctly
- API calls work
- Can modify .env and restart to test different URLs

#### Test 3: Production Build

**Purpose:** Verify environment variables are embedded in production build

```bash
# Set production API URL
cd frontend
cat > .env << EOF
VITE_API_URL=https://api.hnf1b.example.com/api/v2
EOF

# Build for production
npm run build

# Preview production build
npm run preview

# Check network tab in browser DevTools
# All API calls should go to https://api.hnf1b.example.com/api/v2
```

**Expected Behavior:**
- Build completes successfully
- API calls in preview use production URL
- Environment variable is baked into bundle (not changeable after build)

#### Test 4: Custom API URL

**Purpose:** Test with different backend URL (e.g., remote development server)

```bash
# Point to remote backend
cd frontend
cat > .env << EOF
VITE_API_URL=https://dev-backend.example.com/api/v2
EOF

# Start dev server
npm run dev

# Verify API calls go to remote server
# Check Network tab in browser DevTools
```

### Deployment Checklist

#### Development Deployment
- [ ] Copy `.env.example` to `.env`
- [ ] Set `VITE_API_URL=http://localhost:8000/api/v2`
- [ ] Backend running on `localhost:8000`
- [ ] Frontend runs on `localhost:5173`

#### Staging Deployment
- [ ] Set `VITE_API_URL=https://staging-api.hnf1b.example.com/api/v2`
- [ ] Run `npm run build`
- [ ] Verify API calls in preview (`npm run preview`)
- [ ] Deploy `dist/` folder to staging server
- [ ] Test all features work with staging backend

#### Production Deployment
- [ ] Set `VITE_API_URL=https://api.hnf1b.example.com/api/v2`
- [ ] Run `npm run build`
- [ ] Verify no hardcoded URLs in code (`grep -r "localhost:8000" src/`)
- [ ] Verify `.env` file is in `.gitignore`
- [ ] Deploy `dist/` folder to production server
- [ ] Smoke test: Check home page loads and API calls work

### Common Issues & Troubleshooting

#### Issue: API calls return 404

**Symptoms:**
- Console shows `GET http://localhost:8000/phenopackets/ 404 Not Found`

**Causes:**
1. Missing `/api/v2` suffix in `VITE_API_URL`
2. Backend not running
3. Wrong API version

**Solution:**
```bash
# Check .env file
cat frontend/.env
# Should show: VITE_API_URL=http://localhost:8000/api/v2
#                                                       ^^^^^^^^ Must include this!

# Verify backend is running
curl http://localhost:8000/api/v2/phenopackets/
```

#### Issue: Environment variable not updating

**Symptoms:**
- Changed `.env` but API still uses old URL

**Cause:**
- Vite dev server doesn't hot-reload environment variables

**Solution:**
```bash
# Must restart dev server after changing .env
# Press Ctrl+C, then:
npm run dev
```

#### Issue: Production build uses wrong URL

**Symptoms:**
- Built app calls `localhost:8000` instead of production URL

**Cause:**
- `.env` file had development URL during build

**Solution:**
```bash
# Always set correct URL BEFORE building
echo "VITE_API_URL=https://api.hnf1b.example.com/api/v2" > frontend/.env
npm run build
```

#### Issue: CORS errors in production

**Symptoms:**
- `Access-Control-Allow-Origin` errors in browser console

**Cause:**
- Backend CORS configuration doesn't allow frontend domain

**Solution:**
```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hnf1b.example.com"],  # Add your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Security Best Practices

1. **Never commit `.env` files**
   - Both `backend/.env` and `frontend/.env` are in `.gitignore`
   - Use `.env.example` as template for other developers

2. **Use different secrets per environment**
   - Development: Can use simple secrets
   - Staging: Use strong secrets
   - Production: Use cryptographically secure secrets

3. **Rotate secrets regularly**
   - Change `JWT_SECRET` periodically
   - Invalidates all existing tokens (users must re-login)

4. **Verify no sensitive data in code**
   ```bash
   # Search for hardcoded secrets
   grep -r "jwt_secret\|password\|api_key" --exclude-dir=node_modules .
   ```

5. **Use environment-specific databases**
   - Development: `hnf1b_dev`
   - Staging: `hnf1b_staging`
   - Production: `hnf1b_production`

### CI/CD Environment Variables

**For GitHub Actions / CI pipelines:**

```yaml
# .github/workflows/deploy.yml
env:
  VITE_API_URL: ${{ secrets.PRODUCTION_API_URL }}

steps:
  - name: Build frontend
    run: |
      cd frontend
      npm ci
      npm run build
```

**Set secrets in GitHub repository settings:**
- `PRODUCTION_API_URL` = `https://api.hnf1b.example.com/api/v2`

---

### User Management & Authentication

**Initialize User System (First-Time Setup):**
```bash
# Create users table and initial admin user
cd backend
make db-create-admin

# Or combined with migrations:
make db-init  # Runs migrations + creates admin user
```

**Default Admin Credentials** (if not set in `.env`):
- Username: `admin`
- Email: `admin@hnf1b-db.local`
- Password: `ChangeMe!Admin2025`

**⚠️ SECURITY**: Change admin password immediately after first login!

**Customize Admin Credentials:**
```bash
# Add to backend/.env BEFORE running db-create-admin:
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@hnf1b-db.local
ADMIN_PASSWORD=ChangeMe!Admin2025

# Then create/update admin:
cd backend
make db-create-admin
```

**Script Behavior:**
- Idempotent: Safe to run multiple times
- Updates existing admin if username/email matches
- Resets password and ensures admin role/active status
- Located at: `backend/scripts/create_admin_user.py`

**Testing Note:**
- 3 auth tests currently fail due to duplicate admin username conflicts
- Tests need isolation fixes to run with existing admin user
- Script itself is tested, linted, and type-checked ✅

---

### Data Import (Phenopackets Direct Migration)
```bash
# Import all data directly from Google Sheets to Phenopackets format
make phenopackets-migrate

# Import limited test data (20 individuals by default)
make phenopackets-migrate-test

# Custom test limit (e.g., 50 individuals)
TEST_MODE_LIMIT=50 make phenopackets-migrate-test

# Dry run - outputs to JSON file without database changes
make phenopackets-migrate-dry
```

**Prerequisites:**
1. Database running: `make hybrid-up`
2. Environment configured: Valid `backend/.env` file with `DATABASE_URL`
3. Google Sheets URLs configured in migration script

**Modular Migration System (in backend/migration/):**
- Direct conversion from Google Sheets to GA4GH Phenopackets v2
- Main orchestrator: `backend/migration/direct_sheets_to_phenopackets.py`
- Modular architecture with focused components:
  - `vrs/vrs_builder.py` - VRS 2.0 variant representation
  - `vrs/cnv_parser.py` - CNV parsing logic
  - `phenopackets/hpo_mapper.py` - HPO term mapping
  - `phenopackets/age_parser.py` - Age/temporal parsing
  - `phenopackets/publication_mapper.py` - Publication references
  - `phenopackets/evidence_builder.py` - Evidence building
  - `phenopackets/extractors.py` - Phenotype/variant extraction
  - `phenopackets/builder_simple.py` - Phenopacket assembly
  - `data_sources/google_sheets.py` - Data loading
  - `database/storage.py` - Database operations
- Bypasses intermediate PostgreSQL normalization step
- Supports test mode (20 individuals) and dry run mode
- Properly maps HPO terms, MONDO diseases, and variant data
- Generates GA4GH VRS 2.0 compliant variant identifiers with proper digests
- Each module follows Single Responsibility Principle (no file exceeds 500 lines)

### Code Quality Tools

**Backend (Python):**
```bash
# Install development dependencies (automatically included with sync)
uv sync --group dev --group test

# Format and fix code with ruff (replaces black, isort, flake8)
make format

# Run linting with ruff
make lint

# Run type checking with mypy
make typecheck

# Run all quality checks (lint + typecheck + test)
make check

# Run tests
make test

# Alternative: Run tools directly
uv run ruff format .        # Format code
uv run ruff check .         # Lint code
uv run ruff check --fix .   # Lint and auto-fix issues
uv run mypy app/            # Type checking
uv run pytest              # Run tests
```

**Frontend (Vue.js):**
```bash
cd frontend

# Run all quality checks (test + lint + format) - REQUIRED before commits
make check

# Individual commands
make test           # Run Vitest unit tests
make lint           # Lint with ESLint and auto-fix
make format         # Format with Prettier

# Alternative: Run tools directly
npm test            # Run tests
npm run lint        # Lint and auto-fix
npm run lint:check  # Lint without auto-fix
npm run format      # Format code
npm run format:check # Check formatting
```

**⚠️ Pre-Commit Requirements:**
- **ALWAYS run `make check`** before committing (backend or frontend)
- All tests must pass
- All linting errors must be fixed
- Code must be properly formatted
- GitHub Actions CI/CD runs these checks automatically

### Code Quality Guidelines

**DRY Principle (Don't Repeat Yourself):**
- Before adding new code, check for similar patterns that can be extracted into reusable functions/classes
- If copying code blocks (>10 lines), consider extracting to a shared utility
- Use grep to find potential duplication: `grep -r "pattern" --include="*.py"`

**YAGNI Principle (You Aren't Gonna Need It):**
- Don't write code for future "what if" scenarios
- Remove unused code, imports, and modules immediately
- Only implement what's required for current use cases
- Unused code becomes technical debt

**Dead Code Detection:**
- Regularly check for unused imports: `uv run ruff check --select F401`
- Search for unused modules/classes: `grep -r "from path.to.module" app/ tests/`
- Remove directories/files with no active imports
- Clean up commented-out code blocks during reviews

**Code Review Checklist:**
- [ ] No code duplication (DRY principle followed)
- [ ] No unused imports or dead code (YAGNI principle)
- [ ] All modules under 500 lines (Single Responsibility)
- [ ] Tests pass: `make check`
- [ ] Documentation updated if needed

## Testing & CI/CD

### Critical Rule: Never Skip or Ignore Issues

**⚠️ ABSOLUTE REQUIREMENT:**
- **NEVER skip failing tests** - Always fix them properly
- **NEVER ignore linting errors** - Fix or properly suppress with documentation
- **NEVER ignore type checking errors** - Fix code or add documented exceptions
- Use modern best practices (e.g., pytest `caplog` for logging tests, not mocking)
- Pre-existing issues must be fixed, not skipped or worked around
- Quality gates are mandatory - all checks must pass before merge

### Why Testing is Critical

Recent issues (see #20) were caused by:
1. **No CI/CD** - Tests not run automatically on commits
2. **Stale tests** - Tests referenced methods deleted during refactoring
3. **No pre-commit hooks** - No validation before commits
4. **Non-deterministic code** - Used `hash()` instead of `hashlib.sha256()`

### CI/CD Setup (GitHub Actions)

**Status:** ✅ Configured in `.github/workflows/ci.yml`

Runs automatically on push/PR to check:
- Linting, type checking, tests with coverage
- Detects `abs(hash(` usage (non-deterministic)
- Detects broken imports (e.g., `migration.modules`)

### Pre-commit Hooks

**Installation:**
```bash
uv pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

**What it checks:**
- Code formatting & linting (ruff)
- Type checking (mypy)
- No large files, private keys, broken imports
- **Prevents non-deterministic hash() usage**
- Runs pytest on pre-push

### Test-Before-Refactor Protocol

**ALWAYS follow this sequence:**
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
git add . && git commit
```

### Testing Rules

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

### Common Test Commands

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/test_migration.py -v

# Run with coverage
uv run pytest --cov=app --cov=migration

# Check for broken imports
rg "from migration.modules" --type py

# Detect non-deterministic hash
rg "abs\(hash\(" --type py
```

## Architecture Overview

### Monorepo Structure

This is a **full-stack monorepo** with:
- **Backend**: `backend/` - FastAPI REST API
- **Frontend**: `frontend/` - Vue.js application
- **Unified Commands**: Root `Makefile` orchestrates both
- **Component Independence**: Each has its own `Makefile` for direct access

### Backend Architecture (FastAPI)

**Code Location:** All backend code is in `backend/` directory

### API Structure (Phenopackets v2)
The API (in `backend/app/`) uses GA4GH Phenopackets v2 format:

**Main Endpoints:**
- **`/api/v2/phenopackets/`** - Core phenopacket CRUD operations
- **`/api/v2/phenopackets/search`** - Advanced search across phenopackets
- **`/api/v2/phenopackets/aggregate/*`** - Aggregation and statistics
- **`/api/v2/clinical/*`** - Clinical feature-specific queries
  - `/clinical/renal-insufficiency` - Kidney disease cases
  - `/clinical/genital-abnormalities` - Genital tract abnormalities
  - `/clinical/diabetes` - Diabetes cases
  - `/clinical/hypomagnesemia` - Hypomagnesemia cases

### Database Schema (Phenopackets v2)

PostgreSQL tables using JSONB storage for phenopackets:

1. **phenopackets** - Main table storing complete phenopacket documents
   - JSONB column with full GA4GH Phenopackets v2 structure
   - Generated columns: subject_id, subject_sex for fast queries
   - Comprehensive GIN indexes for JSONB queries
   - 864 phenopackets migrated from original data

2. **families** - Family relationships (GA4GH Family messages)

3. **cohorts** - Population study cohorts

4. **resources** - Ontology resources (HPO, MONDO, LOINC, etc.)

5. **phenopacket_audit** - Change tracking and audit trail

### Key Design Patterns

1. **Phenopackets Standard**: Full GA4GH Phenopackets v2 compliance for data exchange

2. **JSONB Storage**: Document-oriented approach with PostgreSQL JSONB for flexibility

3. **Data Validation**: Phenopacket validation in `app/phenopackets/validator.py`

4. **Database Access**: Async PostgreSQL operations with SQLAlchemy + asyncpg

5. **Ontology Integration**: HPO terms for phenotypes, MONDO for diseases, LOINC for labs

6. **VRS (Variation Representation Specification)**: GA4GH VRS 2.0 compliant variant representation
   - Proper digest computation using `ga4gh.vrs` library
   - Format-compliant RefGet placeholders for sequence references
   - Deterministic variant identifiers following GA4GH standards
   - Fallback to placeholder digests when VRS library unavailable

### Data File Formats

The project handles specialized genomic data formats:
- **VCF files** (.vcf) - Variant Call Format for genetic variations
- **VEP files** (.vep.txt) - Variant Effect Predictor annotations
- **Reference genome data** (GRCh38) - TSV format with genomic coordinates

### Frontend Architecture (Vue.js)

**Code Location:** All frontend code is in `frontend/` directory

**Technology Stack:**
- **Framework**: Vue 3 with Composition API
- **UI Library**: Vuetify 3 (Material Design)
- **Build Tool**: Vite 6
- **Router**: Vue Router 4 with lazy-loaded routes
- **HTTP Client**: Axios with JSON:API interceptors
- **Visualization**: D3.js for charts

**Project Structure:**
- `frontend/src/api/` - API service layer with centralized axios client
- `frontend/src/components/` - Reusable components (analyses, tables)
- `frontend/src/views/` - Page-level routed components
- `frontend/src/router/` - Route definitions with dynamic imports
- `frontend/src/utils/` - Authentication utilities

**Key Features:**
- HPO term autocomplete for phenotype selection
- Interactive D3.js visualizations
- Material Design responsive UI
- JWT authentication flow
- Real-time statistics dashboard
- Privacy-first logging system with automatic PII/PHI redaction

**Logging System (REQUIRED):**
- **NEVER use `console.log()`** in frontend code
- **ALWAYS use `window.logService`** for logging
- Automatically redacts sensitive data (HPO terms, emails, variants, DNA sequences, tokens)
- Methods: `window.logService.debug()`, `.info()`, `.warn()`, `.error()`
- Example: `window.logService.info('User logged in', { username: user.value?.user })`
- Logging console OFF by default (enable in LogViewer component)

### Development Considerations

1. **Backend Dependency Management**: Uses uv for fast dependency resolution
   - Run `make dev` (from root) or `cd backend && uv sync`
   - Use `uv run <command>` from backend/ directory

2. **Frontend Dependency Management**: Uses npm
   - Run `cd frontend && npm install`
   - Use `npm run <command>` from frontend/ directory

3. **Environment Variables**:
   - Backend (`backend/.env`): `DATABASE_URL`, `JWT_SECRET` (REQUIRED)
   - Frontend (`frontend/.env`): `VITE_API_URL`

4. **Data validation**: Backend migration and API share Pydantic models for consistency

5. **Async operations**: All backend database operations use async/await with SQLAlchemy

6. **API Integration**: Frontend uses Vite proxy to forward `/api` requests to backend

7. **File Locations**:
   - **Backend code**: `backend/` (app, migration, tests, alembic)
   - **Frontend code**: `frontend/` (src, public, components)
   - Data files: `/data` directory (VCF, VEP, reference genome files)
   - Backend dependencies: `backend/pyproject.toml` and `backend/uv.lock`
   - Frontend dependencies: `frontend/package.json` and `frontend/package-lock.json`

8. **Migration Status**:
   - ✅ Complete: 864 individuals migrated to phenopackets format
   - ✅ Database: hnf1b_phenopackets with full JSONB schema
   - ✅ API: New v2 endpoints fully operational
   - ✅ Frontend: Integrated with monorepo structure
   - 96% of phenopackets have phenotypic features
   - 49% have genetic variants
   - 100% have disease diagnoses

## Issue Management

### Issue Naming Convention

All GitHub issues MUST follow conventional commit message format:

**Format:** `<type>(<scope>): <short description>`

**Types:**
- `feat:` - New feature (e.g., `feat(frontend): add phenopacket detail page`)
- `fix:` - Bug fix (e.g., `fix(api): correct 404 on aggregation endpoints`)
- `refactor:` - Code refactoring (e.g., `refactor(backend): extract variant parsing logic`)
- `perf:` - Performance improvement (e.g., `perf(db): add JSONB GIN indexes`)
- `docs:` - Documentation only (e.g., `docs: update API migration guide`)
- `test:` - Adding/fixing tests (e.g., `test(migration): add phenopacket validation tests`)
- `chore:` - Build/tooling changes (e.g., `chore: update CI/CD pipeline`)
- `style:` - Code style/formatting (e.g., `style(frontend): apply ESLint fixes`)

**Scope (optional):**
- `frontend` - Vue.js frontend changes
- `backend` - FastAPI backend changes
- `api` - API endpoint changes
- `db` - Database schema/migration changes
- `migration` - Data migration scripts
- `ci` - CI/CD pipeline changes

**Examples:**
- ✅ `feat(frontend): migrate individual detail page to phenopackets v2`
- ✅ `fix(api): update aggregation endpoints for phenopacket format`
- ✅ `refactor(backend): extract VRS variant builder to separate module`
- ✅ `perf(db): optimize JSONB queries with generated columns`
- ❌ `Update aggregation endpoints and dashboard visualizations` (missing type)
- ❌ `Fix bug` (too vague, missing scope)

### Issue Structure

Issues should be **concise** on GitHub, with **detailed plans** in markdown files:

**Directory Structure:**
```
docs/issues/
├── issue-##-descriptive-name.md       # Detailed implementation plan
└── github-issue-##-template.md        # Concise GitHub issue template
```

**Detailed Plan File** (`docs/issues/issue-##-descriptive-name.md`):
- **Overview** - Problem statement and goals
- **Why This Matters** - Current vs. new implementation with code examples
- **Required Changes** - Step-by-step technical details
- **Implementation Checklist** - Phased tasks with checkboxes
- **Testing Verification** - Manual test steps and expected results
- **Acceptance Criteria** - Definition of done
- **Files Modified/Created** - Complete file list with line counts
- **Dependencies** - Blocking/blocked issues
- **Performance Impact** - Before/after metrics
- **Timeline** - Estimated hours per phase
- **Priority & Labels** - For GitHub organization

**GitHub Issue Template** (`docs/issues/github-issue-##-template.md`):
```markdown
# <type>(<scope>): <short description>

## Summary
2-3 sentence description of the problem and solution.

**Current:** What's broken/missing
**Target:** What should work

## Details
See detailed implementation plan: [docs/issues/issue-##-descriptive-name.md](link)

## Acceptance Criteria
- [ ] High-level checkpoint 1
- [ ] High-level checkpoint 2
- [ ] ...
(8-10 items maximum)

## Dependencies
- Issue #XX (description) - ✅ Required / ⚠️ Blocked

## Priority
**P1 (High)** / **P2 (Medium)** / **P3 (Low)** - Reason

## Labels
`label1`, `label2`, `label3`
```

### Creating New Issues

**Workflow:**
1. **Create detailed plan** in `docs/issues/issue-##-descriptive-name.md`
2. **Create GitHub template** in `docs/issues/github-issue-##-template.md`
3. **Copy template content** to GitHub issue
4. **Apply labels and priority** in GitHub
5. **Link related issues** in GitHub

**Example:**
```bash
# 1. Create detailed plan
docs/issues/issue-32-migrate-individual-detail-page.md

# 2. Create GitHub template
docs/issues/github-issue-32-template.md

# 3. Copy to GitHub with proper title:
# "feat(frontend): migrate individual detail page to phenopackets v2"
```

### Closing Issues

When closing an issue, provide a **concise closing message**:

**Format:**
```markdown
✅ Resolved in commit <hash>

## Summary
Brief description of what was implemented.

## Changes
- Key change 1
- Key change 2
- Key change 3

## Verification
- ✅ All acceptance criteria met
- ✅ Tests passing
- ✅ No console errors
```

**Example:**
```markdown
✅ Resolved in commit 3db7944

## Summary
Successfully migrated Individuals view to Phenopackets v2 format.

## Changes
- Renamed `Individuals.vue` → `Phenopackets.vue`
- Updated API calls from `getIndividuals()` to `getPhenopackets()`
- Implemented data transformation for JSONB structure
- Updated routes: `/individuals` → `/phenopackets`

## Verification
- ✅ Table displays all 864 phenopackets
- ✅ Pagination works with skip/limit model
- ✅ No 404 errors, all API calls succeed
```

## Git Commit Messages

### Conventional Commit Format

All commits MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

**Format:** `<type>(<scope>): <short description>`

**Examples:**
```bash
feat(frontend): add phenopacket detail view with HPO term display
fix(api): correct pagination offset calculation in search endpoint
refactor(migration): extract VRS variant builder to separate module
perf(db): add GIN indexes for JSONB phenotype queries
docs: update API migration guide with v2 endpoint examples
test(backend): add integration tests for phenopacket CRUD operations
chore(ci): update GitHub Actions workflow for uv dependency caching
style(frontend): apply ESLint autofix for unused imports
```

### Commit Message Guidelines

**When Claude Code Completes a Task:**

After completing work on an issue or task, Claude will provide a suggested commit message in the terminal output. This message will:

1. **Follow conventional commit format** with appropriate type and scope
2. **Reference the issue number** if applicable
3. **Describe what was changed** (not why - that's in the issue)
4. **Be concise** - one-line summary, optional body for complex changes

**Structure:**
```
<type>(<scope>): <imperative mood description> (#issue)

Optional body with:
- Additional context if needed
- Breaking changes (BREAKING CHANGE: ...)
- References to related commits or issues
```

### Commit Types Reference

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature or capability | `feat(api): add phenopacket search endpoint with HPO filters` |
| `fix` | Bug fix | `fix(frontend): resolve table pagination reset on filter change` |
| `refactor` | Code restructuring (no behavior change) | `refactor(migration): split monolithic builder into focused modules` |
| `perf` | Performance improvement | `perf(db): optimize JSONB queries with generated columns` |
| `docs` | Documentation only | `docs: add environment configuration guide` |
| `test` | Adding or updating tests | `test(migration): add VRS digest validation tests` |
| `chore` | Build, dependencies, tooling | `chore: update uv dependencies to latest versions` |
| `style` | Code formatting (no logic change) | `style(backend): apply ruff formatting to migration modules` |
| `build` | Build system or dependencies | `build(frontend): upgrade Vite to 6.0` |
| `ci` | CI/CD pipeline changes | `ci: add pre-commit hooks for ruff and mypy` |
| `revert` | Revert previous commit | `revert: revert "feat(api): add experimental caching layer"` |

### Commit Scope Reference

| Scope | Description | Example |
|-------|-------------|---------|
| `frontend` | Vue.js application changes | `feat(frontend): add HPO term autocomplete` |
| `backend` | FastAPI application changes | `fix(backend): handle missing JWT token gracefully` |
| `api` | API endpoint or contract changes | `feat(api): add aggregation endpoints for dashboard` |
| `db` | Database schema or migrations | `feat(db): add phenopacket_audit table for change tracking` |
| `migration` | Data migration scripts | `fix(migration): correct HPO term mapping for renal phenotypes` |
| `ci` | CI/CD pipeline | `chore(ci): add test coverage reporting` |
| `docs` | Documentation | `docs(api): document phenopacket search parameters` |

### Multi-File Commit Strategy

**Single Logical Change:**
```bash
# ✅ Good: One commit for related changes
feat(frontend): migrate individuals view to phenopackets v2

- Rename Individuals.vue → Phenopackets.vue
- Update API calls to use v2 endpoints
- Transform JSONB data for table display
- Update router paths and navigation
```

**Multiple Independent Changes:**
```bash
# ❌ Bad: Multiple unrelated changes in one commit
feat(frontend): add search and fix styling and update docs

# ✅ Good: Separate commits for each logical change
feat(frontend): add phenopacket search with HPO filters
style(frontend): fix table header alignment in phenopackets view
docs: update frontend architecture guide
```

### Breaking Changes

If a commit introduces breaking changes, use `BREAKING CHANGE:` in the body:

```bash
feat(api): migrate all endpoints to v2 format

BREAKING CHANGE: All API endpoints now require /api/v2/ prefix.
Previous /api/v1/ endpoints are deprecated and will be removed in next release.
Frontend must update VITE_API_URL to include /api/v2 suffix.
```

### Commit Message Template

**Simple Change:**
```bash
<type>(<scope>): <description> (#issue-number)
```

**Complex Change with Body:**
```bash
<type>(<scope>): <description> (#issue-number)

Additional context explaining:
- Why the change was needed
- What alternatives were considered
- Any side effects or migration notes

Refs: #related-issue-1, #related-issue-2
```

**Example Workflow:**

```bash
# After Claude completes work, terminal shows:

---
✅ Task completed successfully

Suggested commit message:
---
feat(frontend): migrate publications view to phenopackets v2 API (#34)

- Update getPhenopackets call to fetch publications
- Extract publication data from JSONB structure
- Update table columns for v2 schema
- Fix PMID link formatting
---

# Review changes
git status
git diff

# Stage changes
git add frontend/src/views/Publications.vue

# Commit with suggested message
git commit -m "feat(frontend): migrate publications view to phenopackets v2 API (#34)

- Update getPhenopackets call to fetch publications
- Extract publication data from JSONB structure
- Update table columns for v2 schema
- Fix PMID link formatting"
```

### Automated Commit Message Validation

**Pre-commit Hook (Optional):**

```bash
# .git/hooks/commit-msg
#!/bin/sh
commit_msg_file=$1
commit_msg=$(cat "$commit_msg_file")

# Check conventional commit format
if ! echo "$commit_msg" | grep -qE '^(feat|fix|refactor|perf|docs|test|chore|style|build|ci|revert)(\([a-z]+\))?: .+'; then
    echo "❌ Error: Commit message must follow conventional commit format"
    echo "Format: <type>(<scope>): <description>"
    echo "Example: feat(frontend): add phenopacket search"
    exit 1
fi

echo "✅ Commit message format valid"
```

### Best Practices

1. **Use imperative mood**: "add feature" not "added feature"
2. **Keep first line under 72 characters** for better git log readability
3. **Reference issue numbers** when applicable
4. **Be specific**: "fix login redirect loop" not "fix bug"
5. **Explain why, not what**: Code shows what changed, commit explains why
6. **One logical change per commit**: Makes reverts and cherry-picks easier
7. **Review suggested message**: Claude's suggestion is a starting point - adjust as needed

### Common Patterns

**Feature Implementation:**
```bash
feat(frontend): add phenopacket detail page with clinical data sections (#32)
```

**Bug Fix:**
```bash
fix(api): correct 404 error on /aggregate/phenotypes endpoint (#28)
```

**Refactoring:**
```bash
refactor(migration): extract CNV parsing logic to dedicated module
```

**Performance:**
```bash
perf(db): add generated columns for subject_id and sex to improve query speed
```

**Documentation:**
```bash
docs: add comprehensive environment configuration guide for frontend
```

**Testing:**
```bash
test(migration): add unit tests for VRS digest generation
```

**Maintenance:**
```bash
chore: update GitHub Actions workflow to use uv for faster CI builds
```