#!/usr/bin/env python3
"""Direct migration from Google Sheets to Phenopackets v2.

This script directly converts data from Google Sheets into GA4GH Phenopackets v2 format,
eliminating the intermediate PostgreSQL normalization step.

Refactored version using modular components.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from migration.data_sources.google_sheets import GoogleSheetsLoader
from migration.database.storage import PhenopacketStorage
from migration.phenopackets.builder_simple import PhenopacketBuilder
from migration.phenopackets.hpo_mapper import HPOMapper
from migration.phenopackets.publication_mapper import PublicationMapper

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Google Sheets configuration
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
GID_CONFIG = {
    "individuals": "0",
    "phenotypes": "1119329208",
    "modifiers": "1350764936",
    "publications": "1670256162",
    "reviewers": "1321366018",
}


class DirectSheetsToPhenopackets:
    """Direct migration from Google Sheets to Phenopackets format.

    Orchestrates the migration process using modular components.
    """

    def __init__(self, target_db_url: str):
        """Initialize migration with target database.

        Args:
            target_db_url: Database connection URL
        """
        # Initialize components
        self.sheets_loader = GoogleSheetsLoader(SPREADSHEET_ID, GID_CONFIG)
        self.storage = PhenopacketStorage(target_db_url)
        self.hpo_mapper = HPOMapper()
        self.publication_mapper = None
        self.phenopacket_builder = None

        # Data storage
        self.individuals_df = None
        self.phenotypes_df = None
        self.publications_df = None

    async def load_data(self) -> None:
        """Load all data from Google Sheets."""
        logger.info("Loading data from Google Sheets...")

        # Load individuals sheet
        self.individuals_df = self.sheets_loader.load_sheet("individuals")
        if self.individuals_df is None:
            raise ValueError("Failed to load individuals sheet")

        logger.info(f"Loaded {len(self.individuals_df)} rows from individuals sheet")

        # Load phenotypes sheet for HPO mappings
        self.phenotypes_df = self.sheets_loader.load_sheet("phenotypes")
        if self.phenotypes_df is not None:
            self.hpo_mapper.build_from_dataframe(self.phenotypes_df)
        else:
            logger.warning("Using default HPO mappings")

        # Load publications (optional)
        self.publications_df = self.sheets_loader.load_sheet("publications")
        if self.publications_df is not None:
            self.publication_mapper = PublicationMapper(self.publications_df)
        else:
            logger.warning("No publication data loaded")

        # Initialize phenopacket builder with mappers
        self.phenopacket_builder = PhenopacketBuilder(
            self.hpo_mapper, self.publication_mapper
        )

    def _is_valid_id(self, value: Any) -> bool:
        """Check if an ID value is valid (not NaN, empty, or whitespace)."""
        if pd.isna(value):
            return False
        str_value = str(value).strip()
        return str_value != "" and str_value != "NaN"

    def build_phenopackets(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Build phenopackets from loaded data.

        Args:
            limit: Optional limit on number of individuals to process

        Returns:
            List of phenopacket dictionaries
        """
        # Normalize column names
        self.individuals_df.columns = [
            col.strip() for col in self.individuals_df.columns
        ]

        # Group rows by individual_id
        individual_groups = self.individuals_df.groupby("individual_id", dropna=False)

        phenopackets = []
        individual_count = 0

        logger.info(f"Processing {len(individual_groups)} individuals...")

        for individual_id, group_df in tqdm(
            individual_groups, desc="Building phenopackets"
        ):
            if not self._is_valid_id(individual_id):
                continue

            if limit and individual_count >= limit:
                break

            try:
                # Build phenopacket for this individual
                phenopacket = self.phenopacket_builder.build_phenopacket(
                    str(individual_id), group_df
                )
                phenopackets.append(phenopacket)
                individual_count += 1

            except Exception as e:
                logger.error(f"Error processing individual {individual_id}: {e}")
                continue

        logger.info(f"Built {len(phenopackets)} phenopackets")
        return phenopackets

    def generate_summary(self, phenopackets: List[Dict[str, Any]]) -> None:
        """Generate migration summary statistics.

        Args:
            phenopackets: List of phenopacket dictionaries
        """
        total = len(phenopackets)
        with_phenotypes = sum(1 for p in phenopackets if p.get("phenotypicFeatures"))
        with_variants = sum(1 for p in phenopackets if p.get("interpretations"))
        with_diseases = sum(1 for p in phenopackets if p.get("diseases"))

        sex_distribution = {}
        for p in phenopackets:
            sex = p.get("subject", {}).get("sex", "UNKNOWN")
            sex_distribution[sex] = sex_distribution.get(sex, 0) + 1

        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total phenopackets created: {total}")
        logger.info(
            f"With phenotypic features: {with_phenotypes} ({with_phenotypes*100//total if total else 0}%)"
        )
        logger.info(
            f"With genetic variants: {with_variants} ({with_variants*100//total if total else 0}%)"
        )
        logger.info(
            f"With disease diagnoses: {with_diseases} ({with_diseases*100//total if total else 0}%)"
        )
        logger.info(f"Sex distribution: {sex_distribution}")
        logger.info("=" * 60)

    async def migrate(
        self,
        limit: Optional[int] = None,
        test_mode: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Execute the complete migration.

        Args:
            limit: Optional limit on number of individuals to process
            test_mode: If True, process only limited individuals
            dry_run: If True, output to JSON file instead of database
        """
        try:
            # Load all data
            await self.load_data()

            # Build phenopackets
            phenopackets = self.build_phenopackets(limit=limit)

            if dry_run:
                # Save to JSON file for inspection
                output_file = f"phenopackets_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, "w") as f:
                    json.dump(phenopackets, f, indent=2)
                logger.info(f"Dry run complete. Phenopackets saved to {output_file}")
            else:
                # Store phenopackets in database
                await self.storage.store_phenopackets(phenopackets)

            # Generate summary report
            self.generate_summary(phenopackets)

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            # Clean up database connection
            await self.storage.close()


async def main():
    """Run the direct migration."""
    # Get database URL from environment
    target_db = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
    )

    # Parse command line arguments
    import sys

    test_mode = "--test" in sys.argv
    dry_run = "--dry-run" in sys.argv
    limit = None

    if test_mode:
        limit = 20
        logger.info("Running in TEST MODE - limiting to 20 individuals")

    if dry_run:
        logger.info("Running in DRY RUN MODE - will output to JSON file")

    # Run migration
    migration = DirectSheetsToPhenopackets(target_db)
    await migration.migrate(limit=limit, test_mode=test_mode, dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())