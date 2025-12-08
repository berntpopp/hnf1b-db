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

# Helper function to get counts from database using the helper module
get_count() {
    python -m scripts.entrypoint_helpers "$1" 2>/dev/null || echo "0"
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
        log_info "Data import is ENABLED, checking configuration..."

        # Step 1: Always initialize reference data first (GRCh38 + HNF1B)
        # This is idempotent and required for proper gene/variant context
        sync_reference_data

        # Note: GOOGLE_SHEETS_ID is optional - the migration script has a default value
        # If set, it will override the default. If not set, the hardcoded default is used.
        if [ -n "$GOOGLE_SHEETS_ID" ]; then
            log_info "Using GOOGLE_SHEETS_ID from environment: ${GOOGLE_SHEETS_ID:0:10}..."
        else
            log_info "Using default Google Sheets ID (set GOOGLE_SHEETS_ID to override)"
        fi

        log_info "Checking if database is empty..."

        # Check if phenopackets table has data
        local count=$(get_count phenopackets)

        if [ "$count" = "0" ]; then
            # Step 2: Import phenopackets from Google Sheets
            log_info "Database is empty, running initial data import..."
            if python -m migration.direct_sheets_to_phenopackets; then
                log_info "Data import completed successfully!"
            else
                log_warn "Data import failed, but continuing startup..."
            fi
        else
            log_info "Database already has $count phenopackets, skipping import"
        fi

        # Step 3-5: Run all sync operations (idempotent, safe to run always)
        # These check internally if sync is needed
        sync_publication_metadata
        sync_variant_annotations
        sync_chr17q12_genes
    else
        log_info "Data import is DISABLED (set ENABLE_DATA_IMPORT=true to enable)"
    fi
}

# Initialize reference data (GRCh38 + HNF1B + transcript + domains)
sync_reference_data() {
    log_info "Checking reference data..."

    # Check if reference data is initialized (GRCh38 genome exists)
    local genome_count=$(get_count genomes)

    if [ "$genome_count" = "0" ]; then
        log_info "Initializing reference data (GRCh38 + HNF1B + transcript + domains)..."
        if python scripts/sync_reference_data.py --init; then
            log_info "Reference data initialized successfully!"
        else
            log_warn "Reference data initialization failed, but continuing startup..."
        fi
    else
        log_info "Reference data already initialized"
    fi
}

# Sync publication metadata from PubMed
sync_publication_metadata() {
    log_info "Checking publication metadata..."

    # Check if publication_metadata table has data
    local pub_count=$(get_count publication_metadata)

    # Count unique PMIDs in phenopackets
    local pmid_count=$(get_count pmids)

    if [ "$pub_count" -lt "$pmid_count" ]; then
        log_info "Found $pmid_count PMIDs, $pub_count cached. Syncing publication metadata from PubMed..."
        if python scripts/sync_publication_metadata.py; then
            log_info "Publication metadata sync completed successfully!"
        else
            log_warn "Publication metadata sync failed, but continuing startup..."
        fi
    else
        log_info "Publication metadata is up to date ($pub_count cached)"
    fi
}

# Sync VEP annotations for variants
sync_variant_annotations() {
    log_info "Checking variant annotations..."

    # Count unique variants in phenopackets
    local variant_count=$(get_count variants)

    # Count existing annotations
    local annotation_count=$(get_count variant_annotations)

    if [ "$annotation_count" -lt "$variant_count" ]; then
        log_info "Found $variant_count variants, $annotation_count annotated. Syncing VEP annotations..."
        if python scripts/sync_variant_annotations.py; then
            log_info "VEP annotation sync completed successfully!"
        else
            log_warn "VEP annotation sync failed, but continuing startup..."
        fi
    else
        log_info "Variant annotations up to date ($annotation_count cached)"
    fi
}

# Sync chr17q12 region genes from Ensembl
sync_chr17q12_genes() {
    log_info "Checking chr17q12 genes..."

    # Count chr17q12 genes (in the region 36000000-39900000)
    local gene_count=$(get_count chr17q12_genes)

    # Expected ~70 genes in chr17q12 region
    if [ "$gene_count" -lt "60" ]; then
        log_info "Found $gene_count chr17q12 genes, syncing from Ensembl..."
        if python scripts/sync_reference_data.py --genes; then
            log_info "chr17q12 genes sync completed successfully!"
        else
            log_warn "chr17q12 genes sync failed, but continuing startup..."
        fi
    else
        log_info "chr17q12 genes up to date ($gene_count genes)"
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
