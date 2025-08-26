.PHONY: help install dev test lint format typecheck server clean

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

dev:  ## Install dependencies including dev and test groups
	uv sync --group dev --group test

test:  ## Run tests
	uv run pytest

lint:  ## Run linting (flake8)
	uv run flake8 .

format:  ## Format code (black and isort)
	uv run black .
	uv run isort .

typecheck:  ## Run type checking (mypy)
	uv run mypy app/

server:  ## Start development server
	uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:  ## Run data migration
	uv run python migrate_from_sheets.py

check: lint typecheck test  ## Run all checks (lint, typecheck, test)

clean:  ## Remove virtual environment and cache
	rm -rf .venv
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

reset: clean install  ## Clean and reinstall everything