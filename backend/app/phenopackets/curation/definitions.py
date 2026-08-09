"""Stable source-question and finding-definition registry."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

_VOCABULARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "ontology"
    / "data"
    / "curation_vocabulary.csv"
)
_SOURCE_COLUMNS = (
    "RenalInsufficancy",
    "Hyperechogenicity",
    "RenalCysts",
    "MulticysticDysplasticKidney",
    "KidneyBiopsy",
    "RenalHypoplasia",
    "SolitaryKidney",
    "UrinaryTractMalformation",
    "GenitalTractAbnormality",
    "AntenatalRenalAbnormalities",
    "Hypomagnesemia",
    "Hypokalemia",
    "Hyperuricemia",
    "Gout",
    "MODY",
    "PancreaticHypoplasia",
    "ExocrinePancreaticInsufficiency",
    "Hyperparathyroidism",
    "NeurodevelopmentalDisorder",
    "MentalDisease",
    "Seizures",
    "BrainAbnormality",
    "PrematureBirth",
    "CongenitalCardiacAnomalies",
    "EyeAbnormality",
    "ShortStature",
    "MusculoskeletalFeatures",
    "DysmorphicFeatures",
    "ElevatedHepaticTransaminase",
    "AbnormalLiverPhysiology",
)
_DEFINITION_IDS = {
    "RenalInsufficancy": (
        "ckd-unspecified",
        "ckd-stage-1",
        "ckd-stage-2",
        "ckd-stage-3",
        "ckd-stage-4",
        "ckd-stage-5",
    ),
    "Hyperechogenicity": ("renal-cortical-hyperechogenicity",),
    "RenalCysts": ("renal-cyst",),
    "MulticysticDysplasticKidney": ("multicystic-kidney-dysplasia",),
    "KidneyBiopsy": ("multiple-glomerular-cysts", "oligomeganephronia"),
    "RenalHypoplasia": ("renal-hypoplasia",),
    "SolitaryKidney": ("unilateral-renal-agenesis",),
    "UrinaryTractMalformation": ("urinary-system-abnormality",),
    "GenitalTractAbnormality": ("genital-system-abnormality",),
    "AntenatalRenalAbnormalities": ("abnormal-renal-morphology",),
    "Hypomagnesemia": ("hypomagnesemia",),
    "Hypokalemia": ("hypokalemia",),
    "Hyperuricemia": ("hyperuricemia",),
    "Gout": ("gout",),
    "MODY": ("maturity-onset-diabetes-young",),
    "PancreaticHypoplasia": ("pancreatic-hypoplasia",),
    "ExocrinePancreaticInsufficiency": ("exocrine-pancreatic-insufficiency",),
    "Hyperparathyroidism": ("hyperparathyroidism",),
    "NeurodevelopmentalDisorder": ("neurodevelopmental-delay",),
    "MentalDisease": ("behavioral-abnormality",),
    "Seizures": ("seizure",),
    "BrainAbnormality": ("abnormal-brain-morphology",),
    "PrematureBirth": ("premature-birth",),
    "CongenitalCardiacAnomalies": ("abnormal-heart-morphology",),
    "EyeAbnormality": ("abnormality-of-eye",),
    "ShortStature": ("short-stature",),
    "MusculoskeletalFeatures": ("musculoskeletal-system-abnormality",),
    "DysmorphicFeatures": ("abnormal-facial-shape",),
    "ElevatedHepaticTransaminase": ("elevated-hepatic-transaminase",),
    "AbnormalLiverPhysiology": ("abnormal-liver-physiology",),
}
_LATERALITY_COLUMNS = {
    "Hyperechogenicity",
    "RenalCysts",
    "MulticysticDysplasticKidney",
    "RenalHypoplasia",
    "UrinaryTractMalformation",
}
_ALLOWED_STATES = (
    "PRESENT",
    "EXCLUDED",
    "NOT_REPORTED",
    "NOT_APPLICABLE",
    "INDETERMINATE",
    "NOT_ASSESSED",
)
with _VOCABULARY_PATH.open(newline="", encoding="utf-8") as _handle:
    _PINNED_ROWS = list(csv.DictReader(_handle))
_TERM_IDS_BY_COLUMN: dict[str, tuple[str, ...]] = {
    column: tuple(
        row["phenotype_id"]
        for row in _PINNED_ROWS
        if row["phenotype_category"] == column
    )
    for column in _SOURCE_COLUMNS
}


@dataclass(frozen=True)
class FindingDefinition:
    """A stable clinical question answer independent of its current ontology ID."""

    definition_id: str
    source_column: str
    term_id: str
    term_label: str
    allowed_states: tuple[str, ...]
    allowed_laterality: str


@dataclass(frozen=True)
class PhenotypeQuestion:
    """One source-question assessment with one or more permitted findings."""

    source_column: str
    definition_ids: tuple[str, ...]
    finding_cardinality: str
    allowed_laterality: str


def _build_registry(
    rows: list[dict[str, str]] | None = None,
) -> tuple[tuple[FindingDefinition, ...], tuple[PhenotypeQuestion, ...]]:
    if rows is None:
        with _VOCABULARY_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    phenotype_rows = [row for row in rows if row["phenotype_category"] != "Modifier"]
    findings: list[FindingDefinition] = []
    by_column: dict[str, list[str]] = {column: [] for column in _SOURCE_COLUMNS}
    for row in phenotype_rows:
        column = row["phenotype_category"]
        definition_id = next(
            definition_id
            for expected_row, definition_id in zip(
                _rows_for_column(column), _DEFINITION_IDS[column]
            )
            if expected_row == row["phenotype_id"]
        )
        by_column[column].append(definition_id)
        findings.append(
            FindingDefinition(
                definition_id,
                column,
                row["phenotype_id"],
                row["phenotype_name"],
                _ALLOWED_STATES,
                "compound" if column in _LATERALITY_COLUMNS else "none",
            )
        )
    questions = tuple(
        PhenotypeQuestion(
            column,
            tuple(by_column[column]),
            "one_of" if len(by_column[column]) > 1 else "single",
            "compound" if column in _LATERALITY_COLUMNS else "none",
        )
        for column in _SOURCE_COLUMNS
    )
    return tuple(findings), questions


def _rows_for_column(column: str) -> tuple[str, ...]:
    """Return the explicitly pinned ontology IDs for a source question."""
    return _TERM_IDS_BY_COLUMN[column]


FINDING_DEFINITIONS, PHENOTYPE_QUESTIONS = _build_registry()
