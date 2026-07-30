"""The importer must never rewrite a curator's term name (spec §3.3 A2).

hpo_mapper._get_canonical_label trusted the identifier and overwrote
phenotype_name with the canonical name of whatever id the sheet supplied. For
HP:0033133 that inverted a clinical finding across 460 features and logged it
at debug level.
"""

import pandas as pd

from migration.phenopackets.hpo_mapper import HPOMapper


def sheet(rows):
    return pd.DataFrame(
        rows, columns=["phenotype_category", "phenotype_id", "phenotype_name"]
    )


def test_curator_label_is_written_verbatim():
    mapper = HPOMapper()
    mapper.build_from_dataframe(sheet([["RenalCysts", "HP:0000107", "Renal cyst"]]))
    assert mapper.get_hpo_term("renalcysts")["label"] == "Renal cyst"


def test_a_local_qualifier_survives_unchanged():
    """HP:0012622's curated label is deliberately not the canonical name."""
    mapper = HPOMapper()
    mapper.build_from_dataframe(
        sheet(
            [
                [
                    "RenalInsufficancy",
                    "HP:0012622",
                    "chronic kidney disease, not specified",
                ]
            ]
        )
    )
    label = mapper.get_hpo_term("renalinsufficancy")["label"]
    assert label == "chronic kidney disease, not specified"
    assert label != "Chronic kidney disease", "canonical name must not be substituted"


def test_the_laundering_method_no_longer_exists():
    """A regression fence: the fix is deletion, not a behaviour flag."""
    assert not hasattr(HPOMapper, "_get_canonical_label")


def test_no_normalization_is_logged(caplog):
    mapper = HPOMapper()
    with caplog.at_level("DEBUG"):
        mapper.build_from_dataframe(sheet([["RenalCysts", "HP:0000107", "Renal cyst"]]))
    assert not any("Normalized label" in r.message for r in caplog.records)
