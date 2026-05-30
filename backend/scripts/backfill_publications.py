#!/usr/bin/env python3
"""Backfill publication abstracts, open-access full text, and (optionally) embeddings.

Runs the same per-publication orchestration as the admin ``POST
/publications/sync`` endpoint over the PMIDs referenced by phenopackets:
ensure base citation metadata, fetch the abstract (efetch), fetch + license-gate
open-access full text (PubTator3 BioC / EuropePMC), chunk into passages, and
persist. Idempotent: re-runs upsert metadata, replace each PMID's passages, and
(with ``--embeddings``) skip passages whose ``text_hash`` is already current.
By default, publications whose full text was fetched within
``publications_rag.fulltext_staleness_days`` are skipped (override with
``--force``).

Usage:
    python scripts/backfill_publications.py --dry-run
    python scripts/backfill_publications.py --limit 10
    python scripts/backfill_publications.py --embeddings        # needs [rag] extra
    python scripts/backfill_publications.py --force

Requirements:
    - Database running (pgvector image) with migrations applied.
    - Valid backend/.env (DATABASE_URL) and internet access for the APIs.
"""
# ruff: noqa: E501 - SQL queries and help strings read better unwrapped

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add backend to path so ``app`` imports resolve when run as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
from sqlalchemy import text

from app.core.config import settings
from app.database import async_session_maker
from app.publications.fulltext.embeddings import get_embedding_provider
from app.publications.fulltext.orchestrator import (
    backfill_embeddings,
    sync_publications,
)
from app.publications.service import get_publication_metadata


async def _all_pmids(db) -> list[str]:
    """Return bare PMIDs referenced by non-deleted phenopackets."""
    result = await db.execute(
        text("""
            SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        """)
    )
    return [row.pmid for row in result.fetchall()]


async def _fresh_pmids(db, staleness_days: int) -> set[str]:
    """Return bare PMIDs whose full text was fetched within the staleness window."""
    result = await db.execute(
        text(
            "SELECT REPLACE(pmid, 'PMID:', '') AS pmid, fulltext_fetched_at "
            "FROM publication_metadata WHERE fulltext_fetched_at IS NOT NULL"
        )
    )
    now = datetime.now(timezone.utc)
    fresh: set[str] = set()
    for row in result.fetchall():
        fetched = row.fulltext_fetched_at
        if fetched is None:
            continue
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if (now - fetched).days < staleness_days:
            fresh.add(row.pmid)
    return fresh


async def main(
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    force: bool = False,
    embeddings: bool = False,
) -> None:
    """Run the publication backfill."""
    rag = settings.publications_rag
    print("=" * 80)
    print("Publication Full-Text Backfill")
    print(
        f"Mode: {'DRY RUN' if dry_run else 'LIVE'}  Force: {force}  "
        f"Embeddings: {embeddings}  Limit: {limit or 'all'}"
    )
    print("=" * 80)

    async with async_session_maker() as db:
        all_pmids = await _all_pmids(db)
        print(f"Found {len(all_pmids)} unique PMIDs in phenopackets")

        to_process = all_pmids
        if not force:
            fresh = await _fresh_pmids(db, rag.fulltext_staleness_days)
            to_process = [p for p in all_pmids if p not in fresh]
            print(
                f"Skipping {len(fresh)} fetched within {rag.fulltext_staleness_days}d"
            )

        to_process = sorted(to_process, key=lambda p: int(p) if p.isdigit() else 0)
        if limit:
            to_process = to_process[:limit]
        print(f"To process: {len(to_process)}")

        if dry_run:
            for pmid in to_process:
                print(f"  would process PMID:{pmid}")
            print("\nDRY RUN — no changes made.")
            return

        async def _ensure_metadata(pmid: str) -> None:
            await get_publication_metadata(pmid, db, fetched_by="backfill")

        async with aiohttp.ClientSession() as session:
            counts = await sync_publications(
                db,
                to_process,
                session=session,
                allowed_licenses=rag.allowed_licenses,
                chunk_max_tokens=rag.chunk_max_tokens,
                chunk_overlap_tokens=rag.chunk_overlap_tokens,
                abstract_api_key=settings.PUBMED_API_KEY,
                ensure_metadata=_ensure_metadata,
            )

        print("-" * 80)
        print(f"Processed:         {counts.processed}")
        print(f"Abstracts fetched: {counts.abstracts_fetched}")
        print(f"Full text fetched: {counts.full_text_fetched}")
        print(f"License-skipped:   {counts.license_skipped}")
        print(f"Errors:            {counts.errors}")

        if embeddings:
            provider = get_embedding_provider(
                model_name=rag.embedding_model,
                query_prefix=rag.embedding_query_prefix,
                batch_size=rag.embedding_batch_size,
                dim=rag.embedding_dim,
            )
            if provider is None:
                print(
                    "\nEmbeddings requested but sentence-transformers is not "
                    "installed (install the [rag] extra). Skipping."
                )
            else:
                print(f"\nEmbedding passages with {provider.model_name}...")
                embedded = await backfill_embeddings(
                    db, provider, batch_size=rag.embedding_batch_size
                )
                print(f"Embedded {embedded} passages.")

        print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill publication full text")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed"
    )
    parser.add_argument("--limit", type=int, help="Process at most N publications")
    parser.add_argument(
        "--force", action="store_true", help="Ignore the staleness window"
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Also backfill embeddings (needs [rag])",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                dry_run=args.dry_run,
                limit=args.limit,
                force=args.force,
                embeddings=args.embeddings,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
