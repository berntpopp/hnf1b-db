"""Ontology conformance for ClinicalQueries.get_morphology_features (spec §3.3).

The fifth independent hardcoded ontology map documented in
docs/ontology-defect-report-2026-07-30.md §5 -- found by the Task 6
implementer while fixing the other four (T7-T11 in `hpo_mapper.py`) but left
unfixed there because it was out of that task's file scope. Same T9 defect,
same shape: `HP:0004719` labelled "Oligomeganephronia" is actually
"Hyperechogenic kidneys"; the corpus stores Oligomeganephronia as
`ORPHA:2260`. Unlike `hpo_mapper.py`'s fallback dict, this map is live: it
backs `GET /kidney-morphology`, so the wrong id silently excluded all 75
stored Oligomeganephronia cases from the `hypoplasia` filter (and the
unfiltered default).

Mirrors `tests/test_ontology_conformance.py::test_hpo_mapper_fallback_is_conformant`.
"""

from app.ontology.conformance import check_label
from app.phenopackets.clinical_queries import MORPHOLOGY_TERM_LABELS

# HP:0000110 and HP:0000113 used to fail check_label only because they were
# absent from the pinned ontology snapshot (app/ontology/data/
# ontology_snapshot.json) -- a coverage gap, not a defect, in the same sense
# the defect report describes for HP:0012759 (§2). Both were independently
# verified against the live HPO API (OLS4, 2026-07-30):
#   HP:0000110 -> "Renal dysplasia" (matches this map's label exactly)
#   HP:0000113 -> "Polycystic kidney dysplasia" (matches this map's label
#     exactly; "Polycystic kidneys" is also a listed synonym)
# scripts/refresh_ontology_snapshot.py now resolves both (Task 5,
# docs/superpowers/plans/2026-07-30-ontology-data-quality.md), closing the
# gap this test used to document explicitly.


def test_morphology_term_labels_are_conformant():
    """Every id/label pair in MORPHOLOGY_TERM_LABELS is A3-conformant.

    A genuine wrong-identifier defect (the T9 shape this test guards
    against, e.g. `HP:0004719` labelled "Oligomeganephronia") fails with a
    *label mismatch* message naming the pinned snapshot's actual canonical
    name/synonyms for that id.
    """
    violations = {
        term_id: violation
        for term_id, label in MORPHOLOGY_TERM_LABELS.items()
        if (violation := check_label(term_id, label)) is not None
    }
    assert not violations, violations


def test_hypoplasia_filter_no_longer_uses_the_wrong_oligomeganephronia_id():
    """Regression fence for the live T9 recurrence.

    `HP:0004719` denotes "Hyperechogenic kidneys", not Oligomeganephronia,
    and appears in zero stored records; the corpus stores Oligomeganephronia
    as `ORPHA:2260`. Filtering `morphology_type=hypoplasia` on the wrong id
    silently returned none of the 75 stored Oligomeganephronia cases.
    """
    assert "HP:0004719" not in MORPHOLOGY_TERM_LABELS
    assert MORPHOLOGY_TERM_LABELS.get("ORPHA:2260") == "Oligomeganephronia"


def test_hypoplasia_query_filters_on_orpha_2260_not_the_wrong_hp_id():
    """Compiled-SQL regression fence: proves the fix at the query level, not
    just at the constant-dictionary level.

    Before the fix, `morphology_type=hypoplasia` compiled a `jsonpath`
    condition against `HP:0004719`, a term that appears in zero stored
    records (see the module docstring and
    docs/ontology-defect-report-2026-07-30.md §2 T9). Compiling with
    literal binds surfaces the jsonpath text exactly as it reaches
    PostgreSQL.
    """
    from app.phenopackets.clinical_queries import ClinicalQueries

    for morphology_type in (None, "hypoplasia"):
        compiled = str(
            ClinicalQueries.get_morphology_features(morphology_type).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "ORPHA:2260" in compiled, morphology_type
        assert "HP:0004719" not in compiled, morphology_type
