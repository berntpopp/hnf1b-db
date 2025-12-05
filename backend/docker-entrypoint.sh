#!/bin/bash
# docker-entrypoint.sh
# Entrypoint script for HNF1B API container
# Handles database initialization, migrations, and optional data import

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Wait for PostgreSQL to be ready
wait_for_db() {
    log_info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "${DB_HOST:-hnf1b_db}" -p "${DB_PORT:-5432}" -U "${POSTGRES_USER:-hnf1b_user}" > /dev/null 2>&1; then
            log_info "PostgreSQL is ready!"
            return 0
        fi
        log_info "Waiting for PostgreSQL... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL did not become ready in time"
    return 1
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    if alembic upgrade head; then
        log_info "Migrations completed successfully"
    else
        log_error "Migration failed!"
        return 1
    fi
}

# Create admin user if not exists
create_admin_user() {
    if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
        log_info "Checking/creating admin user..."
        python -m app.scripts.create_admin || log_warn "Admin user creation skipped or failed"
    else
        log_info "Skipping admin user creation (ADMIN_USERNAME or ADMIN_PASSWORD not set)"
    fi
}

# Run initial data import if enabled
run_data_import() {
    if [ "${ENABLE_DATA_IMPORT:-false}" = "true" ]; then
        log_info "Data import is ENABLED, checking if database is empty..."

        # Check if phenopackets table has data
        local count=$(python -c "
import asyncio
from app.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM phenopackets'))
        return result.scalar()

print(asyncio.run(check()))
" 2>/dev/null || echo "0")

        if [ "$count" = "0" ]; then
            log_info "Database is empty, running initial data import..."
            if python -m migration.direct_sheets_to_phenopackets; then
                log_info "Data import completed successfully!"
            else
                log_warn "Data import failed, but continuing startup..."
            fi
        else
            log_info "Database already has $count phenopackets, skipping import"
        fi
    else
        log_info "Data import is DISABLED (set ENABLE_DATA_IMPORT=true to enable)"
    fi
}

# Main entrypoint logic
main() {
    log_info "=== HNF1B API Container Starting ==="

    # Wait for database
    wait_for_db || exit 1

    # Run migrations
    run_migrations || exit 1

    # Create admin user
    create_admin_user

    # Run data import if enabled
    run_data_import

    log_info "=== Initialization Complete, Starting API ==="

    # Execute the main command (uvicorn)
    exec "$@"
}

# Run main function with all arguments
main "$@"
