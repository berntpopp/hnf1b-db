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
from migration.phenopackets.ontology_mapper import OntologyMapper
from migration.phenopackets.publication_mapper import PublicationMapper
from migration.phenopackets.reviewer_mapper import ReviewerMapper

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
    Follows Dependency Inversion Principle by injecting OntologyMapper abstraction.
    """

    def __init__(
        self, target_db_url: str, ontology_mapper: Optional[OntologyMapper] = None
    ):
        """Initialize migration with target database.

        Args:
            target_db_url: Database connection URL
            ontology_mapper: Optional ontology mapper (defaults to HPOMapper if not provided).
                            Allows dependency injection for testing and flexibility.
        """
        # Initialize components
        self.sheets_loader = GoogleSheetsLoader(SPREADSHEET_ID, GID_CONFIG)
        self.storage = PhenopacketStorage(target_db_url)
        # Use provided mapper or default to HPOMapper (concrete implementation)
        self.ontology_mapper = ontology_mapper if ontology_mapper else HPOMapper()
        self.publication_mapper: Optional[PublicationMapper] = None
        self.reviewer_mapper: Optional[ReviewerMapper] = None
        self.phenopacket_builder: Optional[PhenopacketBuilder] = None

        # Data storage
        self.individuals_df: Optional[pd.DataFrame] = None
        self.phenotypes_df: Optional[pd.DataFrame] = None
        self.publications_df: Optional[pd.DataFrame] = None
        self.reviewers_df: Optional[pd.DataFrame] = None

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
            # Build HPO mappings from dataframe if ontology_mapper is HPOMapper
            if isinstance(self.ontology_mapper, HPOMapper):
                self.ontology_mapper.build_from_dataframe(self.phenotypes_df)
        else:
            logger.warning("Using default HPO mappings")

        # Load publications (optional)
        self.publications_df = self.sheets_loader.load_sheet("publications")
        if self.publications_df is not None:
            self.publication_mapper = PublicationMapper(self.publications_df)
        else:
            logger.warning("No publication data loaded")

        # Load reviewers (for curation attribution)
        self.reviewers_df = self.sheets_loader.load_sheet("reviewers")
        if self.reviewers_df is not None:
            self.reviewer_mapper = ReviewerMapper(self.reviewers_df)
            logger.info(f"Loaded {len(self.reviewers_df)} reviewers")
        else:
            logger.warning(
                "No reviewer data loaded - curation attribution will be skipped"
            )

        # Initialize phenopacket builder with injected dependencies (DIP)
        self.phenopacket_builder = PhenopacketBuilder(
            self.ontology_mapper, self.publication_mapper
        )

    async def import_reviewers_as_users(self) -> Dict[str, int]:
        """Import reviewers from Google Sheets as user accounts.

        Creates user accounts for all reviewers in the Reviewers sheet,
        enabling proper curation attribution via the reviewed_by FK.

        Returns:
            Dictionary mapping reviewer email -> user ID

        Raises:
            ValueError: If reviewer data not loaded or database session unavailable
        """
        if self.reviewers_df is None or self.reviewer_mapper is None:
            logger.warning("No reviewer data available - skipping user import")
            return {}

        logger.info("Importing reviewers as user accounts...")

        # Import UserImportService here to avoid circular imports
        from app.auth.user_import_service import UserImportService

        # Prepare reviewer data for batch import
        reviewer_data_list = []

        for _, reviewer_row in self.reviewers_df.iterrows():
            email = reviewer_row.get("email")
            if not email or pd.isna(email):
                logger.warning("Skipping reviewer with missing email")
                continue

            # Generate username from email
            username = self.reviewer_mapper.generate_username(email)

            # Get full name
            full_name = self.reviewer_mapper.get_full_name(email)

            # Get role
            role = self.reviewer_mapper.get_role(email)

            # Get ORCID
            orcid = self.reviewer_mapper.get_orcid(email)

            reviewer_data_list.append(
                {
                    "email": email,
                    "username": username,
                    "full_name": full_name,
                    "role": role,
                    "orcid": orcid,
                }
            )

        # Import users using the storage's database session
        email_to_user_id = {}

        # Get database session from storage
        async with self.storage.async_session() as db:
            users = await UserImportService.create_or_update_curator_batch(
                db=db, reviewer_data_list=reviewer_data_list
            )

            # Commit the transaction
            await db.commit()

            # Build email -> user ID mapping
            for user in users:
                email_to_user_id[user.email] = user.id

        logger.info(
            f"Successfully imported {len(email_to_user_id)} reviewers as user accounts"
        )

        return email_to_user_id

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
        # Ensure data has been loaded (must call load_data() first)
        assert self.individuals_df is not None, (
            "Must call load_data() before building phenopackets"
        )
        assert self.phenopacket_builder is not None, (
            "Phenopacket builder not initialized"
        )

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

        sex_distribution: Dict[str, int] = {}
        for p in phenopackets:
            sex = p.get("subject", {}).get("sex", "UNKNOWN")
            sex_distribution[sex] = sex_distribution.get(sex, 0) + 1

        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total phenopackets created: {total}")
        logger.info(
            f"With phenotypic features: {with_phenotypes} ({with_phenotypes * 100 // total if total else 0}%)"
        )
        logger.info(
            f"With genetic variants: {with_variants} ({with_variants * 100 // total if total else 0}%)"
        )
        logger.info(
            f"With disease diagnoses: {with_diseases} ({with_diseases * 100 // total if total else 0}%)"
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

            # Import reviewers as user accounts (before building phenopackets)
            # This ensures users exist before we link phenopackets to them
            if not dry_run:
                email_to_user_id = await self.import_reviewers_as_users()
                logger.info(
                    f"Reviewer import complete: {len(email_to_user_id)} users created/updated"
                )
            else:
                logger.info("Dry run mode - skipping reviewer import")

            # Build phenopackets
            phenopackets = self.build_phenopackets(limit=limit)

            if dry_run:
                # Save to JSON file for inspection
                output_file = f"phenopackets_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, "w") as f:
                    json.dump(phenopackets, f, indent=2)
                logger.info(f"Dry run complete. Phenopackets saved to {output_file}")
            else:
                # Store phenopackets in database with reviewer attribution and audit trail
                await self.storage.store_phenopackets(
                    phenopackets=phenopackets,
                    reviewer_mapper=self.reviewer_mapper,
                    create_audit=True,  # Create audit entries for initial import
                )

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
        # Configurable test limit via environment variable or default
        try:
            limit = int(os.getenv("TEST_MODE_LIMIT", "20"))
        except ValueError:
            logger.warning(
                f"Invalid TEST_MODE_LIMIT value: {os.getenv('TEST_MODE_LIMIT')}. "
                "Using default of 20."
            )
            limit = 20
        logger.info(f"Running in TEST MODE - limiting to {limit} individuals")

    if dry_run:
        logger.info("Running in DRY RUN MODE - will output to JSON file")

    # Run migration
    migration = DirectSheetsToPhenopackets(target_db)
    await migration.migrate(limit=limit, test_mode=test_mode, dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())
