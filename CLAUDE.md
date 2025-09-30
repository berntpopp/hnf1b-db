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

### Data Import (Phenopackets Direct Migration)
```bash
# Import all data directly from Google Sheets to Phenopackets format
make phenopackets-migrate

# Import limited test data (20 individuals for testing)
make phenopackets-migrate-test

# Dry run - outputs to JSON file without database changes
make phenopackets-migrate-dry
```

**Prerequisites:**
1. Database running: `make hybrid-up`
2. Environment configured: Valid `.env` file with `DATABASE_URL`
3. Google Sheets URLs configured in migration script

**Modular Migration System:**
- Direct conversion from Google Sheets to GA4GH Phenopackets v2
- Main orchestrator: `migration/direct_sheets_to_phenopackets.py` (253 lines)
- Modular architecture with focused components:
  - `vrs/vrs_builder.py` - VRS 2.0 variant representation (375 lines)
  - `vrs/cnv_parser.py` - CNV parsing logic (350 lines)
  - `phenopackets/hpo_mapper.py` - HPO term mapping (189 lines)
  - `phenopackets/age_parser.py` - Age/temporal parsing (118 lines)
  - `phenopackets/publication_mapper.py` - Publication references (109 lines)
  - `phenopackets/extractors.py` - Phenotype/variant extraction (488 lines)
  - `phenopackets/builder_simple.py` - Phenopacket assembly (322 lines)
  - `data_sources/google_sheets.py` - Data loading (72 lines)
  - `database/storage.py` - Database operations (77 lines)
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
   - Direct migration script: `/migration/direct_sheets_to_phenopackets.py`
   - Dependencies managed in `pyproject.toml` and `uv.lock`

6. **Migration Status**:
   - ✅ Complete: 864 individuals migrated to phenopackets format
   - ✅ Database: hnf1b_phenopackets with full JSONB schema
   - ✅ API: New v2 endpoints fully operational
   - 96% of phenopackets have phenotypic features
   - 49% have genetic variants
   - 100% have disease diagnoses