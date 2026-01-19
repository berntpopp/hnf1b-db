"""Reference data service for managing genomic reference data.

Provides async functions for:
- Initializing reference genome (GRCh38)
- Importing HNF1B gene with transcripts, exons, and protein domains
- Syncing chr17q12 region genes from Ensembl REST API

This service follows the same pattern as publications/service.py and
variants/service.py, providing reusable functions that can be called
from CLI scripts or admin endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, cast

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import CHR17Q12_REGION_END, CHR17Q12_REGION_START
from app.reference.models import (
    Exon,
    Gene,
    ProteinDomain,
    ReferenceGenome,
    Transcript,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Ensembl REST API settings
ENSEMBL_API_BASE = "https://rest.ensembl.org"
CHR17Q12_REGION = f"17:{CHR17Q12_REGION_START}-{CHR17Q12_REGION_END}"
ENSEMBL_RATE_LIMIT_DELAY = 0.1  # 10 req/sec

# Valid biotypes to import (exclude pseudogenes)
VALID_BIOTYPES = ["protein_coding", "lncRNA", "miRNA", "snRNA", "snoRNA"]

# HNF1B protein domains from UniProt P35680 (verified 2025-01-17)
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

# HNF1B exon data (fallback if chr17q12_genes.json not found)
HNF1B_EXONS = [
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


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class SyncResult:
    """Result of a sync operation."""

    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] | None = None

    @property
    def total(self) -> int:
        """Total processed items."""
        return self.imported + self.updated + self.skipped + self.errors


@dataclass
class ReferenceDataStatus:
    """Status of reference data in the database."""

    genome_count: int = 0
    gene_count: int = 0
    transcript_count: int = 0
    exon_count: int = 0
    domain_count: int = 0
    has_grch38: bool = False
    has_hnf1b: bool = False
    chr17q12_gene_count: int = 0
    last_updated: Optional[datetime] = None


# =============================================================================
# Genome Operations
# =============================================================================


async def get_or_create_grch38_genome(
    db: AsyncSession,
) -> tuple[ReferenceGenome, bool]:
    """Get or create the GRCh38 genome assembly.

    Args:
        db: Database session

    Returns:
        Tuple of (ReferenceGenome object for GRCh38, created: bool)
    """
    stmt = select(ReferenceGenome).where(ReferenceGenome.name == "GRCh38")
    result = await db.execute(stmt)
    genome = result.scalar_one_or_none()

    if genome:
        logger.debug("GRCh38 genome already exists")
        return genome, False

    # Create new genome
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
    """Get genome by name.

    Args:
        db: Database session
        name: Genome name (e.g., "GRCh38")

    Returns:
        ReferenceGenome or None if not found
    """
    stmt = select(ReferenceGenome).where(ReferenceGenome.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# =============================================================================
# Gene Operations
# =============================================================================


async def get_gene_by_symbol(
    db: AsyncSession, symbol: str, genome_id: uuid.UUID
) -> Gene | None:
    """Get gene by symbol and genome ID.

    Args:
        db: Database session
        symbol: Gene symbol (e.g., "HNF1B")
        genome_id: Genome UUID

    Returns:
        Gene or None if not found
    """
    stmt = select(Gene).where(and_(Gene.symbol == symbol, Gene.genome_id == genome_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def import_hnf1b_gene(
    db: AsyncSession, genome_id: uuid.UUID
) -> tuple[Gene, bool]:
    """Import or update HNF1B gene.

    Args:
        db: Database session
        genome_id: Genome UUID

    Returns:
        Tuple of (Gene, created: bool)
    """
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
    """Import or update HNF1B canonical transcript.

    Args:
        db: Database session
        gene_id: Gene UUID

    Returns:
        Tuple of (Transcript, created: bool)
    """
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
    """Import HNF1B exon coordinates.

    Args:
        db: Database session
        transcript_id: Transcript UUID
        chromosome: Chromosome (e.g., "17")
        strand: Strand ("+" or "-")

    Returns:
        Tuple of (list of Exon objects, created: bool)
    """
    # Try to load from chr17q12_genes.json
    exon_data = HNF1B_EXONS
    json_path = (
        Path(__file__).parent.parent.parent.parent
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
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load exons from JSON: {e}, using hardcoded data")

    # Check if exons already exist
    stmt = select(Exon).where(Exon.transcript_id == transcript_id)
    result = await db.execute(stmt)
    existing = result.scalars().all()
    if existing:
        logger.debug(f"Exons already exist for transcript {transcript_id}")
        return list(existing), False

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
        db.add(exon)
        exons.append(exon)

    await db.flush()
    logger.info(f"Created {len(exons)} HNF1B exons")
    return exons, True


async def import_hnf1b_domains(
    db: AsyncSession, transcript_id: uuid.UUID
) -> tuple[list[ProteinDomain], bool]:
    """Import HNF1B protein domains from UniProt P35680.

    Args:
        db: Database session
        transcript_id: Transcript UUID

    Returns:
        Tuple of (list of ProteinDomain objects, created: bool)
    """
    # Check if domains already exist
    stmt = select(ProteinDomain).where(ProteinDomain.transcript_id == transcript_id)
    result = await db.execute(stmt)
    existing = result.scalars().all()
    if existing:
        logger.debug(f"Domains already exist for transcript {transcript_id}")
        return list(existing), False

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
        db.add(domain)
        domains.append(domain)

    await db.flush()
    logger.info(f"Created {len(domains)} HNF1B protein domains")
    return domains, True


# =============================================================================
# Bootstrap (HNF1B Reference Data)
# =============================================================================


async def initialize_reference_data(db: AsyncSession) -> SyncResult:
    """Initialize all reference data (GRCh38 + HNF1B gene + transcript + domains).

    This is idempotent - can be called multiple times safely.
    Only newly created items are counted in the result.

    Args:
        db: Database session

    Returns:
        SyncResult with counts of actually created items
    """
    result = SyncResult()

    try:
        # Step 1: Create GRCh38 genome
        genome, genome_created = await get_or_create_grch38_genome(db)
        if genome_created:
            result.imported += 1

        # Step 2: Import HNF1B gene
        gene, gene_created = await import_hnf1b_gene(db, genome.id)
        if gene_created:
            result.imported += 1

        # Step 3: Import canonical transcript
        transcript, transcript_created = await import_hnf1b_transcript(db, gene.id)
        if transcript_created:
            result.imported += 1

        # Step 4: Import exons (only count if newly created)
        exons, exons_created = await import_hnf1b_exons(
            db, transcript.id, gene.chromosome, gene.strand
        )
        if exons_created:
            result.imported += len(exons) if exons else 0

        # Step 5: Import protein domains (only count if newly created)
        domains, domains_created = await import_hnf1b_domains(db, transcript.id)
        if domains_created:
            result.imported += len(domains) if domains else 0

        await db.commit()
        logger.info(f"Reference data initialized: {result.imported} items created")

    except Exception as e:
        await db.rollback()
        result.errors += 1
        result.error_messages = [str(e)]
        logger.error(f"Failed to initialize reference data: {e}")

    return result


# =============================================================================
# chr17q12 Region Gene Sync
# =============================================================================


async def fetch_genes_from_ensembl(
    region: str = CHR17Q12_REGION,
    timeout: int = 30,
) -> list[dict]:
    """Fetch genes in a genomic region from Ensembl REST API.

    Args:
        region: Genomic region in format "chr:start-end"
        timeout: HTTP timeout in seconds

    Returns:
        List of gene dictionaries from Ensembl

    Raises:
        httpx.HTTPError: If API request fails
    """
    url = f"{ENSEMBL_API_BASE}/overlap/region/human/{region}"
    params = {"feature": "gene", "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info(f"Fetching genes from Ensembl: {region}")
        response = await client.get(url, params=params)
        response.raise_for_status()

        # Respect Ensembl rate limits
        await asyncio.sleep(ENSEMBL_RATE_LIMIT_DELAY)

        data = response.json()
        logger.info(f"Received {len(data)} features from Ensembl")
        return data


def parse_gene_from_ensembl(feature: dict) -> dict | None:
    """Parse Ensembl API response into gene data.

    Args:
        feature: Feature dictionary from Ensembl API

    Returns:
        Parsed gene dictionary or None if not a valid gene
    """
    biotype = feature.get("biotype")
    if biotype not in VALID_BIOTYPES:
        return None

    return {
        "symbol": feature.get("external_name") or feature.get("id"),
        "name": feature.get("description", ""),
        "ensembl_id": feature.get("id"),
        "start": feature.get("start"),
        "end": feature.get("end"),
        "strand": "+" if feature.get("strand") == 1 else "-",
        "biotype": biotype,
        "version": feature.get("version"),
    }


async def sync_chr17q12_genes(
    db: AsyncSession,
    region: str = CHR17Q12_REGION,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> SyncResult:
    """Sync chr17q12 region genes from Ensembl REST API.

    Args:
        db: Database session
        region: Genomic region to sync (default: chr17q12)
        dry_run: If True, don't commit changes
        limit: Maximum number of genes to process (for testing)

    Returns:
        SyncResult with counts
    """
    result = SyncResult(error_messages=[])

    try:
        # Ensure GRCh38 genome exists
        genome, _ = await get_or_create_grch38_genome(db)

        # Fetch genes from Ensembl
        features = await fetch_genes_from_ensembl(region)

        # Parse genes
        genes_data = []
        for feature in features:
            gene_data = parse_gene_from_ensembl(feature)
            if gene_data:
                genes_data.append(gene_data)

        if limit:
            genes_data = genes_data[:limit]

        logger.info(f"Processing {len(genes_data)} valid genes")

        for gene_data in genes_data:
            symbol = gene_data["symbol"]

            # Check if gene already exists
            existing = await get_gene_by_symbol(db, symbol, genome.id)

            if existing:
                # Update existing gene
                if not dry_run:
                    existing.name = gene_data["name"]
                    existing.start = gene_data["start"]
                    existing.end = gene_data["end"]
                    existing.strand = gene_data["strand"]
                    existing.ensembl_id = gene_data.get("ensembl_id")
                    existing.source = "Ensembl REST API"
                    existing.source_version = "GRCh38"
                    existing.extra_data = {
                        "ensembl_id": gene_data.get("ensembl_id"),
                        "biotype": gene_data.get("biotype"),
                        "version": gene_data.get("version"),
                    }
                result.updated += 1
                logger.debug(f"Updated: {symbol}")
            else:
                # Skip if gene has invalid coordinates
                if not gene_data.get("start") or not gene_data.get("end"):
                    result.skipped += 1
                    logger.warning(f"Skipped {symbol}: missing coordinates")
                    continue

                if not dry_run:
                    gene = Gene(
                        id=uuid.uuid4(),
                        symbol=symbol,
                        name=gene_data["name"],
                        chromosome="17",
                        start=gene_data["start"],
                        end=gene_data["end"],
                        strand=gene_data["strand"],
                        genome_id=genome.id,
                        ensembl_id=gene_data.get("ensembl_id"),
                        source="Ensembl REST API",
                        source_version="GRCh38",
                        extra_data={
                            "biotype": gene_data.get("biotype"),
                            "version": gene_data.get("version"),
                        },
                    )
                    db.add(gene)
                result.imported += 1
                logger.debug(f"Imported: {symbol}")

        if not dry_run:
            await db.commit()
            logger.info(
                f"chr17q12 sync completed: {result.imported} imported, "
                f"{result.updated} updated, {result.skipped} skipped"
            )
        else:
            await db.rollback()
            logger.info(f"chr17q12 dry run: would process {result.total} genes")

    except httpx.HTTPError as e:
        result.errors += 1
        if result.error_messages is not None:
            result.error_messages.append(f"HTTP error: {e}")
        logger.error(f"Failed to fetch from Ensembl: {e}")
    except Exception as e:
        await db.rollback()
        result.errors += 1
        if result.error_messages is not None:
            result.error_messages.append(str(e))
        logger.error(f"Failed to sync chr17q12 genes: {e}")

    return result


# =============================================================================
# Status & Statistics
# =============================================================================


async def get_reference_data_status(db: AsyncSession) -> ReferenceDataStatus:
    """Get current status of reference data in the database.

    Args:
        db: Database session

    Returns:
        ReferenceDataStatus with counts and flags
    """
    from sqlalchemy import func, text

    status = ReferenceDataStatus()

    # Count genomes
    genome_result = await db.execute(select(func.count(ReferenceGenome.id)))
    status.genome_count = genome_result.scalar() or 0

    # Check for GRCh38
    grch38_result = await db.execute(
        select(ReferenceGenome).where(ReferenceGenome.name == "GRCh38")
    )
    status.has_grch38 = grch38_result.scalar_one_or_none() is not None

    # Count genes
    gene_result = await db.execute(select(func.count(Gene.id)))
    status.gene_count = gene_result.scalar() or 0

    # Check for HNF1B
    hnf1b_result = await db.execute(select(Gene).where(Gene.symbol == "HNF1B"))
    status.has_hnf1b = hnf1b_result.scalar_one_or_none() is not None

    # Count transcripts
    transcript_result = await db.execute(select(func.count(Transcript.id)))
    status.transcript_count = transcript_result.scalar() or 0

    # Count exons
    exon_result = await db.execute(select(func.count(Exon.id)))
    status.exon_count = exon_result.scalar() or 0

    # Count domains
    domain_result = await db.execute(select(func.count(ProteinDomain.id)))
    status.domain_count = domain_result.scalar() or 0

    # Count chr17q12 genes (chr17:36000000-39900000)
    chr17q12_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM genes
            WHERE chromosome = '17'
              AND start >= 36000000
              AND "end" <= 39900000
        """)
    )
    status.chr17q12_gene_count = chr17q12_result.scalar() or 0

    # Get last update time
    last_update_result = await db.execute(
        select(func.max(Gene.updated_at))
    )
    status.last_updated = last_update_result.scalar()

    return status
