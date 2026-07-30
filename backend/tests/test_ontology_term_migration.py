"""Term-correction migration (``efa98cccfa51``), against a seeded fixture.

CI has no corpus: ``conftest.py::_isolate_database_between_tests`` truncates
``phenopackets``/``phenopacket_revisions`` after every test. Whole-corpus
arithmetic lives in ``scripts/ontology_preflight.py``, never here.

This test seeds its own records covering every defect shape and invokes the
migration's ``apply_corrections`` / ``restore_from_journal`` functions
directly, through a real Postgres connection wrapped in a transaction that is
rolled back at the end of every test -- nothing here depends on, or leaks
into, the shared test database's mutable-table truncation.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "efa98cccfa51_correct_ontology_terms.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "efa98cccfa51_correct_ontology_terms", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()
REVISION_ID = "test-efa98cccfa51"  # distinct from the real revision id


# --- fixture building blocks -------------------------------------------------

RCAD_OLD = {"id": "MONDO:0011593", "label": "Renal cysts and diabetes syndrome"}
MODY5_OLD = {
    "id": "MONDO:0010953",
    "label": "Maturity-onset diabetes of the young type 5",
}
RCAD_NEW = {"id": "MONDO:0007669", "label": "renal cysts and diabetes syndrome"}

PRENATAL_CLASS = {"id": "HP:0034199", "label": "Prenatal onset"}
POSTNATAL_CLASS = {"id": "HP:0003674", "label": "Postnatal onset"}
CONGENITAL_CLASS = {"id": "HP:0003577", "label": "Congenital onset"}
ONSET_CLASS = {"id": "HP:0003674", "label": "Onset"}


def _disease(term: dict[str, str], onset_class: dict[str, str] | None = None) -> dict:
    d: dict[str, Any] = {"term": dict(term)}
    if onset_class is not None:
        d["onset"] = {"ontologyClass": dict(onset_class)}
    return d


def _doc(
    *,
    diseases: list[dict] | None = None,
    subject_tale_class: dict[str, str] | None = None,
    features: list[dict] | None = None,
    interpretations: list[dict] | None = None,
    omit_diseases_key: bool = False,
) -> dict:
    subject: dict[str, Any] = {"id": "subject-1", "sex": "FEMALE"}
    if subject_tale_class is not None:
        subject["timeAtLastEncounter"] = {"ontologyClass": dict(subject_tale_class)}

    doc: dict[str, Any] = {
        "id": "test",
        "subject": subject,
        "phenotypicFeatures": features or [],
        "interpretations": interpretations or [],
        "metaData": {"phenopacketSchemaVersion": "2.0.0"},
    }
    if not omit_diseases_key:
        doc["diseases"] = diseases if diseases is not None else []
    return doc


FIXTURE: dict[str, dict] = {
    # collapse + dedupe: two entries for the same record become one
    "pp-both": _doc(diseases=[_disease(RCAD_OLD), _disease(MODY5_OLD)]),
    # collapse only, single entry
    "pp-single": _doc(diseases=[_disease(RCAD_OLD)]),
    # onset remap on the disease entry
    "pp-onset": _doc(diseases=[_disease(RCAD_OLD, PRENATAL_CLASS)]),
    # subject.timeAtLastEncounter path
    "pp-tale": _doc(diseases=[_disease(RCAD_OLD)], subject_tale_class=PRENATAL_CLASS),
    # HP:0003674 keeps its id, gains the corrected label "Onset"
    "pp-post": _doc(diseases=[_disease(RCAD_OLD, POSTNATAL_CLASS)]),
    # already correct: must be a byte-identical no-op
    "pp-clean": _doc(diseases=[_disease(RCAD_NEW, CONGENITAL_CLASS)]),
    # a record with no `diseases` key at all (59 real records have none) --
    # must not error (jsonb_agg-over-NULL hazard, plan Task 3 amendment #1)
    "pp-no-diseases": _doc(
        omit_diseases_key=True,
        features=[{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
    ),
    # phenotypicFeatures[].onset.ontologyClass
    "pp-feature-onset": _doc(
        diseases=[_disease(RCAD_NEW)],
        features=[
            {
                "type": {"id": "HP:0000107", "label": "Renal cyst"},
                "onset": {"ontologyClass": dict(PRENATAL_CLASS)},
            }
        ],
    ),
    # phenotypicFeatures[].onset.age.ontologyClass, disagreeing with its
    # sibling onset.ontologyClass -- each must be corrected independently
    "pp-feature-age-onset-mismatch": _doc(
        diseases=[_disease(RCAD_NEW)],
        features=[
            {
                "type": {"id": "HP:0000107", "label": "Renal cyst"},
                "onset": {
                    "ontologyClass": dict(PRENATAL_CLASS),
                    "age": {"ontologyClass": dict(POSTNATAL_CLASS)},
                },
            }
        ],
    ),
    # interpretations[].diagnosis.disease
    "pp-interpretation": _doc(
        diseases=[_disease(RCAD_NEW)],
        interpretations=[{"diagnosis": {"disease": dict(RCAD_OLD)}}],
    ),
}


@pytest.fixture
def sync_conn():
    """A sync psycopg2-backed connection wrapped in a rolled-back transaction.

    Mirrors ``tests/test_alembic_env_autogenerate.py``'s sync-url derivation.
    Everything this test does -- including the journal-table writes -- is
    undone by the final rollback, so it needs no interaction with
    ``conftest.py``'s async-engine truncation of mutable tables.
    """
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _seed(conn, docs: dict[str, dict]) -> dict[str, dict]:
    """Insert one phenopacket + head-published revision per fixture doc.

    Returns ``{key: {"pp_id": uuid, "rev_id": int, "doc": preimage}}``.
    """
    conn.execute(
        text(
            "INSERT INTO users (email, username, hashed_password, role, is_active) "
            "VALUES (:email, :username, 'x', 'curator', true)"
        ),
        {"email": "migration-test@example.invalid", "username": "migration-test-user"},
    )
    actor_id = conn.execute(
        text("SELECT id FROM users WHERE username = 'migration-test-user'")
    ).scalar_one()

    seeded: dict[str, dict] = {}
    for key, doc in docs.items():
        pp_id = uuid.uuid4()
        phenopacket_id = f"{key}-{pp_id.hex[:8]}"
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
                " actor_id, to_state, is_head_published) "
                "VALUES (:record_id, 1, 'published', cast(:doc as jsonb), 'seed', "
                " :actor_id, 'published', true) "
                "RETURNING id"
            ),
            {"record_id": pp_id, "doc": json.dumps(doc), "actor_id": actor_id},
        ).scalar_one()
        conn.execute(
            text(
                "UPDATE phenopackets SET head_published_revision_id = :rev_id "
                "WHERE id = :id"
            ),
            {"rev_id": rev_id, "id": pp_id},
        )
        seeded[key] = {"pp_id": pp_id, "rev_id": rev_id, "doc": doc}
    return seeded


def _fetch(conn, table: str, column: str, id_col: str, row_id) -> dict:
    return conn.execute(
        text(f"SELECT {column} FROM {table} WHERE {id_col} = :id"), {"id": row_id}
    ).scalar_one()


def test_migration_corrects_every_fixture_shape(sync_conn):
    seeded = _seed(sync_conn, FIXTURE)

    counts = MIGRATION.apply_corrections(sync_conn, REVISION_ID)
    assert counts["diseases"] > 0
    assert counts["subject"] > 0
    assert counts["phenotypicFeatures"] > 0
    assert counts["interpretations"] > 0

    def wc(key: str) -> dict:
        return _fetch(
            sync_conn, "phenopackets", "phenopacket", "id", seeded[key]["pp_id"]
        )

    def head(key: str) -> dict:
        return _fetch(
            sync_conn,
            "phenopacket_revisions",
            "content_jsonb",
            "id",
            seeded[key]["rev_id"],
        )

    # pp-both: collapse + dedupe down to a single disease entry
    both = wc("pp-both")
    assert len(both["diseases"]) == 1
    assert both["diseases"][0]["term"] == RCAD_NEW

    # pp-single: collapse only
    single = wc("pp-single")
    assert len(single["diseases"]) == 1
    assert single["diseases"][0]["term"] == RCAD_NEW

    # pp-onset: term collapsed AND onset remapped
    onset = wc("pp-onset")
    assert onset["diseases"][0]["term"] == RCAD_NEW
    assert onset["diseases"][0]["onset"]["ontologyClass"] == CONGENITAL_CLASS

    # pp-tale: subject.timeAtLastEncounter remapped
    tale = wc("pp-tale")
    assert tale["subject"]["timeAtLastEncounter"]["ontologyClass"] == CONGENITAL_CLASS

    # pp-post: HP:0003674 keeps its id, label becomes "Onset"
    post = wc("pp-post")
    assert post["diseases"][0]["onset"]["ontologyClass"] == ONSET_CLASS

    # pp-clean: byte-identical no-op
    assert wc("pp-clean") == FIXTURE["pp-clean"]
    assert head("pp-clean") == FIXTURE["pp-clean"]

    # pp-no-diseases: guard must not error and must leave the record alone
    no_diseases = wc("pp-no-diseases")
    assert "diseases" not in no_diseases
    assert (
        no_diseases["phenotypicFeatures"]
        == FIXTURE["pp-no-diseases"]["phenotypicFeatures"]
    )

    # pp-feature-onset: phenotypicFeatures[].onset.ontologyClass corrected
    feat = wc("pp-feature-onset")
    assert feat["phenotypicFeatures"][0]["onset"]["ontologyClass"] == CONGENITAL_CLASS

    # pp-feature-age-onset-mismatch: each nested location corrected from its
    # OWN stored value, not copied from its sibling
    mismatch = wc("pp-feature-age-onset-mismatch")
    onset_obj = mismatch["phenotypicFeatures"][0]["onset"]
    assert onset_obj["ontologyClass"] == CONGENITAL_CLASS  # was HP:0034199
    assert onset_obj["age"]["ontologyClass"] == ONSET_CLASS  # was HP:0003674

    # pp-interpretation: interpretations[].diagnosis.disease corrected
    interp = wc("pp-interpretation")
    assert interp["interpretations"][0]["diagnosis"]["disease"] == RCAD_NEW

    # Both copies agree for a representative record
    assert wc("pp-both") == head("pp-both")
    assert wc("pp-tale") == head("pp-tale")

    # No feature or interpretation was dropped or reordered
    assert len(wc("pp-feature-age-onset-mismatch")["phenotypicFeatures"]) == 1
    assert len(wc("pp-interpretation")["interpretations"]) == 1


def test_downgrade_restores_every_fixture_record_byte_identically(sync_conn):
    seeded = _seed(sync_conn, FIXTURE)
    MIGRATION.apply_corrections(sync_conn, REVISION_ID)

    restore_counts = MIGRATION.restore_from_journal(sync_conn, REVISION_ID)
    assert sum(restore_counts.values()) > 0

    for key, info in seeded.items():
        wc_doc = _fetch(sync_conn, "phenopackets", "phenopacket", "id", info["pp_id"])
        head_doc = _fetch(
            sync_conn, "phenopacket_revisions", "content_jsonb", "id", info["rev_id"]
        )
        assert wc_doc == FIXTURE[key], (
            f"{key} working copy not restored byte-identically"
        )
        assert head_doc == FIXTURE[key], (
            f"{key} head revision not restored byte-identically"
        )


def test_downgrade_does_not_touch_a_row_whose_postimage_was_edited_afterwards(
    sync_conn,
):
    """A curator edit made after the migration ran must survive downgrade.

    The whole-array preimage/postimage model can only verify the row hasn't
    changed since the correction; it cannot merge concurrent edits, so the
    contract is "leave it alone", not "silently overwrite".
    """
    seeded = _seed(sync_conn, {"pp-onset": FIXTURE["pp-onset"]})
    MIGRATION.apply_corrections(sync_conn, REVISION_ID)

    edited_diseases = [_disease(RCAD_NEW, ONSET_CLASS)]
    sync_conn.execute(
        text(
            "UPDATE phenopackets SET phenopacket = jsonb_set(phenopacket, "
            "'{diseases}', cast(:diseases as jsonb)) WHERE id = :id"
        ),
        {"diseases": json.dumps(edited_diseases), "id": seeded["pp-onset"]["pp_id"]},
    )

    MIGRATION.restore_from_journal(sync_conn, REVISION_ID)

    current = _fetch(
        sync_conn, "phenopackets", "phenopacket", "id", seeded["pp-onset"]["pp_id"]
    )
    assert current["diseases"] == edited_diseases, (
        "downgrade must not clobber a post-migration curator edit"
    )


def test_upgrade_then_downgrade_then_upgrade_again_is_idempotent(sync_conn):
    """A downgrade -> upgrade cycle must not fail or duplicate journal rows.

    Reproduces a real bug found while applying this migration to the dev
    database: the journal table is deliberately retained across downgrade
    (see module docstring), so a second ``upgrade()`` call re-creating it
    unconditionally raised ``DuplicateTable``, and without clearing this
    revision's prior journal rows first, a second application would leave
    two preimage rows per (table, row, json_path), making
    ``restore_from_journal``'s join ambiguous.
    """
    sync_conn.execute(text(MIGRATION._JOURNAL_TABLE_SQL))
    sync_conn.execute(text(MIGRATION._JOURNAL_INDEX_SQL))

    seeded = _seed(sync_conn, {"pp-onset": FIXTURE["pp-onset"]})

    MIGRATION.apply_corrections(sync_conn, REVISION_ID)
    MIGRATION.restore_from_journal(sync_conn, REVISION_ID)
    # Re-creating the table must be a no-op, not an error.
    sync_conn.execute(text(MIGRATION._JOURNAL_TABLE_SQL))
    sync_conn.execute(text(MIGRATION._JOURNAL_INDEX_SQL))
    sync_conn.execute(
        text(MIGRATION._CLEAR_OWN_JOURNAL_ROWS_SQL), {"revision": REVISION_ID}
    )
    MIGRATION.apply_corrections(sync_conn, REVISION_ID)

    journal_count = sync_conn.execute(
        text(
            "SELECT count(*) FROM ontology_migration_journal "
            "WHERE revision = :revision AND table_name = 'phenopackets' "
            "AND row_id = :row_id AND json_path = 'diseases'"
        ),
        {"revision": REVISION_ID, "row_id": str(seeded["pp-onset"]["pp_id"])},
    ).scalar_one()
    assert journal_count == 1, "re-applying upgrade() must not duplicate journal rows"

    MIGRATION.restore_from_journal(sync_conn, REVISION_ID)
    restored = _fetch(
        sync_conn, "phenopackets", "phenopacket", "id", seeded["pp-onset"]["pp_id"]
    )
    assert restored == FIXTURE["pp-onset"]


def test_journal_table_is_registered_in_alembic_env_include_object():
    import ast

    env_py = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    tree = ast.parse(env_py.read_text(encoding="utf-8"))
    source = env_py.read_text(encoding="utf-8")
    assert "ontology_migration_journal" in source, (
        "ontology_migration_journal must be registered in alembic/env.py's "
        "include_object whitelist"
    )
    _ = tree
