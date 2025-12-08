#!/usr/bin/env python3
"""Sync publication metadata from PubMed for all referenced publications.

This script:
1. Fetches all unique PMIDs from phenopackets
2. Checks which PMIDs are already in the publication_metadata table
3. Fetches metadata from PubMed for missing PMIDs
4. Stores permanently in the database

Usage:
    # Dry run (shows what would be fetched without making changes)
    python scripts/sync_publication_metadata.py --dry-run

    # Sync first 10 publications (testing)
    python scripts/sync_publication_metadata.py --limit 10

    # Sync all publications
    python scripts/sync_publication_metadata.py

    # Force refresh all (re-fetch even if already cached)
    python scripts/sync_publication_metadata.py --force

Requirements:
    - Database running (make hybrid-up)
    - Valid backend/.env with DATABASE_URL
    - Internet connection (for PubMed API calls)
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
from app.publications.service import (
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError,
    get_publication_metadata,
)


async def get_all_pmids(db) -> Set[str]:
    """Get all unique PMIDs referenced in phenopackets.

    Args:
        db: Database session

    Returns:
        Set of PMID strings (numeric only, without PMID: prefix)
    """
    query = text("""
        SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
    """)
    result = await db.execute(query)
    return {row.pmid for row in result.fetchall()}


async def get_stored_pmids(db) -> Set[str]:
    """Get all PMIDs already stored in publication_metadata.

    Args:
        db: Database session

    Returns:
        Set of PMID strings (numeric only, without PMID: prefix)
    """
    query = text("""
        SELECT REPLACE(pmid, 'PMID:', '') as pmid
        FROM publication_metadata
    """)
    result = await db.execute(query)
    return {row.pmid for row in result.fetchall()}


async def main(
    dry_run: bool = False, limit: Optional[int] = None, force: bool = False
):
    """Sync all publication metadata from PubMed.

    Args:
        dry_run: If True, show what would be done without making changes
        limit: Maximum number of publications to sync (for testing)
        force: If True, refresh all metadata even if already cached
    """
    fetched_count = 0
    failed_count = 0
    skipped_count = 0
    rate_limited = 0

    print("=" * 80)
    print("Publication Metadata Sync Script")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE SYNC'}")
    print(f"Force refresh: {force}")
    print(f"Limit: {limit if limit else 'No limit (all publications)'}")
    print("=" * 80)
    print()

    async for db in get_db():
        # Get all PMIDs from phenopackets
        all_pmids = await get_all_pmids(db)
        print(f"Found {len(all_pmids)} unique PMIDs in phenopackets")

        # Get already stored PMIDs
        stored_pmids = await get_stored_pmids(db)
        print(f"Already stored: {len(stored_pmids)} PMIDs")

        # Determine which to fetch
        if force:
            to_fetch = all_pmids
        else:
            to_fetch = all_pmids - stored_pmids

        print(f"To fetch: {len(to_fetch)} PMIDs")
        print()

        if not to_fetch:
            print("Nothing to fetch!")
            break

        # Apply limit
        if limit:
            to_fetch = set(list(to_fetch)[:limit])
            print(f"Limited to {len(to_fetch)} PMIDs for this run")
            print()

        # Sort for consistent ordering
        to_fetch_list = sorted(to_fetch, key=int)

        for i, pmid in enumerate(to_fetch_list, 1):
            print(f"[{i}/{len(to_fetch_list)}] PMID:{pmid}... ", end="", flush=True)

            if dry_run:
                print("(DRY RUN - would fetch)")
                fetched_count += 1
                continue

            try:
                # Fetch from PubMed (with caching via service)
                metadata = await get_publication_metadata(
                    pmid, db, fetched_by="sync_script"
                )
                title = metadata.get("title", "")[:50]
                year = metadata.get("year", "N/A")
                print(f"OK - {year} - {title}...")
                fetched_count += 1

                # Rate limiting: 3 req/sec without API key = ~350ms between requests
                await asyncio.sleep(0.35)

            except PubMedRateLimitError as e:
                print(f"RATE LIMITED - {e}")
                rate_limited += 1
                # Wait longer when rate limited
                await asyncio.sleep(60)

            except PubMedNotFoundError:
                print("NOT FOUND")
                skipped_count += 1

            except PubMedTimeoutError:
                print("TIMEOUT")
                failed_count += 1
                await asyncio.sleep(1)

            except PubMedAPIError as e:
                print(f"API ERROR - {e}")
                failed_count += 1
                await asyncio.sleep(1)

            except Exception as e:
                print(f"FAILED - {str(e)[:50]}")
                failed_count += 1

        break

    print()
    print("=" * 80)
    print("SYNC SUMMARY")
    print("=" * 80)
    print(f"Fetched successfully: {fetched_count}")
    print(f"Not found in PubMed:  {skipped_count}")
    print(f"Rate limited:         {rate_limited}")
    print(f"Failed:               {failed_count}")
    print("=" * 80)

    if dry_run:
        print()
        print("This was a DRY RUN - no changes were made to the database")
        print("Run without --dry-run to apply changes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync publication metadata from PubMed"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of publications to sync (for testing)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if metadata already exists",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(dry_run=args.dry_run, limit=args.limit, force=args.force))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
