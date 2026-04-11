"""Database storage operations for phenopackets."""

import json
import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tqdm import tqdm

from app.core.config import settings

logger = logging.getLogger(__name__)


class PhenopacketStorage:
    """Database storage manager for phenopackets."""

    def __init__(self, database_url: str):
        """Initialize storage with database connection.

        Args:
            database_url: Async database URL
        """
        self.engine = create_async_engine(database_url)
        self.session_maker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def async_session(self):
        """Get an async database session context manager.

        Returns:
            Async session context manager

        Example:
            >>> async with storage.async_session() as db:
            ...     result = await db.execute(query)
            ...     await db.commit()
        """
        return self.session_maker()

    async def store_phenopackets(
        self,
        phenopackets: List[Dict[str, Any]],
        reviewer_mapper=None,
        create_audit: bool = False,
    ) -> int:
        """Store phenopackets in the database with proper attribution.

        Args:
            phenopackets: List of phenopacket dictionaries
            reviewer_mapper: ReviewerMapper instance for curator attribution
            create_audit: Whether to create audit trail entries (default: False for backward compat)

        Returns:
            Number of successfully stored phenopackets
        """
        async with self.session_maker() as session:
            stored_count = 0

            # Resolve the audit-actor user ids once. ``reviewer_mapper``
            # still returns username strings (for logging), but the DB
            # now requires BIGINT FKs to ``users.id``. We JOIN each
            # username against ``users`` and fall back to the
            # ``_system_migration_`` placeholder seeded by the Wave 5a
            # FK-ify migration for anything we can't map.
            placeholder_row = (
                await session.execute(
                    text("SELECT id FROM users WHERE username = '_system_migration_'")
                )
            ).fetchone()
            placeholder_id: int | None = (
                placeholder_row.id if placeholder_row is not None else None
            )
            username_to_id: dict[str, int] = {}

            async def _resolve_actor_id(username: str) -> int | None:
                """Map a username to a ``users.id``, cached per import run."""
                if username in username_to_id:
                    return username_to_id[username]
                row = (
                    await session.execute(
                        text("SELECT id FROM users WHERE username = :u"),
                        {"u": username},
                    )
                ).fetchone()
                actor_id = row.id if row is not None else placeholder_id
                if actor_id is not None:
                    username_to_id[username] = actor_id
                return actor_id

            for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
                try:
                    # Extract subject_id and subject_sex from phenopacket
                    subject_id = phenopacket.get("subject", {}).get("id")
                    subject_sex = phenopacket.get("subject", {}).get("sex")

                    # Get curator attribution from phenopacket metadata
                    created_by_username = "data_migration_system"  # Default fallback
                    if reviewer_mapper and "_migration_metadata" in phenopacket:
                        reviewer_email = phenopacket["_migration_metadata"].get(
                            "reviewer_email"
                        )
                        if reviewer_email:
                            created_by_username = reviewer_mapper.generate_username(
                                reviewer_email
                            )
                            logger.debug(
                                f"Mapped reviewer {reviewer_email} → "
                                f"{created_by_username} "
                                f"for phenopacket {phenopacket['id']}"
                            )

                    created_by_id = await _resolve_actor_id(created_by_username)
                    reimport_id = await _resolve_actor_id("data_reimport")

                    # Remove migration metadata before storing
                    phenopacket_clean = {
                        k: v
                        for k, v in phenopacket.items()
                        if k != "_migration_metadata"
                    }

                    # Insert phenopacket with proper attribution and revision
                    query = text("""
                        INSERT INTO phenopackets
                        (id, phenopacket_id, version, phenopacket, subject_id, subject_sex,
                         created_by_id, schema_version, revision)
                        VALUES (gen_random_uuid(), :phenopacket_id, :version, :phenopacket,
                                :subject_id, :subject_sex, :created_by_id, :schema_version, :revision)
                        ON CONFLICT (phenopacket_id) DO UPDATE
                        SET phenopacket = EXCLUDED.phenopacket,
                            subject_id = EXCLUDED.subject_id,
                            subject_sex = EXCLUDED.subject_sex,
                            updated_by_id = :reimport_id,
                            revision = EXCLUDED.revision,
                            updated_at = CURRENT_TIMESTAMP
                    """)

                    await session.execute(
                        query,
                        {
                            "phenopacket_id": phenopacket["id"],
                            "version": "2.0",
                            "phenopacket": json.dumps(phenopacket_clean),
                            "subject_id": subject_id,
                            "subject_sex": subject_sex,
                            "created_by_id": created_by_id,
                            "reimport_id": reimport_id,
                            "schema_version": "2.0.0",
                            "revision": 1,  # All imports start at revision 1
                        },
                    )

                    # Create audit entry if requested
                    if create_audit:
                        audit_query = text("""
                            INSERT INTO phenopacket_audit
                            (id, phenopacket_id, action, old_value, new_value,
                             changed_by_id, change_reason, change_summary)
                            VALUES (gen_random_uuid(), :phenopacket_id, :action, :old_value,
                                    :new_value, :changed_by_id, :change_reason, :change_summary)
                        """)

                        # Generate change summary
                        phenotype_count = len(
                            phenopacket_clean.get("phenotypicFeatures", [])
                        )
                        variant_count = len(
                            phenopacket_clean.get("interpretations", [])
                        )
                        change_summary = (
                            f"Initial import: {phenotype_count} phenotype(s), "
                            f"{variant_count} variant(s)"
                        )

                        await session.execute(
                            audit_query,
                            {
                                "phenopacket_id": phenopacket["id"],
                                "action": "CREATE",
                                "old_value": None,
                                "new_value": json.dumps(phenopacket_clean),
                                "changed_by_id": created_by_id,
                                "change_reason": "Initial import from Google Sheets",
                                "change_summary": change_summary,
                            },
                        )

                    stored_count += 1

                except Exception as e:
                    logger.error(
                        f"Error storing phenopacket {phenopacket.get('id')}: {e}"
                    )
                    logger.exception(e)  # Full traceback for debugging
                    continue

            await session.commit()
            logger.info(f"Successfully stored {stored_count} phenopackets")

            # Refresh materialized views if enabled
            if settings.materialized_views.auto_refresh_after_import:
                await self._refresh_materialized_views(session)

            return stored_count

    async def _refresh_materialized_views(self, session: AsyncSession) -> None:
        """Refresh aggregation materialized views after data import.

        Uses the PostgreSQL function `refresh_all_aggregation_views()` that
        was created by the migration. This uses CONCURRENTLY refresh to allow
        reads during the update.
        """
        if not settings.materialized_views.enabled:
            logger.debug("Materialized views disabled, skipping refresh")
            return

        logger.info("Refreshing materialized views after import...")

        try:
            await session.execute(text("SELECT refresh_all_aggregation_views()"))
            await session.commit()
            logger.info(
                f"Successfully refreshed {len(settings.materialized_views.views)} "
                "materialized views"
            )
        except Exception as e:
            logger.warning(f"Failed to refresh materialized views: {e}")
            logger.debug(
                "Views may not exist yet. Run 'make db-upgrade' to create them."
            )
            # Don't raise - this is a non-critical optimization

    async def close(self):
        """Close database connection."""
        await self.engine.dispose()
