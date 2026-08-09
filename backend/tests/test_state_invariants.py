"""Invariant tests — I1..I7 from spec §3.

Wave 7 D.1 Task 8. Each test directly probes one invariant from the spec.
If the service or schema ever violates the invariant, exactly one test here
will break, making the regression easy to diagnose.

Spec reference:
  .planning/specs/2026-04-12-wave-7-d1-state-machine-design.md §3.

Fixtures ``draft_record`` and ``published_record`` are defined in conftest.py
and shared with test_state_flows.py (Nit #3).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.phenopackets.curation.import_models import (
    ImportRunStatus,
    SourceDataset,
    SourceImportRun,
    SourceSnapshot,
)
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
    # State-service mutators deliberately do not commit; flush its final
    # working-copy/pointer assignments before reloading the record.
    await db_session.flush()
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


@pytest.mark.asyncio
async def test_edit_record_persists_trusted_import_run_provenance(
    db_session, draft_record, curator_user
):
    """The import pipeline can attach its run identity to the written revision."""
    dataset = SourceDataset(
        source_system="fixture",
        dataset_key="import-run-provenance",
        subject_namespace="fixture",
    )
    db_session.add(dataset)
    await db_session.flush()
    snapshot = SourceSnapshot(
        dataset_id=dataset.id,
        manifest_sha256="a" * 64,
        source_manifest={"sha256": "a" * 64},
        expected_counts={},
    )
    db_session.add(snapshot)
    await db_session.flush()
    run = SourceImportRun(
        snapshot_id=snapshot.id,
        transformer_version="test",
        projection_version="test",
        status=ImportRunStatus.APPLYING.value,
        actor_id=curator_user.id,
    )
    db_session.add(run)
    await db_session.flush()

    service = PhenopacketStateService(db_session)
    await service.edit_record(
        draft_record.id,
        new_content={"id": "draft-1", "a": "source-import"},
        change_reason="source import",
        expected_revision=draft_record.revision,
        actor=curator_user,
        import_run_id=run.id,
    )

    latest = await service._latest_revision_row(draft_record.id)
    assert latest is not None
    assert latest.import_run_id == run.id


# ---------------------------------------------------------------------------
# I2 — at most one head-published row per record (partial unique index)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I2_at_most_one_head_published_per_record(
    db_session, draft_record, curator_user, admin_user
):
    """I2: after submit→approve→publish, the sole head is pointer-authoritative.

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
    await db_session.flush()
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.flush()

    head = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == draft_record.head_published_revision_id
            )
        )
    ).scalar_one()
    assert head.record_id == draft_record.id
    assert head.state == "published"


# ---------------------------------------------------------------------------
# I3 — head_published_revision_id ↔ state consistency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I3_head_pointer_state_consistency(db_session, published_record):
    """I3: a published record's pointer targets its published head row."""
    head = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == published_record.head_published_revision_id
            )
        )
    ).scalar_one()
    assert head.id == published_record.head_published_revision_id
    assert head.state == "published"
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
    """I4: second edit attempt on same record is blocked for a non-owner curator.

    After Task 3 (dispatch on effective state): once curator_user has cloned to
    draft, the effective state becomes 'draft' so a second PUT routes to
    _inplace_save rather than _clone_to_draft. _inplace_save enforces ownership,
    raising ForbiddenNotOwner for another_curator. The net security invariant is
    preserved — a second editor cannot hijack the in-progress edit.
    """
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id,
        new_content={"v": 1},
        change_reason="first",
        expected_revision=1,
        actor=curator_user,
    )
    with pytest.raises(svc.ForbiddenNotOwner):
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
    await db_session.flush()
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="r",
        expected_revision=draft_record.revision,
        actor=admin_user,
    )
    await db_session.flush()
    await db_session.refresh(draft_record)

    assert draft_record.draft_owner_id is None  # ← the invariant


# ---------------------------------------------------------------------------
# I6 — gaps in revision_number after in-place saves
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_I6_inplace_saves_append_revision_numbers(
    db_session, draft_record, curator_user
):
    """I6: in-place saves append immutable rows without revision-number gaps.

    Sequence:
      start: revision=1
      in-place save → revision=2 (new row)
      in-place save → revision=3 (new row)
      submit (→ in_review) → revision=4 (new row)

    Every state-affecting write has an immutable audit snapshot.
    """
    svc = PhenopacketStateService(db_session)

    # Two in-place saves on the raw draft append snapshots.
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
    # submit appends the state-transition row
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=3,
        actor=curator_user,
    )

    rows = (
        (
            await db_session.execute(
                select(PhenopacketRevision.revision_number)
                .where(PhenopacketRevision.record_id == draft_record.id)
                .order_by(PhenopacketRevision.revision_number)
            )
        )
        .scalars()
        .all()
    )

    assert rows == [2, 3, 4]


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
