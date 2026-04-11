"""Phenopacket data-access layer.

Introduced during Wave 4 to give phenopacket CRUD the same Router →
Service → Repository layering already used by the search module. The
repository owns every SQLAlchemy query against the ``Phenopacket``
model; business rules and HTTP concerns live in
``app.phenopackets.services.phenopacket_service`` and
``app.phenopackets.routers.crud`` respectively.
"""

from .phenopacket_repository import PhenopacketRepository

__all__ = ["PhenopacketRepository"]
