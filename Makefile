.PHONY: help install dev test lint format typecheck server clean hybrid-up hybrid-down db-migrate db-upgrade db-reset import-data

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

dev:  ## Install dependencies including dev and test groups
	uv sync --group dev --group test

test:  ## Run tests
	uv run pytest

lint:  ## Run linting (ruff)
	uv run ruff check .

format:  ## Format code (ruff)
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Run type checking (mypy)
	uv run mypy app/

server:  ## Start development server
	uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Hybrid Development Commands
hybrid-up:  ## Start PostgreSQL and Redis services in Docker
	docker-compose -f docker-compose.services.yml up -d
	@echo "Services started. Use 'make server' to start the FastAPI development server."

hybrid-down:  ## Stop PostgreSQL and Redis services
	docker-compose -f docker-compose.services.yml down

# Database Migration Commands
db-migrate:  ## Create new Alembic migration (usage: make db-migrate MESSAGE="description")
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade:  ## Apply pending database migrations
	uv run alembic upgrade head

db-reset:  ## Reset database (drop and recreate all tables)
	uv run alembic downgrade base
	uv run alembic upgrade head

# Data Import Commands  
import-data:  ## Import data from Google Sheets to PostgreSQL
	uv run python migration/migrate.py

import-data-test:  ## Import limited test data from Google Sheets
	uv run python migration/migrate.py --test

check: lint typecheck test  ## Run all checks (lint, typecheck, test)

clean:  ## Remove virtual environment and cache
	rm -rf .venv
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

reset: clean install  ## Clean and reinstall everything