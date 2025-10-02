.PHONY: help install dev test lint format typecheck server clean hybrid-up hybrid-down \
        dev-up dev-down dev-logs backend frontend status db-migrate db-upgrade db-reset \
        phenopackets-migrate phenopackets-migrate-test phenopackets-migrate-dry check reset clean-all

# Detect docker compose command
DOCKER_COMPOSE := $(shell if command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

help:  ## Show this help message
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║     HNF1B Database - Full Stack Development Commands          ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "🚀 HYBRID DEVELOPMENT (Recommended):"
	@echo "  make hybrid-up       - Start DB/Redis in Docker, run backend/frontend locally"
	@echo "  make hybrid-down     - Stop hybrid mode services"
	@echo "  make backend         - Run backend locally (after hybrid-up)"
	@echo "  make frontend        - Run frontend locally (after hybrid-up)"
	@echo ""
	@echo "🐳 FULL DOCKER DEVELOPMENT:"
	@echo "  make dev-up          - Start full stack in Docker"
	@echo "  make dev-down        - Stop all Docker services"
	@echo "  make dev-logs        - Show Docker logs"
	@echo ""
	@echo "🔧 BACKEND COMMANDS:"
	@echo "  make install         - Install backend dependencies"
	@echo "  make dev             - Install all dependencies (dev + test)"
	@echo "  make server          - Start backend development server"
	@echo "  make test            - Run backend tests"
	@echo "  make lint            - Lint backend code"
	@echo "  make format          - Format backend code"
	@echo "  make typecheck       - Run type checking"
	@echo "  make check           - Run all checks (lint + typecheck + test)"
	@echo ""
	@echo "🗄️ DATABASE:"
	@echo "  make db-migrate      - Create new migration"
	@echo "  make db-upgrade      - Apply migrations"
	@echo "  make db-reset        - Reset database"
	@echo "  make phenopackets-migrate      - Import all data from Google Sheets"
	@echo "  make phenopackets-migrate-test - Import test data (20 individuals)"
	@echo ""
	@echo "📊 MONITORING:"
	@echo "  make status          - Show system status"
	@echo ""
	@echo "🧹 CLEANUP:"
	@echo "  make clean           - Remove backend cache files"
	@echo "  make clean-all       - Stop all services and clean data"
	@echo ""

install:  ## Install dependencies
	cd backend && uv sync

dev:  ## Install dependencies including dev and test groups
	cd backend && uv sync --group dev --group test

test:  ## Run tests
	cd backend && uv run pytest

lint:  ## Run linting (ruff)
	cd backend && uv run ruff check .

format:  ## Format code (ruff)
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

typecheck:  ## Run type checking (mypy)
	cd backend && uv run mypy app/ migration/

server:  ## Start development server
	cd backend && uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Hybrid Development Commands (Services in Docker, Apps local)
hybrid-up:  ## Start PostgreSQL and Redis services in Docker
	$(DOCKER_COMPOSE) -f docker-compose.services.yml up -d
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "Next steps:"
	@echo "  Terminal 1: make backend   # Start backend on http://localhost:8000"
	@echo "  Terminal 2: make frontend  # Start frontend on http://localhost:5173"
	@echo ""

hybrid-down:  ## Stop PostgreSQL and Redis services
	$(DOCKER_COMPOSE) -f docker-compose.services.yml down

# Full Docker Development Commands
dev-up:  ## Start full stack in Docker
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✅ Full stack started!"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo ""

dev-down:  ## Stop all Docker services
	$(DOCKER_COMPOSE) down

dev-logs:  ## Show Docker logs
	$(DOCKER_COMPOSE) logs -f

# Component Commands
backend:  ## Run backend locally
	cd backend && make server

frontend:  ## Run frontend locally
	cd frontend && make dev

# Status Command
status:  ## Show system status
	@echo "=== System Status ==="
	@echo ""
	@echo "Docker Containers:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Backend Status:"
	@-curl -s http://localhost:8000/health 2>/dev/null | head -1 || echo "Backend not running"
	@echo ""
	@echo "Frontend Status:"
	@-curl -s http://localhost:5173 >/dev/null 2>&1 && echo "Frontend running on port 5173" || echo "Frontend not running"
	@echo ""

# Database Migration Commands
db-migrate:  ## Create new Alembic migration (usage: make db-migrate MESSAGE="description")
	cd backend && uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade:  ## Apply pending database migrations
	cd backend && uv run alembic upgrade head

db-reset:  ## Reset database (drop and recreate all tables)
	cd backend && uv run alembic downgrade base
	cd backend && uv run alembic upgrade head

# Phenopackets Migration Commands (Primary method for data import)
phenopackets-migrate:  ## Migrate data directly from Google Sheets to Phenopackets format
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets

phenopackets-migrate-test:  ## Test migration with limited data (20 individuals)
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets --test

phenopackets-migrate-dry:  ## Dry run migration - outputs to JSON file without database
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets --test --dry-run

check: lint typecheck test  ## Run all checks (lint, typecheck, test)

clean:  ## Remove virtual environment and cache
	cd backend && rm -rf .venv
	cd backend && rm -rf __pycache__
	find backend -type d -name "__pycache__" -exec rm -rf {} +
	find backend -type f -name "*.pyc" -delete

clean-all:  ## Stop all services and clean data
	@echo "Stopping all services..."
	@$(DOCKER_COMPOSE) down -v 2>/dev/null || true
	@$(DOCKER_COMPOSE) -f docker-compose.services.yml down -v 2>/dev/null || true
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "vite.*5173" 2>/dev/null || true
	@echo "✅ All services stopped and data cleaned"

reset: clean install  ## Clean and reinstall everything