#!/usr/bin/env python3
"""Sync variant annotations from Ensembl VEP for all unique variants.

This script:
1. Extracts all unique variants (VCF format) from phenopackets
2. Checks which variants are already in the variant_annotations table
3. Fetches annotations from VEP API for missing variants (in batches)
4. Stores permanently in the database

Key optimization: Annotates UNIQUE VARIANTS only, not per-phenopacket.
With 864 phenopackets but ~200 unique variants, this significantly reduces API calls.

Usage:
    # Dry run (shows what would be fetched without making changes)
    python scripts/sync_variant_annotations.py --dry-run

    # Sync first 10 variants (testing)
    python scripts/sync_variant_annotations.py --limit 10

    # Sync all variants
    python scripts/sync_variant_annotations.py

    # Force refresh all (re-fetch even if already cached)
    python scripts/sync_variant_annotations.py --force

Requirements:
    - Database running (make hybrid-up)
    - Valid backend/.env with DATABASE_URL
    - Internet connection (for VEP API calls)
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, Set

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import get_db
from app.variants.service import (
    VEPAPIError,
    VEPRateLimitError,
    VEPTimeoutError,
    get_variant_annotations_batch,
)


async def get_all_unique_variants(db) -> Set[str]:
    """Extract all unique variants from phenopackets.

    Extracts VCF format variants from:
    - phenopackets -> interpretations -> diagnosis -> genomicInterpretations
      -> variantInterpretation -> variationDescriptor -> expressions

    Args:
        db: Database session

    Returns:
        Set of unique variant IDs in VCF format (e.g., "17-36459258-A-G")
    """
    # Extract VCF expressions from all phenopackets
    query = text("""
        WITH variant_expressions AS (
            SELECT DISTINCT
                expr->>'value' as vcf_value
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'interpretations'
                 ) as interp,
                 jsonb_array_elements(
                     interp->'diagnosis'->'genomicInterpretations'
                 ) as gi,
                 jsonb_array_elements(
                     gi->'variantInterpretation'->'variationDescriptor'->'expressions'
                 ) as expr
            WHERE expr->>'syntax' = 'vcf'
              AND deleted_at IS NULL
        )
        SELECT
            UPPER(REGEXP_REPLACE(vcf_value, '^chr', '', 'i')) as variant_id
        FROM variant_expressions
        WHERE vcf_value IS NOT NULL
          AND vcf_value !~ '<[A-Z]+>'  -- Exclude structural variants (<DEL>, <DUP>)
          AND vcf_value ~ '^(chr)?[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
    """)
    result = await db.execute(query)
    return {row.variant_id for row in result.fetchall()}


async def get_stored_variants(db) -> Set[str]:
    """Get all variants already stored in variant_annotations.

    Args:
        db: Database session

    Returns:
        Set of variant IDs already in database
    """
    query = text("""
        SELECT variant_id FROM variant_annotations
    """)
    result = await db.execute(query)
    return {row.variant_id for row in result.fetchall()}


async def main(
    dry_run: bool = False,
    limit: Optional[int] = None,
    force: bool = False,
    batch_size: int = 200,
):
    """Sync all variant annotations from VEP.

    Args:
        dry_run: If True, show what would be done without making changes
        limit: Maximum number of variants to sync (for testing)
        force: If True, refresh all annotations even if already cached
        batch_size: Number of variants per VEP batch request
    """
    fetched_count = 0
    failed_count = 0
    skipped_count = 0
    rate_limited = 0

    print("=" * 80)
    print("Variant Annotation Sync Script (VEP)")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE SYNC'}")
    print(f"Force refresh: {force}")
    print(f"Limit: {limit if limit else 'No limit (all variants)'}")
    print(f"Batch size: {batch_size}")
    print("=" * 80)
    print()

    async for db in get_db():
        # Get all unique variants from phenopackets
        all_variants = await get_all_unique_variants(db)
        print(f"Found {len(all_variants)} unique variants in phenopackets")

        # Get already stored variants
        stored_variants = await get_stored_variants(db)
        print(f"Already annotated: {len(stored_variants)} variants")

        # Determine which to fetch
        if force:
            to_fetch = all_variants
        else:
            to_fetch = all_variants - stored_variants

        print(f"To fetch: {len(to_fetch)} variants")
        print()

        if not to_fetch:
            print("Nothing to fetch - all variants already annotated!")
            break

        # Apply limit
        if limit:
            to_fetch = set(list(to_fetch)[:limit])
            print(f"Limited to {len(to_fetch)} variants for this run")
            print()

        # Convert to sorted list for consistent ordering
        to_fetch_list = sorted(to_fetch)

        if dry_run:
            print("DRY RUN - would fetch the following variants:")
            for i, vid in enumerate(to_fetch_list, 1):
                print(f"  [{i}/{len(to_fetch_list)}] {vid}")
            fetched_count = len(to_fetch_list)
        else:
            # Batch process variants
            total_batches = (len(to_fetch_list) + batch_size - 1) // batch_size

            for batch_num, i in enumerate(
                range(0, len(to_fetch_list), batch_size), 1
            ):
                batch = to_fetch_list[i : i + batch_size]
                print(
                    f"[Batch {batch_num}/{total_batches}] "
                    f"Processing {len(batch)} variants..."
                )

                try:
                    results = await get_variant_annotations_batch(
                        batch, db, fetched_by="sync_script", batch_size=batch_size
                    )

                    # Count results
                    for vid in batch:
                        if vid in results and results[vid]:
                            ann = results[vid]
                            consequence = ann.get("most_severe_consequence", "N/A")
                            impact = ann.get("impact", "N/A")
                            cadd = ann.get("cadd_score", "N/A")
                            print(f"  ✅ {vid}: {consequence} ({impact}) CADD:{cadd}")
                            fetched_count += 1
                        else:
                            print(f"  ❌ {vid}: Not found or failed")
                            skipped_count += 1

                    # Rate limiting between batches (Ensembl: 15 req/sec)
                    if batch_num < total_batches:
                        await asyncio.sleep(0.5)

                except VEPRateLimitError as e:
                    print(f"  ⏸️  Rate limited: {e}")
                    rate_limited += 1
                    # Wait before retrying
                    await asyncio.sleep(60)

                except VEPTimeoutError:
                    print("  ⏱️  Timeout - skipping batch")
                    failed_count += len(batch)

                except VEPAPIError as e:
                    print(f"  ❌ API error: {e}")
                    failed_count += len(batch)

                except Exception as e:
                    print(f"  ❌ Unexpected error: {str(e)[:100]}")
                    failed_count += len(batch)

        break

    print()
    print("=" * 80)
    print("SYNC SUMMARY")
    print("=" * 80)
    print(f"Annotated successfully: {fetched_count}")
    print(f"Not found/invalid:      {skipped_count}")
    print(f"Rate limited:           {rate_limited}")
    print(f"Failed:                 {failed_count}")
    print("=" * 80)

    if dry_run:
        print()
        print("This was a DRY RUN - no changes were made to the database")
        print("Run without --dry-run to apply changes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync variant annotations from Ensembl VEP"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of variants to sync (for testing)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if annotation already exists",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of variants per VEP batch request (default: 50)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                dry_run=args.dry_run,
                limit=args.limit,
                force=args.force,
                batch_size=args.batch_size,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
