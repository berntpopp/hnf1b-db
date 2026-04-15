"""Unit tests for PhenopacketStateService._effective_state (spec I9)."""

import pytest

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_effective_state_returns_pp_state_when_no_editing_revision(
    db_session, admin_user
):
    """editing_revision_id IS NULL → effective_state == pp.state."""
    pp = Phenopacket(
        phenopacket_id="eff-state-t1",
        phenopacket={"id": "eff-state-t1"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
        # editing_revision_id stays NULL
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)

    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "published"


@pytest.mark.asyncio
async def test_effective_state_returns_revision_state_when_editing(
    db_session, admin_user
):
    """editing_revision_id set → effective_state == revision.state."""
    pp = Phenopacket(
        phenopacket_id="eff-state-t2",
        phenopacket={"id": "eff-state-t2"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
    )
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=2,
        state="draft",
        content_jsonb={"id": "eff-state-t2"},
        change_reason="clone-to-draft",
        actor_id=admin_user.id,
        from_state="published",
        to_state="draft",
        is_head_published=False,
    )
    db_session.add(rev)
    await db_session.flush()

    pp.editing_revision_id = rev.id
    await db_session.commit()
    await db_session.refresh(pp)

    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "draft"


@pytest.mark.asyncio
async def test_effective_state_never_published_path(db_session, admin_user):
    """Never-published record with pp.state='in_review' returns 'in_review'."""
    pp = Phenopacket(
        phenopacket_id="eff-state-t3",
        phenopacket={"id": "eff-state-t3"},
        state="in_review",
        revision=1,
        created_by_id=admin_user.id,
        # editing_revision_id stays NULL
        # head_published_revision_id stays NULL
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)

    svc = PhenopacketStateService(db_session)
    assert await svc._effective_state(pp) == "in_review"
