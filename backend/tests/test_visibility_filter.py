"""Unit/integration tests for the centralized visibility filter functions.

Wave 7 D.1 Task 9 — TDD red phase.

These tests exercise the four functions in
``app.phenopackets.repositories.visibility``:

- ``public_filter``  — filters per invariants I3 + I7
- ``curator_filter`` — includes/excludes archived + deleted
- ``resolve_public_content`` — dereferences head_published_revision_id (I1)
- ``resolve_curator_content`` — returns working copy directly

Fixtures used: ``draft_record``, ``published_record``,
``admin_user``, ``curator_user``, ``db_session`` — all defined in
``conftest.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket
from app.phenopackets.repositories.visibility import (
    curator_filter,
    public_filter,
    resolve_curator_content,
    resolve_public_content,
)

# ---------------------------------------------------------------------------
# public_filter — invariants I3 + I7
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_filter_excludes_non_published(
    db_session, draft_record, published_record
):
    """Public filter returns only published records — draft is hidden."""
    stmt = public_filter(select(Phenopacket))
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    ids = [r.phenopacket_id for r in rows]
    assert published_record.phenopacket_id in ids
    assert draft_record.phenopacket_id not in ids


@pytest.mark.asyncio
async def test_public_filter_excludes_deleted(db_session, published_record):
    """Public filter excludes soft-deleted published records (I7)."""
    # Soft-delete the published record
    published_record.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    stmt = public_filter(select(Phenopacket))
    result = await db_session.execute(stmt.execution_options(include_deleted=True))
    rows = result.scalars().all()

    ids = [r.phenopacket_id for r in rows]
    assert published_record.phenopacket_id not in ids


# ---------------------------------------------------------------------------
# curator_filter — archived and deleted dimensions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_curator_filter_excludes_archived_by_default(
    db_session, published_record, admin_user
):
    """curator_filter hides archived records unless include_archived=True."""
    from app.phenopackets.services.state_service import PhenopacketStateService

    svc = PhenopacketStateService(db_session)
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="retire",
        expected_revision=published_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(published_record)
    assert published_record.state == "archived"

    stmt = curator_filter(select(Phenopacket))
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    ids = [r.phenopacket_id for r in rows]
    assert published_record.phenopacket_id not in ids


@pytest.mark.asyncio
async def test_curator_filter_include_archived(
    db_session, published_record, admin_user
):
    """curator_filter shows archived records when include_archived=True."""
    from app.phenopackets.services.state_service import PhenopacketStateService

    svc = PhenopacketStateService(db_session)
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="retire",
        expected_revision=published_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(published_record)

    stmt = curator_filter(select(Phenopacket), include_archived=True)
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    ids = [r.phenopacket_id for r in rows]
    assert published_record.phenopacket_id in ids


# ---------------------------------------------------------------------------
# resolve_public_content — fast-path and deref-through-revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_public_content_dereferences_head(
    db_session, published_record
):
    """For a freshly published record with no active edit, resolve_public_content
    returns the same content as pp.phenopacket (fast-path I1 check).
    """
    # published_record has editing_revision_id=None, state='published'
    # → fast path: pp.phenopacket == head revision content
    content = await resolve_public_content(db_session, published_record)
    assert content is not None
    assert content == published_record.phenopacket


@pytest.mark.asyncio
async def test_resolve_public_content_during_clone_uses_head_revision(
    db_session, published_record, curator_user
):
    """After clone-to-draft, resolve_public_content returns the OLD head revision
    content, not the current working copy (I1 test at the repository level).
    """
    original_public_content = dict(published_record.phenopacket)

    from app.phenopackets.services.state_service import PhenopacketStateService

    svc = PhenopacketStateService(db_session)
    new_content = {"id": "wave7-published-1", "a": 99, "changed": True}
    await svc.edit_record(
        published_record.id,
        new_content=new_content,
        change_reason="curator edit",
        expected_revision=published_record.revision,
        actor=curator_user,
    )
    await db_session.refresh(published_record)

    # Sanity: working copy changed
    assert published_record.phenopacket == new_content
    # editing_revision_id is set (clone in progress)
    assert published_record.editing_revision_id is not None

    # resolve_public_content must return the OLD head content, not the new working copy
    public_content = await resolve_public_content(db_session, published_record)
    assert public_content == original_public_content
    assert public_content != new_content


# ---------------------------------------------------------------------------
# resolve_curator_content — always returns working copy
# ---------------------------------------------------------------------------


def test_resolve_curator_content_returns_working_copy(published_record):
    """resolve_curator_content is synchronous and returns pp.phenopacket directly."""
    content = resolve_curator_content(published_record)
    assert content is published_record.phenopacket


@pytest.mark.asyncio
async def test_resolve_public_content_returns_none_when_no_head(
    db_session, draft_record
):
    """resolve_public_content returns None when head_published_revision_id is NULL."""
    assert draft_record.head_published_revision_id is None
    result = await resolve_public_content(db_session, draft_record)
    assert result is None
