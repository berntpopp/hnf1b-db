"""Phenopacket business-logic layer.

Sits between the HTTP router (``app.phenopackets.routers.crud``) and
the data-access layer (``app.phenopackets.repositories``). Owns
sanitisation, validation, audit-trail coordination and the optimistic
locking protocol for phenopacket updates.

Introduced during Wave 4 to give phenopacket CRUD the same Router →
Service → Repository layering already used by the search module.
"""

from .phenopacket_service import PhenopacketService

__all__ = ["PhenopacketService"]
