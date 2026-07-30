"""Ontology conformance (spec §3.3).

A1 catches wrong identifiers. A3 catches drift. A3 alone cannot catch a wrong
identifier, because it is satisfiable by editing the label — which is exactly
how HP:0033133 survived.
"""

import csv
from pathlib import Path

from app.ontology.conformance import ALLOWED_DEVIATIONS, check_label, check_source_row

_CURATION_VOCABULARY_CSV = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "ontology"
    / "data"
    / "curation_vocabulary.csv"
)


class TestA3StoredConformance:
    """A3 `check_label`: naive label-vs-identifier check, deliberately insufficient."""

    def test_accepts_the_canonical_name(self):
        """A label matching the pinned snapshot's canonical name passes."""
        assert check_label("HP:0000107", "Renal cyst") is None

    def test_accepts_a_listed_synonym(self):
        """A label matching a listed synonym, not just the primary name, passes."""
        assert check_label("HP:0000708", "Behavioral abnormality") is None

    def test_rejects_an_unrelated_label(self):
        """A label unrelated to the id's canonical name/synonyms fails."""
        assert check_label("HP:0000107", "Seizure")

    def test_rejects_an_unknown_identifier(self):
        """An id absent from the pinned snapshot fails rather than passing silently."""
        assert check_label("HP:9999999", "Nonexistent")

    def test_covers_mondo_not_only_hpo(self):
        """Two of the five stored defects were MONDO."""
        assert check_label("MONDO:0007669", "renal cysts and diabetes syndrome") is None
        assert check_label("MONDO:0011593", "Renal cysts and diabetes syndrome")

    def test_cannot_catch_a_normalized_wrong_id(self):
        """Documents the limitation, so nobody mistakes A3 for the guard.

        HP:0033133 paired with ITS OWN canonical name passes A3 and is still
        the wrong term for this database. Only A1 catches that.
        """
        assert check_label("HP:0033133", "Renal cortical hypoechogeneity") is None


class TestA1SourceIntegrity:
    """A1 `check_source_row`: the discriminator, anchored on the description field."""

    def test_accepts_a_row_whose_definition_corroborates_its_id(self):
        """A description matching the id's canonical definition passes."""
        assert (
            check_source_row(
                "HP:0000107", "Renal cyst", "A fluid filled sac in the kidney."
            )
            is None
        )

    def test_accepts_a_local_qualifier_backed_by_a_matching_definition(self):
        """HP:0012622's name is curated, but its definition matches canonical."""
        assert (
            check_source_row(
                "HP:0012622",
                "chronic kidney disease, not specified",
                "Functional anomaly of the kidney persisting for at least three months.",
            )
            is None
        )

    def test_rejects_the_real_defect(self):
        """The row that produced T1: right name, right definition, wrong id."""
        violation = check_source_row(
            "HP:0033133",
            "Renal cortical hyperechogenicity",
            "Increased echogenecity of the kidney cortex.",
        )
        assert violation
        assert "HP:0033132" in violation, "must name the term the description describes"

    def test_accepts_a_name_only_match_when_no_definition_is_given(self):
        """No description falls back to a name-or-synonym match."""
        assert check_source_row("HP:0000107", "Renal cyst", "") is None

    def test_rejects_when_neither_field_corroborates(self):
        """Neither a matching description nor a matching name is a failure."""
        assert check_source_row("HP:0000107", "Seizure", "An epileptic event.")


def test_every_allowlisted_deviation_carries_a_reason():
    """Every ALLOWED_DEVIATIONS entry needs a justification, not a placeholder."""
    for key, reason in ALLOWED_DEVIATIONS.items():
        assert len(reason) > 40, f"{key} needs a justification, not a placeholder"


def test_check_source_row_against_the_real_curation_vocabulary():
    """A1 against the shipped CSV, not a hand-picked fixture built to pass.

    Hand-picked fixtures (above) have descriptions engineered to match their
    canonical definition verbatim. Real curated descriptions are usually a
    paraphrase, not a verbatim copy — e.g. HP:0001250's sheet description
    says "characterised", HPO's canonical definition says "characterized".
    Running every row of the committed `curation_vocabulary.csv` through
    `check_source_row` is what caught A1's rule-2-never-runs regression: 7
    of 8 "violations" it once reported were paraphrase mismatches on rows
    whose name matched the canonical name/synonym exactly, and only
    HP:0033133 (T1) is a genuine defect.
    """
    violations = []
    with _CURATION_VOCABULARY_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 41, (
        "expected 41 rows (36 Phenotype + 5 Phenotype_modifier); the CSV "
        "shape changed — update this test deliberately, don't just raise "
        "the number"
    )

    for row in rows:
        violation = check_source_row(
            row["phenotype_id"],
            row["phenotype_name"],
            row["phenotype_description"],
        )
        if violation:
            violations.append((row["phenotype_id"], violation))

    assert len(violations) == 1, (
        f"expected exactly one violation (the T1 defect), got "
        f"{len(violations)}: {violations}"
    )

    term_id, violation = violations[0]
    assert term_id == "HP:0033133"
    assert "HP:0033132" in violation, "must name the term the description describes"


def test_ontology_service_hardcoded_terms_are_conformant():
    """Three independent hardcoded maps is how these defects multiplied (§5).

    ``ADDITIONAL_TERMS`` is a module-level constant precisely so this test
    can import and check every entry, rather than a dict built inline inside
    a method body.
    """
    from app.services.ontology_service import ADDITIONAL_TERMS

    for term_id, label in ADDITIONAL_TERMS.items():
        assert check_label(term_id, label) is None, f"{term_id}: {label}"


def test_hpo_mapper_fallback_is_conformant():
    """T7-T11: every entry in HPOMapper's Sheets-outage fallback dict must be conformant.

    This is the assertion that would have caught T6-T9 (and, once extended
    while fixing them, T10-T11) without anyone auditing anything by hand.
    """
    from migration.phenopackets.hpo_mapper import HPOMapper

    for entry in HPOMapper().hpo_mappings.values():
        assert check_label(entry["id"], entry["label"]) is None, entry
