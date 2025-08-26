# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B-API is a FastAPI-based REST API for managing clinical and genetic data for individuals with HNF1B disease. It provides endpoints for managing patients, genetic variants, clinical reports, and related publications.

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

# Then start the development server
make server        # Start FastAPI with auto-reload

# Alternative direct method (after hybrid-up)
uv run python -m uvicorn app.main:app --reload
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
# Import data from Google Sheets to PostgreSQL
make import-data
```

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

### API Structure
The API is organized into 8 main endpoint groups, each handling a specific domain:

- **`/api/auth`** - JWT authentication (login, token management)
- **`/api/individuals`** - Patient demographic data
- **`/api/variants`** - Genetic variant information with classifications
- **`/api/publications`** - Publication metadata and references
- **`/api/proteins`** - Protein-related data
- **`/api/genes`** - Gene information
- **`/api/search`** - Cross-collection search functionality
- **`/api/aggregations`** - Data aggregation endpoints (statistics, summaries)

### Database Schema

PostgreSQL tables with their relationships:

1. **users** - System users/reviewers
   - Referenced by: reports (reviewed_by)

2. **individuals** - Patient demographics
   - Referenced by: reports, variants

3. **reports** - Clinical presentations with phenotypes
   - References: individuals (individual_id), users (reviewed_by)
   - Embeds: phenotypes array

4. **variants** - Genetic variants with annotations and classifications
   - References: individuals (individual_id)
   - Uses `is_current` flag for versioning

5. **publications** - Research papers and references

### Key Design Patterns

1. **Authentication**: JWT-based with dependency injection via `app/dependencies.py`

2. **Data Validation**: Pydantic models in `app/models.py` ensure consistency between API and database

3. **Database Access**: Async PostgreSQL operations using SQLAlchemy through `app/database.py`

4. **CORS**: Configured for all origins (development mode)

5. **Variant Versioning**: Multiple variant records per individual with `is_current` flag

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
   - API code in `/app` directory with modular endpoint organization
   - Dependencies managed in `pyproject.toml` and `uv.lock`
   - Migration script at root level: `migrate_from_sheets.py`