# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B-API is a GA4GH Phenopackets v2 compliant REST API for managing clinical and genetic data for individuals with HNF1B disease. The API has been completely restructured to use the international standard Phenopackets format for clinical and genomic data exchange.

## Essential Commands

### Quick Start with Make
```bash
make help          # Show all available commands
make dev           # Install all dependencies

# Development workflow (PostgreSQL required):
make hybrid-up     # Start PostgreSQL and Redis containers
make server        # Start development server (after hybrid-up)
make hybrid-down   # Stop containers when done

make test          # Run tests
make check         # Run all checks (lint + typecheck + tests)
```

### Development Server
```bash
# IMPORTANT: Start database services first!
make hybrid-up     # Start PostgreSQL and Redis containers

# Then start the development server (new Phenopackets v2 API)
uv run python -m uvicorn app.main:app --reload

# Database: hnf1b_phenopackets (864 phenopackets migrated from original data)
```

### Environment Setup
```bash
# Install/sync dependencies
uv sync

# Install with development dependencies
uv sync --group dev --group test

# Create .env file with required variables:
# DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db
# JWT_SECRET=your-secret-key
```

### Data Import
```bash
# Import all data from Google Sheets to PostgreSQL
make import-data

# Import limited test data (faster for development/testing)  
make import-data-test
```

**Prerequisites:**
1. Database running: `make hybrid-up`
2. Schema applied: `make db-upgrade`
3. Environment configured: Valid `.env` file

**Migration System:**
- Uses modular PostgreSQL migration in `/migration/` directory
- Main script: `migration/migrate.py` 
- Supports test mode with `--test` flag for limited data import
- Processes data from Google Sheets + genomic files in `/data/` directory

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

## Architecture Overview

### API Structure (Phenopackets v2)
The API has been completely restructured to use GA4GH Phenopackets v2 format:

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

### Data File Formats

The project handles specialized genomic data formats:
- **VCF files** (.vcf) - Variant Call Format for genetic variations
- **VEP files** (.vep.txt) - Variant Effect Predictor annotations
- **Reference genome data** (GRCh38) - TSV format with genomic coordinates

### Development Considerations

1. **Dependency management**: Uses uv for fast dependency resolution and environment management
   - Run `uv sync` to install dependencies
   - Use `uv run <command>` to execute scripts in the managed environment

2. **Environment variables required**:
   - `DATABASE_URL` - PostgreSQL connection string
   - `JWT_SECRET` - Secret for JWT token signing

3. **Data validation**: The migration script and API share Pydantic models for consistency

4. **Async operations**: All database operations use async/await patterns with SQLAlchemy

5. **File locations**:
   - Data files in `/data` directory (VCF, VEP, and reference genome files)
   - Phenopackets API in `/app/main.py` and `/app/phenopackets/` directory
   - Migration scripts in `/migration/` directory (phenopackets_migration.py)
   - Dependencies managed in `pyproject.toml` and `uv.lock`

6. **Migration Status**:
   - ✅ Complete: 864 individuals migrated to phenopackets format
   - ✅ Database: hnf1b_phenopackets with full JSONB schema
   - ✅ API: New v2 endpoints fully operational
   - 96% of phenopackets have phenotypic features
   - 49% have genetic variants
   - 100% have disease diagnoses