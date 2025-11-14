"""Database storage operations for phenopackets."""

import json
import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tqdm import tqdm

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

    async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]) -> int:
        """Store phenopackets in the database.

        Args:
            phenopackets: List of phenopacket dictionaries

        Returns:
            Number of successfully stored phenopackets
        """
        async with self.session_maker() as session:
            stored_count = 0

            for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
                try:
                    # Extract subject_id and subject_sex from phenopacket
                    subject_id = phenopacket.get("subject", {}).get("id")
                    subject_sex = phenopacket.get("subject", {}).get("sex")

                    # Insert phenopacket with extracted subject data
                    query = text("""
                        INSERT INTO phenopackets
                        (id, phenopacket_id, version, phenopacket, subject_id, subject_sex, created_by, schema_version)
                        VALUES (gen_random_uuid(), :phenopacket_id, :version, :phenopacket, :subject_id, :subject_sex, :created_by, :schema_version)
                        ON CONFLICT (phenopacket_id) DO UPDATE
                        SET phenopacket = EXCLUDED.phenopacket,
                            subject_id = EXCLUDED.subject_id,
                            subject_sex = EXCLUDED.subject_sex,
                            updated_at = CURRENT_TIMESTAMP
                    """)

                    await session.execute(
                        query,
                        {
                            "phenopacket_id": phenopacket["id"],
                            "version": "2.0",
                            "phenopacket": json.dumps(phenopacket),
                            "subject_id": subject_id,
                            "subject_sex": subject_sex,
                            "created_by": "direct_sheets_migration",
                            "schema_version": "2.0.0",
                        },
                    )

                    stored_count += 1

                except Exception as e:
                    logger.error(
                        f"Error storing phenopacket {phenopacket.get('id')}: {e}"
                    )
                    continue

            await session.commit()
            logger.info(f"Successfully stored {stored_count} phenopackets")
            return stored_count

    async def close(self):
        """Close database connection."""
        await self.engine.dispose()
