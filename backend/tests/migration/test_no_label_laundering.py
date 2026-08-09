"""The importer must never rewrite a curator's term name (spec §3.3 A2).

hpo_mapper._get_canonical_label trusted the identifier and overwrote
phenotype_name with the canonical name of whatever id the sheet supplied. For
HP:0033133 that inverted a clinical finding across 460 features and logged it
at debug level.

Also covers A1 (`check_source_row`, spec §3.3), wired into
`build_from_dataframe` in the same commit: a row whose identifier disagrees
with its own description must raise, naming the term the description
actually describes.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.ontology.conformance import OntologySourceError
from migration.phenopackets.hpo_mapper import HPOMapper


def sheet(rows):
    """Build a minimal Phenotype-sheet-shaped DataFrame from 4-tuple rows.

    Each row is (category, id, name, description). A description is
    required on every row here so A1 (`check_source_row`) can corroborate
    the identifier via the sheet's own definition — the same field the
    label-laundering defect never touched.
    """
    return pd.DataFrame(
        rows,
        columns=[
            "phenotype_category",
            "phenotype_id",
            "phenotype_name",
            "phenotype_description",
        ],
    )


def test_curator_label_is_written_verbatim():
    """HP:0012622's curated label is deliberately not the canonical name.

    Re-pointed from HP:0000107/"Renal cyst" (where curator label == canonical
    label, so the assertion could not have caught a regression) to a term
    whose curated label genuinely differs — the case this test exists for.
    """
    mapper = HPOMapper()
    mapper.build_from_dataframe(
        sheet(
            [
                [
                    "RenalInsufficancy",
                    "HP:0012622",
                    "chronic kidney disease, not specified",
                    "Functional anomaly of the kidney persisting for at least "
                    "three months.",
                ]
            ]
        )
    )
    assert (
        mapper.get_hpo_term("renalinsufficancy")["label"]
        == "chronic kidney disease, not specified"
    )


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
                    "Functional anomaly of the kidney persisting for at least "
                    "three months.",
                ]
            ]
        )
    )
    term = mapper.get_hpo_term("renalinsufficancy")
    assert term["id"] == "HP:0012622"
    assert term["label"] == "chronic kidney disease, not specified"
    assert term["label"] != "Chronic kidney disease", (
        "canonical name must not be substituted"
    )


def test_the_laundering_method_no_longer_exists():
    """A regression fence: the fix is deletion, not a behaviour flag."""
    assert not hasattr(HPOMapper, "_get_canonical_label")


def test_no_normalization_is_logged(caplog):
    """Re-pointed at HP:0012622 alongside the other two Wave 2A minor fixes."""
    mapper = HPOMapper()
    with caplog.at_level("DEBUG"):
        mapper.build_from_dataframe(
            sheet(
                [
                    [
                        "RenalInsufficancy",
                        "HP:0012622",
                        "chronic kidney disease, not specified",
                        "Functional anomaly of the kidney persisting for at "
                        "least three months.",
                    ]
                ]
            )
        )
    assert not any("Normalized label" in r.message for r in caplog.records)


def test_a_row_with_the_t1_defect_raises_and_names_the_right_term():
    """A1: the exact row that produced T1 must fail the import, not just A3.

    HP:0033133 paired with "Renal cortical hyperechogenicity" and a
    description that is verbatim HP:0033132's canonical definition — right
    name, right description, wrong id. `build_from_dataframe` must raise
    `OntologySourceError` and name `HP:0033132` in the message.
    """
    mapper = HPOMapper()
    with pytest.raises(OntologySourceError) as excinfo:
        mapper.build_from_dataframe(
            sheet(
                [
                    [
                        "Hyperechogenicity",
                        "HP:0033133",
                        "Renal cortical hyperechogenicity",
                        "Increased echogenecity of the kidney cortex.",
                    ]
                ]
            )
        )
    assert "HP:0033132" in str(excinfo.value)


def test_no_script_rewrites_stored_curator_labels():
    """scripts/normalize_hpo_labels.py rewrote stored labels to match ids (§4.1).

    It was a sixth instance of the label-laundering defect family and the
    one that most directly defeated this file's fix: it rewrote
    ``feature["type"]["label"]`` on *already-stored* records (so deleting
    ``_get_canonical_label`` did not contain it), and wrote only
    ``pp.phenopacket``, never the head-published revision. Confirmed invoked
    by no Makefile target, CI workflow, or migration path -- deleted rather
    than flagged, matching this file's precedent that the fix is deletion,
    not a behaviour flag. ``check_label`` +
    ``scripts/ontology_preflight.py`` replace it.
    """
    assert not (
        Path(__file__).parents[2] / "scripts" / "normalize_hpo_labels.py"
    ).exists()
