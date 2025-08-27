# app/repositories/report.py
"""Report repository for handling clinical report database operations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Report
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    """Repository for Report model with phenotype search capabilities."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        super().__init__(Report, session)

    async def get_by_report_id(
        self, report_id: str, load_relationships: bool = False
    ) -> Optional[Report]:
        """Get report by report_id (e.g., 'rep0001').

        Args:
            report_id: The report identifier
            load_relationships: Whether to load related data

        Returns:
            Report instance or None if not found
        """
        relationships = (
            ["individual", "reviewer", "publication"] if load_relationships else None
        )
        return await self.get_by_field("report_id", report_id, relationships)

    async def get_with_full_data(self, id: uuid.UUID) -> Optional[Report]:
        """Get report with all related data loaded.

        Args:
            id: Report UUID

        Returns:
            Report instance with all relationships loaded
        """
        return await self.get_by_id(
            id, load_relationships=["individual", "reviewer", "publication"]
        )

    async def get_by_individual_id(self, individual_id: uuid.UUID) -> List[Report]:
        """Get all reports for a specific individual.

        Args:
            individual_id: Individual UUID

        Returns:
            List of reports for the individual
        """
        query = select(Report).where(Report.individual_id == individual_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_reviewer(self, reviewer_id: uuid.UUID) -> List[Report]:
        """Get all reports reviewed by a specific user.

        Args:
            reviewer_id: User UUID

        Returns:
            List of reports reviewed by the user
        """
        query = select(Report).where(Report.reviewed_by == reviewer_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_by_phenotype(
        self,
        phenotype_id: str = None,
        phenotype_name: str = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Report], int]:
        """Search reports by phenotype data stored in JSONB.

        Args:
            phenotype_id: Phenotype ID to search for
            phenotype_name: Phenotype name to search for (partial match)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (reports list, total count)
        """
        query = select(Report)

        conditions = []

        if phenotype_id:
            # Search for specific phenotype ID in the JSONB data
            conditions.append(Report.phenotypes.op("?")(phenotype_id))

        if phenotype_name:
            # Search for phenotype name in the nested JSONB structure
            # This searches for the name in any phenotype entry
            conditions.append(
                func.jsonb_path_exists(
                    Report.phenotypes,
                    f'$.**{{name like_regex "{phenotype_name}" flag "i"}}',
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and ordering
        query = (
            query.options(selectinload(Report.individual))
            .order_by(Report.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        reports = list(result.scalars().all())

        return reports, total

    async def create_report(
        self,
        individual_id: uuid.UUID,
        report_id: str,
        phenotypes: Dict[str, Any] = None,
        reviewed_by: Optional[uuid.UUID] = None,
        publication_ref: Optional[uuid.UUID] = None,
        review_date: Optional[datetime] = None,
        report_date: Optional[datetime] = None,
        comment: Optional[str] = None,
        family_history: Optional[str] = None,
        age_reported: Optional[str] = None,
        age_onset: Optional[str] = None,
        cohort: Optional[str] = None,
    ) -> Report:
        """Create a new report.

        Args:
            individual_id: UUID of the associated individual
            report_id: Report identifier (e.g., 'rep0001')
            phenotypes: Phenotype data as dictionary
            reviewed_by: UUID of reviewing user
            publication_ref: UUID of associated publication
            review_date: Date of review
            report_date: Date of report
            comment: Report comment
            family_history: Family history information
            age_reported: Age when reported
            age_onset: Age at onset
            cohort: Cohort information

        Returns:
            Created report instance
        """
        return await self.create(
            individual_id=individual_id,
            report_id=report_id,
            phenotypes=phenotypes or {},
            reviewed_by=reviewed_by,
            publication_ref=publication_ref,
            review_date=review_date,
            report_date=report_date,
            comment=comment,
            family_history=family_history,
            age_reported=age_reported,
            age_onset=age_onset,
            cohort=cohort,
        )

    async def get_pending_review(self) -> List[Report]:
        """Get reports that are pending review (no reviewer assigned).

        Returns:
            List of reports pending review
        """
        query = (
            select(Report)
            .where(Report.reviewed_by.is_(None))
            .options(selectinload(Report.individual))
            .order_by(Report.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_reviewed_reports(
        self, include_relationships: bool = False
    ) -> List[Report]:
        """Get all reviewed reports.

        Args:
            include_relationships: Whether to load related data

        Returns:
            List of reviewed reports
        """
        query = select(Report).where(Report.reviewed_by.isnot(None))

        if include_relationships:
            query = query.options(
                selectinload(Report.individual),
                selectinload(Report.reviewer),
                selectinload(Report.publication),
            )

        query = query.order_by(Report.review_date.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_reports_by_cohort(self, cohort: str) -> List[Report]:
        """Get reports by cohort.

        Args:
            cohort: Cohort identifier

        Returns:
            List of reports in the cohort
        """
        query = (
            select(Report)
            .where(Report.cohort == cohort)
            .options(selectinload(Report.individual))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_phenotype_statistics(self) -> Dict[str, int]:
        """Get statistics about phenotypes across all reports.

        Returns:
            Dictionary with phenotype counts
        """
        # This query extracts all phenotype IDs from the JSONB data
        query = select(
            func.jsonb_object_keys(Report.phenotypes).label("phenotype_id")
        ).distinct()

        result = await self.session.execute(query)
        phenotype_ids = [row.phenotype_id for row in result.all()]

        # Count occurrences of each phenotype
        phenotype_counts = {}
        for phenotype_id in phenotype_ids:
            count_query = select(func.count(Report.id)).where(
                Report.phenotypes.op("?")(phenotype_id)
            )
            count_result = await self.session.execute(count_query)
            phenotype_counts[phenotype_id] = count_result.scalar()

        return phenotype_counts

    async def update_phenotypes(
        self, id: uuid.UUID, phenotypes: Dict[str, Any]
    ) -> Optional[Report]:
        """Update phenotypes for a report.

        Args:
            id: Report UUID
            phenotypes: New phenotype data

        Returns:
            Updated report instance
        """
        return await self.update(id, phenotypes=phenotypes)

    async def assign_reviewer(
        self, id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> Optional[Report]:
        """Assign a reviewer to a report.

        Args:
            id: Report UUID
            reviewer_id: User UUID of the reviewer

        Returns:
            Updated report instance
        """
        return await self.update(
            id, reviewed_by=reviewer_id, review_date=datetime.utcnow()
        )
