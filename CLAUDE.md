# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B-API is a GA4GH Phenopackets v2 compliant REST API for managing clinical and genetic data for individuals with HNF1B disease. The API has been completely restructured to use the international standard Phenopackets format for clinical and genomic data exchange.

## Project Structure

**ALL backend code is in the `backend/` directory:**

```
hnf1b-db-api/
├── backend/              # ALL backend code
│   ├── app/             # FastAPI application
│   ├── migration/       # Data migration scripts
│   ├── tests/           # Test suite
│   ├── alembic/         # Database migrations
│   ├── examples/        # Example scripts
│   ├── pyproject.toml   # Python dependencies
│   ├── Makefile         # Backend commands
│   └── .env             # Environment config (not in git)
├── docs/                # Documentation
├── Makefile             # Root commands (calls backend/)
└── docker-compose.services.yml  # Services
```

**IMPORTANT:**
- All Python code is in `backend/`
- Root Makefile runs commands with `cd backend && ...`
- Environment file is `backend/.env`

## Essential Commands

### Quick Start with Make (from project root)
```bash
make help          # Show all available commands
make dev           # Install all dependencies

# Development workflow:
make hybrid-up     # Start PostgreSQL and Redis
make server        # Start development server
make hybrid-down   # Stop containers

make test          # Run tests
make check         # Run all checks
```

### Development Server
```bash
# IMPORTANT: Start database services first!
make hybrid-up     # Start PostgreSQL and Redis (from root)

# Then start the development server
make server        # From root

# Database: hnf1b_phenopackets (864 phenopackets)
```

### Environment Setup
```bash
# Install dependencies (from root)
make dev

# Create backend/.env file with REQUIRED variables:
cp backend/.env.example backend/.env

# Generate secure JWT_SECRET (REQUIRED)
openssl rand -hex 32  # Copy output to backend/.env

# Edit backend/.env and set:
# DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db
# JWT_SECRET=<paste-generated-secret-here>
```

**⚠️ Security: JWT_SECRET is REQUIRED**
- Application will **exit on startup** if JWT_SECRET is empty
- Never commit backend/.env file (in .gitignore)
- Use different secrets for dev/staging/production

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

### Development Considerations

1. **Dependency management**: Uses uv for fast dependency resolution
   - Run `make dev` (from root) or `cd backend && uv sync`
   - Use `uv run <command>` from backend/ directory

2. **Environment variables required** (in `backend/.env`):
   - `DATABASE_URL` - PostgreSQL connection string
   - `JWT_SECRET` - Secret for JWT token signing (REQUIRED)

3. **Data validation**: Migration and API share Pydantic models for consistency

4. **Async operations**: All database operations use async/await with SQLAlchemy

5. **File locations**:
   - **Backend code**: `backend/` directory (app, migration, tests, alembic)
   - Data files in `/data` directory (VCF, VEP, reference genome files)
   - Phenopackets API: `backend/app/main.py` and `backend/app/phenopackets/`
   - Migration script: `backend/migration/direct_sheets_to_phenopackets.py`
   - Dependencies: `backend/pyproject.toml` and `backend/uv.lock`

6. **Migration Status**:
   - ✅ Complete: 864 individuals migrated to phenopackets format
   - ✅ Database: hnf1b_phenopackets with full JSONB schema
   - ✅ API: New v2 endpoints fully operational
   - 96% of phenopackets have phenotypic features
   - 49% have genetic variants
   - 100% have disease diagnoses