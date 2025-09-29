# app/repositories/variant.py
"""Variant repository for handling genetic variant database operations."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ReportedEntry, Variant, VariantAnnotation, VariantClassification
from app.repositories.base import BaseRepository


class VariantRepository(BaseRepository[Variant]):
    """Repository for Variant model with classification and annotation methods."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        super().__init__(Variant, session)

    async def get_by_variant_id(
        self, variant_id: str, include_current_only: bool = True
    ) -> Optional[Variant]:
        """Get variant by variant_id (e.g., 'var0001').

        Args:
            variant_id: The variant identifier
            include_current_only: Whether to only return current variants

        Returns:
            Variant instance or None if not found
        """
        query = select(Variant).where(Variant.variant_id == variant_id)

        if include_current_only:
            query = query.where(Variant.is_current is True)

        query = query.options(
            selectinload(Variant.classifications),
            selectinload(Variant.annotations),
            selectinload(Variant.reported_entries),
            selectinload(Variant.individuals),
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_full_data(self, id: uuid.UUID) -> Optional[Variant]:
        """Get variant with all related data loaded.

        Args:
            id: Variant UUID

        Returns:
            Variant instance with all relationships loaded
        """
        return await self.get_by_id(
            id,
            load_relationships=[
                "classifications",
                "annotations",
                "reported_entries",
                "individuals",
            ],
        )

    async def get_current_variants(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[List[Variant], int]:
        """Get all current variants (is_current = True).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (variants list, total count)
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            filters={"is_current": True},
            load_relationships=["classifications", "annotations"],
        )

    async def search_variants(
        self,
        search_term: str = None,
        classification_verdict: str = None,
        include_current_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Variant], int]:
        """Search variants with various filters.

        Args:
            search_term: Search in variant_id
            classification_verdict: Filter by classification verdict
            include_current_only: Only include current variants
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (variants list, total count)
        """
        filters = {}

        if include_current_only:
            filters["is_current"] = True

        # If filtering by classification verdict, we need a custom query
        if classification_verdict:
            query = select(Variant)

            if include_current_only:
                query = query.where(Variant.is_current is True)

            # Join with classifications and filter by verdict
            query = query.join(Variant.classifications).where(
                VariantClassification.verdict == classification_verdict
            )

            # Add search term if provided
            if search_term:
                query = query.where(Variant.variant_id.ilike(f"%{search_term}%"))

            # Load relationships
            query = query.options(
                selectinload(Variant.classifications),
                selectinload(Variant.annotations),
                selectinload(Variant.individuals),
            ).distinct()

            # Get total count with optimized query
            from sqlalchemy import func

            # Optimized count query: join only necessary tables, apply filters, count distinct Variant.id
            count_query = select(func.count(func.distinct(Variant.id))).join(Variant.classifications)
            count_query = count_query.where(VariantClassification.verdict == classification_verdict)
            if include_current_only:
                count_query = count_query.where(Variant.is_current.is_(True))
            if search_term:
                count_query = count_query.where(Variant.variant_id.ilike(f"%{search_term}%"))

            count_result = await self.session.execute(count_query)
            total = count_result.scalar() or 0

            # Apply pagination and ordering
            query = query.order_by(Variant.created_at.desc()).offset(skip).limit(limit)

            result = await self.session.execute(query)
            variants = list(result.scalars().all())

            return variants, total
        else:
            search_fields = ["variant_id"] if search_term else None
            return await self.get_multi(
                skip=skip,
                limit=limit,
                filters=filters,
                search=search_term,
                search_fields=search_fields,
                load_relationships=["classifications", "annotations"],
            )

    async def create_variant(self, variant_id: str, is_current: bool = True) -> Variant:
        """Create a new variant.

        Args:
            variant_id: Variant identifier (e.g., 'var0001')
            is_current: Whether this is the current version

        Returns:
            Created variant instance
        """
        return await self.create(variant_id=variant_id, is_current=is_current)

    async def add_classification(
        self,
        variant_id: uuid.UUID,
        verdict: Optional[str] = None,
        criteria: Optional[str] = None,
        comment: Optional[str] = None,
        system: Optional[str] = None,
        classification_date: Optional[datetime] = None,
    ) -> VariantClassification:
        """Add a classification to a variant.

        Args:
            variant_id: Variant UUID
            verdict: Classification verdict
            criteria: Classification criteria
            comment: Comment
            system: Classification system
            classification_date: Date of classification

        Returns:
            Created classification instance
        """
        classification = VariantClassification(
            variant_id=variant_id,
            verdict=verdict,
            criteria=criteria,
            comment=comment,
            system=system,
            classification_date=classification_date,
        )
        self.session.add(classification)
        await self.session.flush()
        await self.session.refresh(classification)
        return classification

    async def add_annotation(
        self,
        variant_id: uuid.UUID,
        transcript: Optional[str] = None,
        c_dot: Optional[str] = None,
        p_dot: Optional[str] = None,
        source: Optional[str] = None,
        annotation_date: Optional[datetime] = None,
    ) -> VariantAnnotation:
        """Add an annotation to a variant.

        Args:
            variant_id: Variant UUID
            transcript: Transcript identifier
            c_dot: cDNA notation
            p_dot: Protein notation
            source: Annotation source
            annotation_date: Date of annotation

        Returns:
            Created annotation instance
        """
        annotation = VariantAnnotation(
            variant_id=variant_id,
            transcript=transcript,
            c_dot=c_dot,
            p_dot=p_dot,
            source=source,
            annotation_date=annotation_date,
        )
        self.session.add(annotation)
        await self.session.flush()
        await self.session.refresh(annotation)
        return annotation

    async def add_reported_entry(
        self,
        variant_id: uuid.UUID,
        variant_reported: str,
        publication_ref: Optional[uuid.UUID] = None,
    ) -> ReportedEntry:
        """Add a reported entry to a variant.

        Args:
            variant_id: Variant UUID
            variant_reported: Reported variant description
            publication_ref: Publication reference UUID

        Returns:
            Created reported entry instance
        """
        entry = ReportedEntry(
            variant_id=variant_id,
            variant_reported=variant_reported,
            publication_ref=publication_ref,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_variants_by_classification(self, verdict: str) -> List[Variant]:
        """Get all variants with a specific classification verdict.

        Args:
            verdict: Classification verdict

        Returns:
            List of variants
        """
        query = (
            select(Variant)
            .join(Variant.classifications)
            .where(VariantClassification.verdict == verdict)
            .options(selectinload(Variant.classifications))
            .distinct()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_variants_by_individual(
        self, individual_id: uuid.UUID
    ) -> List[Variant]:
        """Get all variants associated with a specific individual.

        Args:
            individual_id: Individual UUID

        Returns:
            List of variants
        """
        from app.models import IndividualVariant

        query = (
            select(Variant)
            .join(IndividualVariant)
            .where(IndividualVariant.individual_id == individual_id)
            .where(IndividualVariant.is_current is True)
            .options(
                selectinload(Variant.classifications), selectinload(Variant.annotations)
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_as_outdated(self, variant_id: str) -> List[Variant]:
        """Mark all variants with the given variant_id as not current.

        Args:
            variant_id: Variant identifier

        Returns:
            List of updated variants
        """
        query = select(Variant).where(Variant.variant_id == variant_id)
        result = await self.session.execute(query)
        variants = result.scalars().all()

        for variant in variants:
            variant.is_current = False

        await self.session.flush()
        return list(variants)

    async def get_classification_statistics(self) -> dict:
        """Get statistics about variant classifications.

        Returns:
            Dictionary with classification counts
        """
        from sqlalchemy import func

        query = select(
            VariantClassification.verdict, func.count(VariantClassification.id)
        ).group_by(VariantClassification.verdict)

        result = await self.session.execute(query)
        return {verdict or "Unknown": count for verdict, count in result.all()}

    async def get_recent_variants(
        self, days: int = 30, limit: int = 10
    ) -> List[Variant]:
        """Get recently added variants.

        Args:
            days: Number of days to look back
            limit: Maximum number of variants to return

        Returns:
            List of recent variants
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(Variant)
            .where(Variant.created_at >= cutoff_date)
            .where(Variant.is_current is True)
            .options(selectinload(Variant.classifications))
            .order_by(Variant.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())
