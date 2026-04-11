"""PhenopacketService: business rules and orchestration for phenopacket CRUD.

Extracted during Wave 4 from the old monolithic
``app/phenopackets/routers/crud.py``. The router now delegates to this
class for everything that is not pure HTTP plumbing:

- ``create_phenopacket`` → sanitise + validate + insert + map
  SQLAlchemy integrity errors to the right HTTP status
- ``update_phenopacket`` → optimistic-locking check, sanitise +
  validate, copy old state, increment revision, create an audit
  entry, commit
- ``soft_delete_phenopacket`` → set ``deleted_at`` / ``deleted_by``,
  create an audit entry, commit

Each method returns either the updated ORM instance or raises a
``ServiceError`` / ``ServiceConflict`` / ``ServiceNotFound`` —
lightweight subclasses that the router converts to the matching
``HTTPException`` status code.

This layering keeps business rules reusable (future: batch import
script, admin CLI) without dragging FastAPI types into the service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.phenopackets.models import (
    Phenopacket,
    PhenopacketCreate,
    PhenopacketUpdate,
)
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.validator import PhenopacketSanitizer, PhenopacketValidator
from app.utils.audit import create_audit_entry

logger = logging.getLogger(__name__)


# =============================================================================
# Service-level error hierarchy
# =============================================================================


class ServiceError(Exception):
    """Base class for errors raised by :class:`PhenopacketService`."""


class ServiceNotFound(ServiceError):
    """Raised when the requested phenopacket does not exist or is soft-deleted."""


class ServiceValidationError(ServiceError):
    """Raised when sanitised input fails schema validation.

    Carries the ``errors`` dict produced by ``PhenopacketValidator``.
    """

    def __init__(self, errors: Any) -> None:
        """Wire the validator errors dict into the exception state."""
        super().__init__("Phenopacket failed validation")
        self.errors = errors


class ServiceConflict(ServiceError):
    """Raised for 409 situations.

    ``detail`` is the structured JSON payload the HTTP layer will use
    as the ``HTTPException.detail``. ``code`` distinguishes the two
    conflict flavours the router cares about:

    - ``"duplicate_id"``    → request tried to create a phenopacket with
      an id that already exists
    - ``"revision_mismatch"`` → optimistic locking failed
    """

    def __init__(self, detail: Any, *, code: str) -> None:
        """Wire the structured payload and a short code into the exception."""
        super().__init__(str(detail))
        self.detail = detail
        self.code = code


class ServiceDatabaseError(ServiceError):
    """Raised for unexpected SQLAlchemy errors that aren't integrity issues."""


# =============================================================================
# Service class
# =============================================================================


class PhenopacketService:
    """Business-logic layer for phenopacket create / update / delete."""

    def __init__(self, repo: PhenopacketRepository) -> None:
        """Wire the service to a repository (which owns the db session)."""
        self._repo = repo
        self._validator = PhenopacketValidator()
        self._sanitizer = PhenopacketSanitizer()

    async def get(
        self, phenopacket_id: str, *, include_deleted: bool = False
    ) -> Optional[Phenopacket]:
        """Fetch a phenopacket by id through the service layer.

        Thin pass-through to :meth:`PhenopacketRepository.get_by_id`
        that gives callers a service-level read API so they don't have
        to reach into the repository directly. ``include_deleted=True``
        also returns soft-deleted rows — used by the audit/timeline
        views that still want to render history for deleted items.
        """
        return await self._repo.get_by_id(
            phenopacket_id, include_deleted=include_deleted
        )

    async def create(
        self,
        payload: PhenopacketCreate,
        *,
        actor_id: Optional[int],
    ) -> Phenopacket:
        """Create a new phenopacket.

        The ``actor_id`` is the authenticated user's ``users.id``.
        Nullable so batch import scripts can pass ``None`` for
        unattributed system inserts.

        Raises:
        ------
        ServiceValidationError
            Sanitised phenopacket fails schema validation.
        ServiceConflict (code="duplicate_id")
            A phenopacket with the same id already exists.
        ServiceDatabaseError
            Any other SQLAlchemy error during commit.
        """
        sanitized = self._sanitizer.sanitize_phenopacket(payload.phenopacket)
        errors = self._validator.validate(sanitized)
        if errors:
            raise ServiceValidationError(errors)

        phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by_id=actor_id,
        )
        self._repo.add(phenopacket)

        try:
            await self._repo.commit_and_refresh(phenopacket)
        except IntegrityError as exc:
            await self._repo.rollback()
            # Postgres SQLSTATE 23505 = unique_violation (PEP 249 compliant).
            # Prefer the structured sqlstate over substring matching because
            # error text varies across locales and driver versions.
            sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if sqlstate == "23505":
                raise ServiceConflict(
                    f"Phenopacket with ID '{sanitized['id']}' already exists",
                    code="duplicate_id",
                ) from exc
            raise ServiceDatabaseError(f"Database error: {exc}") from exc
        except SQLAlchemyError as exc:
            await self._repo.rollback()
            raise ServiceDatabaseError(f"Database error: {exc}") from exc

        # Re-fetch via the repository so the actor FK relationships are
        # eager-loaded for the response renderer.
        reloaded = await self._repo.get_by_id(sanitized["id"])
        return reloaded if reloaded is not None else phenopacket

    async def update(
        self,
        phenopacket_id: str,
        payload: PhenopacketUpdate,
        *,
        actor_id: Optional[int],
    ) -> Phenopacket:
        """Update an existing phenopacket with optimistic locking + audit.

        Raises:
        ------
        ServiceNotFound
            Phenopacket does not exist or has been soft-deleted.
        ServiceConflict (code="revision_mismatch")
            The optimistic-locking revision check failed.
        ServiceValidationError
            Sanitised phenopacket fails schema validation.
        ServiceDatabaseError
            Any other SQLAlchemy error during commit.
        """
        existing = await self._repo.get_by_id(phenopacket_id)
        if existing is None:
            raise ServiceNotFound(f"Phenopacket {phenopacket_id} not found")

        if payload.revision is not None and existing.revision != payload.revision:
            raise ServiceConflict(
                {
                    "error": "Conflict detected",
                    "message": (
                        f"Phenopacket was modified by another user. "
                        f"Expected revision {payload.revision}, "
                        f"but current revision is {existing.revision}"
                    ),
                    "current_revision": existing.revision,
                    "expected_revision": payload.revision,
                },
                code="revision_mismatch",
            )

        old_phenopacket = existing.phenopacket.copy()
        sanitized = self._sanitizer.sanitize_phenopacket(payload.phenopacket)
        errors = self._validator.validate(sanitized)
        if errors:
            raise ServiceValidationError(errors)

        existing.phenopacket = sanitized
        existing.subject_id = sanitized["subject"]["id"]
        existing.subject_sex = sanitized["subject"].get("sex", "UNKNOWN_SEX")
        existing.updated_by_id = actor_id
        existing.revision += 1

        try:
            await create_audit_entry(
                db=self._repo.session,
                phenopacket_id=phenopacket_id,
                action="UPDATE",
                old_value=old_phenopacket,
                new_value=sanitized,
                changed_by_id=actor_id,
                change_reason=payload.change_reason,
            )
            await self._repo.commit_and_refresh(existing)
        except SQLAlchemyError as exc:
            await self._repo.rollback()
            logger.error("Failed to update phenopacket %s: %s", phenopacket_id, exc)
            raise ServiceDatabaseError(f"Database error: {exc}") from exc

        # Re-fetch so the actor FK relationships are eager-loaded for
        # the response renderer (refresh by itself does not re-apply
        # ``selectinload`` options attached at the query level).
        reloaded = await self._repo.get_by_id(phenopacket_id)
        return reloaded if reloaded is not None else existing

    async def soft_delete(
        self,
        phenopacket_id: str,
        change_reason: str,
        *,
        actor_id: Optional[int],
        actor_username: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Soft-delete a phenopacket and create an audit entry.

        Returns a dict with the deletion metadata the router renders
        directly. ``actor_username`` is echoed back in the response
        under the ``deleted_by`` key for display purposes — the
        persisted FK is ``actor_id``. Raises ``ServiceNotFound`` if
        the row is missing or already soft-deleted; raises
        ``ServiceDatabaseError`` on commit failure.
        """
        phenopacket = await self._repo.get_by_id(phenopacket_id)
        if phenopacket is None:
            raise ServiceNotFound(
                f"Phenopacket {phenopacket_id} not found or already deleted"
            )

        old_phenopacket = phenopacket.phenopacket.copy()
        phenopacket.deleted_at = datetime.now(timezone.utc)
        phenopacket.deleted_by_id = actor_id

        try:
            await create_audit_entry(
                db=self._repo.session,
                phenopacket_id=phenopacket_id,
                action="DELETE",
                old_value=old_phenopacket,
                new_value=None,
                changed_by_id=actor_id,
                change_reason=change_reason,
            )
            await self._repo.session.commit()
        except SQLAlchemyError as exc:
            await self._repo.rollback()
            logger.error("Failed to delete phenopacket %s: %s", phenopacket_id, exc)
            raise ServiceDatabaseError(f"Database error: {exc}") from exc

        return {
            "message": f"Phenopacket {phenopacket_id} deleted successfully",
            "deleted_at": phenopacket.deleted_at.isoformat(),
            "deleted_by": actor_username,
        }
