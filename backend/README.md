# HNF1B-API Backend

This directory contains the backend components of the HNF1B-API project.

## Structure

```
backend/
├── app/                # FastAPI application
│   ├── phenopackets/  # Phenopackets v2 endpoints
│   └── services/      # Shared services
├── migration/          # Data migration scripts
│   ├── phenopackets/  # Phenopacket builders
│   ├── vrs/           # VRS variant representation
│   ├── data_sources/  # Data source loaders
│   └── database/      # Database storage
├── tests/             # Test suite
├── alembic/           # Database migrations
├── examples/          # Example scripts
└── pyproject.toml     # Python dependencies
```

## Quick Start

```bash
# From the backend directory
make dev              # Install all dependencies
make server           # Start development server

# Or from the project root
make server           # Uses backend/Makefile internally
```

## Development

See the root [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) for comprehensive documentation.

### Common Commands

```bash
make help             # Show all available commands
make test             # Run tests
make check            # Run all checks (lint + typecheck + tests)
make format           # Format code with ruff
```

## Database Services

Database services (PostgreSQL, Redis) are managed from the project root:

```bash
# From project root
make hybrid-up        # Start services
make hybrid-down      # Stop services
```

## Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

Required variables:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT token signing (generate with `openssl rand -hex 32`)

## API Documentation

### Phenopackets Module

Comprehensive API for phenopacket operations, variant search, and clinical queries.

**Module Documentation:** [app/phenopackets/README.md](app/phenopackets/README.md)

**Key Features:**
- GA4GH Phenopackets v2 CRUD operations
- **Variant Search** with 8 search fields (HGVS, coordinates, type, classification, etc.)
- Clinical feature queries (renal, genital, diabetes, hypomagnesemia)
- Aggregation endpoints for statistics

**Variant Search API:** [docs/api/VARIANT_SEARCH.md](../docs/api/VARIANT_SEARCH.md)

### Variant Annotation Module

Comprehensive VEP-powered variant annotation, validation, and recoding system.

**Module Documentation:** [app/phenopackets/validation/variant_validator.py](app/phenopackets/validation/variant_validator.py)

**Key Features:**
- **Variant Validation** - Validate HGVS, VCF, and rsID notations
- **VEP Annotation** - Rich annotations from Ensembl VEP (consequences, CADD, gnomAD)
- **Variant Recoding** - Convert between formats (HGVS ↔ VCF ↔ rsID)
- **Notation Suggestions** - Smart suggestions for fixing invalid notations
- **Rate Limiting** - Token bucket algorithm (15 req/sec)
- **LRU Caching** - 1000-variant cache for performance
- **Format Support** - HGVS, VCF, rsID, genomic/coding/protein

**API Endpoints:**
- `POST /api/v2/variants/validate` - Validate variant notation
- `POST /api/v2/variants/annotate` - Get VEP annotations
- `POST /api/v2/variants/recode` - Convert between formats
- `GET /api/v2/variants/suggest/{notation}` - Get notation suggestions

**Documentation:**
- **API Reference:** [docs/api/variant-annotation.md](../docs/api/variant-annotation.md)
- **User Guide:** [docs/user-guide/variant-annotation.md](../docs/user-guide/variant-annotation.md)
- **Developer Guide:** [docs/variant-annotation-implementation-plan.md](../docs/variant-annotation-implementation-plan.md)

**Test Coverage:**
- 83 unit tests + 18 integration tests
- 99% code coverage (332/337 lines)
- Tests run in ~7 seconds

### Interactive API Docs

When the server is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Testing

Run the test suite:

```bash
make test             # Run all tests
make check            # Run lint + typecheck + tests
```

**Testing Documentation:** [tests/README.md](tests/README.md)

**Key Test Files:**
- `test_variant_search.py` - Variant search validation (40+ tests)
- `test_variant_validator_enhanced.py` - Variant annotation unit tests (83 tests, 99% coverage)
- `test_variant_validator_api_integration.py` - Variant annotation API tests (18 tests)
- `test_batch_endpoints.py` - Batch endpoint performance
- `test_jsonb_indexes.py` - Database index verification
- `test_phenopackets.py` - Core CRUD operations

## Database Migrations

Run migrations with Alembic:

```bash
# Upgrade to latest version
uv run alembic upgrade head

# Check current version
uv run alembic current

# See migration history
uv run alembic history
```

**Recent Migrations:**
- `001_initial_phenopackets_v2_schema.py` - Phenopackets v2 tables
- `002_add_jsonb_path_indexes.py` - JSONB GIN indexes
- `003_add_variant_search_indexes.py` - Variant search optimization (10x faster)
