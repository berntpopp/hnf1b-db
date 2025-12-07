"""Add GRCh37/hg19 genome assembly to the database.

Creates GRCh37 genome entry for legacy coordinate support.

Usage:
    cd backend
    uv run python scripts/add_grch37_assembly.py
"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.reference.models import ReferenceGenome


async def add_grch37():
    """Add GRCh37 genome assembly."""
    print("=" * 80)
    print("Add GRCh37 Genome Assembly")
    print("=" * 80)
    print()

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Check if GRCh37 already exists
            from sqlalchemy import select

            stmt = select(ReferenceGenome).where(ReferenceGenome.name == "GRCh37")
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                print("⚠ GRCh37 genome assembly already exists")
                print(f"  ID: {existing.id}")
                print(f"  Created: {existing.created_at}")
                print()
                return

            # Create GRCh37 genome entry
            genome = ReferenceGenome(
                id=uuid.uuid4(),
                name="GRCh37",
                ucsc_name="hg19",
                ensembl_name="GRCh37",
                ncbi_name="GCA_000001405.14",
                version="p13",
                release_date=datetime(2009, 2, 27),
                is_default=False,  # GRCh38 remains default
                source_url="https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.25/",
                extra_data={
                    "description": "Genome Reference Consortium Human Build 37",
                    "note": "Legacy assembly for backward compatibility",
                },
            )
            session.add(genome)
            await session.flush()

            print("✓ Created GRCh37 genome assembly")
            print(f"  ID: {genome.id}")
            print(f"  UCSC: {genome.ucsc_name}")
            print(f"  Ensembl: {genome.ensembl_name}")
            print(f"  NCBI: {genome.ncbi_name}")
            print(f"  Version: {genome.version}")
            print(f"  Release: {genome.release_date.strftime('%Y-%m-%d')}")
            print()

            # Commit
            await session.commit()
            print("=" * 80)
            print("✓ GRCh37 assembly added successfully!")
            print("=" * 80)
            print()
            print("Next steps:")
            print("  1. Run liftover script to convert GRCh38 coordinates to GRCh37")
            print("  2. Test API: GET http://localhost:8000/api/v2/reference/genomes")
            print()

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(add_grch37())
