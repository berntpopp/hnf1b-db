"""PhenopacketRepository: pure data-access layer for phenopackets.

Mirrors the pattern already in use in ``backend/app/search/`` — the
class is stateless apart from the injected async session, and every
method exposes a single query surface the router / service layers can
rely on without touching SQLAlchemy directly.

Only the queries used by the ``crud`` router layer live here. The
``aggregations`` / ``comparisons`` / ``search`` modules already own
their own query layers and continue to do so.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket, PhenopacketAudit
from app.phenopackets.query_builders import (
    add_has_variants_filter,
    add_sex_filter,
)

logger = logging.getLogger(__name__)


class PhenopacketRepository:
    """Async data-access object for the ``Phenopacket`` table.

    Each method returns plain model instances or primitive values —
    never ``HTTPException`` or any HTTP-aware type. The caller (a
    service or a router) is responsible for translating "not found"
    into the appropriate HTTP response.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Wire the repository to an async session."""
        self._session = session

    # ------------------------------------------------------------------ read

    async def get_by_id(
        self, phenopacket_id: str, *, include_deleted: bool = False
    ) -> Optional[Phenopacket]:
        """Fetch a phenopacket by its public id.

        Soft-deleted rows are filtered out by default. Set
        ``include_deleted=True`` to read history-only records — used
        by the audit-history endpoint, which still needs to render
        old entries for deleted phenopackets.
        """
        conditions = [Phenopacket.phenopacket_id == phenopacket_id]
        if not include_deleted:
            conditions.append(Phenopacket.deleted_at.is_(None))

        stmt = select(Phenopacket).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_batch(
        self, phenopacket_ids: Sequence[str]
    ) -> List[Phenopacket]:
        """Fetch many phenopackets by id in a single round-trip."""
        if not phenopacket_ids:
            return []
        stmt = select(Phenopacket).where(
            and_(
                Phenopacket.phenopacket_id.in_(phenopacket_ids),
                Phenopacket.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ----------------------------------------------------------- list / count

    def base_list_query(
        self,
        *,
        filter_sex: Optional[str],
        filter_has_variants: Optional[bool],
    ) -> Select:
        """Return the base ``SELECT Phenopacket`` statement for list views.

        The standard soft-delete and filter predicates are applied. The
        router is responsible for chaining ``.order_by`` and ``.offset
        / .limit`` because those depend on user-supplied sort parameters
        that involve helper-built expressions.
        """
        query = select(Phenopacket).where(Phenopacket.deleted_at.is_(None))
        query = add_sex_filter(query, filter_sex)
        query = add_has_variants_filter(query, filter_has_variants)
        return query

    async def count_filtered(
        self,
        *,
        filter_sex: Optional[str],
        filter_has_variants: Optional[bool],
    ) -> int:
        """Return the total count of phenopackets matching the filters."""
        count_query = (
            select(func.count())
            .select_from(Phenopacket)
            .where(Phenopacket.deleted_at.is_(None))
        )
        count_query = add_sex_filter(count_query, filter_sex)
        count_query = add_has_variants_filter(count_query, filter_has_variants)
        result = await self._session.execute(count_query)
        return int(result.scalar() or 0)

    async def list_paginated(
        self, query: Select, *, offset: int, limit: int
    ) -> Tuple[List[Phenopacket], int]:
        """Execute ``query`` with pagination applied.

        Returns ``(rows, len(rows))``. Accepts a pre-built query from
        :meth:`base_list_query` so the router can attach its own
        ORDER BY before pagination without exposing SQLAlchemy internals.
        """
        paginated = query.offset(offset).limit(limit)
        result = await self._session.execute(paginated)
        rows = list(result.scalars().all())
        return rows, len(rows)

    # ---------------------------------------------------------------- mutate

    def add(self, phenopacket: Phenopacket) -> None:
        """Stage a new phenopacket row. The caller commits."""
        self._session.add(phenopacket)

    async def commit_and_refresh(self, phenopacket: Phenopacket) -> None:
        """Commit the current session and refresh ``phenopacket`` in place."""
        await self._session.commit()
        await self._session.refresh(phenopacket)

    async def rollback(self) -> None:
        """Roll back the current session — for error handlers."""
        await self._session.rollback()

    # ------------------------------------------------------------- audit log

    async def list_audit_history(
        self, phenopacket_id: str
    ) -> List[PhenopacketAudit]:
        """Return audit entries for a phenopacket, newest first."""
        stmt = (
            select(PhenopacketAudit)
            .where(PhenopacketAudit.phenopacket_id == phenopacket_id)
            .order_by(PhenopacketAudit.changed_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------- debug / reporting use

    @property
    def session(self) -> AsyncSession:
        """Expose the underlying session for callers that need raw SQL.

        Used by the ``crud_related`` router for the heavy JSONB
        by-variant / by-publication queries that don't benefit from
        being wrapped in dedicated repository methods.
        """
        return self._session
