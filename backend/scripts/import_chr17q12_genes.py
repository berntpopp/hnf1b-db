"""Import chr17q12 region genes into the database.

Imports all 30 genes from the chr17q12 region (GRCh38).

Data source:
- frontend/src/data/chr17q12_genes.json

Genes imported:
- CCL3, CCL4, CCL18, CCL23 (chemokines)
- TBC1D3B, TBC1D3G, TBC1D3 (GTPase activators)
- ZNHIT3, SYNRG, MYO19, AATF, DDX52 (various functions)
- PIGW, ACACA, TADA2A, DUSP14, GGNBP2 (metabolism, signaling)
- HNF1B (transcription factor - already imported)
- LHX1 (homeobox)
- MRPL45, SOCS7, LASP1, PLXDC1, CDK12 (various)
- ERBB2, GRB7 (oncogenes)
- DHRS11, MRM1, C17orf78 (various)

Usage:
    cd backend
    uv run python scripts/import_chr17q12_genes.py
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.reference.models import Gene, ReferenceGenome


async def import_chr17q12_genes():
    """Import chr17q12 region genes from JSON file."""
    print("=" * 80)
    print("chr17q12 Region Genes Import (GRCh38)")
    print("=" * 80)
    print()

    # Load gene data from JSON file
    json_path = (
        Path(__file__).parent.parent.parent
        / "frontend"
        / "src"
        / "data"
        / "chr17q12_genes.json"
    )

    if not json_path.exists():
        print(f"❌ Error: {json_path} not found")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    genes_data = data.get("genes", [])
    if not genes_data:
        print("❌ Error: No genes found in JSON file")
        sys.exit(1)

    print(f"📁 Loaded {len(genes_data)} genes from {json_path.name}")
    print()

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Get GRCh38 genome
            print("[1/3] Fetching GRCh38 genome assembly...")
            genome = await get_genome(session, "GRCh38")
            print(f"  ✓ Found genome: {genome.name} (ID: {genome.id})")
            print()

            # Import genes
            print(f"[2/3] Importing {len(genes_data)} genes...")
            imported_count = 0
            updated_count = 0

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
                    existing.source = "chr17q12_genes.json"
                    existing.extra_data = {
                        "transcript_id": gene_data.get("transcriptId"),
                        "mim": gene_data.get("mim"),
                        "function": gene_data.get("function"),
                        "phenotype": gene_data.get("phenotype"),
                        "clinical_significance": gene_data.get("clinicalSignificance"),
                        "color": gene_data.get("color"),
                        "size": gene_data.get("size"),
                    }
                    updated_count += 1
                    start = gene_data["start"]
                    end = gene_data["end"]
                    print(f"  ↻ Updated: {symbol} (chr17:{start}-{end})")
                else:
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
                        source="chr17q12_genes.json",
                        source_version="2025-01",
                        extra_data={
                            "transcript_id": gene_data.get("transcriptId"),
                            "mim": gene_data.get("mim"),
                            "function": gene_data.get("function"),
                            "phenotype": gene_data.get("phenotype"),
                            "clinical_significance": gene_data.get(
                                "clinicalSignificance"
                            ),
                            "color": gene_data.get("color"),
                            "size": gene_data.get("size"),
                        },
                    )
                    session.add(gene)
                    imported_count += 1
                    start = gene_data["start"]
                    end = gene_data["end"]
                    print(f"  + Imported: {symbol} (chr17:{start}-{end})")

            await session.flush()
            print()
            print(f"  ✓ Imported: {imported_count} new genes")
            print(f"  ✓ Updated: {updated_count} existing genes")
            print()

            # Commit all changes
            print("[3/3] Committing changes...")
            await session.commit()
            print("  ✓ Changes committed")
            print()

            print("=" * 80)
            print("✓ Import completed successfully!")
            print("=" * 80)
            print()
            print("Summary:")
            print(f"  - Total genes in JSON: {len(genes_data)}")
            print(f"  - New genes imported: {imported_count}")
            print(f"  - Existing genes updated: {updated_count}")
            total = imported_count + updated_count
            print(f"  - Total genes in chr17q12 region: {total}")
            print()
            print("Test the API:")
            print("  GET http://localhost:8000/api/v2/reference/genes?chromosome=17")
            print("  GET http://localhost:8000/api/v2/reference/regions/17:36000000-39900000")
            print()

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        finally:
            await engine.dispose()


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

    stmt = select(Gene).where(
        and_(Gene.symbol == symbol, Gene.genome_id == genome_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


if __name__ == "__main__":
    asyncio.run(import_chr17q12_genes())
