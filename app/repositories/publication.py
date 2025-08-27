# app/repositories/publication.py
"""Publication repository for handling publication database operations."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Author, Publication
from app.repositories.base import BaseRepository


class PublicationRepository(BaseRepository[Publication]):
    """Repository for Publication model with author handling capabilities."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        super().__init__(Publication, session)

    async def get_by_publication_id(self, publication_id: str) -> Optional[Publication]:
        """Get publication by publication_id (e.g., 'pub0001').

        Args:
            publication_id: The publication identifier

        Returns:
            Publication instance or None if not found
        """
        return await self.get_by_field(
            "publication_id", publication_id, load_relationships=["authors", "assignee"]
        )

    async def get_by_pmid(self, pmid: int) -> Optional[Publication]:
        """Get publication by PubMed ID.

        Args:
            pmid: PubMed ID

        Returns:
            Publication instance or None if not found
        """
        return await self.get_by_field(
            "pmid", pmid, load_relationships=["authors", "assignee"]
        )

    async def get_by_doi(self, doi: str) -> Optional[Publication]:
        """Get publication by DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Publication instance or None if not found
        """
        return await self.get_by_field(
            "doi", doi, load_relationships=["authors", "assignee"]
        )

    async def get_with_authors(self, id: uuid.UUID) -> Optional[Publication]:
        """Get publication with authors loaded and ordered.

        Args:
            id: Publication UUID

        Returns:
            Publication instance with authors
        """
        query = (
            select(Publication)
            .where(Publication.id == id)
            .options(selectinload(Publication.authors))
        )
        result = await self.session.execute(query)
        publication = result.scalar_one_or_none()

        if publication:
            # Sort authors by order
            publication.authors.sort(key=lambda author: author.author_order)

        return publication

    async def search_publications(
        self,
        search_term: str = None,
        publication_type: str = None,
        assignee_id: uuid.UUID = None,
        has_pmid: bool = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Publication], int]:
        """Search publications with various filters.

        Args:
            search_term: Search in title, publication_id, publication_alias
            publication_type: Filter by publication type
            assignee_id: Filter by assignee
            has_pmid: Filter publications with/without PMID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (publications list, total count)
        """
        filters = {}

        if publication_type:
            filters["publication_type"] = publication_type

        if assignee_id:
            filters["assignee_id"] = assignee_id

        # Handle has_pmid filter with custom query if needed
        if has_pmid is not None:
            query = select(Publication)

            # Apply other filters
            if publication_type:
                query = query.where(Publication.publication_type == publication_type)
            if assignee_id:
                query = query.where(Publication.assignee_id == assignee_id)

            # Apply PMID filter
            if has_pmid:
                query = query.where(Publication.pmid.isnot(None))
            else:
                query = query.where(Publication.pmid.is_(None))

            # Apply search
            if search_term:
                from sqlalchemy import or_

                search_pattern = f"%{search_term}%"
                query = query.where(
                    or_(
                        Publication.title.ilike(search_pattern),
                        Publication.publication_id.ilike(search_pattern),
                        Publication.publication_alias.ilike(search_pattern),
                    )
                )

            # Load relationships
            query = query.options(
                selectinload(Publication.authors), selectinload(Publication.assignee)
            )

            # Get total count
            from sqlalchemy import func

            count_query = select(func.count()).select_from(query.subquery())
            count_result = await self.session.execute(count_query)
            total = count_result.scalar()

            # Apply pagination and ordering
            query = (
                query.order_by(Publication.created_at.desc()).offset(skip).limit(limit)
            )

            result = await self.session.execute(query)
            publications = list(result.scalars().all())

            return publications, total
        else:
            search_fields = (
                ["title", "publication_id", "publication_alias"]
                if search_term
                else None
            )
            return await self.get_multi(
                skip=skip,
                limit=limit,
                filters=filters,
                search=search_term,
                search_fields=search_fields,
                load_relationships=["authors", "assignee"],
            )

    async def create_publication(
        self,
        publication_id: str,
        publication_alias: str,
        publication_type: Optional[str] = None,
        publication_entry_date: Optional[datetime] = None,
        pmid: Optional[int] = None,
        doi: Optional[str] = None,
        pdf: Optional[str] = None,
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        publication_date: Optional[datetime] = None,
        journal_abbreviation: Optional[str] = None,
        journal: Optional[str] = None,
        keywords: List[str] = None,
        medical_specialty: List[str] = None,
        comment: Optional[str] = None,
        assignee_id: Optional[uuid.UUID] = None,
    ) -> Publication:
        """Create a new publication.

        Args:
            publication_id: Publication identifier (e.g., 'pub0001')
            publication_alias: Publication alias
            publication_type: Type of publication
            publication_entry_date: Entry date
            pmid: PubMed ID
            doi: Digital Object Identifier
            pdf: PDF file path/URL
            title: Publication title
            abstract: Abstract text
            publication_date: Publication date
            journal_abbreviation: Journal abbreviation
            journal: Journal name
            keywords: List of keywords
            medical_specialty: List of medical specialties
            comment: Comment
            assignee_id: Assignee user ID

        Returns:
            Created publication instance
        """
        return await self.create(
            publication_id=publication_id,
            publication_alias=publication_alias,
            publication_type=publication_type,
            publication_entry_date=publication_entry_date or datetime(2021, 11, 1),
            pmid=pmid,
            doi=doi,
            pdf=pdf,
            title=title,
            abstract=abstract,
            publication_date=publication_date,
            journal_abbreviation=journal_abbreviation,
            journal=journal,
            keywords=keywords or [],
            medical_specialty=medical_specialty or [],
            comment=comment,
            assignee_id=assignee_id,
        )

    async def add_author(
        self,
        publication_id: uuid.UUID,
        lastname: Optional[str] = None,
        firstname: Optional[str] = None,
        initials: Optional[str] = None,
        affiliations: List[str] = None,
        author_order: int = 0,
    ) -> Author:
        """Add an author to a publication.

        Args:
            publication_id: Publication UUID
            lastname: Author's last name
            firstname: Author's first name
            initials: Author's initials
            affiliations: List of affiliations
            author_order: Order of the author in the author list

        Returns:
            Created author instance
        """
        author = Author(
            publication_id=publication_id,
            lastname=lastname,
            firstname=firstname,
            initials=initials,
            affiliations=affiliations or [],
            author_order=author_order,
        )
        self.session.add(author)
        await self.session.flush()
        await self.session.refresh(author)
        return author

    async def update_authors(
        self, publication_id: uuid.UUID, authors_data: List[dict]
    ) -> List[Author]:
        """Update all authors for a publication (replace existing).

        Args:
            publication_id: Publication UUID
            authors_data: List of author data dictionaries

        Returns:
            List of created author instances
        """
        # Delete existing authors
        from sqlalchemy import delete

        await self.session.execute(
            delete(Author).where(Author.publication_id == publication_id)
        )

        # Create new authors
        authors = []
        for order, author_data in enumerate(authors_data):
            author = await self.add_author(
                publication_id=publication_id,
                lastname=author_data.get("lastname"),
                firstname=author_data.get("firstname"),
                initials=author_data.get("initials"),
                affiliations=author_data.get("affiliations", []),
                author_order=order,
            )
            authors.append(author)

        return authors

    async def get_by_assignee(self, assignee_id: uuid.UUID) -> List[Publication]:
        """Get all publications assigned to a specific user.

        Args:
            assignee_id: User UUID

        Returns:
            List of publications
        """
        query = (
            select(Publication)
            .where(Publication.assignee_id == assignee_id)
            .options(selectinload(Publication.authors))
            .order_by(Publication.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_publications(
        self, days: int = 30, limit: int = 10
    ) -> List[Publication]:
        """Get recently added publications.

        Args:
            days: Number of days to look back
            limit: Maximum number of publications to return

        Returns:
            List of recent publications
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(Publication)
            .where(Publication.created_at >= cutoff_date)
            .options(selectinload(Publication.authors))
            .order_by(Publication.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_publications_by_year(self, year: int) -> List[Publication]:
        """Get publications by publication year.

        Args:
            year: Publication year

        Returns:
            List of publications
        """
        from sqlalchemy import extract

        query = (
            select(Publication)
            .where(extract("year", Publication.publication_date) == year)
            .options(selectinload(Publication.authors))
            .order_by(Publication.publication_date.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_publications_without_pmid(self) -> List[Publication]:
        """Get publications that don't have a PMID assigned.

        Returns:
            List of publications without PMID
        """
        query = (
            select(Publication)
            .where(Publication.pmid.is_(None))
            .options(selectinload(Publication.authors))
            .order_by(Publication.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def assign_publication(
        self, id: uuid.UUID, assignee_id: uuid.UUID
    ) -> Optional[Publication]:
        """Assign a publication to a user.

        Args:
            id: Publication UUID
            assignee_id: User UUID

        Returns:
            Updated publication instance
        """
        return await self.update(id, assignee_id=assignee_id)
