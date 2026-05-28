"""Data-class taxonomy tags attached to every payload."""
from __future__ import annotations


class DataClass:
    """Provenance/trust class for returned data."""

    CURATED = "curated_hnf1b_evidence"
    DERIVED = "curated_derived_analysis"
    EXTERNAL_REF = "external_reference_identifier"
    OPERATIONAL = "operational_metadata"
