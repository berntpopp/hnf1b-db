"""API enum vocabularies as Literal aliases + value tuples.

GENERATED FILE — do not hand-edit.
Regenerate with ``scripts/gen_contract.py`` (``make contract``) from
``contract/openapi.snapshot.json``.
"""

from __future__ import annotations


from typing import Literal

# --- component schema enums ---

MolecularConsequence = Literal[
    "Frameshift",
    "Nonsense",
    "Missense",
    "Splice Donor",
    "Splice Acceptor",
    "In-frame Deletion",
    "In-frame Insertion",
    "Synonymous",
    "Intronic Variant",
    "Coding Sequence Variant",
]
MOLECULAR_CONSEQUENCE_VALUES: tuple[str, ...] = (
    "Frameshift",
    "Nonsense",
    "Missense",
    "Splice Donor",
    "Splice Acceptor",
    "In-frame Deletion",
    "In-frame Insertion",
    "Synonymous",
    "Intronic Variant",
    "Coding Sequence Variant",
)

ProteinDomain = Literal[
    "Dimerization Domain",
    "POU-Specific Domain",
    "POU Homeodomain",
    "Transactivation Domain",
]
PROTEIN_DOMAIN_VALUES: tuple[str, ...] = (
    "Dimerization Domain",
    "POU-Specific Domain",
    "POU Homeodomain",
    "Transactivation Domain",
)

VariantClassification = Literal[
    "PATHOGENIC",
    "LIKELY_PATHOGENIC",
    "UNCERTAIN_SIGNIFICANCE",
    "LIKELY_BENIGN",
    "BENIGN",
]
VARIANT_CLASSIFICATION_VALUES: tuple[str, ...] = (
    "PATHOGENIC",
    "LIKELY_PATHOGENIC",
    "UNCERTAIN_SIGNIFICANCE",
    "LIKELY_BENIGN",
    "BENIGN",
)

VariantType = Literal[
    "SNV", "deletion", "duplication", "insertion", "indel", "inversion", "CNV"
]
VARIANT_TYPE_VALUES: tuple[str, ...] = (
    "SNV",
    "deletion",
    "duplication",
    "insertion",
    "indel",
    "inversion",
    "CNV",
)

# --- inline parameter enums ---

Comparison = Literal[
    "truncating_vs_non_truncating",
    "truncating_vs_non_truncating_excl_cnv",
    "cnv_vs_point_mutation",
    "cnv_deletion_vs_duplication",
]
COMPARISON_VALUES: tuple[str, ...] = (
    "truncating_vs_non_truncating",
    "truncating_vs_non_truncating_excl_cnv",
    "cnv_vs_point_mutation",
    "cnv_deletion_vs_duplication",
)

DiabetesType = Literal["Type 1", "Type 2", "MODY"]
DIABETES_TYPE_VALUES: tuple[str, ...] = ("Type 1", "Type 2", "MODY")

ReportingMode = Literal["all_cases", "reported_only"]
REPORTING_MODE_VALUES: tuple[str, ...] = ("all_cases", "reported_only")

SexFilter = Literal["FEMALE", "MALE"]
SEX_FILTER_VALUES: tuple[str, ...] = ("FEMALE", "MALE")

SortBy = Literal["p_value", "effect_size", "prevalence_diff"]
SORT_BY_VALUES: tuple[str, ...] = ("p_value", "effect_size", "prevalence_diff")
