"""Centralized visibility filters for phenopacket read paths.

Implements the "what is visible to whom" rule from the Wave 7 D.1 spec
(§8 filter centralization).  Every read path that returns phenopackets
to callers must go through one of the two filter functions here rather
than inlining its own ``deleted_at / state`` predicates.

Invariants enforced:
- I3: public reads see only ``state='published'`` rows with a non-NULL
  ``head_published_revision_id``.
- I7: soft-deleted rows are excluded from all public reads; archived
  rows are visible to curators but not to the public.
- I1: ``resolve_public_content`` always dereferences
  ``head_published_revision_id`` so that a clone-to-draft edit does not
  accidentally expose the curator's working copy to anonymous callers.
"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket, PhenopacketRevision


def public_filter(stmt: Select) -> Select:
    """Apply the public (anonymous / non-curator) visibility filter.

    Returns a modified statement that excludes:
    - soft-deleted rows (``deleted_at IS NOT NULL``)
    - non-published rows (``state != 'published'``)
    - published rows whose head_published_revision_id is NULL (data
      integrity guard; should never occur in practice after Wave 7 D.1
      migration)

    Satisfies invariants I3 and I7.

    Note: This filter is *independent* of the global soft-delete filter
    registered in ``app.database``.  The global filter is applied by
    default on ORM selects inside the session, but this function is
    used to build raw ``Select`` statements that may be executed with
    ``execution_options(include_deleted=True)``.  Including an explicit
    ``deleted_at.is_(None)`` predicate here makes the filter
    self-contained and portable across all execution paths.
    """
    return stmt.where(
        Phenopacket.deleted_at.is_(None),
        Phenopacket.state == "published",
        Phenopacket.head_published_revision_id.is_not(None),
    )


def curator_filter(
    stmt: Select,
    *,
    include_deleted: bool = False,
    include_archived: bool = False,
) -> Select:
    """Apply the curator / admin visibility filter.

    By default excludes:
    - soft-deleted rows (``deleted_at IS NOT NULL``)
    - archived rows (``state = 'archived'``)

    Both exclusions can be lifted independently via the keyword flags.
    ``include_deleted=True`` is used by audit/history views that still
    want to render rows a curator has removed.  ``include_archived=True``
    is used by dedicated archive-list views.

    Satisfies invariant I7 (soft-delete ⊥ archive are orthogonal, both
    independently filter-able).
    """
    if not include_deleted:
        stmt = stmt.where(Phenopacket.deleted_at.is_(None))
    if not include_archived:
        stmt = stmt.where(Phenopacket.state != "archived")
    return stmt


async def resolve_public_content(
    db: AsyncSession,
    pp: Phenopacket,
) -> dict | None:
    """Return the authoritative public content for a phenopacket.

    Dereferences ``head_published_revision_id`` to fetch the correct
    public snapshot.  Invariant I1 states that ``pp.phenopacket`` (the
    working copy) is *not* the authoritative public copy when a
    clone-to-draft edit is in progress.

    Fast-path: when ``editing_revision_id IS NULL`` AND
    ``state='published'`` the working copy equals the head-published
    revision content (the head-swap guarantees this at publish time).
    We skip the second DB round-trip in that case.

    Returns:
        The content dict, or ``None`` when ``head_published_revision_id``
        is ``NULL`` (i.e. the record has never been published).
    """
    if pp.head_published_revision_id is None:
        return None

    # Fast-path: no active clone → working copy == public copy
    if pp.editing_revision_id is None and pp.state == "published":
        return pp.phenopacket

    # Deref through head revision row
    rev = (
        await db.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == pp.head_published_revision_id
            )
        )
    ).scalar_one()
    return rev.content_jsonb


def resolve_curator_content(pp: Phenopacket) -> dict:
    """Return the curator-visible content for a phenopacket.

    Curators always see the current working copy (``pp.phenopacket``),
    regardless of state.  This is a pure, synchronous function — no DB
    round-trip required.
    """
    return pp.phenopacket
