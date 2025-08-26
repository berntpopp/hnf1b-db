# app/repositories/individual.py
"""Individual repository for handling individual database operations."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Individual
from app.repositories.base import BaseRepository


class IndividualRepository(BaseRepository[Individual]):
    """Repository for Individual model with report loading capabilities."""

    def __init__(self, session: AsyncSession):
        super().__init__(Individual, session)

    async def get_by_individual_id(
        self, individual_id: str, include_reports: bool = False
    ) -> Optional[Individual]:
        """Get individual by their individual_id (e.g., 'ind0001').

        Args:
            individual_id: The individual identifier
            include_reports: Whether to load associated reports

        Returns:
            Individual instance or None if not found
        """
        load_relationships = ["reports"] if include_reports else None
        return await self.get_by_field(
            "individual_id", individual_id, load_relationships
        )

    async def get_with_reports(self, id) -> Optional[Individual]:
        """Get individual with all associated reports loaded.

        Args:
            id: Individual UUID

        Returns:
            Individual instance with reports or None if not found
        """
        return await self.get_by_id(id, load_relationships=["reports"])

    async def get_with_variants(self, id) -> Optional[Individual]:
        """Get individual with associated variants loaded.

        Args:
            id: Individual UUID

        Returns:
            Individual instance with variants or None if not found
        """
        return await self.get_by_id(id, load_relationships=["variants"])

    async def get_with_full_data(self, id) -> Optional[Individual]:
        """Get individual with all related data (reports and variants).

        Args:
            id: Individual UUID

        Returns:
            Individual instance with all relationships loaded
        """
        return await self.get_by_id(id, load_relationships=["reports", "variants"])

    async def search_individuals(
        self,
        search_term: str = None,
        sex: str = None,
        problematic_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Individual], int]:
        """Search individuals with various filters.

        Args:
            search_term: Search in individual_id, individual_identifier
            sex: Filter by sex
            problematic_only: Only return individuals marked as problematic
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (individuals list, total count)
        """
        filters = {}

        if sex:
            filters["sex"] = sex

        if problematic_only:
            # Filter individuals where problematic field is not empty
            # This will be handled in the custom query below
            pass

        search_fields = (
            ["individual_id", "individual_identifier"] if search_term else None
        )

        if problematic_only:
            # Custom handling for problematic filter
            from sqlalchemy import and_, or_

            query = select(Individual)

            # Add search conditions
            if search_term:
                search_conditions = []
                search_pattern = f"%{search_term}%"
                search_conditions.append(Individual.individual_id.ilike(search_pattern))
                if Individual.individual_identifier:
                    search_conditions.append(
                        Individual.individual_identifier.ilike(search_pattern)
                    )
                query = query.where(or_(*search_conditions))

            # Add sex filter
            if sex:
                query = query.where(Individual.sex == sex)

            # Add problematic filter (not empty string)
            query = query.where(
                and_(Individual.problematic != "", Individual.problematic.isnot(None))
            )

            # Get total count
            from sqlalchemy import func

            count_query = select(func.count()).select_from(query.subquery())
            count_result = await self.session.execute(count_query)
            total = count_result.scalar()

            # Apply pagination and ordering
            query = (
                query.order_by(Individual.created_at.desc()).offset(skip).limit(limit)
            )

            result = await self.session.execute(query)
            individuals = list(result.scalars().all())

            return individuals, total
        else:
            return await self.get_multi(
                skip=skip,
                limit=limit,
                filters=filters,
                search=search_term,
                search_fields=search_fields,
            )

    async def create_individual(
        self,
        individual_id: str,
        sex: Optional[str] = None,
        individual_doi: Optional[str] = None,
        dup_check: Optional[str] = None,
        individual_identifier: Optional[str] = None,
        problematic: str = "",
    ) -> Individual:
        """Create a new individual.

        Args:
            individual_id: Individual identifier (e.g., 'ind0001')
            sex: Sex of the individual
            individual_doi: DOI reference
            dup_check: Duplicate check identifier
            individual_identifier: Alternative identifier
            problematic: Problematic status description

        Returns:
            Created individual instance
        """
        return await self.create(
            individual_id=individual_id,
            sex=sex,
            individual_doi=individual_doi,
            dup_check=dup_check,
            individual_identifier=individual_identifier,
            problematic=problematic,
        )

    async def get_by_sex(self, sex: str) -> List[Individual]:
        """Get all individuals by sex.

        Args:
            sex: Sex to filter by

        Returns:
            List of individuals
        """
        query = select(Individual).where(Individual.sex == sex)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_problematic(self) -> List[Individual]:
        """Get all individuals marked as problematic.

        Returns:
            List of problematic individuals
        """
        from sqlalchemy import and_

        query = select(Individual).where(
            and_(Individual.problematic != "", Individual.problematic.isnot(None))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_sex(self) -> dict:
        """Count individuals by sex.

        Returns:
            Dictionary with sex counts
        """
        from sqlalchemy import func

        query = select(Individual.sex, func.count(Individual.id)).group_by(
            Individual.sex
        )
        result = await self.session.execute(query)
        return {sex or "Unknown": count for sex, count in result.all()}

    async def get_individuals_with_variants(self) -> List[Individual]:
        """Get all individuals that have associated variants.

        Returns:
            List of individuals with variants
        """
        query = (
            select(Individual)
            .join(Individual.variants)
            .options(selectinload(Individual.variants))
            .distinct()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
