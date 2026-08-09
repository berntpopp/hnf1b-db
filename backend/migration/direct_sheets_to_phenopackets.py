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
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from app.core.config import settings
from app.database import async_session_maker
from app.models.user import User
from app.phenopackets.curation.projection import project_individual
from migration.data_sources.local_fixture_adapter import LocalFixtureSourceAdapter
from migration.data_sources.source_adapter import SourceAdapter
from migration.database.storage import PhenopacketStorage
from migration.phenopackets.laterality import (
    ModifierVocabulary,
    modifier_vocabulary_from_rows,
)
from migration.phenopackets.observation_extractor import (
    ObservationExtractionError,
    extract_observation,
    validate_reviewer_mapping,
)
from migration.phenopackets.ontology_mapper import OntologyMapper
from migration.phenopackets.publication_mapping import (
    PublicationReference,
    publication_mapping_from_rows,
)
from migration.source_manifest import SourceManifest

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

_SHA256 = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceImportCliConfiguration:
    """All explicit, non-live dependencies required by the import command."""

    target_db_url: str
    adapter: LocalFixtureSourceAdapter
    row_hmac_key: bytes
    reviewer_mapping: Mapping[str, tuple[str, str]]
    actor_id: int


ApplySourceImport = Callable[[AsyncSession, User], Awaitable[object]]


async def run_source_import_transaction(
    session: AsyncSession,
    *,
    actor_id: int,
    apply: ApplySourceImport,
) -> object:
    """Run a source import in the caller-owned transaction and commit once."""
    async with session.begin():
        actor = await session.get(User, actor_id)
        if actor is None:
            raise RuntimeError("configured source import actor does not exist")
        return await apply(session, actor)


def source_import_cli_configuration(config: Any) -> SourceImportCliConfiguration:
    """Build the CLI dependencies only from explicit pinned configuration."""
    fixture_dir = str(config.SOURCE_IMPORT_FIXTURE_DIR).strip()
    manifest_sha256 = str(config.SOURCE_IMPORT_MANIFEST_SHA256).strip()
    row_hmac_key = str(config.SOURCE_IMPORT_ROW_HMAC_KEY).encode()
    actor_id = config.SOURCE_IMPORT_ACTOR_ID
    target_db_url = str(config.DATABASE_URL).strip()
    if not target_db_url:
        raise RuntimeError("source import requires a configured database URL")
    if not fixture_dir or not Path(fixture_dir).is_dir():
        raise RuntimeError("source import requires a configured pinned fixture directory")
    if not _SHA256.fullmatch(manifest_sha256):
        raise RuntimeError("source import requires a pinned SHA-256 manifest")
    if len(row_hmac_key) < 16:
        raise RuntimeError("source import requires a configured row HMAC key")
    if not isinstance(actor_id, int) or actor_id < 1:
        raise RuntimeError("source import requires a configured actor")
    try:
        raw_mapping = json.loads(config.SOURCE_IMPORT_REVIEWER_MAPPING_JSON)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("source import requires a configured reviewer mapping") from exc
    if not isinstance(raw_mapping, dict) or not raw_mapping:
        raise RuntimeError("source import requires a configured reviewer mapping")
    reviewer_mapping: dict[str, tuple[str, str]] = {}
    for source_reviewer, mapped in raw_mapping.items():
        if (
            not isinstance(source_reviewer, str)
            or not isinstance(mapped, list)
            or len(mapped) != 2
            or not all(isinstance(value, str) for value in mapped)
        ):
            raise RuntimeError("source import reviewer mapping is invalid")
        reviewer_mapping[source_reviewer] = (mapped[0], mapped[1])
    try:
        validate_reviewer_mapping(reviewer_mapping)
    except ObservationExtractionError as exc:
        raise RuntimeError("source import reviewer mapping is invalid") from exc
    return SourceImportCliConfiguration(
        target_db_url=target_db_url,
        adapter=LocalFixtureSourceAdapter(
            Path(fixture_dir), expected_manifest_sha256=manifest_sha256
        ),
        row_hmac_key=row_hmac_key,
        reviewer_mapping=reviewer_mapping,
        actor_id=actor_id,
    )


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
        reviewer_mapping: Mapping[str, tuple[str, str]] | None = None,
        row_hmac_key: bytes | None = None,
    ):
        """Initialize migration with target database.

        Args:
            target_db_url: Database connection URL
            ontology_mapper: Optional ontology mapper (defaults to HPOMapper if not provided).
                            Allows dependency injection for testing and flexibility.
            source_adapter: Required complete pinned source snapshot adapter.
            reviewer_mapping: Approved pseudonymous reviewer mapping only.
            row_hmac_key: Key for non-reversible per-row source fingerprints.
        """
        # The legacy raw-storage writer is intentionally disabled. New applies
        # must use the staged atomic import service and state-service methods.
        self.legacy_apply_is_disabled = True
        # Migration input must be an approved, immutable snapshot adapter.
        # Google Sheets may be probed separately for drift but is never a
        # direct migration authority.
        self.source_adapter = source_adapter
        self.reviewer_mapping = dict(reviewer_mapping or {})
        self.row_hmac_key = row_hmac_key
        self.storage = PhenopacketStorage(target_db_url)
        self.ontology_mapper = ontology_mapper
        self.publication_mapping: Mapping[str, PublicationReference] | None = None
        self.phenopacket_builder = None

        # Data storage
        self.individuals_df: Optional[pd.DataFrame] = None
        self.phenotypes_df: Optional[pd.DataFrame] = None
        self.publications_df: Optional[pd.DataFrame] = None
        self.modifier_vocabulary: ModifierVocabulary | None = None
        self._source_manifest: SourceManifest | None = None

    async def load_data(self) -> None:
        """Load one complete, validated source snapshot through the adapter."""
        if not settings.SOURCE_IMPORT_ENABLED:
            raise RuntimeError("source import is disabled by configuration")
        if self.source_adapter is None:
            raise RuntimeError("a pinned source snapshot adapter is required")
        snapshot = await self.source_adapter.load()
        self._source_manifest = snapshot.manifest
        self.individuals_df = pd.read_csv(BytesIO(snapshot.raw_sheets["Individuals"]))

        logger.info(f"Loaded {len(self.individuals_df)} rows from individuals sheet")

        self.phenotypes_df = pd.read_csv(BytesIO(snapshot.raw_sheets["Phenotypes"]))
        modifier_df = pd.read_csv(
            BytesIO(snapshot.raw_sheets["Phenotype_modifier"]), dtype=str
        ).fillna("")
        self.modifier_vocabulary = modifier_vocabulary_from_rows(
            modifier_df.to_dict(orient="records"),
            version_sha256=snapshot.manifest.sheets["Phenotype_modifier"].sha256,
        )
        self.publications_df = pd.read_csv(
            BytesIO(snapshot.raw_sheets["Publications"]), dtype=str
        ).fillna("")
        self.publication_mapping = publication_mapping_from_rows(
            self.publications_df.to_dict(orient="records")
        )


    def _build_typed_observations(
        self, *, limit: int | None = None
    ) -> dict[str, list[Any]]:
        """Extract the complete source ledger before any projection or apply."""
        if self.individuals_df is None or self._source_manifest is None:
            raise RuntimeError("source snapshot has not been loaded")
        if self.modifier_vocabulary is None:
            raise RuntimeError("source modifier vocabulary has not been loaded")
        if self.publication_mapping is None:
            raise RuntimeError("source publication mapping has not been loaded")
        if not self.reviewer_mapping or self.row_hmac_key is None:
            raise RuntimeError("approved reviewer mapping and row HMAC key are required")

        observations_by_subject: dict[str, list[Any]] = {}
        for row_number, (_, row) in enumerate(self.individuals_df.iterrows(), start=2):
            observation = extract_observation(
                row.to_dict(),
                row_number=row_number,
                source_system=self._source_manifest.source_system,
                dataset_key=self._source_manifest.dataset_key,
                manifest_sha256=self._source_manifest.sha256,
                row_hmac_key=self.row_hmac_key,
                reviewer_mapping=self.reviewer_mapping,
                modifier_vocabulary=self.modifier_vocabulary,
                publication_mapping=self.publication_mapping,
            )
            observations_by_subject.setdefault(
                observation.identifiers.source_subject_id, []
            ).append(observation)

        if limit is None:
            return observations_by_subject
        if limit < 1:
            raise RuntimeError("test dry-run limit must be positive")
        return dict(sorted(observations_by_subject.items())[:limit])

    def build_typed_phenopackets(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Project validated observations without exporting source-ledger fields."""
        observations_by_subject = self._build_typed_observations(limit=limit)
        return self._project_typed_observations(observations_by_subject)

    @staticmethod
    def _project_typed_observations(
        observations_by_subject: Mapping[str, list[Any]],
    ) -> list[dict[str, Any]]:
        """Project a validated ledger without using the legacy builder."""
        output: list[dict[str, Any]] = []
        for observations in observations_by_subject.values():
            projection = project_individual(
                observations, [], algorithm_version="1.0"
            )
            if projection.blocking_conflicts:
                raise RuntimeError("source projection has unresolved conflicts")
            output.append(projection.phenopacket)
        return output

    async def apply_typed(
        self,
        db: AsyncSession,
        *,
        actor: User,
        observations_by_subject: Mapping[str, list[Any]] | None = None,
    ) -> None:
        """Apply typed observations through the transactional import service."""
        from migration.typed_import_service import TypedObservationImportService

        if self._source_manifest is None:
            raise RuntimeError("source snapshot has not been loaded")
        await TypedObservationImportService(db, actor=actor).apply(
            manifest=self._source_manifest,
            observations_by_subject=(
                dict(observations_by_subject)
                if observations_by_subject is not None
                else self._build_typed_observations()
            ),
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
        # The legacy builder stores raw reviewer metadata and cannot participate
        # in the typed, privacy-safe import pipeline.
        raise RuntimeError("legacy phenopacket builder is disabled")

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
        db: AsyncSession | None = None,
        actor: User | None = None,
    ) -> None:
        """Execute the complete migration.

        Args:
            limit: Optional limit on number of individuals to process
            test_mode: If True, process only limited individuals
            dry_run: If True, output to JSON file instead of database
            db: Caller-owned async session used only for a non-dry apply.
            actor: Accountable import actor used only for a non-dry apply.
        """
        try:
            if not settings.SOURCE_IMPORT_ENABLED:
                raise RuntimeError("source import is disabled by configuration")
            # Load all data
            await self.load_data()

            if limit is not None and not (test_mode and dry_run):
                raise RuntimeError("limited imports require test dry-run mode")
            observations_by_subject = self._build_typed_observations(limit=limit)
            phenopackets = self._project_typed_observations(observations_by_subject)

            if dry_run:
                # Save to JSON file for inspection
                output_file = Path(
                    f"phenopackets_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                write_dry_run_atomically(output_file, phenopackets)
                logger.info(f"Dry run complete. Phenopackets saved to {output_file}")
            else:
                if db is None or actor is None:
                    raise RuntimeError("typed apply requires an injected session and actor")
                await self.apply_typed(
                    db, actor=actor, observations_by_subject=observations_by_subject
                )

            # Generate summary report
            self.generate_summary(phenopackets)

        except Exception:
            logger.error("Migration failed")
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
    if not settings.SOURCE_IMPORT_ENABLED:
        raise RuntimeError("source import is disabled by configuration")
    configuration = source_import_cli_configuration(settings)

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
    migration = DirectSheetsToPhenopackets(
        configuration.target_db_url,
        source_adapter=configuration.adapter,
        reviewer_mapping=configuration.reviewer_mapping,
        row_hmac_key=configuration.row_hmac_key,
    )
    async with async_session_maker() as session:
        await run_source_import_transaction(
            session,
            actor_id=configuration.actor_id,
            apply=lambda transaction_session, actor: migration.migrate(
                limit=limit,
                test_mode=test_mode,
                dry_run=dry_run,
                db=transaction_session,
                actor=actor,
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
