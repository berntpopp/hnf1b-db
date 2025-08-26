# app/repositories/__init__.py
"""Repository module providing data access layer for all models.

The repository pattern abstracts database operations and provides a clean
interface for the API layer to interact with the database.
"""

from .base import BaseRepository
from .gene import GeneRepository
from .individual import IndividualRepository
from .protein import ProteinRepository
from .publication import PublicationRepository
from .report import ReportRepository
from .user import UserRepository
from .variant import VariantRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "IndividualRepository",
    "ReportRepository",
    "VariantRepository",
    "PublicationRepository",
    "ProteinRepository",
    "GeneRepository",
]
