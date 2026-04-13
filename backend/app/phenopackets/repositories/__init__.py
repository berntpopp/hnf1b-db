"""Phenopacket data-access layer.

Introduced during Wave 4 to give phenopacket CRUD the same Router →
Service → Repository layering already used by the search module. The
repository owns every SQLAlchemy query against the ``Phenopacket``
model; business rules and HTTP concerns live in
``app.phenopackets.services.phenopacket_service`` and
``app.phenopackets.routers.crud`` respectively.
"""

from .phenopacket_repository import PhenopacketRepository
from .visibility import (
    curator_filter,
    public_filter,
    resolve_curator_content,
    resolve_public_content,
)

__all__ = [
    "PhenopacketRepository",
    "curator_filter",
    "public_filter",
    "resolve_curator_content",
    "resolve_public_content",
]
