"""Integration tests for the four §6 transaction sequences.

Wave 7 D.1 Task 7. Tests cover:
- §6.1 clone-to-draft on a published record
- §6.3 in-place edit on draft (no new revision row)
- §6.4 simple state transitions
- §6.2 publish (head-swap)
- Error conditions: EditInProgress, RevisionMismatch, InvalidTransition
"""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService


# ---------------------------------------------------------------------------
# Local fixtures — shared with test_state_invariants.py via conftest scope
# ---------------------------------------------------------------------------


@pytest.fixture
async def draft_record(db_session, curator_user):
    """A phenopacket in state='draft' owned by curator_user."""
    pp = Phenopacket(
        phenopacket_id="draft-flow-1",
        phenopacket={"id": "draft-flow-1"},
        state="draft",
        revision=1,
        draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)
    return pp


@pytest.fixture
async def published_record(db_session, admin_user):
    """A phenopacket in state='published' with a head revision row.

    draft_owner_id is intentionally NULL — migrated historical records have
    no active edit, so ownership semantics don't apply (I5a).
    """
    pp = Phenopacket(
        phenopacket_id="pub-flow-1",
        phenopacket={"id": "pub-flow-1", "a": 1},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
        # draft_owner_id stays NULL — matches migration 3 behaviour
    )
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=1,
        state="published",
        content_jsonb={"id": "pub-flow-1", "a": 1},
        change_reason="init",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()

    pp.head_published_revision_id = rev.id
    await db_session.commit()
    await db_session.refresh(pp)
    return pp


# ---------------------------------------------------------------------------
# §6.1 — clone-to-draft on a published record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_to_draft_on_published(db_session, published_record, curator_user):
    """§6.1: editing a published record clones a draft; public pointer unchanged."""
    svc = PhenopacketStateService(db_session)
    old_head_id = published_record.head_published_revision_id

    new_content = {"id": "pub-flow-1", "a": 2}
    await svc.edit_record(
        published_record.id,
        new_content=new_content,
        change_reason="fix typo",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.refresh(published_record)

    # working copy updated
    assert published_record.phenopacket == {"id": "pub-flow-1", "a": 2}
    # public head pointer UNCHANGED (I1)
    assert published_record.head_published_revision_id == old_head_id
    # edit pointer and owner set
    assert published_record.editing_revision_id is not None
    assert published_record.draft_owner_id == curator_user.id
    # state stays 'published'
    assert published_record.state == "published"
    # revision bumped
    assert published_record.revision == 2

    # a new revision row was created with to_state='draft'
    rows = (
        await db_session.execute(
            select(PhenopacketRevision)
            .where(PhenopacketRevision.record_id == published_record.id)
            .order_by(PhenopacketRevision.revision_number)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[1].to_state == "draft"
    assert rows[1].is_head_published is False
    assert rows[1].content_jsonb == new_content


@pytest.mark.asyncio
async def test_clone_to_draft_blocks_second_edit(
    db_session, published_record, curator_user, another_curator
):
    """§6.1 / I4: second clone-to-draft raises EditInProgress (409)."""
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id,
        new_content={"id": "pub-flow-1", "a": 2},
        change_reason="first edit",
        expected_revision=1,
        actor=curator_user,
    )

    with pytest.raises(svc.EditInProgress):
        await svc.edit_record(
            published_record.id,
            new_content={"id": "pub-flow-1", "a": 3},
            change_reason="second edit",
            expected_revision=2,
            actor=another_curator,
        )


@pytest.mark.asyncio
async def test_clone_revision_mismatch(db_session, published_record, curator_user):
    """§6.1: stale expected_revision raises RevisionMismatch (409)."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.RevisionMismatch):
        await svc.edit_record(
            published_record.id,
            new_content={"id": "pub-flow-1", "a": 99},
            change_reason="stale edit",
            expected_revision=999,  # wrong
            actor=curator_user,
        )


# ---------------------------------------------------------------------------
# §6.3 — in-place edit on a draft (no new revision row)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_place_draft_save_no_new_row(db_session, draft_record, curator_user):
    """§6.3: in-place save on draft doesn't create a revision row."""
    svc = PhenopacketStateService(db_session)

    # First transition: submit → in_review (creates row 1)
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    # Withdraw → draft (creates row 2)
    await svc.transition(
        draft_record.id,
        to_state="draft",
        reason="back",
        expected_revision=2,
        actor=curator_user,
    )

    rows_before = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == draft_record.id
            )
        )
    ).scalars().all()

    # In-place save — should NOT add another row
    await svc.edit_record(
        draft_record.id,
        new_content={"id": "draft-flow-1", "x": "y"},
        change_reason="tweak",
        expected_revision=3,
        actor=curator_user,
    )

    rows_after = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == draft_record.id
            )
        )
    ).scalars().all()

    # No new row created; working copy updated
    assert len(rows_after) == len(rows_before)
    await db_session.refresh(draft_record)
    assert draft_record.phenopacket == {"id": "draft-flow-1", "x": "y"}
    assert draft_record.revision == 4  # bumped by save


@pytest.mark.asyncio
async def test_in_place_save_updates_editing_row_content(
    db_session, draft_record, curator_user
):
    """§6.3: in-place save updates content_jsonb of the existing in-progress row."""
    svc = PhenopacketStateService(db_session)
    # submit creates the editing row
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    await svc.transition(
        draft_record.id,
        to_state="draft",
        reason="back",
        expected_revision=2,
        actor=curator_user,
    )
    await db_session.refresh(draft_record)
    editing_id = draft_record.editing_revision_id

    new_content = {"id": "draft-flow-1", "updated": True}
    await svc.edit_record(
        draft_record.id,
        new_content=new_content,
        change_reason="updated reason",
        expected_revision=3,
        actor=curator_user,
    )

    editing_row = (
        await db_session.execute(
            select(PhenopacketRevision).where(PhenopacketRevision.id == editing_id)
        )
    ).scalar_one()
    assert editing_row.content_jsonb == new_content
    assert editing_row.change_reason == "updated reason"


@pytest.mark.asyncio
async def test_in_place_save_forbidden_non_owner(
    db_session, draft_record, curator_user, another_curator
):
    """§6.3: non-owner curator cannot perform in-place save."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.ForbiddenNotOwner):
        await svc.edit_record(
            draft_record.id,
            new_content={"id": "draft-flow-1", "x": 1},
            change_reason="sneaky",
            expected_revision=1,
            actor=another_curator,
        )


# ---------------------------------------------------------------------------
# §6.4 — full lifecycle: draft → in_review → approved → published
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle(db_session, draft_record, curator_user, admin_user):
    """Full pipeline: create → submit → approve → publish."""
    svc = PhenopacketStateService(db_session)

    # submit
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="ready",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.refresh(draft_record)
    assert draft_record.state == "in_review"
    assert draft_record.draft_owner_id == curator_user.id  # preserved through submit

    # approve
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="ok",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(draft_record)
    assert draft_record.state == "approved"

    # publish (head-swap §6.2)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="go live",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(draft_record)
    assert draft_record.state == "published"
    assert draft_record.head_published_revision_id is not None
    assert draft_record.editing_revision_id is None   # cleared on publish
    assert draft_record.draft_owner_id is None         # I5: cleared on publish

    # Only one head-published row
    heads = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == draft_record.id,
                PhenopacketRevision.is_head_published.is_(True),
            )
        )
    ).scalars().all()
    assert len(heads) == 1


@pytest.mark.asyncio
async def test_archive_is_terminal(db_session, published_record, admin_user):
    """Archived state rejects all further transitions."""
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="retire",
        expected_revision=1,
        actor=admin_user,
    )
    await db_session.refresh(published_record)
    assert published_record.state == "archived"
    assert published_record.draft_owner_id is None  # cleared on archive

    with pytest.raises(svc.InvalidTransition):
        await svc.transition(
            published_record.id,
            to_state="draft",
            reason="revive",
            expected_revision=2,
            actor=admin_user,
        )


@pytest.mark.asyncio
async def test_transition_revision_mismatch(db_session, draft_record, curator_user):
    """§6.4: stale expected_revision raises RevisionMismatch."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.RevisionMismatch):
        await svc.transition(
            draft_record.id,
            to_state="in_review",
            reason="go",
            expected_revision=999,
            actor=curator_user,
        )


@pytest.mark.asyncio
async def test_transition_forbidden_role(db_session, draft_record, curator_user):
    """§6.4: curator cannot approve — raises ForbiddenNotOwner (or InvalidTransition)."""
    svc = PhenopacketStateService(db_session)
    # submit first to reach in_review
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    with pytest.raises((svc.ForbiddenNotOwner, PermissionError)):
        await svc.transition(
            draft_record.id,
            to_state="approved",
            reason="self-approve",
            expected_revision=2,
            actor=curator_user,
        )


@pytest.mark.asyncio
async def test_simple_transition_creates_revision_row(
    db_session, draft_record, curator_user
):
    """§6.4: each simple transition creates exactly one new revision row."""
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="submitting",
        expected_revision=1,
        actor=curator_user,
    )
    rows = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == draft_record.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].to_state == "in_review"
    assert rows[0].from_state == "draft"
