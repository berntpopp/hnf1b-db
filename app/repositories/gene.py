# app/repositories/gene.py
"""Gene repository for handling gene structure database operations."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Gene
from app.repositories.base import BaseRepository


class GeneRepository(BaseRepository[Gene]):
    """Repository for Gene model with genomic coordinate search capabilities."""

    def __init__(self, session: AsyncSession):
        super().__init__(Gene, session)

    async def get_by_gene_symbol(self, gene_symbol: str) -> Optional[Gene]:
        """Get gene by gene symbol.

        Args:
            gene_symbol: Gene symbol (e.g., 'HNF1B')

        Returns:
            Gene instance or None if not found
        """
        return await self.get_by_field("gene_symbol", gene_symbol)

    async def get_by_ensembl_id(self, ensembl_gene_id: str) -> Optional[Gene]:
        """Get gene by Ensembl gene ID.

        Args:
            ensembl_gene_id: Ensembl gene identifier

        Returns:
            Gene instance or None if not found
        """
        return await self.get_by_field("ensembl_gene_id", ensembl_gene_id)

    async def get_by_transcript(self, transcript: str) -> Optional[Gene]:
        """Get gene by transcript identifier.

        Args:
            transcript: Transcript identifier

        Returns:
            Gene instance or None if not found
        """
        return await self.get_by_field("transcript", transcript)

    async def search_genes(
        self, search_term: str = None, skip: int = 0, limit: int = 100
    ) -> tuple[List[Gene], int]:
        """Search genes with text search.

        Args:
            search_term: Search in gene_symbol, ensembl_gene_id, transcript
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (genes list, total count)
        """
        search_fields = (
            ["gene_symbol", "ensembl_gene_id", "transcript"] if search_term else None
        )

        return await self.get_multi(
            skip=skip, limit=limit, search=search_term, search_fields=search_fields
        )

    async def create_gene(
        self,
        gene_symbol: str,
        ensembl_gene_id: str,
        transcript: str,
        exons: List[Dict[str, Any]] = None,
        hg38: Dict[str, Any] = None,
        hg19: Dict[str, Any] = None,
    ) -> Gene:
        """Create a new gene record.

        Args:
            gene_symbol: Gene symbol
            ensembl_gene_id: Ensembl gene ID
            transcript: Transcript identifier
            exons: List of exon data
            hg38: Genomic coordinates for hg38
            hg19: Genomic coordinates for hg19

        Returns:
            Created gene instance
        """
        return await self.create(
            gene_symbol=gene_symbol,
            ensembl_gene_id=ensembl_gene_id,
            transcript=transcript,
            exons=exons or [],
            hg38=hg38 or {},
            hg19=hg19 or {},
        )

    async def update_coordinates(
        self, id, hg38: Dict[str, Any] = None, hg19: Dict[str, Any] = None
    ) -> Optional[Gene]:
        """Update genomic coordinates for a gene.

        Args:
            id: Gene UUID
            hg38: hg38 coordinates
            hg19: hg19 coordinates

        Returns:
            Updated gene instance
        """
        update_data = {}
        if hg38 is not None:
            update_data["hg38"] = hg38
        if hg19 is not None:
            update_data["hg19"] = hg19

        return await self.update(id, **update_data)

    async def update_exons(self, id, exons: List[Dict[str, Any]]) -> Optional[Gene]:
        """Update exon structure for a gene.

        Args:
            id: Gene UUID
            exons: List of exon data

        Returns:
            Updated gene instance
        """
        return await self.update(id, exons=exons)

    async def get_genes_by_chromosome(
        self, chromosome: str, genome_build: str = "hg38"
    ) -> List[Gene]:
        """Get genes on a specific chromosome.

        Args:
            chromosome: Chromosome identifier (e.g., 'chr17')
            genome_build: Genome build ('hg38' or 'hg19')

        Returns:
            List of genes on the chromosome
        """
        from sqlalchemy import func

        coordinate_field = getattr(Gene, genome_build)

        query = select(Gene).where(
            func.jsonb_extract_path_text(coordinate_field, "chromosome") == chromosome
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_genes_in_region(
        self,
        chromosome: str,
        start_position: int,
        end_position: int,
        genome_build: str = "hg38",
    ) -> List[Gene]:
        """Get genes in a genomic region.

        Args:
            chromosome: Chromosome identifier
            start_position: Start position
            end_position: End position
            genome_build: Genome build ('hg38' or 'hg19')

        Returns:
            List of genes in the region
        """
        from sqlalchemy import and_, func

        coordinate_field = getattr(Gene, genome_build)

        query = select(Gene).where(
            and_(
                func.jsonb_extract_path_text(coordinate_field, "chromosome")
                == chromosome,
                func.cast(
                    func.jsonb_extract_path_text(coordinate_field, "start"), Integer
                )
                <= end_position,
                func.cast(
                    func.jsonb_extract_path_text(coordinate_field, "end"), Integer
                )
                >= start_position,
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_exon_count(self, id) -> int:
        """Get the number of exons for a gene.

        Args:
            id: Gene UUID

        Returns:
            Number of exons
        """
        gene = await self.get_by_id(id)
        if gene and gene.exons:
            return len(gene.exons)
        return 0

    async def get_gene_length(self, id, genome_build: str = "hg38") -> Optional[int]:
        """Calculate gene length from coordinates.

        Args:
            id: Gene UUID
            genome_build: Genome build to use

        Returns:
            Gene length in base pairs or None if coordinates not available
        """
        gene = await self.get_by_id(id)
        if not gene:
            return None

        coordinates = getattr(gene, genome_build)
        if coordinates and "start" in coordinates and "end" in coordinates:
            try:
                return int(coordinates["end"]) - int(coordinates["start"]) + 1
            except (ValueError, TypeError):
                return None

        return None

    async def get_all_gene_symbols(self) -> List[str]:
        """Get all unique gene symbols.

        Returns:
            List of gene symbols
        """
        query = select(Gene.gene_symbol).distinct().order_by(Gene.gene_symbol)
        result = await self.session.execute(query)
        return [symbol for symbol in result.scalars().all()]

    async def get_genes_with_coordinates(
        self, genome_build: str = "hg38"
    ) -> List[Gene]:
        """Get genes that have coordinate information for the specified genome build.

        Args:
            genome_build: Genome build to check

        Returns:
            List of genes with coordinates
        """
        from sqlalchemy import func

        coordinate_field = getattr(Gene, genome_build)

        query = select(Gene).where(
            func.jsonb_array_length(func.jsonb_object_keys(coordinate_field)) > 0
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


from sqlalchemy import Integer
