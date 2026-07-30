"""Conformance fence for the timeline categoriser's HPO ids.

Regression guard for ``backend/app/phenopackets/routers/crud_timeline.py``'s
category membership sets: every id the categoriser classifies must agree
with the pinned ontology snapshot's canonical name
(``app.ontology.conformance.check_label``, A3) wherever the snapshot covers
that id. Ids the pinned snapshot does not cover (all four have zero
occurrences in the corpus the snapshot was built from) are reported here
explicitly rather than silently added to the snapshot -- that decision
belongs to whoever owns ``app/ontology/data/``, not to this test.

See ``.superpowers/sdd/2026-07-30-ontology-data-quality/
task-timeline-report.md`` for the live HPO API resolution log every name
below was taken from (resolved against
``https://ontology.jax.org/api/hp/terms/{id}``, field ``name``).
"""

from __future__ import annotations

from app.ontology.conformance import check_label
from app.phenopackets.routers.crud_timeline import (
    _DIABETES_IDS,
    _GENITAL_IDS,
    _HEPATIC_IDS,
    _METABOLIC_IDS,
    _NEURO_IDS,
    _RENAL_IDS,
)

# id -> canonical name, resolved live from
# https://ontology.jax.org/api/hp/terms/{id} (field "name").
_EXPECTED_NAMES: dict[str, str] = {
    "HP:0000107": "Renal cyst",
    "HP:0000003": "Multicystic kidney dysplasia",
    "HP:0000122": "Unilateral renal agenesis",
    "HP:0000089": "Renal hypoplasia",
    "HP:0033132": "Renal cortical hyperechogenicity",
    "HP:0000079": "Abnormality of the urinary system",
    "HP:0012210": "Abnormal renal morphology",
    "HP:0012622": "Chronic kidney disease",
    "HP:0012623": "Stage 1 chronic kidney disease",
    "HP:0012624": "Stage 2 chronic kidney disease",
    "HP:0012625": "Stage 3 chronic kidney disease",
    "HP:0003774": "Stage 5 chronic kidney disease",
    "HP:0012626": "Stage 4 chronic kidney disease",
    "HP:0100611": "Multiple glomerular cysts",
    "HP:0000077": "Abnormality of the kidney",
    "HP:0000119": "Abnormality of the genitourinary system",
    "HP:0000078": "Abnormality of the genital system",
    "HP:0000080": "Abnormality of reproductive system physiology",
    "HP:0004904": "Maturity-onset diabetes of the young",
    "HP:0002594": "Pancreatic hypoplasia",
    "HP:0001738": "Exocrine pancreatic insufficiency",
    "HP:0003111": "Abnormal circulating electrolyte concentration",
    "HP:0002149": "Hyperuricemia",
    "HP:0002917": "Hypomagnesemia",
    "HP:0002900": "Hypokalemia",
    "HP:0000843": "Hyperparathyroidism",
    "HP:0001997": "Gout",
    "HP:0012758": "Neurodevelopmental delay",
    "HP:0000708": "Atypical behavior",
    "HP:0001250": "Seizure",
    "HP:0012443": "Abnormal brain morphology",
    "HP:0002910": "Elevated circulating hepatic transaminase concentration",
    "HP:0031865": "Abnormal liver physiology",
}

_ALL_CATEGORISED_IDS = (
    _RENAL_IDS
    | _GENITAL_IDS
    | _DIABETES_IDS
    | _METABOLIC_IDS
    | _NEURO_IDS
    | _HEPATIC_IDS
)

# Ids the categoriser classifies that the pinned snapshot
# (app/ontology/data/ontology_snapshot.json) does not cover -- all four
# have zero occurrences in the dev corpus the snapshot was built from.
# Documented explicitly, not silently added to the snapshot: that decision
# belongs to whoever owns app/ontology/data/ on this branch.
_NOT_COVERED_BY_SNAPSHOT = frozenset(
    {
        "HP:0000077",
        "HP:0000080",
        "HP:0000119",
        "HP:0003111",
    }
)


def test_every_categorised_id_has_an_expected_name():
    """Guard against a category set gaining an id this fence forgot to cover."""
    missing = _ALL_CATEGORISED_IDS - _EXPECTED_NAMES.keys()
    assert not missing, (
        "id(s) in a crud_timeline category set are missing from "
        f"_EXPECTED_NAMES -- add their live-resolved name: {sorted(missing)}"
    )


def test_categorised_ids_agree_with_pinned_snapshot_where_covered():
    """Every categorised id's live-resolved name must match the pinned
    snapshot's canonical name/synonyms, for every id the snapshot covers.

    Ids the snapshot does not cover are collected and reported via the
    second assertion below instead of being silently ignored or added to
    the snapshot.
    """
    uncovered: set[str] = set()
    disagreements: list[str] = []

    for hpo_id, name in _EXPECTED_NAMES.items():
        violation = check_label(hpo_id, name)
        if violation is None:
            continue
        if f"{hpo_id} is not a known term in the pinned ontology snapshot" in violation:
            uncovered.add(hpo_id)
            continue
        disagreements.append(violation)

    assert not disagreements, (
        "categoriser id(s) disagree with the pinned ontology snapshot's "
        "canonical name: " + "; ".join(disagreements)
    )
    # Report exactly which ids the snapshot doesn't cover, rather than
    # silently adding them. If this assertion breaks: either the snapshot
    # started covering one of these (shrink _NOT_COVERED_BY_SNAPSHOT) or a
    # newly-categorised id needs triage by the ontology data owner (grow it,
    # with a reason).
    assert uncovered == _NOT_COVERED_BY_SNAPSHOT, (
        f"pinned ontology snapshot coverage changed for categoriser ids: "
        f"now-uncovered={sorted(uncovered)}"
    )
