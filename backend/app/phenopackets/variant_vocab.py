"""Controlled vocabularies for variant search and aggregation.

This module is the single source of truth for the variant-related controlled
vocabularies exposed by the HNF1B-db API. Each vocabulary is modeled as a
``str, Enum`` so that the same definition serves three purposes:

1. **Validation** — FastAPI rejects values outside the enum with a 422.
2. **Documentation** — FastAPI emits the enum members into the OpenAPI schema,
   eliminating discrepancies between the code and the published contract.
3. **Internal derivation** — modules such as ``variant_search_validation`` derive
   their ``frozenset`` allow-lists from these enums, so a value only ever needs
   to be added in one place.

Because each class inherits from ``str``, every member compares equal to its
string value (e.g. ``VariantClassification.PATHOGENIC == "PATHOGENIC"``), so
membership checks and SQL parameter binding keep working with plain strings.
"""

from enum import Enum

__all__ = [
    "VariantClassification",
    "MolecularConsequence",
    "VariantType",
    "ProteinDomain",
]


class VariantClassification(str, Enum):
    """ACMG/AMP pathogenicity classification of a variant.

    Member values match the classifications stored on phenopacket
    interpretations and exposed through the variant search filters.
    """

    PATHOGENIC = "PATHOGENIC"
    LIKELY_PATHOGENIC = "LIKELY_PATHOGENIC"
    UNCERTAIN_SIGNIFICANCE = "UNCERTAIN_SIGNIFICANCE"
    LIKELY_BENIGN = "LIKELY_BENIGN"
    BENIGN = "BENIGN"


class MolecularConsequence(str, Enum):
    """Molecular consequence of a variant, computed from HGVS notation.

    CNV-related consequences (copy-number loss/gain) are intentionally omitted
    because they are covered by the :class:`VariantType` filter instead.
    """

    FRAMESHIFT = "Frameshift"
    NONSENSE = "Nonsense"
    MISSENSE = "Missense"
    SPLICE_DONOR = "Splice Donor"
    SPLICE_ACCEPTOR = "Splice Acceptor"
    IN_FRAME_DELETION = "In-frame Deletion"
    IN_FRAME_INSERTION = "In-frame Insertion"
    SYNONYMOUS = "Synonymous"
    INTRONIC_VARIANT = "Intronic Variant"
    CODING_SEQUENCE_VARIANT = "Coding Sequence Variant"


class VariantType(str, Enum):
    """Structural type of a variant.

    Mirrors the GA4GH/VRS-style structural type values stored on variation
    descriptors in the phenopacket data.
    """

    SNV = "SNV"
    DELETION = "deletion"
    DUPLICATION = "duplication"
    INSERTION = "insertion"
    INDEL = "indel"
    INVERSION = "inversion"
    CNV = "CNV"


class ProteinDomain(str, Enum):
    """HNF1B protein domains (UniProt P35680) used for domain-based filtering.

    Each member corresponds to an amino-acid range; the canonical ranges live in
    ``DOMAIN_BOUNDARIES`` in the all-variants aggregation router, keyed by these
    member values.
    """

    DIMERIZATION = "Dimerization Domain"
    POU_SPECIFIC = "POU-Specific Domain"
    POU_HOMEODOMAIN = "POU Homeodomain"
    TRANSACTIVATION = "Transactivation Domain"
