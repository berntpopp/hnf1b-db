"""API endpoints for reference genome data.

Provides read-only access to:
- Reference genomes (GRCh37, GRCh38, T2T-CHM13)
- Genes (HNF1B and chr17q12 region)
- Transcripts (RefSeq isoforms)
- Protein domains (UniProt/Pfam/InterPro)
- Exons (genomic coordinates)

All endpoints support caching headers for performance.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.reference.models import (
    Gene,
    ReferenceGenome,
    Transcript,
)
from app.reference.schemas import (
    GeneDetailSchema,
    GeneSchema,
    GenomicRegionResponse,
    ProteinDomainsResponse,
    ReferenceGenomeSchema,
    TranscriptDetailSchema,
)

router = APIRouter(prefix="/reference", tags=["reference"])
logger = logging.getLogger(__name__)

# Cache-Control header for reference data (24 hours)
CACHE_MAX_AGE = 86400


@router.get("/genomes", response_model=List[ReferenceGenomeSchema])
async def list_genomes(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> List[ReferenceGenome]:
    """List all available genome assemblies.

    Returns:
        List of genome assemblies with metadata.

    Example:
        GET /api/v2/reference/genomes
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    stmt = select(ReferenceGenome).order_by(
        ReferenceGenome.is_default.desc(), ReferenceGenome.name
    )
    result = await db.execute(stmt)
    genomes = result.scalars().all()

    return list(genomes)


@router.get("/genes", response_model=List[GeneSchema])
async def list_genes(
    response: Response,
    symbol: Optional[str] = Query(None, description="Filter by gene symbol"),
    chromosome: Optional[str] = Query(None, description="Filter by chromosome"),
    genome_build: Optional[str] = Query(
        None, description="Genome assembly name (default: GRCh38)"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Gene]:
    """Query genes by symbol or chromosome.

    Args:
        response: FastAPI response object for setting cache headers
        symbol: Gene symbol to filter (e.g., "HNF1B")
        chromosome: Chromosome to filter (e.g., "17")
        genome_build: Genome assembly name (default: GRCh38)
        db: Database session dependency

    Returns:
        List of genes matching the criteria.

    Example:
        GET /api/v2/reference/genes?symbol=HNF1B&genome_build=GRCh38
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    # Get genome
    genome = await _get_genome(db, genome_build)

    # Build query
    stmt = (
        select(Gene)
        .options(selectinload(Gene.genome))
        .where(Gene.genome_id == genome.id)
    )

    if symbol:
        stmt = stmt.where(Gene.symbol.ilike(f"%{symbol}%"))
    if chromosome:
        stmt = stmt.where(Gene.chromosome == chromosome)

    stmt = stmt.order_by(Gene.symbol)

    result = await db.execute(stmt)
    genes = result.scalars().all()

    return list(genes)


@router.get("/genes/{symbol}", response_model=GeneDetailSchema)
async def get_gene(
    symbol: str,
    response: Response,
    genome_build: Optional[str] = Query(
        None, description="Genome assembly name (default: GRCh38)"
    ),
    db: AsyncSession = Depends(get_db),
) -> Gene:
    """Get gene details with transcripts.

    Args:
        symbol: Gene symbol (e.g., "HNF1B")
        response: FastAPI response object for setting cache headers
        genome_build: Genome assembly name (default: GRCh38)
        db: Database session dependency

    Returns:
        Gene details with transcript isoforms.

    Example:
        GET /api/v2/reference/genes/HNF1B?genome_build=GRCh38
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    # Get genome
    genome = await _get_genome(db, genome_build)

    # Query gene
    stmt = (
        select(Gene)
        .options(
            selectinload(Gene.genome),
            selectinload(Gene.transcripts),
        )
        .where(and_(Gene.symbol == symbol.upper(), Gene.genome_id == genome.id))
    )

    result = await db.execute(stmt)
    gene = result.scalar_one_or_none()

    if not gene:
        raise HTTPException(
            status_code=404,
            detail=f"Gene '{symbol}' not found in {genome.name}",
        )

    return gene


@router.get(
    "/genes/{symbol}/transcripts",
    response_model=List[TranscriptDetailSchema],
)
async def get_gene_transcripts(
    symbol: str,
    response: Response,
    genome_build: Optional[str] = Query(
        None, description="Genome assembly name (default: GRCh38)"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Transcript]:
    """Get all transcript isoforms for a gene with exon coordinates.

    Args:
        symbol: Gene symbol (e.g., "HNF1B")
        response: FastAPI response object for setting cache headers
        genome_build: Genome assembly name (default: GRCh38)
        db: Database session dependency

    Returns:
        List of transcripts with exon coordinates.

    Example:
        GET /api/v2/reference/genes/HNF1B/transcripts
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    # Get genome
    genome = await _get_genome(db, genome_build)

    # Query gene to get transcripts
    stmt = (
        select(Gene)
        .options(
            selectinload(Gene.transcripts).selectinload(Transcript.exons),
        )
        .where(and_(Gene.symbol == symbol.upper(), Gene.genome_id == genome.id))
    )

    result = await db.execute(stmt)
    gene = result.scalar_one_or_none()

    if not gene:
        raise HTTPException(
            status_code=404,
            detail=f"Gene '{symbol}' not found in {genome.name}",
        )

    return list(gene.transcripts)


@router.get("/genes/{symbol}/domains", response_model=ProteinDomainsResponse)
async def get_gene_domains(
    symbol: str,
    response: Response,
    genome_build: Optional[str] = Query(
        None, description="Genome assembly name (default: GRCh38)"
    ),
    db: AsyncSession = Depends(get_db),
) -> ProteinDomainsResponse:
    """Get protein domains for a gene's canonical transcript.

    Returns empty domains array gracefully if reference data is not populated.
    This avoids 404 errors in production when reference tables are empty.

    Args:
        symbol: Gene symbol (e.g., "HNF1B")
        response: FastAPI response object for setting cache headers
        genome_build: Genome assembly name (default: GRCh38)
        db: Database session dependency

    Returns:
        Protein domains with UniProt/Pfam/InterPro annotations.
        Returns empty domains array if reference data unavailable.

    Example:
        GET /api/v2/reference/genes/HNF1B/domains
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    # Resolve genome build name (default to GRCh38 if not specified)
    resolved_genome_build = genome_build or "GRCh38"

    # Try to get genome - return empty response if not found
    # This handles the case where reference tables aren't populated
    try:
        genome = await _get_genome(db, genome_build)
    except HTTPException:
        # Reference data not populated - return empty response gracefully
        return ProteinDomainsResponse(
            gene=symbol.upper(),
            protein=None,
            uniprot=None,
            length=None,
            domains=[],
            genome_build=resolved_genome_build,
            updated_at=None,
        )

    # Query gene to get canonical transcript
    stmt = (
        select(Gene)
        .options(
            selectinload(Gene.transcripts).selectinload(Transcript.protein_domains)
        )
        .where(and_(Gene.symbol == symbol.upper(), Gene.genome_id == genome.id))
    )

    result = await db.execute(stmt)
    gene = result.scalar_one_or_none()

    if not gene:
        # Gene not found - return empty response gracefully
        return ProteinDomainsResponse(
            gene=symbol.upper(),
            protein=None,
            uniprot=None,
            length=None,
            domains=[],
            genome_build=genome.name,
            updated_at=None,
        )

    # Find canonical transcript
    canonical = next((t for t in gene.transcripts if t.is_canonical), None)

    if not canonical:
        # Fallback to first transcript
        canonical = gene.transcripts[0] if gene.transcripts else None

    if not canonical:
        # No transcript - return empty response gracefully
        return ProteinDomainsResponse(
            gene=symbol.upper(),
            protein=None,
            uniprot=None,
            length=None,
            domains=[],
            genome_build=genome.name,
            updated_at=gene.updated_at,
        )

    # Calculate protein length from domain data if available
    protein_length = None
    if canonical.protein_domains:
        protein_length = max(d.end for d in canonical.protein_domains)

    # Get UniProt ID from first domain that has it
    uniprot_id = None
    for domain in canonical.protein_domains:
        if domain.uniprot_id:
            uniprot_id = domain.uniprot_id
            break

    return ProteinDomainsResponse(
        gene=symbol.upper(),
        protein=canonical.protein_id,
        uniprot=uniprot_id,
        length=protein_length,
        domains=list(canonical.protein_domains),  # type: ignore[arg-type]
        genome_build=genome.name,
        updated_at=gene.updated_at,
    )


@router.get("/regions/{region}", response_model=GenomicRegionResponse)
async def get_genomic_region(
    region: str,
    response: Response,
    genome_build: Optional[str] = Query(
        None, description="Genome assembly name (default: GRCh38)"
    ),
    db: AsyncSession = Depends(get_db),
) -> GenomicRegionResponse:
    """Get all genes in a genomic region.

    Args:
        region: Genomic region in format "chr:start-end"
        response: FastAPI response object for setting cache headers
        genome_build: Genome assembly name (default: GRCh38)
        db: Database session dependency

    Returns:
        List of genes overlapping the region.

    Example:
        GET /api/v2/reference/regions/17:36000000-37000000
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

    # Parse region
    try:
        chrom, coords = region.split(":")
        start_str, end_str = coords.split("-")
        start = int(start_str)
        end = int(end_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid region format '{region}'. "
                "Expected: chr:start-end (e.g., 17:36000000-37000000)"
            ),
        )

    # Get genome
    genome = await _get_genome(db, genome_build)

    # Query genes that overlap the region
    # A gene overlaps if: gene.start <= region.end AND gene.end >= region.start
    stmt = (
        select(Gene)
        .options(selectinload(Gene.genome))
        .where(
            and_(
                Gene.genome_id == genome.id,
                Gene.chromosome == chrom,
                Gene.start <= end,
                Gene.end >= start,
            )
        )
        .order_by(Gene.start)
    )

    result = await db.execute(stmt)
    genes = result.scalars().all()

    # Convert genes to schema format with genome_build
    gene_schemas = []
    for gene in genes:
        gene_dict = {
            "id": gene.id,
            "symbol": gene.symbol,
            "name": gene.name,
            "chromosome": gene.chromosome,
            "start": gene.start,
            "end": gene.end,
            "strand": gene.strand,
            "ensembl_id": gene.ensembl_id,
            "ncbi_gene_id": gene.ncbi_gene_id,
            "hgnc_id": gene.hgnc_id,
            "omim_id": gene.omim_id,
            "source": gene.source,
            "source_version": gene.source_version,
            "source_url": gene.source_url,
            "extra_data": gene.extra_data,
            "created_at": gene.created_at,
            "updated_at": gene.updated_at,
        }
        gene_schemas.append(gene_dict)

    return GenomicRegionResponse(
        region=region,
        genome_build=genome.name,
        genes=gene_schemas,  # type: ignore[arg-type]
        total=len(genes),
    )


async def _get_genome(db: AsyncSession, genome_build: Optional[str]) -> ReferenceGenome:
    """Get genome by name or default.

    Args:
        db: Database session
        genome_build: Genome assembly name (or None for default)

    Returns:
        ReferenceGenome object

    Raises:
        HTTPException: If genome not found
    """
    if genome_build:
        stmt = select(ReferenceGenome).where(ReferenceGenome.name == genome_build)
    else:
        # Get default genome
        stmt = select(ReferenceGenome).where(ReferenceGenome.is_default)

    result = await db.execute(stmt)
    genome = result.scalar_one_or_none()

    if not genome:
        if genome_build:
            raise HTTPException(
                status_code=404,
                detail=f"Genome assembly '{genome_build}' not found",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="No default genome assembly configured",
            )

    return genome
