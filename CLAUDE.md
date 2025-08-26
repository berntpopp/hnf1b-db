# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B-API is a FastAPI-based REST API for managing clinical and genetic data for individuals with HNF1B disease. It provides endpoints for managing patients, genetic variants, clinical reports, and related publications.

## Essential Commands

### Quick Start with Make
```bash
make help          # Show all available commands
make dev           # Install all dependencies
make server        # Start development server
make test          # Run tests
make check         # Run all checks (lint + typecheck + tests)
```

### Development Server
```bash
# Start development server with auto-reload
uv run python -m uvicorn app.main:app --reload

# Alternative method (use uv run for proper module resolution)
uv run python -m app.main
```

### Environment Setup
```bash
# Install/sync dependencies
uv sync

# Install with development dependencies
uv sync --group dev --group test

# Create .env file with required variables:
# MONGODB_URI=mongodb://localhost:27017
# DATABASE_NAME=hnf1b_db
# JWT_SECRET=your-secret-key
```

### Data Migration
```bash
# Import data from spreadsheets to MongoDB
uv run python migrate_from_sheets.py
```

### Code Quality Tools
```bash
# Install development dependencies (automatically included with sync)
uv sync --group dev --group test

# Format code with Black
uv run black .

# Sort imports with isort
uv run isort .

# Run linting with flake8
uv run flake8 .

# Run type checking with mypy
uv run mypy app/

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_specific_file.py

# Run specific test
uv run pytest tests/test_file.py::test_function_name
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

MongoDB collections with their relationships:

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

3. **Database Access**: Async MongoDB operations using Motor driver through `app/database.py`

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
   - `MONGODB_URI` - MongoDB connection string
   - `DATABASE_NAME` - Database name
   - `JWT_SECRET` - Secret for JWT token signing

3. **Data validation**: The migration script and API share Pydantic models for consistency

4. **Async operations**: All database operations use async/await patterns with Motor

5. **File locations**: 
   - Data files in `/data` directory (VCF, VEP, and reference genome files)
   - API code in `/app` directory with modular endpoint organization
   - Dependencies managed in `pyproject.toml` and `uv.lock`
   - Migration script at root level: `migrate_from_sheets.py`