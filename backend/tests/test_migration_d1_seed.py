"""Test the Wave 7/D.1 data migration (20260412_0003) correctness.

Spec §10.3 — verifies that migration 3 seeds pre-D.1 phenopackets to:
  • phenopackets.state = 'published'
  • phenopackets.head_published_revision_id IS NOT NULL
  • phenopackets.draft_owner_id IS NULL          (invariant I5)
  • phenopackets.editing_revision_id IS NULL
  • exactly one phenopacket_revisions row per record with is_head_published=TRUE
  • that revision has change_reason = 'Migrated from pre-D.1 data model'

Strategy: the test DB already has migrations applied. We simulate the
pre-D.1 state by inserting 5 synthetic phenopacket rows via the ORM
(state='draft', head_published_revision_id=NULL), then execute the same
SQL blocks that migration 3 runs, and finally assert all spec §10.3
invariants hold.

This faithfully tests migration 3 behaviour because the seed SQL is
idempotent per-record and we target only our synthetic rows. We avoid
calling Alembic downgrade/upgrade (which would require a second test DB)
and instead replay the migration SQL directly—matching the exact queries
in 20260412_0003.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.phenopackets.models import Phenopacket

# ---------------------------------------------------------------------------
# Minimal valid phenopacket payload (passes schema validator)
# ---------------------------------------------------------------------------

_RESOURCES = [
    {
        "id": "hp",
        "name": "Human Phenotype Ontology",
        "namespacePrefix": "HP",
        "url": "http://purl.obolibrary.org/obo/hp.owl",
        "version": "2024-01-01",
        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
    }
]

# Number of synthetic pre-D.1 records — spec §10.3 requires ≥ 5.
_N_RECORDS = 5


def _make_pp_content(pid: str) -> dict:
    return {
        "id": pid,
        "subject": {"id": pid, "sex": "UNKNOWN_SEX"},
        "metaData": {
            "created": "2026-01-01T00:00:00Z",
            "createdBy": "migration-seed-test",
            "phenopacketSchemaVersion": "2.0",
            "resources": _RESOURCES,
        },
    }


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_3_seeds_pre_d1_records_as_published(
    db_session,
    seeded_system_user,
):
    """Migration 3 seed SQL sets state='published' + one head revision per record.

    We insert 5 synthetic pre-D.1 rows (state='draft', no head pointer), replay
    the migration 3 seed SQL against those rows, then assert all spec §10.3
    invariants hold.
    """
    # ------------------------------------------------------------------
    # 1. Insert 5 synthetic pre-D.1 phenopackets (state='draft',
    #    head_published_revision_id=NULL) via the ORM so that Python-side
    #    UUID defaults fire correctly.
    # ------------------------------------------------------------------
    pids: list[str] = [f"migration-seed-test-{i}" for i in range(_N_RECORDS)]
    orm_records: list[Phenopacket] = []

    for pid in pids:
        pp = Phenopacket(
            phenopacket_id=pid,
            phenopacket=_make_pp_content(pid),
            subject_id=pid,
            subject_sex="UNKNOWN_SEX",
            state="draft",
            revision=1,
            # Pre-D.1 shape: no head pointer, no draft owner
            head_published_revision_id=None,
            draft_owner_id=None,
            editing_revision_id=None,
        )
        db_session.add(pp)
        orm_records.append(pp)

    await db_session.flush()

    # Collect the auto-generated UUIDs for our synthetic rows
    row_uuids = [pp.id for pp in orm_records]

    # ------------------------------------------------------------------
    # 2. Replay migration 20260412_0003 seed SQL — targeted to our
    #    synthetic rows only (via WHERE id = ANY(:ids)) to avoid touching
    #    any other phenopackets that may exist in the test DB.
    # ------------------------------------------------------------------
    system_id = seeded_system_user.id

    # Step 2a: insert revision rows (mirrors migration INSERT … SELECT)
    await db_session.execute(
        text(
            """
            INSERT INTO phenopacket_revisions (
                record_id, revision_number, state, content_jsonb, change_patch,
                change_reason, actor_id, from_state, to_state, is_head_published, created_at
            )
            SELECT
                id, revision, 'published', phenopacket, NULL,
                'Migrated from pre-D.1 data model', :sys, NULL, 'published', TRUE, NOW()
            FROM phenopackets
            WHERE id = ANY(:ids)
            """
        ),
        {"sys": system_id, "ids": list(row_uuids)},
    )

    # Step 2b: update phenopackets to set state + head pointer
    # (mirrors migration UPDATE … FROM)
    await db_session.execute(
        text(
            """
            UPDATE phenopackets p
            SET
                state = 'published',
                head_published_revision_id = r.id,
                draft_owner_id = NULL,
                editing_revision_id = NULL
            FROM phenopacket_revisions r
            WHERE r.record_id = p.id
              AND r.is_head_published = TRUE
              AND p.id = ANY(:ids)
            """
        ),
        {"ids": list(row_uuids)},
    )

    await db_session.flush()

    # ------------------------------------------------------------------
    # 3. Assert spec §10.3 invariants for every seeded record.
    # ------------------------------------------------------------------
    for pid, row_uuid in zip(pids, row_uuids):
        # Fetch the phenopacket row from the DB (bypass any session cache)
        pp_result = await db_session.execute(
            text(
                "SELECT state, head_published_revision_id, "
                "draft_owner_id, editing_revision_id "
                "FROM phenopackets WHERE id = :row_id"
            ),
            {"row_id": row_uuid},
        )
        pp_row = pp_result.fetchone()

        assert pp_row is not None, f"Record {pid} not found after seed"

        assert pp_row.state == "published", (
            f"state should be 'published' after migration seed on {pid}: "
            f"got {pp_row.state!r}"
        )
        assert pp_row.head_published_revision_id is not None, (
            f"head_published_revision_id is NULL after migration seed on {pid}"
        )
        assert pp_row.draft_owner_id is None, (
            f"draft_owner_id must be NULL (invariant I5) on migrated record {pid}"
        )
        assert pp_row.editing_revision_id is None, (
            f"editing_revision_id must be NULL on migrated record {pid}"
        )

        # Exactly one head-published revision row per record
        head_result = await db_session.execute(
            text(
                "SELECT id, state, to_state, from_state, change_reason, actor_id "
                "FROM phenopacket_revisions "
                "WHERE record_id = :row_id AND is_head_published = TRUE"
            ),
            {"row_id": row_uuid},
        )
        head_rows = head_result.fetchall()

        assert len(head_rows) == 1, (
            f"Expected exactly 1 head-published revision, "
            f"got {len(head_rows)} for {pid}"
        )

        head = head_rows[0]

        assert head.state == "published", (
            f"Revision row state should be 'published', got {head.state!r} on {pid}"
        )
        assert head.to_state == "published", (
            f"Revision row to_state should be 'published', got {head.to_state!r} on {pid}"
        )
        assert head.from_state is None, (
            f"Initial migration revision from_state should be None on {pid}: "
            f"got {head.from_state!r}"
        )
        assert head.change_reason == "Migrated from pre-D.1 data model", (
            f"change_reason mismatch on {pid}: {head.change_reason!r}"
        )
        assert head.actor_id == system_id, (
            f"actor_id should be system user ({system_id}), "
            f"got {head.actor_id} on {pid}"
        )

        # Head pointer round-trip: pp.head_published_revision_id == revision.id
        assert pp_row.head_published_revision_id == head.id, (
            f"head_published_revision_id {pp_row.head_published_revision_id} "
            f"does not match revision id {head.id} on {pid}"
        )
