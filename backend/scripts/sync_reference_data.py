#!/usr/bin/env python
"""Sync reference data (genomes, genes) to the database.

This script provides CLI access to the reference data synchronization functions.
It can initialize core reference data (GRCh38 + HNF1B) and sync chr17q12 genes
from the Ensembl REST API.

Usage:
    # Initialize core reference data (GRCh38 genome + HNF1B gene + transcript + domains)
    uv run python scripts/sync_reference_data.py --init

    # Sync chr17q12 genes from Ensembl
    uv run python scripts/sync_reference_data.py --genes

    # Dry run (show what would be synced)
    uv run python scripts/sync_reference_data.py --genes --dry-run

    # Limit to first N genes (for testing)
    uv run python scripts/sync_reference_data.py --genes --limit 10

    # Both operations
    uv run python scripts/sync_reference_data.py --init --genes

Environment:
    DATABASE_URL: PostgreSQL connection string (required)

Example:
    cd backend
    DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db" \
        uv run python scripts/sync_reference_data.py --init --genes
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.reference.service import (
    get_reference_data_status,
    initialize_reference_data,
    sync_chr17q12_genes,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_init(session: AsyncSession) -> bool:
    """Initialize core reference data.

    Returns:
        True if successful, False otherwise
    """
    print()
    print("=" * 70)
    print("Initializing Reference Data (GRCh38 + HNF1B)")
    print("=" * 70)
    print()

    # Check current status
    status = await get_reference_data_status(session)
    if status.has_grch38 and status.has_hnf1b:
        print("Reference data already initialized:")
        print("  - GRCh38 genome: Present")
        print("  - HNF1B gene: Present")
        print(f"  - Transcripts: {status.transcript_count}")
        print(f"  - Exons: {status.exon_count}")
        print(f"  - Protein domains: {status.domain_count}")
        print()
        print("No action needed.")
        return True

    # Run initialization
    print("Creating reference data...")
    result = await initialize_reference_data(session)

    if result.errors > 0:
        print(f"\nInitialization failed with {result.errors} error(s)")
        if result.error_messages:
            for msg in result.error_messages:
                print(f"  Error: {msg}")
        return False

    print()
    print("Summary:")
    print(f"  - Items created: {result.imported}")
    print()
    print("Reference data initialized successfully!")
    return True


async def run_genes_sync(
    session: AsyncSession,
    dry_run: bool = False,
    limit: int | None = None,
) -> bool:
    """Sync chr17q12 genes from Ensembl.

    Returns:
        True if successful, False otherwise
    """
    print()
    print("=" * 70)
    print("Syncing chr17q12 Region Genes from Ensembl")
    print("=" * 70)
    print()

    if dry_run:
        print("DRY RUN - No changes will be made")
        print()

    # Check current status
    status = await get_reference_data_status(session)
    print(f"Current chr17q12 gene count: {status.chr17q12_gene_count}")
    print()

    if limit:
        print(f"Limiting to first {limit} genes")
        print()

    # Run sync
    print("Fetching genes from Ensembl REST API...")
    result = await sync_chr17q12_genes(session, dry_run=dry_run, limit=limit)

    if result.errors > 0:
        print(f"\nSync completed with {result.errors} error(s)")
        if result.error_messages:
            for msg in result.error_messages:
                print(f"  Error: {msg}")

    print()
    print("Summary:")
    print(f"  - Imported: {result.imported}")
    print(f"  - Updated: {result.updated}")
    print(f"  - Skipped: {result.skipped}")
    print(f"  - Errors: {result.errors}")
    print(f"  - Total processed: {result.total}")
    print()

    if dry_run:
        print("DRY RUN complete - no changes were made")
    else:
        print("Gene sync completed successfully!")

    return result.errors == 0


async def show_status(session: AsyncSession) -> None:
    """Show current reference data status."""
    print()
    print("=" * 70)
    print("Reference Data Status")
    print("=" * 70)
    print()

    status = await get_reference_data_status(session)

    print("Genomes:")
    print(f"  - Count: {status.genome_count}")
    print(f"  - GRCh38 present: {status.has_grch38}")
    print()

    print("Genes:")
    print(f"  - Total: {status.gene_count}")
    print(f"  - HNF1B present: {status.has_hnf1b}")
    print(f"  - chr17q12 region: {status.chr17q12_gene_count}")
    print()

    print("Transcripts:")
    print(f"  - Count: {status.transcript_count}")
    print()

    print("Exons:")
    print(f"  - Count: {status.exon_count}")
    print()

    print("Protein Domains:")
    print(f"  - Count: {status.domain_count}")
    print()

    if status.last_updated:
        print(f"Last updated: {status.last_updated.isoformat()}")
    else:
        print("Last updated: Never")
    print()

    # Status summary
    if status.has_grch38 and status.has_hnf1b:
        print("Status: Reference data initialized")
    else:
        print("Status: Reference data NOT initialized")
        print("  Run: make reference-init")

    if status.chr17q12_gene_count >= 60:
        print("Status: chr17q12 genes synced")
    else:
        print("Status: chr17q12 genes NOT synced")
        print("  Run: make genes-sync")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync reference data (genomes, genes) to the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize core reference data
  uv run python scripts/sync_reference_data.py --init

  # Sync chr17q12 genes
  uv run python scripts/sync_reference_data.py --genes

  # Dry run (no changes)
  uv run python scripts/sync_reference_data.py --genes --dry-run

  # Show current status
  uv run python scripts/sync_reference_data.py --status
        """,
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize core reference data (GRCh38 + HNF1B + transcript)",
    )
    parser.add_argument(
        "--genes",
        action="store_true",
        help="Sync chr17q12 region genes from Ensembl REST API",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current reference data status",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of genes to sync (for testing)",
    )

    args = parser.parse_args()

    # Require at least one action
    if not (args.init or args.genes or args.status):
        parser.print_help()
        print("\nError: At least one of --init, --genes, or --status is required")
        sys.exit(1)

    # Create database engine
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    except Exception as e:
        print(f"Error: Failed to connect to database: {e}")
        print("Make sure DATABASE_URL is set correctly")
        sys.exit(1)

    success = True

    try:
        async with async_session() as session:
            # Show status
            if args.status:
                await show_status(session)

            # Initialize reference data
            if args.init:
                if not await run_init(session):
                    success = False

            # Sync genes
            if args.genes:
                if not await run_genes_sync(session, args.dry_run, args.limit):
                    success = False

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        success = False
    finally:
        await engine.dispose()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
