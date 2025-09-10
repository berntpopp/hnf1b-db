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

```bash
make import-data   # Import from Google Sheets to PostgreSQL
```

## Requirements

- Python 3.8+
- Docker (for PostgreSQL/Redis containers)
- uv package manager