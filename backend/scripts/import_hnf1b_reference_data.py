"""Import HNF1B reference data into the database.

Imports:
- Reference genome (GRCh38)
- HNF1B gene data (from chr17q12_genes.json)
- Protein domains (from HNF1BProteinVisualization.vue)
- Exon coordinates

Data sources:
- UniProt P35680 (protein domains, verified 2025-01-17)
- NCBI Gene (gene coordinates)
- chr17q12_genes.json (exon data)

Usage:
    cd backend
    uv run python scripts/import_hnf1b_reference_data.py
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import cast

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.reference.models import (
    Exon,
    Gene,
    ProteinDomain,
    ReferenceGenome,
    Transcript,
)

# HNF1B protein domains from UniProt P35680 (verified 2025-01-17)
# Source: https://www.uniprot.org/uniprotkb/P35680/entry
HNF1B_DOMAINS = [
    {
        "name": "Dimerization Domain",
        "short_name": "Dim",
        "start": 1,
        "end": 31,
        "function": "Mediates homodimer or heterodimer formation",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "POU-Specific Domain",
        "short_name": "POU-S",
        "start": 8,
        "end": 173,
        "function": "DNA binding (part 1)",
        "pfam_id": "PF00157",
        "interpro_id": "IPR000327",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "POU Homeodomain",
        "short_name": "POU-H",
        "start": 232,
        "end": 305,
        "function": "DNA binding (part 2)",
        "interpro_id": "IPR001356",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "Transactivation Domain",
        "short_name": "TAD",
        "start": 314,
        "end": 557,
        "function": "Transcriptional activation",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
]


async def import_reference_data():
    """Import HNF1B reference data."""
    print("=" * 80)
    print("HNF1B Reference Data Import")
    print("=" * 80)
    print()

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Step 1: Import GRCh38 genome
            print("[1/5] Importing GRCh38 genome assembly...")
            genome = await import_genome(session)
            print(f"  ✓ Created genome: {genome.name} (ID: {genome.id})")
            print()

            # Step 2: Import HNF1B gene
            print("[2/5] Importing HNF1B gene...")
            gene = await import_hnf1b_gene(session, genome.id)
            print(
                f"  ✓ Created gene: {gene.symbol} "
                f"({gene.chromosome}:{gene.start}-{gene.end})"
            )
            print()

            # Step 3: Import canonical transcript
            print("[3/5] Importing NM_000458.4 transcript...")
            transcript = await import_hnf1b_transcript(session, gene.id)
            print(
                f"  ✓ Created transcript: {transcript.transcript_id} "
                f"(protein: {transcript.protein_id})"
            )
            print()

            # Step 4: Import exons
            print("[4/5] Importing exon coordinates...")
            exons = await import_hnf1b_exons(
                session, transcript.id, gene.chromosome, gene.strand
            )
            print(f"  ✓ Created {len(exons)} exons")
            print()

            # Step 5: Import protein domains
            print("[5/5] Importing protein domains from UniProt P35680...")
            domains = await import_hnf1b_domains(session, transcript.id)
            print(f"  ✓ Created {len(domains)} protein domains")
            for domain in domains:
                interpro = f" ({domain.interpro_id})" if domain.interpro_id else ""
                print(f"    - {domain.name}{interpro}: aa {domain.start}-{domain.end}")
            print()

            # Commit all changes
            await session.commit()

            print("=" * 80)
            print("✓ Import completed successfully!")
            print("=" * 80)
            print()
            print("Test the API:")
            print("  GET http://localhost:8000/api/v2/reference/genomes")
            print("  GET http://localhost:8000/api/v2/reference/genes/HNF1B")
            print("  GET http://localhost:8000/api/v2/reference/genes/HNF1B/domains")
            print()

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        finally:
            await engine.dispose()


async def import_genome(session: AsyncSession) -> ReferenceGenome:
    """Create GRCh38 genome entry."""
    genome = ReferenceGenome(
        id=uuid.uuid4(),
        name="GRCh38",
        ucsc_name="hg38",
        ensembl_name="GRCh38",
        ncbi_name="GCA_000001405.28",
        version="p14",
        release_date=datetime(2017, 12, 21),
        is_default=True,
        source_url="https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/",
        extra_data={"description": "Genome Reference Consortium Human Build 38"},
    )
    session.add(genome)
    await session.flush()
    return genome


async def import_hnf1b_gene(session: AsyncSession, genome_id: uuid.UUID) -> Gene:
    """Create HNF1B gene entry."""
    gene = Gene(
        id=uuid.uuid4(),
        symbol="HNF1B",
        name="HNF1 homeobox B",
        chromosome="17",
        start=36098063,  # From chr17q12_genes.json
        end=36112306,
        strand="-",
        genome_id=genome_id,
        ensembl_id="ENSG00000275410",
        ncbi_gene_id="6928",
        hgnc_id="HGNC:11630",
        omim_id="189907",
        source="NCBI Gene",
        source_version="2025-01",
        source_url="https://www.ncbi.nlm.nih.gov/gene/6928",
        extra_data={
            "aliases": ["TCF2", "MODY5"],
            "chromosome_band": "17q12",
        },
    )
    session.add(gene)
    await session.flush()
    return gene


async def import_hnf1b_transcript(
    session: AsyncSession, gene_id: uuid.UUID
) -> Transcript:
    """Create HNF1B canonical transcript."""
    transcript = Transcript(
        id=uuid.uuid4(),
        transcript_id="NM_000458.4",
        protein_id="NP_000449.3",
        is_canonical=True,
        cds_start=36098301,  # Approximate CDS coordinates
        cds_end=36111805,
        exon_count=9,  # HNF1B has 9 exons
        gene_id=gene_id,
        source="RefSeq",
        source_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_000458.4",
        extra_data={"protein_length": 557},
    )
    session.add(transcript)
    await session.flush()
    return transcript


async def import_hnf1b_exons(
    session: AsyncSession,
    transcript_id: uuid.UUID,
    chromosome: str,
    strand: str,
) -> list[Exon]:
    """Import HNF1B exon coordinates from chr17q12_genes.json."""
    # Load exon data from JSON file
    json_path = (
        Path(__file__).parent.parent.parent
        / "frontend"
        / "src"
        / "data"
        / "chr17q12_genes.json"
    )

    if not json_path.exists():
        print(f"  ⚠ Warning: {json_path} not found, using hardcoded exon data")
        # Hardcoded exon data as fallback (from chr17q12_genes.json)
        exon_data = [
            {"number": 1, "start": 36098063, "end": 36098372},
            {"number": 2, "start": 36099035, "end": 36099371},
            {"number": 3, "start": 36102283, "end": 36102437},
            {"number": 4, "start": 36103407, "end": 36103619},
            {"number": 5, "start": 36104458, "end": 36104588},
            {"number": 6, "start": 36105361, "end": 36105505},
            {"number": 7, "start": 36106626, "end": 36106784},
            {"number": 8, "start": 36108060, "end": 36108311},
            {"number": 9, "start": 36111731, "end": 36112306},
        ]
    else:
        with open(json_path) as f:
            data = json.load(f)
            hnf1b_data = next(
                (g for g in data["genes"] if g["symbol"] == "HNF1B"), None
            )
            if hnf1b_data and "exons" in hnf1b_data:
                exon_data = hnf1b_data["exons"]
            else:
                print(
                    "  ⚠ Warning: HNF1B exons not found in JSON, using hardcoded data"
                )
                exon_data = [
                    {"number": 1, "start": 36098063, "end": 36098372},
                    {"number": 2, "start": 36099035, "end": 36099371},
                    {"number": 3, "start": 36102283, "end": 36102437},
                    {"number": 4, "start": 36103407, "end": 36103619},
                    {"number": 5, "start": 36104458, "end": 36104588},
                    {"number": 6, "start": 36105361, "end": 36105505},
                    {"number": 7, "start": 36106626, "end": 36106784},
                    {"number": 8, "start": 36108060, "end": 36108311},
                    {"number": 9, "start": 36111731, "end": 36112306},
                ]

    exons = []
    for exon_info in exon_data:
        exon = Exon(
            id=uuid.uuid4(),
            exon_number=exon_info["number"],
            chromosome=chromosome,
            start=exon_info["start"],
            end=exon_info["end"],
            strand=strand,
            transcript_id=transcript_id,
            source="NCBI RefSeq",
        )
        session.add(exon)
        exons.append(exon)

    await session.flush()
    return exons


async def import_hnf1b_domains(
    session: AsyncSession, transcript_id: uuid.UUID
) -> list[ProteinDomain]:
    """Import HNF1B protein domains from UniProt P35680."""
    domains = []
    for domain_data in HNF1B_DOMAINS:
        start_pos = cast(int, domain_data["start"])
        end_pos = cast(int, domain_data["end"])
        domain = ProteinDomain(
            id=uuid.uuid4(),
            name=domain_data["name"],
            short_name=domain_data.get("short_name"),
            start=start_pos,
            end=end_pos,
            length=end_pos - start_pos + 1,
            pfam_id=domain_data.get("pfam_id"),
            interpro_id=domain_data.get("interpro_id"),
            uniprot_id=domain_data.get("uniprot_id"),
            function=domain_data.get("function"),
            transcript_id=transcript_id,
            source=domain_data.get("source", "UniProt"),
            source_url="https://www.uniprot.org/uniprotkb/P35680/entry",
            extra_data={"verified_date": "2025-01-17"},
        )
        session.add(domain)
        domains.append(domain)

    await session.flush()
    return domains


if __name__ == "__main__":
    asyncio.run(import_reference_data())
