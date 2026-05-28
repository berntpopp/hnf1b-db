"""HNF1B API contract — generated from the backend OpenAPI snapshot.

This package is the single source of truth for the *contract values* the curated
MCP tools/services/allowlist consume: API path templates, parameter / vocabulary
enums, and response-model field names. The ``_generated_*`` modules are produced
by ``scripts/gen_contract.py`` + ``datamodel-codegen`` (``make contract``) and must
not be hand-edited.

Public surface:

- :data:`ALL_PATHS` and the named path-template constants from
  :mod:`._generated_paths` (re-exported via ``*``).
- The enum :class:`typing.Literal` aliases and their ``*_VALUES`` tuples from
  :mod:`._generated_enums` (re-exported via ``*``).
- The pydantic response models from :mod:`._generated_models` (imported as
  :data:`models` for namespaced access; key models also re-exported by name).
"""

from __future__ import annotations

from . import _generated_models as models
from ._generated_enums import (
    COMPARISON_VALUES,
    DIABETES_TYPE_VALUES,
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    REPORTING_MODE_VALUES,
    SEX_FILTER_VALUES,
    SORT_BY_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
    Comparison,
    DiabetesType,
    MolecularConsequence,
    ProteinDomain,
    ReportingMode,
    SexFilter,
    SortBy,
    VariantClassification,
    VariantType,
)
from ._generated_models import GeneDetailSchema, ProteinDomainsResponse
from ._generated_paths import ALL_PATHS

__all__ = [
    "ALL_PATHS",
    "models",
    # enum value tuples
    "COMPARISON_VALUES",
    "DIABETES_TYPE_VALUES",
    "MOLECULAR_CONSEQUENCE_VALUES",
    "PROTEIN_DOMAIN_VALUES",
    "REPORTING_MODE_VALUES",
    "SEX_FILTER_VALUES",
    "SORT_BY_VALUES",
    "VARIANT_CLASSIFICATION_VALUES",
    "VARIANT_TYPE_VALUES",
    # enum Literal aliases
    "Comparison",
    "DiabetesType",
    "MolecularConsequence",
    "ProteinDomain",
    "ReportingMode",
    "SexFilter",
    "SortBy",
    "VariantClassification",
    "VariantType",
    # response models
    "GeneDetailSchema",
    "ProteinDomainsResponse",
]
