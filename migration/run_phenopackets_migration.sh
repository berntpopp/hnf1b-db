#!/bin/bash

# Complete migration script for phenopackets restructuring
# This script handles the complete cutover from normalized PostgreSQL to phenopackets

set -e  # Exit on error

echo "=================================================="
echo "HNF1B-API Complete Phenopackets Migration"
echo "=================================================="
echo ""

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/hnf1b_backup_${TIMESTAMP}.sql"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check required environment variables
if [ -z "$DATABASE_URL" ] || [ -z "$OLD_DATABASE_URL" ]; then
    echo "ERROR: Required environment variables not set"
    echo "Please ensure DATABASE_URL and OLD_DATABASE_URL are set in .env"
    exit 1
fi

# Function to extract database name from URL
get_db_name() {
    echo $1 | sed -n 's/.*\/\([^?]*\).*/\1/p'
}

OLD_DB_NAME=$(get_db_name $OLD_DATABASE_URL)
NEW_DB_NAME=$(get_db_name $DATABASE_URL)

echo "Source Database: $OLD_DB_NAME"
echo "Target Database: $NEW_DB_NAME"
echo ""

# Step 1: Create backup directory
echo "Step 1: Creating backup directory..."
mkdir -p $BACKUP_DIR

# Step 2: Backup existing database
echo "Step 2: Backing up existing database..."
pg_dump $OLD_DATABASE_URL > $BACKUP_FILE
echo "Backup saved to: $BACKUP_FILE"

# Step 3: Create new database (if it doesn't exist)
echo "Step 3: Setting up new phenopackets database..."
psql -c "CREATE DATABASE $NEW_DB_NAME;" 2>/dev/null || echo "Database $NEW_DB_NAME already exists"

# Step 4: Apply phenopackets schema
echo "Step 4: Applying phenopackets schema..."
psql $DATABASE_URL < migration/phenopackets_schema.sql
echo "Schema applied successfully"

# Step 5: Run migration
echo "Step 5: Running data migration..."
echo "This may take several minutes depending on data size..."
uv run python migration/phenopackets_migration.py

# Step 6: Verify migration
echo "Step 6: Verifying migration..."
PHENOPACKET_COUNT=$(psql -t -c "SELECT COUNT(*) FROM phenopackets;" $DATABASE_URL)
echo "Migrated $PHENOPACKET_COUNT phenopackets"

# Step 7: Create validation report
echo "Step 7: Creating validation report..."
psql $DATABASE_URL <<EOF > migration_report_${TIMESTAMP}.txt
-- Migration Validation Report
SELECT 'Total Phenopackets:', COUNT(*) FROM phenopackets;
SELECT 'By Sex:', subject_sex, COUNT(*) FROM phenopackets GROUP BY subject_sex;
SELECT 'With Variants:', COUNT(*) FROM phenopackets WHERE jsonb_array_length(phenopacket->'interpretations') > 0;
SELECT 'With Features:', COUNT(*) FROM phenopackets WHERE jsonb_array_length(phenopacket->'phenotypicFeatures') > 0;
SELECT 'With Diseases:', COUNT(*) FROM phenopackets WHERE jsonb_array_length(phenopacket->'diseases') > 0;
EOF

echo "Validation report saved to: migration_report_${TIMESTAMP}.txt"

echo ""
echo "=================================================="
echo "Migration Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Review the validation report"
echo "2. Test the new API endpoints"
echo "3. Update application configuration to use new endpoints"
echo ""
echo "Rollback instructions (if needed):"
echo "  psql $OLD_DATABASE_URL < $BACKUP_FILE"
echo ""