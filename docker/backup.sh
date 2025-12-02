#!/bin/bash
# docker/backup.sh - PostgreSQL backup for HNF1B Database

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hnf1b_backup_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating backup: $BACKUP_FILE"
docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_db \
    pg_dump -U hnf1b_user -d hnf1b_phenopackets | gzip > "$BACKUP_FILE"

echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/hnf1b_backup_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm --
echo "Cleanup complete. Keeping last 7 backups."
