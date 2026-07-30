"""``hpo_terms_lookup``'s free-text metadata must agree with the pinned
ontology snapshot -- the assertion that would have caught the
``d4e8b1f60a27`` C1 defect.

That migration retargeted only ``hpo_id``/``label`` for the
renal-echogenicity correction, leaving ``category``/``description``/
``synonyms`` carrying HP:0033133's own true metadata (Hypoechogenicity,
"Decreased echogenicity...") under the now-corrected HP:0033132 id/label
(Hyperechogenicity). Neither ``app.ontology.conformance``'s A1 (id/name) nor
A3 (label-vs-snapshot) check catches this, because the row is
``(id, label)``-correct and only its *description* is inverted.

This module reads ``app/ontology/data/ontology_snapshot.json`` directly
(not via ``app.ontology.conformance._snapshot()``) to avoid depending on that
module's internals while it is under concurrent edit elsewhere on this
branch; both read the same file the same way.

``hpo_terms_lookup`` is a static lookup table Alembic migrations populate
(``tests/conftest.py``'s ``_MUTABLE_TABLES`` deliberately excludes it), so
its real, migration-applied content is visible here without any seeding --
this test exercises the actual corpus-wide table, not a synthetic fixture.

Deliberately NOT a strict "every row must match exactly" assertion: several
rows carry a paraphrased description that means the same thing as the
snapshot's HPO definition (different wording, same clinical concept -- see
``_KNOWN_PARAPHRASE_DIFFERENCES`` below), inherited from the original
curation-sheet seed rather than the pinned HPO snapshot text. Those are
pre-existing, out of scope for this migration-safety fix, and listed
explicitly with their diff so a *new*, unexplained disagreement (a real
meaning inversion, like HP:0033132 before its fix) still fails the test.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import settings

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "ontology"
    / "data"
    / "ontology_snapshot.json"
)

# hpo_id -> reason this row's stored description differs from the pinned
# snapshot's definition without being a clinical contradiction. Every entry
# here was verified by hand against both texts (see this module's docstring
# and the migration-safety report this test accompanies): each pair
# describes the *same* finding in different words (paraphrase, spelling
# variant, or a strictly-more-detailed synonym list), never the opposite
# finding. HP:0033132 is deliberately NOT in this list -- it must match
# exactly, since that is the row this test exists to guard.
_KNOWN_PARAPHRASE_DIFFERENCES = {
    "ORPHA:2260": "paraphrase: 'developmental anomaly...' vs 'rare kidney malformation...', same concept",
    "HP:0002917": "paraphrase: 'abnormally decreased' vs 'below the lower limit of normal', same concept",
    "HP:0002900": "paraphrase: 'abnormally decreased' vs 'below the lower limit of normal', same concept",
    "HP:0002149": "paraphrase: 'abnormally high' vs 'above the upper limit of normal', same concept",
    "HP:0004904": "wording/spelling variant only ('resistence' -> 'resistance')",
    "HP:0012758": "stored description is empty; snapshot has the real HPO definition -- a "
    "missing-data gap, not a contradiction, and out of this fix's scope",
    "HP:0001250": "spelling variant only (British 'characterised' vs American 'characterized')",
    "HP:0000708": "paraphrase: different wording, same concept (mental/behavioural abnormality)",
}


def _load_snapshot_terms() -> dict[str, dict]:
    with _SNAPSHOT_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["terms"]


def _load_lookup_rows() -> list[dict]:
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT hpo_id, label, category, description, synonyms "
                        "FROM hpo_terms_lookup ORDER BY hpo_id"
                    )
                )
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]
    finally:
        engine.dispose()


def test_hpo_terms_lookup_description_agrees_with_snapshot_definition():
    """Every ``hpo_terms_lookup`` row present in the snapshot must describe
    the same finding as ``snapshot[hpo_id]['definition']`` -- exactly, unless
    explicitly allow-listed as a known paraphrase (see module docstring).
    """
    snapshot_terms = _load_snapshot_terms()
    lookup_rows = _load_lookup_rows()

    compared = 0
    unexplained_disagreements: list[str] = []
    for row in lookup_rows:
        term = snapshot_terms.get(row["hpo_id"])
        if term is None:
            continue
        compared += 1
        stored = (row["description"] or "").strip()
        canonical = (term.get("definition") or "").strip()
        if stored == canonical:
            continue
        if row["hpo_id"] in _KNOWN_PARAPHRASE_DIFFERENCES:
            continue
        unexplained_disagreements.append(
            f"{row['hpo_id']} ({row['label']!r}): stored={stored!r} "
            f"snapshot={canonical!r}"
        )

    assert compared > 0, (
        "sanity: at least one hpo_terms_lookup row must be in the snapshot"
    )
    assert not unexplained_disagreements, (
        "hpo_terms_lookup.description disagrees with the pinned snapshot's "
        "definition for row(s) not covered by _KNOWN_PARAPHRASE_DIFFERENCES "
        "-- this is the id/label-correct-but-description-inverted defect "
        "class d4e8b1f60a27's C1 fix exists to close:\n"
        + "\n".join(unexplained_disagreements)
    )


def test_renal_echogenicity_lookup_row_is_fully_coherent():
    """Targeted regression lock for the actual C1 defect: HP:0033132's
    category and description must agree with its (hyper-)echogenicity label,
    not the opposite (hypo-)echogenicity finding HP:0033133 carries.
    """
    snapshot_terms = _load_snapshot_terms()
    lookup_rows = {row["hpo_id"]: row for row in _load_lookup_rows()}

    row = lookup_rows.get("HP:0033132")
    assert row is not None, "HP:0033132 must exist in hpo_terms_lookup"
    assert row["label"] == "Renal cortical hyperechogenicity"
    assert "hyper" in row["category"].lower()
    assert "hypo" not in row["category"].lower()
    assert "increas" in row["description"].lower()
    assert "decreas" not in row["description"].lower()
    assert (
        row["description"].strip() == snapshot_terms["HP:0033132"]["definition"].strip()
    )

    # HP:0033133 itself (the wrong id) must no longer be present as a lookup
    # row -- d4e8b1f60a27 repoints the row's own hpo_id from 0033133 to 0033132.
    assert "HP:0033133" not in lookup_rows
