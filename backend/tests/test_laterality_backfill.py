"""Laterality restoration migration (``18cfc57307f6``), against a seeded fixture.

Same isolation strategy as ``tests/test_ontology_term_migration.py``: a real
Postgres connection wrapped in a transaction that is rolled back at the end
of every test, so nothing here depends on -- or leaks into --
``conftest.py``'s async-engine truncation of mutable tables. Whole-corpus
arithmetic (the real 1140-row fixture, 377 backfilled / 763 already-correct)
lives in the manual verification recorded in the migration's docstring and
the commit message, never in pytest.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from migration.phenopackets.laterality import (
    modifier_vocabulary_from_rows,
    parse_laterality,
)

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "18cfc57307f6_restore_laterality.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "18cfc57307f6_restore_laterality", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()
REVISION_ID = "test-18cfc57307f6"


def test_frozen_parser_matches_the_shared_implementation():
    """The migration's frozen ``_parse_laterality`` must match Task 1's shared one.

    The migration deliberately does not import
    ``migration.phenopackets.laterality.parse_laterality`` -- see the
    migration's module docstring "Frozen parsing logic" -- so parity is
    enforced here instead, over every real source value plus edge cases.
    """
    samples = [
        None,
        "",
        "bilateral",
        "Bilateral",
        "unilateral unspecified",
        "unilateral left",
        "unilateral right",
        "UNILATERAL LEFT",
        "no",
        "not reported",
        "unknown",
    ]
    for value in samples:
        assert MIGRATION._parse_laterality(value) == parse_laterality(
            value, vocabulary=_HISTORICAL_MODIFIER_VOCABULARY
        ), value

    # The historical migration treated malformed qualifiers as an unparseable
    # no-op.  The active source importer must reject them so it cannot silently
    # alter laterality semantics in a new pinned snapshot.
    with pytest.raises(ValueError, match="invalid laterality qualifier"):
        parse_laterality(
            "bilateral and unilateral", vocabulary=_HISTORICAL_MODIFIER_VOCABULARY
        )
    with pytest.raises(ValueError, match="invalid laterality qualifier"):
        parse_laterality("left", vocabulary=_HISTORICAL_MODIFIER_VOCABULARY)


def _feature(hpo_id: str, label: str, modifiers: list[dict] | None = None) -> dict:
    feature = {"type": {"id": hpo_id, "label": label}}
    if modifiers is not None:
        feature["modifiers"] = modifiers
    return feature


BILATERAL = {"id": "HP:0012832", "label": "Bilateral"}
UNILATERAL = {"id": "HP:0012833", "label": "Unilateral"}
LEFT = {"id": "HP:0012835", "label": "Left"}
RIGHT = {"id": "HP:0012834", "label": "Right"}

_HISTORICAL_MODIFIER_VOCABULARY = modifier_vocabulary_from_rows(
    [
        {"modifier": value["label"], "modifier_id": value["id"]}
        for value in (BILATERAL, UNILATERAL, LEFT, RIGHT)
    ],
    version_sha256="0" * 64,
)

RENAL_CYST = "HP:0000107"
HYPERECHOGENICITY = "HP:0033132"
SOLITARY_KIDNEY = "HP:0000122"


@pytest.fixture
def sync_conn():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        # This migration predates the append-only revision triggers.  Running
        # its frozen historical SQL against a database at current head must
        # emulate that prior schema rule; the surrounding transaction rolls
        # the temporary trigger state back after each test.
        conn.execute(text("ALTER TABLE phenopacket_revisions DISABLE TRIGGER USER"))
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _seed_phenopacket(
    conn, actor_id: int, individual_id: str, features: list[dict]
) -> dict:
    doc = {
        "id": f"test-{individual_id}",
        "subject": {"id": individual_id, "sex": "FEMALE"},
        "phenotypicFeatures": features,
        "diseases": [],
        "interpretations": [],
        "metaData": {"phenopacketSchemaVersion": "2.0.0"},
    }
    pp_id = uuid.uuid4()
    phenopacket_id = f"phenopacket-{individual_id}"
    conn.execute(
        text(
            "INSERT INTO phenopackets (id, phenopacket_id, phenopacket) "
            "VALUES (:id, :phenopacket_id, cast(:doc as jsonb))"
        ),
        {"id": pp_id, "phenopacket_id": phenopacket_id, "doc": json.dumps(doc)},
    )
    rev_id = conn.execute(
        text(
            "INSERT INTO phenopacket_revisions "
            "(record_id, revision_number, state, content_jsonb, change_reason, "
            " actor_id, to_state) "
            "VALUES (:record_id, 1, 'published', cast(:doc as jsonb), 'seed', "
            " :actor_id, 'published') "
            "RETURNING id"
        ),
        {"record_id": pp_id, "doc": json.dumps(doc), "actor_id": actor_id},
    ).scalar_one()
    conn.execute(
        text(
            "UPDATE phenopackets SET head_published_revision_id = :rev_id WHERE id = :id"
        ),
        {"rev_id": rev_id, "id": pp_id},
    )
    return {
        "pp_id": pp_id,
        "rev_id": rev_id,
        "phenopacket_id": phenopacket_id,
        "doc": doc,
    }


def _seed_actor(conn) -> int:
    conn.execute(
        text(
            "INSERT INTO users (email, username, hashed_password, role, is_active) "
            "VALUES (:email, :username, 'x', 'curator', true)"
        ),
        {
            "email": "laterality-test@example.invalid",
            "username": "laterality-test-user",
        },
    )
    return conn.execute(
        text("SELECT id FROM users WHERE username = 'laterality-test-user'")
    ).scalar_one()


def _fetch(conn, table, column, row_id) -> dict:
    return conn.execute(
        text(f"SELECT {column} FROM {table} WHERE id = :id"), {"id": row_id}
    ).scalar_one()


def test_backfills_and_leaves_correct_and_disagreeing_features_alone(sync_conn):
    actor_id = _seed_actor(sync_conn)

    # gains [Unilateral, Left]
    rec_gain = _seed_phenopacket(
        sync_conn, actor_id, "9001", [_feature(RENAL_CYST, "Renal cyst")]
    )
    # already has Bilateral, untouched
    rec_correct = _seed_phenopacket(
        sync_conn,
        actor_id,
        "9002",
        [
            _feature(
                HYPERECHOGENICITY, "Renal cortical hyperechogenicity", [dict(BILATERAL)]
            )
        ],
    )
    # stored modifier disagrees with the source -> skipped, not overwritten
    rec_disagree = _seed_phenopacket(
        sync_conn,
        actor_id,
        "9003",
        [_feature(SOLITARY_KIDNEY, "Unilateral renal agenesis", [dict(BILATERAL)])],
    )
    # this individual has no phenopacket at all -> unmatched, not an error
    fixture_rows = [
        {
            "individual_id": "9001",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral left",
        },
        {
            "individual_id": "9002",
            "phenotype_column": "Hyperechogenicity",
            "hpo_id": HYPERECHOGENICITY,
            "laterality_value": "bilateral",
        },
        {
            "individual_id": "9003",
            "phenotype_column": "SolitaryKidney",
            "hpo_id": SOLITARY_KIDNEY,
            "laterality_value": "unilateral right",
        },
        {
            "individual_id": "9999",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "bilateral",
        },
    ]

    counts = MIGRATION.apply_restoration(
        sync_conn, REVISION_ID, fixture_rows=fixture_rows
    )
    assert counts["phenopackets"] == {
        "backfilled": 1,
        "already_correct": 1,
        "disagreement": 1,
        "unmatched": 1,
    }

    gained = _fetch(sync_conn, "phenopackets", "phenopacket", rec_gain["pp_id"])
    assert gained["phenotypicFeatures"][0]["modifiers"] == [
        dict(UNILATERAL),
        dict(LEFT),
    ]

    correct = _fetch(sync_conn, "phenopackets", "phenopacket", rec_correct["pp_id"])
    assert correct["phenotypicFeatures"][0]["modifiers"] == [dict(BILATERAL)]
    assert correct == rec_correct["doc"]  # byte-identical: genuinely untouched

    disagreed = _fetch(sync_conn, "phenopackets", "phenopacket", rec_disagree["pp_id"])
    assert disagreed["phenotypicFeatures"][0]["modifiers"] == [dict(BILATERAL)], (
        "a disagreeing stored modifier must never be overwritten"
    )
    assert disagreed == rec_disagree["doc"]

    # both copies agree
    head_gained = _fetch(
        sync_conn, "phenopacket_revisions", "content_jsonb", rec_gain["rev_id"]
    )
    assert head_gained == gained

    # global invariants (plan controller's laterality policy note)
    for row in (gained, correct, disagreed):
        for feature in row["phenotypicFeatures"]:
            ids = {m["id"] for m in feature.get("modifiers", [])}
            if "HP:0012832" in ids:  # Bilateral
                assert not ids & {"HP:0012833", "HP:0012835", "HP:0012834"}
            if ids & {"HP:0012835", "HP:0012834"}:  # Left or Right
                assert "HP:0012833" in ids  # ... implies Unilateral


def test_total_feature_count_unchanged(sync_conn):
    actor_id = _seed_actor(sync_conn)
    features = [_feature(RENAL_CYST, "Renal cyst"), _feature(HYPERECHOGENICITY, "x")]
    rec = _seed_phenopacket(sync_conn, actor_id, "9101", features)
    fixture_rows = [
        {
            "individual_id": "9101",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral unspecified",
        }
    ]
    MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)
    doc = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    assert len(doc["phenotypicFeatures"]) == 2


def test_downgrade_restores_seeded_preimages_byte_identically(sync_conn):
    actor_id = _seed_actor(sync_conn)
    rec = _seed_phenopacket(
        sync_conn, actor_id, "9201", [_feature(RENAL_CYST, "Renal cyst")]
    )
    fixture_rows = [
        {
            "individual_id": "9201",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral right",
        }
    ]
    MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)

    changed = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    assert changed != rec["doc"]
    changed_head = _fetch(
        sync_conn, "phenopacket_revisions", "content_jsonb", rec["rev_id"]
    )
    assert changed_head != rec["doc"], (
        "head revision must have actually been modified by apply_restoration "
        "-- otherwise the byte-identical-restore assertions below would pass "
        "just as well against a head-side write that never happened, since "
        "an untouched document already equals its own preimage"
    )

    MIGRATION.restore_from_journal(sync_conn, REVISION_ID)

    restored_wc = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    restored_head = _fetch(
        sync_conn, "phenopacket_revisions", "content_jsonb", rec["rev_id"]
    )
    assert restored_wc == rec["doc"]
    assert restored_head == rec["doc"]


def test_downgrade_refuses_when_a_row_was_edited_after_the_migration_ran(sync_conn):
    """A curator edit made after the migration ran must abort the downgrade,
    not be silently skipped -- see efa98cccfa51's equivalent test for why a
    silent skip is unsafe (Alembic would still record the schema version as
    moved backward, and the next successful upgrade() clears the journal,
    making the true original preimage permanently unreachable).
    """
    actor_id = _seed_actor(sync_conn)
    rec = _seed_phenopacket(
        sync_conn, actor_id, "9301", [_feature(RENAL_CYST, "Renal cyst")]
    )
    fixture_rows = [
        {
            "individual_id": "9301",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral left",
        }
    ]
    MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)

    edited_features = [_feature(RENAL_CYST, "Renal cyst", [dict(BILATERAL)])]
    sync_conn.execute(
        text(
            "UPDATE phenopackets SET phenopacket = jsonb_set(phenopacket, "
            "'{phenotypicFeatures}', cast(:features as jsonb)) WHERE id = :id"
        ),
        {"features": json.dumps(edited_features), "id": rec["pp_id"]},
    )

    with pytest.raises(RuntimeError, match="phenopackets"):
        MIGRATION.restore_from_journal(sync_conn, REVISION_ID)

    current = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    assert current["phenotypicFeatures"] == edited_features, (
        "downgrade must not clobber a post-migration curator edit"
    )


def test_apply_restoration_refuses_when_the_journal_already_has_rows(sync_conn):
    """H2 regression test: calling ``apply_restoration`` twice without an
    intervening successful ``restore_from_journal`` must raise, not silently
    clear the journal and journal nothing in its place.

    Against an already-restored corpus every backfilled feature takes the
    "already_correct" branch in ``_restore_and_journal`` (``changed`` stays
    ``False``), so a second, unguarded application journals nothing while an
    unconditional clear-first would have destroyed the first application's
    preimage rows outright.
    """
    actor_id = _seed_actor(sync_conn)
    rec = _seed_phenopacket(
        sync_conn, actor_id, "9302", [_feature(RENAL_CYST, "Renal cyst")]
    )
    fixture_rows = [
        {
            "individual_id": "9302",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral left",
        }
    ]
    MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)

    with pytest.raises(RuntimeError, match="journal"):
        MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)

    current = _fetch(sync_conn, "phenopackets", "phenopacket", rec["pp_id"])
    assert current["phenotypicFeatures"][0]["modifiers"] == [
        dict(UNILATERAL),
        dict(LEFT),
    ]


def test_aborts_when_the_join_is_lossy(sync_conn, monkeypatch):
    """``apply_restoration`` must raise, not silently under-report, on a lossy join."""
    actor_id = _seed_actor(sync_conn)
    _seed_phenopacket(sync_conn, actor_id, "9401", [_feature(RENAL_CYST, "Renal cyst")])

    fixture_rows = [
        {
            "individual_id": "9401",
            "phenotype_column": "RenalCysts",
            "hpo_id": RENAL_CYST,
            "laterality_value": "unilateral left",
        }
    ]

    original = MIGRATION._restore_and_journal

    def _broken(*args, **kwargs):
        result = original(*args, **kwargs)
        # Simulate a lossy join by under-reporting on the working-copy call only.
        if kwargs.get("table") == "phenopackets":
            result = dict(result)
            result["unmatched"] = 0
            result["backfilled"] = 0
        return result

    monkeypatch.setattr(MIGRATION, "_restore_and_journal", _broken)
    with pytest.raises(RuntimeError, match="lossy"):
        MIGRATION.apply_restoration(sync_conn, REVISION_ID, fixture_rows=fixture_rows)
