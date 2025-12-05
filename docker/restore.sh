#!/bin/bash
# docker/restore.sh - PostgreSQL restore for HNF1B Database
#
# Usage:
#   ./docker/restore.sh <backup_file.sql.gz>
#
# Environment variables (with defaults):
#   POSTGRES_USER   - Database user (default: from .env.docker or hnf1b_user)
#   POSTGRES_DB     - Database name (default: from .env.docker or hnf1b_phenopackets)
#   DB_CONTAINER    - Container name (default: hnf1b_db)

set -e

# Load environment from .env.docker if available
if [ -f "docker/.env.docker" ]; then
    # shellcheck disable=SC1091
    source docker/.env.docker 2>/dev/null || true
fi

# Configuration with environment variable fallbacks
DB_CONTAINER="${DB_CONTAINER:-hnf1b_db}"
DB_USER="${POSTGRES_USER:-hnf1b_user}"
DB_NAME="${POSTGRES_DB:-hnf1b_phenopackets}"

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Configuration:"
    echo "  Container: $DB_CONTAINER"
    echo "  Database:  $DB_NAME"
    echo "  User:      $DB_USER"
    echo ""
    echo "Available backups:"
    ls -lh backups/hnf1b_backup_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will replace all data in the database!"
echo "  Container: $DB_CONTAINER"
echo "  Database:  $DB_NAME"
echo "  User:      $DB_USER"
echo ""
read -p "Are you sure you want to restore from $BACKUP_FILE? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring from: $BACKUP_FILE"

# Use docker exec directly on the container (works regardless of compose setup)
# This avoids needing to know which compose files were used to start the containers
gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"

echo "Restore complete!"
