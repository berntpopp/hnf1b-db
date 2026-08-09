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
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from app.core.config import settings
from migration.data_sources.google_sheets_adapter import GoogleSheetsSourceAdapter
from migration.data_sources.source_adapter import SourceAdapter
from migration.database.storage import PhenopacketStorage
from migration.phenopackets.builder_simple import PhenopacketBuilder
from migration.phenopackets.hpo_mapper import HPOMapper
from migration.phenopackets.laterality import (
    ModifierVocabulary,
    modifier_vocabulary_from_rows,
)
from migration.phenopackets.ontology_mapper import OntologyMapper
from migration.phenopackets.publication_mapper import PublicationMapper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def write_dry_run_atomically(
    destination: Path, phenopackets: list[dict[str, Any]]
) -> None:
    """Publish a complete dry-run artifact or leave no output behind."""
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(phenopackets, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


class DirectSheetsToPhenopackets:
    """Direct migration from Google Sheets to Phenopackets format.

    Orchestrates the migration process using modular components.
    Follows Dependency Inversion Principle by injecting OntologyMapper abstraction.
    """

    def __init__(
        self,
        target_db_url: str,
        ontology_mapper: Optional[OntologyMapper] = None,
        source_adapter: SourceAdapter | None = None,
    ):
        """Initialize migration with target database.

        Args:
            target_db_url: Database connection URL
            ontology_mapper: Optional ontology mapper (defaults to HPOMapper if not provided).
                            Allows dependency injection for testing and flexibility.
            source_adapter: Complete source snapshot adapter; defaults to the
                explicitly configured remote adapter.
        """
        # The legacy raw-storage writer is intentionally disabled. New applies
        # must use the staged atomic import service and state-service methods.
        self.legacy_apply_is_disabled = True
        self.source_adapter = source_adapter or GoogleSheetsSourceAdapter(
            spreadsheet_id=settings.SOURCE_SPREADSHEET_ID,
            gids={
                "Individuals": settings.SOURCE_INDIVIDUALS_GID,
                "Phenotypes": settings.SOURCE_PHENOTYPES_GID,
                "Phenotype_modifier": settings.SOURCE_PHENOTYPE_MODIFIER_GID,
                "Publications": settings.SOURCE_PUBLICATIONS_GID,
            },
        )
        self.storage = PhenopacketStorage(target_db_url)
        # Use provided mapper or default to HPOMapper (concrete implementation)
        self.ontology_mapper = ontology_mapper if ontology_mapper else HPOMapper()
        self.publication_mapper: Optional[PublicationMapper] = None
        self.phenopacket_builder: Optional[PhenopacketBuilder] = None

        # Data storage
        self.individuals_df: Optional[pd.DataFrame] = None
        self.phenotypes_df: Optional[pd.DataFrame] = None
        self.publications_df: Optional[pd.DataFrame] = None
        self.modifier_vocabulary: ModifierVocabulary | None = None

    async def load_data(self) -> None:
        """Load one complete, validated source snapshot through the adapter."""
        if not settings.SOURCE_IMPORT_ENABLED:
            raise RuntimeError("source import is disabled by configuration")
        snapshot = await self.source_adapter.load()
        self.individuals_df = pd.read_csv(BytesIO(snapshot.raw_sheets["Individuals"]))

        logger.info(f"Loaded {len(self.individuals_df)} rows from individuals sheet")

        self.phenotypes_df = pd.read_csv(BytesIO(snapshot.raw_sheets["Phenotypes"]))
        if isinstance(self.ontology_mapper, HPOMapper):
            self.ontology_mapper.build_from_dataframe(self.phenotypes_df)
        modifier_df = pd.read_csv(
            BytesIO(snapshot.raw_sheets["Phenotype_modifier"]), dtype=str
        ).fillna("")
        self.modifier_vocabulary = modifier_vocabulary_from_rows(
            modifier_df.to_dict(orient="records"),
            version_sha256=snapshot.manifest.sheets["Phenotype_modifier"].sha256,
        )
        self.publications_df = pd.read_csv(BytesIO(snapshot.raw_sheets["Publications"]))
        self.publication_mapper = PublicationMapper(self.publications_df)

        # Initialize phenopacket builder with injected dependencies (DIP)
        self.phenopacket_builder = PhenopacketBuilder(
            self.ontology_mapper,
            self.publication_mapper,
            modifier_vocabulary=self.modifier_vocabulary,
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

        errors: list[str] = []
        for individual_id, group_df in tqdm(
            individual_groups, desc="Building phenopackets"
        ):
            if not self._is_valid_id(individual_id):
                errors.append("invalid source individual identifier")
                continue
            if limit:
                raise RuntimeError("limited source imports are forbidden outside fixture mode")

            try:
                # Build phenopacket for this individual
                phenopacket = self.phenopacket_builder.build_phenopacket(
                    str(individual_id), group_df
                )
                phenopackets.append(phenopacket)
                individual_count += 1

            except Exception:
                errors.append("individual build failed")

        if errors:
            raise RuntimeError("source build failed; no partial output")

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
            if not settings.SOURCE_IMPORT_ENABLED:
                raise RuntimeError("source import is disabled by configuration")
            # Load all data
            await self.load_data()

            # Build phenopackets
            phenopackets = self.build_phenopackets(limit=limit)

            if dry_run:
                # Save to JSON file for inspection
                output_file = Path(
                    f"phenopackets_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                write_dry_run_atomically(output_file, phenopackets)
                logger.info(f"Dry run complete. Phenopackets saved to {output_file}")
            else:
                raise RuntimeError(
                    "legacy direct import is disabled; use the atomic observation "
                    "import service after staging and validation"
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
    # Load environment variables from .env when run as a CLI. This is kept out
    # of module scope on purpose: importing this module (e.g. during test
    # collection) must not mutate os.environ. See
    # tests/test_migration_import_no_env_side_effects.py.
    load_dotenv()

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
