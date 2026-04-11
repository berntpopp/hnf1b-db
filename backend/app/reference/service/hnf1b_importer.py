"""HNF1B reference-data importer.

Owns the idempotent "initialize reference data" workflow: create the
GRCh38 genome assembly, import HNF1B gene + canonical transcript +
nine exons + four protein domains. Extracted during Wave 4 from the
monolithic ``reference/service.py``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import cast

import httpx
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.reference.models import (
    Exon,
    Gene,
    ProteinDomain,
    ReferenceGenome,
    Transcript,
)

from .constants import HNF1B_DOMAINS, HNF1B_EXONS
from .types import SyncResult

logger = logging.getLogger(__name__)


async def get_or_create_grch38_genome(
    db: AsyncSession,
) -> tuple[ReferenceGenome, bool]:
    """Get or create the GRCh38 genome assembly row.

    Returns ``(genome, created)`` — ``created`` is ``True`` only on
    the very first call.
    """
    stmt = select(ReferenceGenome).where(ReferenceGenome.name == "GRCh38")
    result = await db.execute(stmt)
    genome = result.scalar_one_or_none()

    if genome:
        logger.debug("GRCh38 genome already exists")
        return genome, False

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
    db.add(genome)
    await db.flush()
    logger.info("Created GRCh38 genome assembly")
    return genome, True


async def get_genome_by_name(db: AsyncSession, name: str) -> ReferenceGenome | None:
    """Get a genome by name (e.g., ``"GRCh38"``)."""
    stmt = select(ReferenceGenome).where(ReferenceGenome.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_gene_by_symbol(
    db: AsyncSession, symbol: str, genome_id: uuid.UUID
) -> Gene | None:
    """Get a gene by symbol + genome id."""
    stmt = select(Gene).where(and_(Gene.symbol == symbol, Gene.genome_id == genome_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def import_hnf1b_gene(
    db: AsyncSession, genome_id: uuid.UUID
) -> tuple[Gene, bool]:
    """Import or fetch the HNF1B gene row."""
    existing = await get_gene_by_symbol(db, "HNF1B", genome_id)
    if existing:
        return existing, False

    gene = Gene(
        id=uuid.uuid4(),
        symbol="HNF1B",
        name="HNF1 homeobox B",
        chromosome="17",
        start=36098063,
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
    db.add(gene)
    await db.flush()
    logger.info("Created HNF1B gene")
    return gene, True


async def import_hnf1b_transcript(
    db: AsyncSession, gene_id: uuid.UUID
) -> tuple[Transcript, bool]:
    """Import or fetch the HNF1B canonical transcript (NM_000458.4)."""
    stmt = select(Transcript).where(Transcript.transcript_id == "NM_000458.4")
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return existing, False

    transcript = Transcript(
        id=uuid.uuid4(),
        transcript_id="NM_000458.4",
        protein_id="NP_000449.3",
        is_canonical=True,
        cds_start=36098301,
        cds_end=36111805,
        exon_count=9,
        gene_id=gene_id,
        source="RefSeq",
        source_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_000458.4",
        extra_data={"protein_length": 557},
    )
    db.add(transcript)
    await db.flush()
    logger.info("Created HNF1B transcript NM_000458.4")
    return transcript, True


async def import_hnf1b_exons(
    db: AsyncSession,
    transcript_id: uuid.UUID,
    chromosome: str,
    strand: str,
) -> tuple[list[Exon], bool]:
    """Import the nine HNF1B exons.

    Tries to load exon coordinates from ``frontend/src/data/chr17q12_genes.json``
    first; falls back to the ``HNF1B_EXONS`` constant if the file is
    missing or unreadable.
    """
    exon_data = HNF1B_EXONS
    json_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "frontend"
        / "src"
        / "data"
        / "chr17q12_genes.json"
    )

    if json_path.exists():
        try:
            with open(json_path) as f:
                data = json.load(f)
                hnf1b_data = next(
                    (g for g in data.get("genes", []) if g.get("symbol") == "HNF1B"),
                    None,
                )
                if hnf1b_data and "exons" in hnf1b_data:
                    exon_data = hnf1b_data["exons"]
                    logger.debug("Loaded HNF1B exons from chr17q12_genes.json")
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "Failed to load exons from JSON: %s, using hardcoded data", exc
            )

    stmt = select(Exon).where(Exon.transcript_id == transcript_id)
    result = await db.execute(stmt)
    existing = result.scalars().all()
    if existing:
        logger.debug("Exons already exist for transcript %s", transcript_id)
        return list(existing), False

    exons: list[Exon] = []
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
        db.add(exon)
        exons.append(exon)

    await db.flush()
    logger.info("Created %s HNF1B exons", len(exons))
    return exons, True


async def import_hnf1b_domains(
    db: AsyncSession, transcript_id: uuid.UUID
) -> tuple[list[ProteinDomain], bool]:
    """Import the four HNF1B protein domains from UniProt P35680."""
    stmt = select(ProteinDomain).where(ProteinDomain.transcript_id == transcript_id)
    result = await db.execute(stmt)
    existing = result.scalars().all()
    if existing:
        logger.debug("Domains already exist for transcript %s", transcript_id)
        return list(existing), False

    domains: list[ProteinDomain] = []
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
        db.add(domain)
        domains.append(domain)

    await db.flush()
    logger.info("Created %s HNF1B protein domains", len(domains))
    return domains, True


async def initialize_reference_data(db: AsyncSession) -> SyncResult:
    """Initialise all reference data (GRCh38 + HNF1B chain).

    Idempotent — safe to call multiple times. Only newly-created
    items are counted in the result.
    """
    result = SyncResult()

    try:
        genome, genome_created = await get_or_create_grch38_genome(db)
        if genome_created:
            result.imported += 1

        gene, gene_created = await import_hnf1b_gene(db, genome.id)
        if gene_created:
            result.imported += 1

        transcript, transcript_created = await import_hnf1b_transcript(db, gene.id)
        if transcript_created:
            result.imported += 1

        exons, exons_created = await import_hnf1b_exons(
            db, transcript.id, gene.chromosome, gene.strand
        )
        if exons_created:
            result.imported += len(exons) if exons else 0

        domains, domains_created = await import_hnf1b_domains(db, transcript.id)
        if domains_created:
            result.imported += len(domains) if domains else 0

        await db.commit()
        logger.info("Reference data initialized: %s items created", result.imported)

    except (SQLAlchemyError, httpx.HTTPError, ValueError, KeyError) as exc:
        await db.rollback()
        result.errors += 1
        result.error_messages = [str(exc)]
        logger.error("Failed to initialize reference data: %s", exc)

    return result
