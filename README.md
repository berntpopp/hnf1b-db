# HNF1B Database - Full Stack Monorepo

GA4GH Phenopackets v2 compliant database for HNF1B clinical and genetic data. A unified full-stack application with FastAPI backend and Vue.js frontend.

## 🏗️ Project Structure

```
hnf1b-db/
├── backend/              # FastAPI REST API
│   ├── app/             # FastAPI application
│   ├── migration/       # Data migration scripts
│   ├── tests/           # Backend tests
│   ├── alembic/         # Database migrations
│   ├── pyproject.toml   # Python dependencies
│   └── Makefile         # Backend commands
├── frontend/            # Vue.js application
│   ├── src/            # Vue components & views
│   ├── public/         # Static assets
│   ├── package.json    # Node dependencies
│   └── Makefile        # Frontend commands
├── docs/               # Documentation
├── docker-compose.yml  # Full stack (development)
├── docker-compose.services.yml  # Services only (hybrid mode)
└── Makefile            # Unified commands
```

## 🚀 Quick Start

### Hybrid Development (Recommended)

**Prerequisites:** Python 3.10+, Node.js 16+, Docker, uv package manager

```bash
# 1. Install dependencies
make dev              # Install backend + frontend dependencies

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with database settings and JWT_SECRET

# 3. Start services (PostgreSQL + Redis)
make hybrid-up

# 4. Start backend (Terminal 1)
make backend          # http://localhost:8000

# 5. Start frontend (Terminal 2)
make frontend         # http://localhost:5173
```

### Full Docker Mode

```bash
# Start everything in Docker
make dev-up

# Access:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

## 📋 Development Commands

Run from **project root**:

```bash
make help          # Show all available commands
make status        # Show system status

# Hybrid mode (recommended)
make hybrid-up     # Start services (DB + Redis)
make backend       # Run backend locally
make frontend      # Run frontend locally
make hybrid-down   # Stop services

# Full Docker mode
make dev-up        # Start full stack
make dev-down      # Stop full stack
make dev-logs      # Show logs

# Backend
make test          # Run tests
make format        # Format code
make lint          # Lint code
make check         # Run all checks

# Database
make db-migrate    # Create migration
make db-upgrade    # Apply migrations
make phenopackets-migrate  # Import data

# Cleanup
make clean         # Clean backend cache
make clean-all     # Stop all + clean data
```

### Component-Specific Commands

**Backend** (from `backend/`):
```bash
cd backend
make server        # Start dev server
make test          # Run tests
make check         # Lint + typecheck + test
```

**Frontend** (from `frontend/`):
```bash
cd frontend
make dev           # Start dev server
make build         # Build for production
make lint          # Lint and fix code
```

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL with SQLAlchemy
- **Cache**: Redis
- **Auth**: JWT tokens
- **Tools**: uv (dependencies), ruff (linting/formatting), mypy (type checking)

### Frontend
- **Framework**: Vue 3 with Composition API
- **UI**: Vuetify 3 (Material Design)
- **Build**: Vite 6
- **Router**: Vue Router 4
- **HTTP**: Axios with JSON:API interceptors
- **Visualization**: D3.js

### Development
- **Containerization**: Docker & Docker Compose
- **Monorepo**: Hierarchical Makefiles for unified commands
- **Standards**: GA4GH Phenopackets v2, VRS 2.0

## 💡 Why Monorepo?

This project uses a monorepo structure (backend + frontend in one repository) for:

- **Single Source of Truth**: All code in one place, easier version control
- **Simplified Development**: One `git clone`, one setup process
- **Coordinated Releases**: Frontend/backend changes in single commit
- **Shared Tooling**: Common CI/CD, linting, Docker orchestration
- **Better Documentation**: Architecture docs alongside code
- **Proven Pattern**: Follows successful [kidney-genetics-db](https://github.com/halbritter-lab/kidney-genetics-db) structure

Industry best practices recommend separate `backend/` and `frontend/` folders for FastAPI + Vue.js monorepos.

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

Create `.env` file in the `backend/` directory:
```bash
cd backend
cp .env.example .env
# Edit .env with your settings
```

Required variables:
```
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db
JWT_SECRET=your-secret-key  # Generate with: openssl rand -hex 32
```

## Data Import

The project includes a direct Google Sheets to GA4GH Phenopackets v2 migration system that imports clinical and genetic data directly into the international standard format.

### Prerequisites

```bash
# 1. Start database services
make hybrid-up     # Start PostgreSQL and Redis containers

# 2. Verify environment
# Ensure .env file exists with valid DATABASE_URL pointing to hnf1b_phenopackets database
```

### Import Commands

```bash
# Full production import (processes all 864 individuals)
make phenopackets-migrate

# Limited test import (processes 20 individuals, faster for development)
make phenopackets-migrate-test

# Dry run - outputs to JSON file without database changes
make phenopackets-migrate-dry

# Alternative: Run directly with Python
uv run python migration/direct_sheets_to_phenopackets.py          # Full import
uv run python migration/direct_sheets_to_phenopackets.py --test   # Test import
uv run python migration/direct_sheets_to_phenopackets.py --dry-run # Dry run
```

### Data Sources

The migration system processes data from multiple sources:

1. **Google Sheets**: Clinical and genetic data from configured spreadsheet
   - Individual demographics and clinical reports
   - Publication metadata with PMID and DOI identifiers
   - Variant classifications with original and standardized nomenclature
   - Temporal data with complex age formats (e.g., "1y9m", "prenatal")

2. **Genomic Files** (in `/data/` directory):
   - `HNF1B_all_small.vcf` - Small genetic variants (182 variants)
   - `HNF1B_all_large.vcf` - Large structural variants (19 variants)  
   - `HNF1B_all_small.vep.txt` - VEP annotations for small variants (303 annotations)
   - `HNF1B_all_large.vep.txt` - VEP annotations for large variants (53,855 annotations)
   - `GRCh38-v1.6_*.tsv.gz` - CADD pathogenicity scores

### Migration System Architecture

The direct migration system is located in `backend/migration/` directory:

```
backend/migration/
├── direct_sheets_to_phenopackets.py  # Main migration orchestrator
├── phenopackets/     # Phenopacket builders and mappers
├── vrs/              # VRS variant representation
├── data_sources/     # Data source loaders
└── database/         # Database storage operations
```

### Features

- **Direct conversion**: Google Sheets data directly to GA4GH Phenopackets v2 format
- **Deduplication**: Automatically consolidates multiple rows per individual
- **Test mode**: Processes limited dataset (20 individuals) for faster development
- **Dry run mode**: Outputs to JSON file for inspection without database changes
- **HPO mapping**: Automatic mapping of clinical terms to Human Phenotype Ontology
  - Special onset terms mapped to HPO (prenatal → HP:0034199, congenital → HP:0003577)
- **MONDO diseases**: Proper disease classification using MONDO ontology
- **Variant handling**: Prioritizes Varsome format, falls back to other formats
  - Preserves original notation alongside standardized HGVS nomenclature
  - **VRS 2.0 compliance**: Generates GA4GH VRS-compliant variant identifiers with proper digests
- **Age parsing**: Handles complex formats (1y9m → P1Y9M ISO 8601 duration)
- **Publication references**: PMID and DOI identifiers with proper GA4GH ExternalReference format
- **Evidence tracking**: Complete provenance with timestamps and publication attribution

### Import Process

The direct migration:

1. **Loads Google Sheets data**: Fetches clinical and genetic data
2. **Groups by individual**: Consolidates 939 rows into 864 unique individuals
3. **Builds Phenopackets**: Creates GA4GH v2 compliant phenopackets
4. **Maps ontologies**: HPO terms for phenotypes, MONDO for diseases
5. **Stores in database**: Saves as JSONB documents in PostgreSQL

### Typical Output

```
Loading data from Google Sheets...
Loaded 939 rows from individuals sheet
Loaded 160 rows from publications sheet
Created publication map with 320 entries
Processing 864 individuals...
Building phenopackets: 100%|████████████| 864/864 [00:01<00:00, 681.39it/s]
Built 864 phenopackets
Storing phenopackets: 100%|████████████| 864/864 [00:02<00:00, 327.69it/s]
Successfully stored 864 phenopackets

============================================================
MIGRATION SUMMARY
============================================================
Total phenopackets created: 864
With phenotypic features: 830 (96%)
With genetic variants: 864 (100%)
With disease diagnoses: 864 (100%)
Sex distribution: {'UNKNOWN_SEX': 187, 'FEMALE': 329, 'MALE': 348}
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

# Install all dependencies (from root directory)
make dev

# Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env with your settings (see Environment Configuration below)
```

### 3. Environment Configuration

Create/edit `backend/.env` file with required variables:

```bash
# Copy template
cp backend/.env.example backend/.env

# PostgreSQL Database (matches docker-compose.services.yml)
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db

# JWT Authentication (REQUIRED - generate with: openssl rand -hex 32)
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
python migration/direct_sheets_to_phenopackets.py --test  # instead of 'make phenopackets-migrate-test'
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

## 🌐 Frontend Application

The Vue.js frontend provides an interactive interface for browsing and managing HNF1B data.

### Features
- Browse individuals, variants, and publications
- Interactive data visualizations (D3.js charts)
- Advanced search across all collections
- Aggregated statistics dashboard
- Material Design UI (Vuetify 3)

### Development Setup

**Option 1: Hybrid Mode (Recommended)**
```bash
make hybrid-up     # Start services
make frontend      # Start frontend dev server
# Access: http://localhost:5173
```

**Option 2: Standalone**
```bash
cd frontend
npm install
npm run dev
# Access: http://localhost:5173
```

**Option 3: Full Docker**
```bash
make dev-up
# Access: http://localhost:3000
```

### Configuration

Create `frontend/.env`:
```bash
cp frontend/.env.example frontend/.env
```

Configure API URL:
```env
VITE_API_URL=http://localhost:8000
```

The Vite proxy forwards `/api` requests to the backend automatically.

### API Integration

The frontend includes:
- JWT authentication flow
- HPO term autocomplete for phenotype selection
- Phenopackets v2 CRUD operations
- Real-time statistics and aggregations

See component documentation in `frontend/README.md` and `frontend/CLAUDE.md`.

### API Documentation
- Interactive API docs: http://localhost:8000/docs
- Phenopackets endpoints: `/api/v2/phenopackets/`
- HPO proxy endpoints: `/api/v2/hpo/`
- Authentication: `/api/v2/auth/`

For detailed information:
- Backend details: [backend/README.md](backend/README.md)
- Frontend details: [frontend/README.md](frontend/README.md)
- Migration guide: [PHENOPACKETS_MIGRATION_GUIDE.md](PHENOPACKETS_MIGRATION_GUIDE.md)