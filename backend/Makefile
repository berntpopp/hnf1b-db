.PHONY: help install dev check-env test lint format typecheck server clean db-migrate db-upgrade db-reset phenopackets-migrate phenopackets-migrate-test phenopackets-migrate-dry

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

dev:  ## Install dependencies including dev and test groups
	uv sync --group dev --group test

check-env:  ## Verify virtual environment integrity
	@echo "🔍 Checking virtual environment..."
	@uv run python -c "import sys; sys.exit(0 if '.venv' in sys.executable else 1)" || \
		(echo "❌ ERROR: Not using project venv!"; \
		 echo "Current: $$(uv run which python)"; \
		 echo "Expected: $$(pwd)/.venv/bin/python"; \
		 echo ""; \
		 echo "FIX: export UV_LINK_MODE=copy && rm -rf .venv && uv sync --group dev --group test"; \
		 exit 1)
	@echo "✅ Virtual environment OK"
	@echo "🔍 Checking critical dependencies..."
	@uv run python -c "import asyncpg, pytest" 2>/dev/null || \
		(echo "❌ ERROR: Missing dependencies!"; \
		 echo "FIX: uv sync --group dev --group test"; \
		 exit 1)
	@echo "✅ Dependencies OK"
	@echo "✅ Environment is healthy"

test: check-env  ## Run tests
	uv run pytest

lint: check-env  ## Run linting (ruff)
	uv run ruff check .

format:  ## Format code (ruff)
	uv run ruff format .
	uv run ruff check --fix .

typecheck: check-env  ## Run type checking (mypy)
	uv run mypy app/ migration/

server:  ## Start development server
	uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database Migration Commands
db-migrate:  ## Create new Alembic migration (usage: make db-migrate MESSAGE="description")
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade:  ## Apply pending database migrations
	uv run alembic upgrade head

db-reset:  ## Reset database (drop and recreate all tables)
	uv run alembic downgrade base
	uv run alembic upgrade head

# Phenopackets Migration Commands (Primary method for data import)
phenopackets-migrate:  ## Migrate data directly from Google Sheets to Phenopackets format
	uv run python -m migration.direct_sheets_to_phenopackets

phenopackets-migrate-test:  ## Test migration with limited data (20 individuals)
	uv run python -m migration.direct_sheets_to_phenopackets --test

phenopackets-migrate-dry:  ## Dry run migration - outputs to JSON file without database
	uv run python -m migration.direct_sheets_to_phenopackets --test --dry-run

check: check-env lint typecheck test  ## Run all checks (lint, typecheck, test)

clean:  ## Remove virtual environment and cache
	rm -rf .venv
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

reset: clean install  ## Clean and reinstall everything
