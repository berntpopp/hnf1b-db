#!/usr/bin/env python3
"""Normalize HPO labels in existing phenopackets to canonical form.

This script updates all phenopacket records to use canonical HPO labels
from the official HPO API, fixing data quality issues where the same
HPO ID has different label text.

Problem:
    HP:0012622 appears as both "Chronic kidney disease" (141 records)
    and "chronic kidney disease, not specified" (69 records)

Solution:
    Fetch canonical labels from HPO API and update all records to use
    the authoritative label from the Human Phenotype Ontology.

Usage:
    # Dry run (shows what would change, no database modifications)
    python -m scripts.normalize_hpo_labels --dry-run

    # Execute normalization
    python -m scripts.normalize_hpo_labels

    # Verbose output
    python -m scripts.normalize_hpo_labels --verbose

Fixes #165: Data quality: Normalize HPO term labels during import
"""

import asyncio
import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.phenopacket import Phenopacket
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.ontology_service import ontology_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_phenopacket_labels(
    phenopacket: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    """Normalize HPO labels in a phenopacket to canonical form.

    Args:
        phenopacket: The phenopacket data dictionary

    Returns:
        Tuple of (updated phenopacket, count of normalized labels)
    """
    # Work on a deep copy to avoid mutating the original
    updated = deepcopy(phenopacket)
    normalized_count = 0

    # Normalize phenotypic features
    for feature in updated.get("phenotypicFeatures", []):
        if "type" not in feature or "id" not in feature["type"]:
            continue

        hpo_id = feature["type"]["id"]
        if not hpo_id.startswith("HP:"):
            continue

        # Get canonical label from ontology service
        term = ontology_service.get_term(hpo_id)
        if term and not term.label.startswith("Unknown"):
            old_label = feature["type"].get("label", "")
            if old_label != term.label:
                feature["type"]["label"] = term.label
                normalized_count += 1
                logger.debug(f"  {hpo_id}: '{old_label}' -> '{term.label}'")

    return updated, normalized_count


async def main() -> None:
    """Run the HPO label normalization."""
    # Parse arguments
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made to the database")

    # Create database connection
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    total_processed = 0
    total_updated = 0
    total_labels_normalized = 0

    async with async_session() as db:
        # Get all non-deleted phenopackets
        result = await db.execute(
            select(Phenopacket).where(Phenopacket.deleted_at.is_(None))
        )
        phenopackets = result.scalars().all()

        logger.info(f"Processing {len(phenopackets)} phenopackets...")

        for pp in phenopackets:
            total_processed += 1

            # Normalize labels in this phenopacket
            updated_data, count = normalize_phenopacket_labels(pp.phenopacket)

            if count > 0:
                total_labels_normalized += count
                total_updated += 1

                subject_id = pp.phenopacket.get("subject", {}).get("id", pp.id)
                logger.info(f"  Phenopacket {subject_id}: {count} labels normalized")

                if not dry_run:
                    pp.phenopacket = updated_data

        if not dry_run and total_updated > 0:
            await db.commit()
            logger.info(f"Committed {total_updated} updated phenopackets")

            # Refresh materialized views to reflect the changes
            logger.info("Refreshing materialized views...")
            try:
                await db.execute(text("SELECT refresh_all_aggregation_views()"))
                await db.commit()
                logger.info("Materialized views refreshed successfully")
            except Exception as e:
                logger.warning(f"Could not refresh materialized views: {e}")
                logger.info(
                    "You may need to run: SELECT refresh_all_aggregation_views();"
                )

    await engine.dispose()

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("NORMALIZATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Phenopackets processed: {total_processed}")
    logger.info(f"  Phenopackets updated:   {total_updated}")
    logger.info(f"  Labels normalized:      {total_labels_normalized}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("")
        logger.info("This was a DRY RUN. To apply changes, run without --dry-run")


if __name__ == "__main__":
    asyncio.run(main())
