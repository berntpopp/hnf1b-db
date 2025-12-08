.PHONY: help install dev test lint format typecheck server clean hybrid-up hybrid-down \
        dev-up dev-down dev-logs backend frontend status db-migrate db-upgrade db-reset db-init db-create-admin \
        phenopackets-migrate phenopackets-migrate-test phenopackets-migrate-dry check reset clean-all \
        docker-build docker-npm docker-npm-bg docker-down docker-logs docker-clean docker-clean-all \
        docker-dev docker-dev-bg docker-health docker-ps docker-db-migrate docker-db-init docker-db-backup \
        docker-shell-api docker-shell-db docker-import-full docker-import-test \
        publications-sync publications-sync-dry publications-sync-test docker-publications-sync \
        variants-sync variants-sync-dry variants-sync-test docker-variants-sync

# Detect docker compose command
DOCKER_COMPOSE := $(shell if command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

# Docker compose file paths
COMPOSE_BASE := docker/docker-compose.yml
COMPOSE_NPM := docker/docker-compose.npm.yml
COMPOSE_DEV := docker/docker-compose.dev.yml
ENV_FILE := .env.docker

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
	@echo "  make dev-up          - Start full stack in Docker (with ports)"
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
	@echo "  make db-init         - Initialize database (migrations + admin user)"
	@echo "  make db-create-admin - Create/update admin user"
	@echo "  make db-migrate      - Create new migration"
	@echo "  make db-upgrade      - Apply migrations"
	@echo "  make db-reset        - Reset database"
	@echo "  make phenopackets-migrate      - Import all data from Google Sheets"
	@echo "  make phenopackets-migrate-test - Import test data (20 individuals)"
	@echo "  make publications-sync         - Sync publication metadata from PubMed"
	@echo "  make variants-sync             - Sync variant annotations from VEP"
	@echo ""
	@echo "📊 MONITORING:"
	@echo "  make status          - Show system status"
	@echo ""
	@echo "🧹 CLEANUP:"
	@echo "  make clean           - Remove backend cache files"
	@echo "  make clean-all       - Stop all services and clean data"
	@echo ""
	@echo "🐋 DOCKER PRODUCTION (NPM):"
	@echo "  make docker-build    - Build production Docker images"
	@echo "  make docker-npm      - Start NPM production mode (foreground)"
	@echo "  make docker-npm-bg   - Start NPM production mode (background)"
	@echo "  make docker-down     - Stop all containers (preserves data)"
	@echo "  make docker-logs     - View container logs"
	@echo "  make docker-health   - Check container health"
	@echo "  make docker-clean    - Clean up (preserves volumes)"
	@echo "  make docker-clean-all - Full clean (DATA LOSS!)"
	@echo ""
	@echo "💾 DOCKER DATABASE:"
	@echo "  make docker-db-migrate - Run migrations in Docker"
	@echo "  make docker-db-backup  - Backup database"
	@echo "  make docker-import-full - Import all data"
	@echo "  make docker-import-test - Import test data (20 records)"
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
	$(DOCKER_COMPOSE) -f $(COMPOSE_DEV) up -d
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "Next steps:"
	@echo "  Terminal 1: make backend   # Start backend on http://localhost:8000"
	@echo "  Terminal 2: make frontend  # Start frontend on http://localhost:5173"
	@echo ""

hybrid-down:  ## Stop PostgreSQL and Redis services
	$(DOCKER_COMPOSE) -f $(COMPOSE_DEV) down

# Full Docker Development Commands
dev-up:  ## Start full stack in Docker (with ports exposed)
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) up -d --build
	@echo ""
	@echo "✅ Full stack started!"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo ""

dev-down:  ## Stop all Docker services
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) down

dev-logs:  ## Show Docker logs
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) logs -f

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
	@$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) ps 2>/dev/null || echo "No containers running"
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

db-init:  ## Initialize database (run migrations + create admin user)
	cd backend && make db-init

db-create-admin:  ## Create or update admin user
	cd backend && make db-create-admin

# Phenopackets Migration Commands (Primary method for data import)
phenopackets-migrate:  ## Migrate data directly from Google Sheets to Phenopackets format
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets

phenopackets-migrate-test:  ## Test migration with limited data (20 individuals)
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets --test

phenopackets-migrate-dry:  ## Dry run migration - outputs to JSON file without database
	cd backend && uv run python -m migration.direct_sheets_to_phenopackets --test --dry-run

# Publication Metadata Sync Commands
publications-sync:  ## Sync all publication metadata from PubMed
	cd backend && uv run python scripts/sync_publication_metadata.py

publications-sync-dry:  ## Dry run - shows what would be fetched without changes
	cd backend && uv run python scripts/sync_publication_metadata.py --dry-run

publications-sync-test:  ## Sync first 10 publications (for testing)
	cd backend && uv run python scripts/sync_publication_metadata.py --limit 10

# Variant Annotation Sync Commands (Fetch VEP annotations for unique variants)
variants-sync:  ## Sync all variant annotations from VEP
	cd backend && uv run python scripts/sync_variant_annotations.py

variants-sync-dry:  ## Dry run - shows what would be fetched without changes
	cd backend && uv run python scripts/sync_variant_annotations.py --dry-run

variants-sync-test:  ## Sync first 10 variants (for testing)
	cd backend && uv run python scripts/sync_variant_annotations.py --limit 10

check: lint typecheck test  ## Run all checks (lint, typecheck, test)

clean:  ## Remove virtual environment and cache
	cd backend && rm -rf .venv
	cd backend && rm -rf __pycache__
	find backend -type d -name "__pycache__" -exec rm -rf {} +
	find backend -type f -name "*.pyc" -delete

clean-all:  ## Stop all services and clean data
	@echo "Stopping all services..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) down -v 2>/dev/null || true
	@$(DOCKER_COMPOSE) -f $(COMPOSE_DEV) down -v 2>/dev/null || true
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "vite.*5173" 2>/dev/null || true
	@echo "✅ All services stopped and data cleaned"

reset: clean install  ## Clean and reinstall everything

# ============================================
# Docker Production Targets (NPM)
# ============================================

docker-build:  ## Build production Docker images
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) build

docker-npm:  ## Start NPM production mode (foreground)
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) up --build

docker-npm-bg:  ## Start NPM production mode (background)
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) up -d --build

docker-down:  ## Stop all containers (preserves data)
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) down

docker-logs:  ## View container logs
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) logs -f

docker-logs-api:  ## View API container logs
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) logs -f hnf1b_api

docker-logs-frontend:  ## View frontend container logs
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) logs -f hnf1b_frontend

docker-clean:  ## Clean up (preserves volumes)
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) down --rmi local

docker-clean-all:  ## Full clean (removes volumes - DATA LOSS!)
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) down -v --rmi local

# ============================================
# Health & Status
# ============================================

docker-health:  ## Check container health status
	@echo "Checking container health..."
	@docker inspect --format='{{.Name}}: {{.State.Health.Status}}' hnf1b_api hnf1b_frontend hnf1b_db hnf1b_cache 2>/dev/null || \
	docker inspect --format='{{.Name}}: {{.State.Health.Status}}' hnf1b_api_npm hnf1b_frontend_npm hnf1b_db hnf1b_cache 2>/dev/null || \
	echo "Containers not running"

docker-ps:  ## Show running containers
	$(DOCKER_COMPOSE) -f $(COMPOSE_BASE) -f $(COMPOSE_NPM) --env-file $(ENV_FILE) ps

# ============================================
# Database Operations (Docker)
# ============================================
# Note: These targets auto-detect whether to use standard (hnf1b_api) or NPM
# (hnf1b_api_npm) container names based on which containers are running.

docker-db-migrate:  ## Run Alembic migrations in Docker
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER alembic upgrade head

docker-db-init:  ## Initialize database with admin user in Docker
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER python -m app.scripts.create_admin

docker-db-backup:  ## Backup database
	./docker/backup.sh

docker-shell-api:  ## Shell into API container
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Connecting to: $$API_CONTAINER"; \
	docker exec -it $$API_CONTAINER /bin/sh

docker-shell-db:  ## Connect to PostgreSQL CLI
	@DB_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_db$$' | head -1); \
	if [ -z "$$DB_CONTAINER" ]; then echo "Error: No DB container running"; exit 1; fi; \
	echo "Connecting to: $$DB_CONTAINER"; \
	docker exec -it $$DB_CONTAINER psql -U $${POSTGRES_USER:-hnf1b_user} -d $${POSTGRES_DB:-hnf1b_phenopackets}

# ============================================
# Data Import (Docker)
# ============================================

docker-import-full:  ## Run full data import in Docker
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER python -m migration.direct_sheets_to_phenopackets

docker-import-test:  ## Run test data import in Docker (20 records)
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER python -m migration.direct_sheets_to_phenopackets --test

docker-publications-sync:  ## Sync publication metadata from PubMed in Docker
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER python scripts/sync_publication_metadata.py

docker-variants-sync:  ## Sync variant annotations from VEP in Docker
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	docker exec $$API_CONTAINER python scripts/sync_variant_annotations.py

# Combined data import command (phenopackets + publications + variants)
docker-import-full-with-sync:  ## Full data import with publication and variant sync
	@API_CONTAINER=$$(docker ps --format '{{.Names}}' | grep -E '^hnf1b_api(_npm)?$$' | head -1); \
	if [ -z "$$API_CONTAINER" ]; then echo "Error: No API container running"; exit 1; fi; \
	echo "Using container: $$API_CONTAINER"; \
	echo "Step 1/3: Importing phenopackets..."; \
	docker exec $$API_CONTAINER python -m migration.direct_sheets_to_phenopackets; \
	echo "Step 2/3: Syncing publication metadata from PubMed..."; \
	docker exec $$API_CONTAINER python scripts/sync_publication_metadata.py; \
	echo "Step 3/3: Syncing variant annotations from VEP..."; \
	docker exec $$API_CONTAINER python scripts/sync_variant_annotations.py
