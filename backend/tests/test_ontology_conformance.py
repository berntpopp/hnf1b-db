"""Ontology conformance (spec §3.3).

A1 catches wrong identifiers. A3 catches drift. A3 alone cannot catch a wrong
identifier, because it is satisfiable by editing the label — which is exactly
how HP:0033133 survived.
"""

from app.ontology.conformance import ALLOWED_DEVIATIONS, check_label, check_source_row


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
    for key, reason in ALLOWED_DEVIATIONS.items():
        assert len(reason) > 40, f"{key} needs a justification, not a placeholder"
