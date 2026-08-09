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
# This is deliberately a definition-id -> ontology-id manifest, rather than a
# CSV row position. The vocabulary CSV supplies labels and a checked copy of
# the rows, but cannot silently reassign a persisted definition ID.
_TERM_ID_BY_DEFINITION = {
    "ckd-unspecified": "HP:0012622",
    "ckd-stage-1": "HP:0012623",
    "ckd-stage-2": "HP:0012624",
    "ckd-stage-3": "HP:0012625",
    "ckd-stage-4": "HP:0012626",
    "ckd-stage-5": "HP:0003774",
    "renal-cortical-hyperechogenicity": "HP:0033132",
    "renal-cyst": "HP:0000107",
    "multicystic-kidney-dysplasia": "HP:0000003",
    "multiple-glomerular-cysts": "HP:0100611",
    "oligomeganephronia": "ORPHA:2260",
    "renal-hypoplasia": "HP:0000089",
    "unilateral-renal-agenesis": "HP:0000122",
    "urinary-system-abnormality": "HP:0000079",
    "genital-system-abnormality": "HP:0000078",
    "abnormal-renal-morphology": "HP:0012210",
    "hypomagnesemia": "HP:0002917",
    "hypokalemia": "HP:0002900",
    "hyperuricemia": "HP:0002149",
    "gout": "HP:0001997",
    "maturity-onset-diabetes-young": "HP:0004904",
    "pancreatic-hypoplasia": "HP:0002594",
    "exocrine-pancreatic-insufficiency": "HP:0001738",
    "hyperparathyroidism": "HP:0000843",
    "neurodevelopmental-delay": "HP:0012758",
    "behavioral-abnormality": "HP:0000708",
    "seizure": "HP:0001250",
    "abnormal-brain-morphology": "HP:0012443",
    "premature-birth": "HP:0001622",
    "abnormal-heart-morphology": "HP:0001627",
    "abnormality-of-eye": "HP:0000478",
    "short-stature": "HP:0004322",
    "musculoskeletal-system-abnormality": "HP:0033127",
    "abnormal-facial-shape": "HP:0001999",
    "elevated-hepatic-transaminase": "HP:0002910",
    "abnormal-liver-physiology": "HP:0031865",
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
    rows_by_term = {row["phenotype_id"]: row for row in rows}
    findings: list[FindingDefinition] = []
    by_column: dict[str, list[str]] = {column: [] for column in _SOURCE_COLUMNS}
    for column in _SOURCE_COLUMNS:
        for definition_id in _DEFINITION_IDS[column]:
            term_id = _TERM_ID_BY_DEFINITION[definition_id]
            row = rows_by_term.get(term_id)
            if row is None or row["phenotype_category"] != column:
                raise ValueError(
                    f"vocabulary does not match pinned definition {definition_id}"
                )
            by_column[column].append(definition_id)
            findings.append(
                FindingDefinition(
                    definition_id,
                    column,
                    term_id,
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


FINDING_DEFINITIONS, PHENOTYPE_QUESTIONS = _build_registry()
