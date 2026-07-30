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

# Ids present in MORPHOLOGY_TERM_LABELS but absent from the pinned ontology
# snapshot (app/ontology/data/ontology_snapshot.json) -- a coverage gap, not
# a defect, in the same sense the defect report describes for HP:0012759
# (§2): "it only failed check_label because it was missing from the pinned
# snapshot, a coverage gap rather than a defect." Both ids were independently
# verified against the live HPO API (OLS4, 2026-07-30):
#   HP:0000110 -> "Renal dysplasia" (matches this map's label exactly)
#   HP:0000113 -> "Polycystic kidney dysplasia", with "Polycystic kidneys"
#     (this map's label) listed as a synonym
# Extending the pinned snapshot's explicit term list is out of scope for this
# fix (file scope: clinical_queries.py, this test, the defect-report doc), so
# this test asserts the coverage gap explicitly rather than silently
# skipping these two ids -- if the snapshot is later extended to cover them,
# `check_label` will start returning `None` and this test documents exactly
# that expected transition.
_NOT_IN_PINNED_SNAPSHOT = {"HP:0000110", "HP:0000113"}


def test_morphology_term_labels_are_conformant_or_a_documented_coverage_gap():
    """Every id/label pair is either A3-conformant or a known snapshot gap.

    A genuine wrong-identifier defect (the T9 shape this test guards
    against) fails with a *label mismatch* message naming the pinned
    snapshot's actual canonical name/synonyms for that id -- distinct from
    the "not a known term in the pinned ontology snapshot" message a
    coverage gap produces. Asserting on the message content, not just
    truthiness, keeps this test from silently reclassifying a real defect as
    a coverage gap if a future edit reuses one of the gap ids for something
    else.
    """
    unexpected_violations = {}
    for term_id, label in MORPHOLOGY_TERM_LABELS.items():
        violation = check_label(term_id, label)
        if violation is None:
            assert term_id not in _NOT_IN_PINNED_SNAPSHOT, (
                f"{term_id} now resolves against the pinned snapshot -- "
                "remove it from _NOT_IN_PINNED_SNAPSHOT."
            )
            continue
        if term_id in _NOT_IN_PINNED_SNAPSHOT:
            assert "not a known term in the pinned ontology snapshot" in violation, (
                f"{term_id} failed check_label for a reason other than "
                f"snapshot coverage -- investigate: {violation}"
            )
            continue
        unexpected_violations[term_id] = violation

    assert not unexpected_violations, unexpected_violations


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
