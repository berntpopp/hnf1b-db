#!/bin/bash
# docker/backup.sh - PostgreSQL backup for HNF1B Database
#
# Usage:
#   ./docker/backup.sh
#
# Environment variables (with defaults):
#   BACKUP_DIR      - Directory for backups (default: ./backups)
#   POSTGRES_USER   - Database user (default: from .env.docker or hnf1b_user)
#   POSTGRES_DB     - Database name (default: from .env.docker or hnf1b_phenopackets)
#   DB_CONTAINER    - Container name (default: hnf1b_db)
#
# Note: This script is designed for Linux systems. The cleanup uses GNU xargs.

set -e

# Load environment from .env.docker if available
if [ -f "docker/.env.docker" ]; then
    # shellcheck disable=SC1091
    source docker/.env.docker 2>/dev/null || true
fi

# Configuration with environment variable fallbacks
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_CONTAINER="${DB_CONTAINER:-hnf1b_db}"
DB_USER="${POSTGRES_USER:-hnf1b_user}"
DB_NAME="${POSTGRES_DB:-hnf1b_phenopackets}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hnf1b_backup_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating backup: $BACKUP_FILE"
echo "  Container: $DB_CONTAINER"
echo "  Database:  $DB_NAME"
echo "  User:      $DB_USER"

docker compose -f docker/docker-compose.yml -f docker/docker-compose.npm.yml --env-file docker/.env.docker exec -T "$DB_CONTAINER" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"

echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Keep only last 7 backups (Linux-compatible cleanup)
echo "Cleaning up old backups..."
files_to_delete=$(ls -t "$BACKUP_DIR"/hnf1b_backup_*.sql.gz 2>/dev/null | tail -n +8 || true)
if [ -n "$files_to_delete" ]; then
    echo "$files_to_delete" | xargs rm --
    echo "Removed old backups"
fi
echo "Cleanup complete. Keeping last 7 backups."
