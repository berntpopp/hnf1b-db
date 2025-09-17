# HNF1B-API

A FastAPI-based REST API for managing clinical and genetic data for individuals with HNF1B disease.

## Quick Start

**Prerequisites:** Python 3.10+, Docker, uv package manager ([install guide](#1-install-uv-package-manager))

```bash
# 1. Install dependencies
make dev

# 2. Configure environment  
cp .env.example .env
# Edit .env with your database settings

# 3. Start services and database
make hybrid-up      # Start PostgreSQL and Redis containers
make db-upgrade     # Apply database schema

# 4. Start development server
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

### Phenopackets v2 API (Current)
- `/api/v2/phenopackets` - GA4GH Phenopackets CRUD operations
- `/api/v2/clinical` - Clinical feature-specific queries
- `/api/v2/auth` - JWT authentication
- `/api/v2/hpo` - HPO term search and validation
- `/api/v2/docs` - Interactive API documentation

### Legacy Endpoints (Being phased out)
- `/api/individuals` - Patient demographics
- `/api/variants` - Genetic variants
- `/api/publications` - Publication metadata
- `/api/search` - Cross-collection search
- `/api/aggregations` - Data statistics

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

## Installation & Setup

### Prerequisites

- **Python 3.10+** (required for modern type hints)
- **Docker & Docker Compose** (for PostgreSQL/Redis services)
- **uv package manager** (for dependency management)

### 1. Install uv Package Manager

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative (with pip):**
```bash
pip install uv
```

### 2. Clone and Setup Project

```bash
# Clone repository
git clone <repository-url>
cd hnf1b-api

# Install all dependencies (including dev and test groups)
make dev
# OR manually:
uv sync --group dev --group test

# Create environment file
cp .env.example .env
# Edit .env with your settings (see Environment Configuration below)
```

### 3. Environment Configuration

Create/edit `.env` file with required variables:

```bash
# PostgreSQL Database (matches docker-compose.services.yml)
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db

# JWT Authentication
JWT_SECRET=your-secret-key-change-this-in-production

# Development Settings
DEBUG=true
```

### 4. Start Services & Database

```bash
# Start PostgreSQL and Redis containers
make hybrid-up

# Apply database schema
make db-upgrade

# Verify services are running
docker ps
```

### 5. Run the Application

```bash
# Start development server
make server

# API will be available at:
# - http://localhost:8000 (API)  
# - http://localhost:8000/docs (API documentation)
```

## Alternative Installation (without uv)

If you prefer using pip/virtualenv:

```bash
# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate
# Activate (Windows)  
.venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt  # Includes dev and test dependencies

# Follow steps 3-5 above, but replace 'make' commands:
python -m uvicorn app.main:app --reload  # instead of 'make server'
python migration/migrate.py --test       # instead of 'make import-data-test'
```

### Dependency Files Available

- `requirements.txt` - Core runtime dependencies only
- `requirements-dev.txt` - All dependencies including dev tools and tests
- `pyproject.toml` - Modern Python project configuration (preferred with uv)

## Troubleshooting

### uv Issues
- **"uv not found"**: Ensure uv is in your PATH, restart terminal
- **Permission errors**: On Linux/macOS, ensure `~/.local/bin` is in PATH
- **Python version**: uv requires Python 3.8+, project needs 3.10+

### Database Issues  
- **Connection refused**: Ensure `make hybrid-up` completed successfully
- **Schema errors**: Run `make db-upgrade` to apply migrations
- **Port conflicts**: Check if port 5433 is available (`lsof -i :5433`)

### Docker Issues
- **Services won't start**: Check Docker is running and ports 5433, 6379 available
- **Permission errors**: Ensure user is in docker group (Linux)

### Alternative Database Setup
If Docker isn't available, install PostgreSQL locally:

```bash
# Update DATABASE_URL in .env to match your local setup
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/hnf1b_db
```

## Frontend Integration

### Authentication
The API uses JWT authentication for data modification. Demo credentials are available for testing:

```javascript
// Login to get JWT token
const response = await axios.post('/api/v2/auth/login', {
  username: 'researcher',  // or 'admin'
  password: 'research123'   // or 'admin123'
});
axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
```

### HPO Term Search
The API provides HPO term search endpoints for phenotype selection:

```javascript
// Search HPO terms for autocomplete
await axios.get('/api/v2/hpo/autocomplete?q=kidney&limit=10');

// Get common HNF1B-related terms
await axios.get('/api/v2/hpo/common-terms?category=renal');

// Validate HPO term IDs
await axios.get('/api/v2/hpo/validate?term_ids=HP:0012622,HP:0000107');
```

### Creating New Patients
With authentication, you can add new patients using the Phenopackets format:

```javascript
await axios.post('/api/v2/phenopackets/', {
  phenopacket: {
    id: "phenopacket:HNF1B:NEW001",
    subject: { id: "NEW001", sex: "FEMALE" },
    phenotypicFeatures: [
      { type: { id: "HP:0012622", label: "Chronic kidney disease" }}
    ],
    meta_data: {
      created: new Date().toISOString(),
      created_by: "researcher"
    }
  }
});
```

### API Documentation
- Interactive API docs: http://localhost:8000/api/v2/docs
- Phenopackets endpoints: `/api/v2/phenopackets/`
- HPO proxy endpoints: `/api/v2/hpo/`
- Authentication: `/api/v2/auth/`

For detailed migration information, see [PHENOPACKETS_MIGRATION_GUIDE.md](PHENOPACKETS_MIGRATION_GUIDE.md)