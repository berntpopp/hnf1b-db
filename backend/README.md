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
