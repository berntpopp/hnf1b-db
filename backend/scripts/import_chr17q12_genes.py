"""Import chr17q12 region genes into the database.

Imports all genes from the chr17q12 region (GRCh38) by fetching data
from Ensembl REST API.

Region: chr17:36,000,000-39,900,000 (GRCh38)

Key genes in this region:
- HNF1B (transcription factor - already imported separately)
- LHX1, CCL3, CCL4, CCL18, CCL23, ERBB2, GRB7, and others

Usage:
    cd backend
    uv run python scripts/import_chr17q12_genes.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

import httpx

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.reference.models import Gene, ReferenceGenome

# Ensembl REST API settings
ENSEMBL_API = "https://rest.ensembl.org"
CHR17Q12_REGION = "17:36000000-39900000"


async def fetch_genes_from_ensembl(region: str, timeout: int = 30) -> list[dict]:
    """Fetch genes in a genomic region from Ensembl REST API.

    Args:
        region: Genomic region in format "chr:start-end"
        timeout: HTTP timeout in seconds

    Returns:
        List of gene dictionaries from Ensembl

    Raises:
        httpx.HTTPError: If API request fails
    """
    url = f"{ENSEMBL_API}/overlap/region/human/{region}"
    params = {"feature": "gene", "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        print("📡 Fetching genes from Ensembl API...")
        print(f"   URL: {url}")
        print(f"   Region: {region}")
        print()

        response = await client.get(url, params=params)
        response.raise_for_status()

        # Respect Ensembl rate limits
        await asyncio.sleep(0.1)

        data = response.json()
        print(f"✓ Received {len(data)} features from Ensembl")
        print()

        return data


def parse_gene_from_ensembl(feature: dict) -> dict | None:
    """Parse Ensembl API response into gene data.

    Args:
        feature: Feature dictionary from Ensembl API

    Returns:
        Parsed gene dictionary or None if not a valid gene
    """
    # Filter out non-genes and pseudogenes
    if feature.get("biotype") not in [
        "protein_coding",
        "lncRNA",
        "miRNA",
        "snRNA",
        "snoRNA",
    ]:
        return None

    # Extract gene data
    return {
        "symbol": feature.get("external_name") or feature.get("id"),
        "name": feature.get("description", ""),
        "ensembl_id": feature.get("id"),
        "start": feature.get("start"),
        "end": feature.get("end"),
        "strand": "+" if feature.get("strand") == 1 else "-",
        "biotype": feature.get("biotype"),
        "version": feature.get("version"),
    }


async def import_chr17q12_genes():
    """Import chr17q12 region genes from Ensembl API."""
    print("=" * 80)
    print("chr17q12 Region Genes Import (GRCh38)")
    print("=" * 80)
    print()

    try:
        # Fetch gene data from Ensembl
        print("[1/4] Fetching genes from Ensembl REST API...")
        features = await fetch_genes_from_ensembl(CHR17Q12_REGION)

        # Parse genes
        print("[2/4] Parsing gene data...")
        genes_data = []
        for feature in features:
            gene_data = parse_gene_from_ensembl(feature)
            if gene_data:
                genes_data.append(gene_data)

        if not genes_data:
            print("❌ Error: No valid genes found in Ensembl response")
            sys.exit(1)

        print(f"  ✓ Parsed {len(genes_data)} valid genes")
        print()

        # Create async engine
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Get GRCh38 genome
            print("[3/4] Fetching GRCh38 genome assembly...")
            genome = await get_genome(session, "GRCh38")
            print(f"  ✓ Found genome: {genome.name} (ID: {genome.id})")
            print()

            # Import genes
            print(f"[4/4] Importing {len(genes_data)} genes...")
            imported_count = 0
            updated_count = 0
            skipped_count = 0

            for gene_data in genes_data:
                symbol = gene_data["symbol"]

                # Check if gene already exists
                existing = await get_gene_by_symbol(session, symbol, genome.id)

                if existing:
                    # Update existing gene
                    existing.name = gene_data["name"]
                    existing.start = gene_data["start"]
                    existing.end = gene_data["end"]
                    existing.strand = gene_data["strand"]
                    existing.source = "Ensembl REST API"
                    existing.source_version = "GRCh38"
                    existing.extra_data = {
                        "ensembl_id": gene_data.get("ensembl_id"),
                        "biotype": gene_data.get("biotype"),
                        "version": gene_data.get("version"),
                    }
                    updated_count += 1
                    start = gene_data["start"]
                    end = gene_data["end"]
                    print(f"  ↻ Updated: {symbol} (chr17:{start:,}-{end:,})")
                else:
                    # Skip if gene has invalid coordinates
                    if not gene_data["start"] or not gene_data["end"]:
                        skipped_count += 1
                        print(f"  ⊗ Skipped: {symbol} (missing coordinates)")
                        continue

                    # Create new gene
                    gene = Gene(
                        id=uuid.uuid4(),
                        symbol=symbol,
                        name=gene_data["name"],
                        chromosome="17",
                        start=gene_data["start"],
                        end=gene_data["end"],
                        strand=gene_data["strand"],
                        genome_id=genome.id,
                        source="Ensembl REST API",
                        source_version="GRCh38",
                        extra_data={
                            "ensembl_id": gene_data.get("ensembl_id"),
                            "biotype": gene_data.get("biotype"),
                            "version": gene_data.get("version"),
                        },
                    )
                    session.add(gene)
                    imported_count += 1
                    start = gene_data["start"]
                    end = gene_data["end"]
                    print(f"  + Imported: {symbol} (chr17:{start:,}-{end:,})")

            await session.flush()
            print()
            print(f"  ✓ Imported: {imported_count} new genes")
            print(f"  ✓ Updated: {updated_count} existing genes")
            print(f"  ⊗ Skipped: {skipped_count} genes")
            print()

            # Commit all changes
            print("Committing changes...")
            await session.commit()
            print("  ✓ Changes committed")
            print()

            print("=" * 80)
            print("✓ Import completed successfully!")
            print("=" * 80)
            print()
            print("Summary:")
            print(f"  - Total features from Ensembl: {len(features)}")
            print(f"  - Valid genes parsed: {len(genes_data)}")
            print(f"  - New genes imported: {imported_count}")
            print(f"  - Existing genes updated: {updated_count}")
            print(f"  - Genes skipped: {skipped_count}")
            total = imported_count + updated_count
            print(f"  - Total genes in chr17q12 region: {total}")
            print()
            print("Test the API:")
            print("  GET http://localhost:8000/api/v2/reference/genes?chromosome=17")
            print(
                "  GET http://localhost:8000/api/v2/reference/regions/17:36000000-39900000"
            )
            print()

            await engine.dispose()

    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print("   Check your internet connection and Ensembl API status")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def get_genome(session: AsyncSession, genome_build: str) -> ReferenceGenome:
    """Get genome by name.

    Args:
        session: Database session
        genome_build: Genome assembly name

    Returns:
        ReferenceGenome object

    Raises:
        ValueError: If genome not found
    """
    from sqlalchemy import select

    stmt = select(ReferenceGenome).where(ReferenceGenome.name == genome_build)
    result = await session.execute(stmt)
    genome = result.scalar_one_or_none()

    if not genome:
        raise ValueError(
            f"Genome assembly '{genome_build}' not found. "
            f"Run import_hnf1b_reference_data.py first."
        )

    return genome


async def get_gene_by_symbol(
    session: AsyncSession, symbol: str, genome_id: uuid.UUID
) -> Gene | None:
    """Get gene by symbol and genome ID.

    Args:
        session: Database session
        symbol: Gene symbol
        genome_id: Genome ID

    Returns:
        Gene object or None
    """
    from sqlalchemy import and_, select

    stmt = select(Gene).where(and_(Gene.symbol == symbol, Gene.genome_id == genome_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


if __name__ == "__main__":
    asyncio.run(import_chr17q12_genes())
