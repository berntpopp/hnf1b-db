# HNF1B-API

A FastAPI-based REST API for managing clinical and genetic data for individuals with HNF1B disease.

## Quick Start

```bash
# Install dependencies
make dev

# Start PostgreSQL and Redis containers
make hybrid-up

# Start development server
make server

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Development Commands

```bash
make help          # Show all available commands
make check         # Run all checks (lint + typecheck + tests)
make test          # Run tests
make format        # Format code with ruff
make lint          # Lint code with ruff
make typecheck     # Type check with mypy
make hybrid-down   # Stop containers
```

## Tech Stack

- **API**: FastAPI with async/await
- **Database**: PostgreSQL with SQLAlchemy
- **Cache**: Redis
- **Auth**: JWT tokens
- **Tools**: uv (dependencies), ruff (linting/formatting), mypy (types)
- **Development**: Docker containers for services

## API Endpoints

- `/api/auth` - JWT authentication
- `/api/individuals` - Patient demographics
- `/api/variants` - Genetic variants with classifications
- `/api/publications` - Publication metadata
- `/api/proteins` - Protein data
- `/api/genes` - Gene information
- `/api/search` - Cross-collection search
- `/api/aggregations` - Data statistics and summaries

## Environment Setup

Create `.env` file:
```
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db
JWT_SECRET=your-secret-key
```

## Data Import

The project includes a comprehensive PostgreSQL migration system that imports data from Google Sheets and processes genomic annotation files. This system handles the complete data pipeline for the HNF1B clinical database.

### Prerequisites

```bash
# 1. Start database services
make hybrid-up     # Start PostgreSQL and Redis containers

# 2. Apply database schema
make db-upgrade    # Apply all database migrations

# 3. Verify environment
# Ensure .env file exists with valid DATABASE_URL and JWT_SECRET
```

### Import Commands

```bash
# Full production import (processes all ~900+ individuals)
make import-data

# Limited test import (processes ~20 individuals, faster for development)
make import-data-test

# Alternative: Run directly with Python
uv run python migration/migrate.py          # Full import
uv run python migration/migrate.py --test   # Test import
```

### Data Sources

The migration system processes data from multiple sources:

1. **Google Sheets**: Clinical and genetic data from configured spreadsheet
   - User/reviewer information
   - Publication metadata with PubMed enrichment
   - Individual demographics and clinical reports
   - Variant classifications and annotations

2. **Genomic Files** (in `/data/` directory):
   - `HNF1B_all_small.vcf` - Small genetic variants (182 variants)
   - `HNF1B_all_large.vcf` - Large structural variants (19 variants)  
   - `HNF1B_all_small.vep.txt` - VEP annotations for small variants (303 annotations)
   - `HNF1B_all_large.vep.txt` - VEP annotations for large variants (53,855 annotations)
   - `GRCh38-v1.6_*.tsv.gz` - CADD pathogenicity scores

### Migration System Architecture

Located in `/migration/` directory with modular design:

```
migration/
├── migrate.py              # Main orchestrator script
└── modules/
    ├── users.py           # Import user/reviewer data
    ├── publications.py    # Import publications with PubMed enrichment
    ├── individuals.py     # Import patients and clinical reports
    ├── variants.py        # Import genetic variants with classifications
    ├── proteins.py        # Import protein structure data
    ├── genes.py           # Import gene structure from Ensembl API
    └── genomics.py        # Process VCF/VEP/CADD files
```

### Features

- **PostgreSQL native**: Uses SQLAlchemy with async/await patterns
- **Duplicate handling**: Skips existing records to prevent re-import conflicts
- **Test mode**: Processes limited dataset for faster development cycles
- **Error resilience**: Continues processing despite individual record failures
- **Progress tracking**: Detailed logging of import progress and statistics
- **Data validation**: Uses Pydantic models for consistent data validation

### Import Process

The migration runs in 6 phases:

1. **Users**: Import reviewer/user accounts
2. **Publications**: Import and enrich publication metadata via PubMed API
3. **Individuals**: Import patient demographics and clinical phenotype reports
4. **Proteins**: Import HNF1B protein structure and domain information
5. **Genes**: Import HNF1B gene structure from Ensembl API
6. **Variants**: Import genetic variants with annotations from genomic files

### Typical Output

```
============================================================
Starting PostgreSQL Migration from Google Sheets
*** TEST MODE - Limited data import ***
============================================================

--- Phase 1: Importing Users ---
[import_users] Successfully imported 8 users

--- Phase 2: Importing Publications ---
[import_publications] Successfully imported 10 publications

--- Phase 3: Importing Individuals ---
[import_individuals] Successfully processed 17 individuals with 20 reports

--- Phase 4: Importing Proteins ---
[import_proteins] Successfully created protein structure

--- Phase 5: Importing Genes ---
[import_genes] Successfully created gene structure  

--- Phase 6: Importing Variants ---
[import_variants] Successfully imported 200 variants

============================================================
Migration completed successfully!
============================================================
```

## Requirements

- Python 3.8+
- Docker (for PostgreSQL/Redis containers)
- uv package manager