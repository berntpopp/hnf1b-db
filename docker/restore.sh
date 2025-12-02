#!/bin/bash
# docker/restore.sh - PostgreSQL restore for HNF1B Database

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
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
read -p "Are you sure you want to restore from $BACKUP_FILE? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring from: $BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | \
docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_db \
    psql -U hnf1b_user -d hnf1b_phenopackets

echo "Restore complete!"
