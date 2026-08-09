"""Public behaviour for the versioned ontology-correction ledger."""

from app.ontology.conformance import correction_counts, load_correction_ledger


def test_ledger_is_complete_and_keeps_the_audited_hyperechogenicity_fix():
    """A missing field or a changed target must fail before source preflight runs."""
    entries = load_correction_ledger()

    required = {
        "defect_key",
        "location",
        "wrong_id",
        "wrong_label",
        "intended_id",
        "intended_label",
        "correction_kind",
        "ontology_release",
        "evidence",
        "affected_count",
        "test_or_migration_reference",
    }
    assert entries
    assert all(required <= set(entry) for entry in entries)

    hyperechogenicity = next(entry for entry in entries if entry["defect_key"] == "T1")
    assert hyperechogenicity["wrong_id"] == "HP:0033133"
    assert hyperechogenicity["intended_id"] == "HP:0033132"
    assert hyperechogenicity["intended_label"] == "Renal cortical hyperechogenicity"


def test_ledger_summary_is_derived_from_correction_kinds_not_a_magic_total():
    """The historic, contradictory '14 wrong identifiers' claim must not return."""
    entries = load_correction_ledger()
    counts = correction_counts(entries)

    assert counts["identifier_change"] == sum(
        entry["correction_kind"] == "identifier_change" for entry in entries
    )
    assert counts["label_only"] == sum(
        entry["correction_kind"] == "label_only" for entry in entries
    )
    assert counts["semantic_unprojection"] == sum(
        entry["correction_kind"] == "semantic_unprojection" for entry in entries
    )
    assert counts["identifier_change"] > 0
    assert counts["label_only"] > 0
    assert any(
        entry["intended_id"] == "HP:0030674"
        and entry["intended_label"] == "Antenatal onset"
        for entry in entries
    )
