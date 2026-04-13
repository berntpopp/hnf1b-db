"""Invariant tests — I1..I7 from spec §3.

Wave 7 D.1 Task 8. Each test directly probes one invariant from the spec.
If the service or schema ever violates the invariant, exactly one test here
will break, making the regression easy to diagnose.

Spec reference:
  docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §3.

Fixtures ``draft_record`` and ``published_record`` are defined in conftest.py
and shared with test_state_flows.py (Nit #3).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService

# ---------------------------------------------------------------------------
# I1 — state='published' does NOT imply working copy == public copy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I1_state_published_does_not_imply_working_copy_equals_public_copy(
    db_session, published_record, curator_user
):
    """I1: during clone-to-draft the record is still 'published' but
    phenopackets.phenopacket (working copy) != head_published.content_jsonb.
    """
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id,
        new_content={"id": "wave7-published-1", "a": 99},
        change_reason="edit",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.refresh(published_record)

    # state is still 'published'
    assert published_record.state == "published"

    # but the public copy (via head pointer) differs from the working copy
    head = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == published_record.head_published_revision_id
            )
        )
    ).scalar_one()
    assert head.content_jsonb != published_record.phenopacket  # ← the invariant


# ---------------------------------------------------------------------------
# I2 — at most one head-published row per record (partial unique index)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I2_at_most_one_head_published_per_record(
    db_session, draft_record, curator_user, admin_user
):
    """I2: after submit→approve→publish, exactly one row has is_head_published=TRUE.

    Uses draft_record (not published_record) to exercise the full publish path
    without hitting the unsupported 'published→in_review' transition.
    """
    svc = PhenopacketStateService(db_session)

    # submit → approve → publish
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="r",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )

    heads = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == draft_record.id,
                PhenopacketRevision.is_head_published.is_(True),
            )
        )
    ).scalars().all()
    assert len(heads) == 1  # ← the invariant


# ---------------------------------------------------------------------------
# I3 — head_published_revision_id ↔ state consistency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I3_head_pointer_state_consistency(db_session, published_record):
    """I3: for a published record the head row is_head_published=TRUE and to_state='published'."""
    head = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == published_record.head_published_revision_id
            )
        )
    ).scalar_one()
    assert head.is_head_published is True
    assert head.to_state == "published"
    assert published_record.state == "published"
    assert published_record.head_published_revision_id is not None


# ---------------------------------------------------------------------------
# I4 — editing_revision_id blocks concurrent clone-to-draft
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I4_edit_in_progress_blocks_second_clone(
    db_session, published_record, curator_user, another_curator
):
    """I4: second clone-to-draft on same record raises EditInProgress."""
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id,
        new_content={"v": 1},
        change_reason="first",
        expected_revision=1,
        actor=curator_user,
    )
    with pytest.raises(svc.EditInProgress):
        await svc.edit_record(
            published_record.id,
            new_content={"v": 2},
            change_reason="second",
            expected_revision=2,
            actor=another_curator,
        )


# ---------------------------------------------------------------------------
# I5a — draft_owner_id is NULL on migrated (historical) published records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I5a_draft_owner_null_on_historical_records(db_session, published_record):
    """I5a: migrated published records have draft_owner_id=NULL (no active draft)."""
    assert published_record.draft_owner_id is None


# ---------------------------------------------------------------------------
# I5b — draft_owner_id cleared on publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I5b_draft_owner_cleared_on_publish(
    db_session, draft_record, curator_user, admin_user
):
    """I5b: publishing clears draft_owner_id (per spec §6.2 step 11)."""
    svc = PhenopacketStateService(db_session)

    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="r",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.refresh(draft_record)

    assert draft_record.draft_owner_id is None  # ← the invariant


# ---------------------------------------------------------------------------
# I6 — gaps in revision_number after in-place saves
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I6_gaps_in_revision_numbers_after_inplace_saves(
    db_session, draft_record, curator_user
):
    """I6: in-place saves bump phenopackets.revision but never insert rows.

    Sequence:
      start: revision=1
      in-place save → revision=2 (no row)
      in-place save → revision=3 (no row)
      submit (→ in_review) → revision=4, row with revision_number=4

    So the only revision row has revision_number=4 — a gap of [2,3] is expected.
    """
    svc = PhenopacketStateService(db_session)

    # Two in-place saves on the raw draft (no editing_revision_id yet — row is
    # created at submit time, not at draft-save time per spec §6.3 note)
    await svc.edit_record(
        draft_record.id,
        new_content={"x": 1},
        change_reason="a",
        expected_revision=1,
        actor=curator_user,
    )
    await svc.edit_record(
        draft_record.id,
        new_content={"x": 2},
        change_reason="b",
        expected_revision=2,
        actor=curator_user,
    )
    # submit — creates the first (and only) transition row
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=3,
        actor=curator_user,
    )

    rows = (
        await db_session.execute(
            select(PhenopacketRevision.revision_number)
            .where(PhenopacketRevision.record_id == draft_record.id)
            .order_by(PhenopacketRevision.revision_number)
        )
    ).scalars().all()

    # Only the submit created a row; its revision_number = 4
    assert rows == [4]


# ---------------------------------------------------------------------------
# I7 — archived + soft-delete are orthogonal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I7_archived_orthogonal_to_soft_delete(
    db_session, published_record, admin_user
):
    """I7: a record can be both archived and soft-deleted simultaneously."""
    svc = PhenopacketStateService(db_session)

    # Archive the record
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="retire",
        expected_revision=1,
        actor=admin_user,
    )

    # Soft-delete on top (direct SQL — soft-delete path is separate from state machine)
    await db_session.execute(
        sa_update(Phenopacket)
        .where(Phenopacket.id == published_record.id)
        .values(deleted_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=timezone.utc))
    )
    await db_session.commit()
    await db_session.refresh(published_record)

    # Both coexist
    assert published_record.state == "archived"
    assert published_record.deleted_at is not None
    # draft_owner_id cleared on archive (I5)
    assert published_record.draft_owner_id is None
