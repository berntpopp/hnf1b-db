# app/dependencies.py
"""FastAPI dependencies for database sessions and repositories."""

from typing import Any, Dict, Optional

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import (
    GeneRepository,
    IndividualRepository,
    ProteinRepository,
    PublicationRepository,
    ReportRepository,
    UserRepository,
    VariantRepository,
)


# Repository Dependencies
def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """Get UserRepository instance with database session."""
    return UserRepository(db)


def get_individual_repository(
    db: AsyncSession = Depends(get_db),
) -> IndividualRepository:
    """Get IndividualRepository instance with database session."""
    return IndividualRepository(db)


def get_report_repository(db: AsyncSession = Depends(get_db)) -> ReportRepository:
    """Get ReportRepository instance with database session."""
    return ReportRepository(db)


def get_variant_repository(db: AsyncSession = Depends(get_db)) -> VariantRepository:
    """Get VariantRepository instance with database session."""
    return VariantRepository(db)


def get_publication_repository(
    db: AsyncSession = Depends(get_db),
) -> PublicationRepository:
    """Get PublicationRepository instance with database session."""
    return PublicationRepository(db)


def get_protein_repository(db: AsyncSession = Depends(get_db)) -> ProteinRepository:
    """Get ProteinRepository instance with database session."""
    return ProteinRepository(db)


def get_gene_repository(db: AsyncSession = Depends(get_db)) -> GeneRepository:
    """Get GeneRepository instance with database session."""
    return GeneRepository(db)


# Query Parameter Parsers
def parse_filter(
    filter: Optional[str] = Query(
        None,
        description=(
            "Comma separated list of filters to apply. "
            "Format: field:value,field2:value2"
        ),
    ),
) -> Dict[str, Any]:
    """Parses a filter query string into a dictionary.

    For example, if filter is "Sex:male,AgeReported:30",
    returns: {"Sex": "male", "AgeReported": "30"}
    """
    filters = {}
    if filter:
        parts = filter.split(",")
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                filters[key.strip()] = value.strip()
    return filters


def parse_pagination(
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
) -> tuple[int, int]:
    """Parse pagination parameters and return skip/limit values.

    Args:
        page: Current page number (1-based)
        page_size: Number of items per page

    Returns:
        Tuple of (skip, limit) for repository queries
    """
    skip = (page - 1) * page_size
    limit = page_size
    return skip, limit


def parse_sort_order(
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'individual_id' for ascending or '-individual_id' "
            "for descending order)"
        ),
    ),
) -> tuple[Optional[str], bool]:
    """Parse sort parameter into field name and direction.

    Args:
        sort: Sort string (e.g., 'field_name' or '-field_name')

    Returns:
        Tuple of (field_name, is_descending)
    """
    if not sort:
        return None, False

    if sort.startswith("-"):
        return sort[1:], True

    return sort, False
