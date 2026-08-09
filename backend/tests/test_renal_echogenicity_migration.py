"""Renal echogenicity HPO-id correction migration (``d4e8b1f60a27``), against a
seeded fixture.

Same isolation strategy as ``tests/test_ontology_term_migration.py``: a real
Postgres connection wrapped in a transaction that is rolled back at the end
of every test, so nothing here depends on -- or leaks into -- the shared test
database's mutable-table truncation. ``hpo_terms_lookup`` is a static lookup
table Alembic migrations populate (``tests/conftest.py``'s
``_MUTABLE_TABLES`` deliberately excludes it), so its real, migration-applied
content is visible here without any seeding.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "d4e8b1f60a27_fix_renal_echogenicity_hpo_term.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "d4e8b1f60a27_fix_renal_echogenicity_hpo_term", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()


@pytest.fixture
def sync_conn():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        # The migration predates append-only revision snapshots and rewrites
        # the historical head in place. Scope this emulation to the fixture's
        # rolled-back transaction; production revisions remain immutable.
        conn.execute(text("ALTER TABLE phenopacket_revisions DISABLE TRIGGER USER"))
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _seed_actor(conn) -> int:
    conn.execute(
        text(
            "INSERT INTO users (email, username, hashed_password, role, is_active) "
            "VALUES (:email, :username, 'x', 'curator', true)"
        ),
        {
            "email": "echogenicity-test@example.invalid",
            "username": "echogenicity-test-user",
        },
    )
    return conn.execute(
        text("SELECT id FROM users WHERE username = 'echogenicity-test-user'")
    ).scalar_one()


def _doc(hpo_id: str, label: str) -> dict:
    return {
        "id": "test",
        "subject": {"id": "subject-1", "sex": "FEMALE"},
        "phenotypicFeatures": [{"type": {"id": hpo_id, "label": label}}],
        "diseases": [],
        "interpretations": [],
        "metaData": {"phenopacketSchemaVersion": "2.0.0"},
    }


def _seed_record_with_two_revisions(
    conn,
    actor_id: int,
    phenopacket_id: str,
    *,
    working_doc: dict,
    head_doc: dict,
    old_doc: dict,
) -> dict:
    """Seed a phenopacket with a superseded (non-head) revision AND a head one.

    ``old_doc`` becomes revision 1 (superseded, immutable history); ``head_doc``
    becomes revision 2 (selected by ``head_published_revision_id``); ``working_doc`` becomes
    ``phenopackets.phenopacket`` (the working copy). Mirrors the seeding
    pattern in ``tests/test_ontology_term_migration.py`` /
    ``tests/test_laterality_backfill.py`` with an extra non-head revision.
    """
    pp_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO phenopackets (id, phenopacket_id, phenopacket) "
            "VALUES (:id, :phenopacket_id, cast(:doc as jsonb))"
        ),
        {
            "id": pp_id,
            "phenopacket_id": phenopacket_id,
            "doc": json.dumps(working_doc),
        },
    )
    old_rev_id = conn.execute(
        text(
            "INSERT INTO phenopacket_revisions "
            "(record_id, revision_number, state, content_jsonb, change_reason, "
            " actor_id, to_state) "
            "VALUES (:record_id, 1, 'published', cast(:doc as jsonb), 'seed', "
            " :actor_id, 'published') "
            "RETURNING id"
        ),
        {"record_id": pp_id, "doc": json.dumps(old_doc), "actor_id": actor_id},
    ).scalar_one()
    head_rev_id = conn.execute(
        text(
            "INSERT INTO phenopacket_revisions "
            "(record_id, revision_number, state, content_jsonb, change_reason, "
            " actor_id, to_state) "
            "VALUES (:record_id, 2, 'published', cast(:doc as jsonb), 'seed', "
            " :actor_id, 'published') "
            "RETURNING id"
        ),
        {"record_id": pp_id, "doc": json.dumps(head_doc), "actor_id": actor_id},
    ).scalar_one()
    conn.execute(
        text(
            "UPDATE phenopackets SET head_published_revision_id = :rev_id "
            "WHERE id = :id"
        ),
        {"rev_id": head_rev_id, "id": pp_id},
    )
    return {"pp_id": pp_id, "old_rev_id": old_rev_id, "head_rev_id": head_rev_id}


def _fetch(conn, table, column, row_id) -> dict:
    return conn.execute(
        text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": row_id}
    ).scalar_one()


# --- CRITICAL 1: phenopacket_revisions write must be head-scoped -----------


def test_upgrade_leaves_non_head_revisions_untouched(sync_conn):
    """A superseded (non-head) revision carrying the wrong id is immutable
    history and must survive ``_retarget`` untouched -- only the working copy
    and the head-published revision are rewritten.
    """
    actor_id = _seed_actor(sync_conn)
    old_doc = _doc(MIGRATION.WRONG_ID, MIGRATION.WRONG_LABEL)
    head_doc = _doc(MIGRATION.WRONG_ID, MIGRATION.WRONG_LABEL)
    rec = _seed_record_with_two_revisions(
        sync_conn,
        actor_id,
        "echo-1",
        working_doc=head_doc,
        head_doc=head_doc,
        old_doc=old_doc,
    )

    MIGRATION._retarget(
        sync_conn, MIGRATION.WRONG_ID, MIGRATION.RIGHT_ID, MIGRATION.RIGHT_LABEL
    )

    working = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    head = _fetch(
        sync_conn, "phenopacket_revisions", "content_jsonb", rec["head_rev_id"]
    )
    old = _fetch(sync_conn, "phenopacket_revisions", "content_jsonb", rec["old_rev_id"])

    assert working["phenotypicFeatures"][0]["type"]["id"] == MIGRATION.RIGHT_ID
    assert head["phenotypicFeatures"][0]["type"]["id"] == MIGRATION.RIGHT_ID
    assert old["phenotypicFeatures"][0]["type"]["id"] == MIGRATION.WRONG_ID, (
        "a non-head revision is immutable history and must not be rewritten"
    )
    assert old == old_doc, "non-head revision must be byte-identical to its preimage"


def test_upgrade_fixes_hpo_terms_lookup_metadata_not_just_id_and_label(sync_conn):
    """CRITICAL C1 regression test: category/description/synonyms must be
    corrected alongside id/label, or the lookup row stays self-contradictory
    (id+label say hyperechogenicity, category+description say hypo-).
    """
    sync_conn.execute(
        text(
            "UPDATE hpo_terms_lookup SET hpo_id = :wrong_id, label = :wrong_label, "
            "category = 'Hypoechogenicity', "
            "description = 'Decreased echogenicity of the kidney cortex.', "
            "synonyms = 'Hypoechogenic renal cortex' "
            "WHERE hpo_id IN (:wrong_id, :right_id)"
        ),
        {
            "wrong_id": MIGRATION.WRONG_ID,
            "wrong_label": MIGRATION.WRONG_LABEL,
            "right_id": MIGRATION.RIGHT_ID,
        },
    )

    MIGRATION._retarget(
        sync_conn, MIGRATION.WRONG_ID, MIGRATION.RIGHT_ID, MIGRATION.RIGHT_LABEL
    )

    row = (
        sync_conn.execute(
            text(
                "SELECT hpo_id, label, category, description, synonyms "
                "FROM hpo_terms_lookup WHERE hpo_id = :id"
            ),
            {"id": MIGRATION.RIGHT_ID},
        )
        .mappings()
        .one()
    )
    assert row["label"] == MIGRATION.RIGHT_LABEL
    assert row["category"] == MIGRATION.RIGHT_CATEGORY
    assert row["description"] == MIGRATION.RIGHT_DESCRIPTION
    assert row["synonyms"] == MIGRATION.RIGHT_SYNONYMS
    assert "hyper" in row["category"].lower()
    assert "increas" in row["description"].lower(), (
        "description must agree with the label's direction (increased/hyper), "
        "not the inverse (decreased/hypo)"
    )


# --- CRITICAL 2: downgrade must refuse on scope divergence -----------------


def test_downgrade_refuses_when_touched_rowcount_diverges_from_guard(sync_conn):
    """A curator-created record now legitimately carrying the correct id
    changes the row count downgrade would touch versus what upgrade()
    originally touched -- downgrade must refuse rather than silently
    re-inverting a clinical finding for a record it never should touch.

    ``_retarget`` raises as soon as it detects the mismatch (on whichever
    table it is currently processing), rather than checking both tables
    up front; the resulting Python exception is what makes the *caller*
    (Alembic, wrapping the whole migration in one transaction) roll back
    anything ``_retarget`` already wrote in the same call. That
    transactional guarantee is Alembic's, not this function's, so this test
    only asserts the raise itself and its message, not post-rollback state.
    """
    actor_id = _seed_actor(sync_conn)
    doc = _doc(MIGRATION.RIGHT_ID, MIGRATION.RIGHT_LABEL)
    _seed_record_with_two_revisions(
        sync_conn, actor_id, "echo-2", working_doc=doc, head_doc=doc, old_doc=doc
    )

    with pytest.raises(RuntimeError, match="Refusing to downgrade"):
        MIGRATION._retarget(
            sync_conn,
            MIGRATION.RIGHT_ID,
            MIGRATION.WRONG_ID,
            MIGRATION.WRONG_LABEL,
            guard_rowcounts={"phenopackets": 999, "phenopacket_revisions": 999},
        )


def test_downgrade_proceeds_when_touched_rowcount_matches_guard(sync_conn):
    """The complementary case: when the guard count matches exactly, the
    inverse remap does proceed.
    """
    actor_id = _seed_actor(sync_conn)
    doc = _doc(MIGRATION.RIGHT_ID, MIGRATION.RIGHT_LABEL)
    rec = _seed_record_with_two_revisions(
        sync_conn, actor_id, "echo-3", working_doc=doc, head_doc=doc, old_doc=doc
    )

    MIGRATION._retarget(
        sync_conn,
        MIGRATION.RIGHT_ID,
        MIGRATION.WRONG_ID,
        MIGRATION.WRONG_LABEL,
        guard_rowcounts={"phenopackets": 1, "phenopacket_revisions": 1},
    )

    working = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    assert working["phenotypicFeatures"][0]["type"]["id"] == MIGRATION.WRONG_ID
