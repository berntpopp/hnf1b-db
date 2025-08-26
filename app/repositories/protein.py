# app/repositories/protein.py
"""Protein repository for handling protein structure database operations."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Protein
from app.repositories.base import BaseRepository


class ProteinRepository(BaseRepository[Protein]):
    """Repository for Protein model with feature search capabilities."""

    def __init__(self, session: AsyncSession):
        super().__init__(Protein, session)

    async def get_by_gene(self, gene: str) -> List[Protein]:
        """Get all proteins for a specific gene.

        Args:
            gene: Gene symbol

        Returns:
            List of proteins for the gene
        """
        query = select(Protein).where(Protein.gene == gene)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_protein(self, protein: str) -> Optional[Protein]:
        """Get protein by protein identifier.

        Args:
            protein: Protein identifier

        Returns:
            Protein instance or None if not found
        """
        return await self.get_by_field("protein", protein)

    async def get_by_transcript(self, transcript: str) -> Optional[Protein]:
        """Get protein by transcript identifier.

        Args:
            transcript: Transcript identifier

        Returns:
            Protein instance or None if not found
        """
        return await self.get_by_field("transcript", transcript)

    async def search_proteins(
        self, search_term: str = None, gene: str = None, skip: int = 0, limit: int = 100
    ) -> tuple[List[Protein], int]:
        """Search proteins with various filters.

        Args:
            search_term: Search in gene, transcript, protein fields
            gene: Filter by gene
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (proteins list, total count)
        """
        filters = {}

        if gene:
            filters["gene"] = gene

        search_fields = ["gene", "transcript", "protein"] if search_term else None

        return await self.get_multi(
            skip=skip,
            limit=limit,
            filters=filters,
            search=search_term,
            search_fields=search_fields,
        )

    async def create_protein(
        self, gene: str, transcript: str, protein: str, features: Dict[str, Any] = None
    ) -> Protein:
        """Create a new protein record.

        Args:
            gene: Gene symbol
            transcript: Transcript identifier
            protein: Protein identifier
            features: Protein features as JSONB data

        Returns:
            Created protein instance
        """
        return await self.create(
            gene=gene, transcript=transcript, protein=protein, features=features or {}
        )

    async def update_features(self, id, features: Dict[str, Any]) -> Optional[Protein]:
        """Update protein features.

        Args:
            id: Protein UUID
            features: New features data

        Returns:
            Updated protein instance
        """
        return await self.update(id, features=features)

    async def search_by_feature_type(self, feature_type: str) -> List[Protein]:
        """Search proteins that have a specific feature type.

        Args:
            feature_type: Type of feature to search for

        Returns:
            List of proteins with the feature type
        """
        from sqlalchemy import func

        query = select(Protein).where(
            func.jsonb_path_exists(Protein.features, f"$.{feature_type}")
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_protein_domains(self, id) -> Dict[str, Any]:
        """Get domain information for a protein.

        Args:
            id: Protein UUID

        Returns:
            Domain features or empty dict
        """
        protein = await self.get_by_id(id)
        if protein and protein.features:
            return protein.features.get("domains", {})
        return {}

    async def get_all_genes(self) -> List[str]:
        """Get all unique gene symbols.

        Returns:
            List of gene symbols
        """
        query = select(Protein.gene).distinct()
        result = await self.session.execute(query)
        return [gene for gene in result.scalars().all()]

    async def get_proteins_by_feature_count(
        self, min_features: int = 1
    ) -> List[Protein]:
        """Get proteins with at least a specified number of features.

        Args:
            min_features: Minimum number of features

        Returns:
            List of proteins
        """
        from sqlalchemy import func

        query = select(Protein).where(
            func.jsonb_array_length(
                func.jsonb_path_query_array(Protein.features, "$.**")
            )
            >= min_features
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
