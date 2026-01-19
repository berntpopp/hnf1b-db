"""Domain constants for the HNF1B database.

This module contains hardcoded values that are domain-specific and do not
change based on environment. For environment-dependent configuration,
see app/core/config.py.

Usage:
    from app.constants import STRUCTURE_START, STRUCTURE_END
    from app.constants import DOMAIN_BOUNDARIES

Naming Convention:
    SCREAMING_SNAKE_CASE for all constants (PEP 8).

Categories:
    - PDB 2H8R Structure Boundaries
    - HNF1B Gene Boundaries (GRCh38)
    - 17q12 Region Boundaries
    - Variant Classification Thresholds
    - Domain Boundaries (UniProt P35680)
    - Caching Constants
"""

from typing import Dict, TypedDict

# =============================================================================
# Type Definitions
# =============================================================================


class DomainBoundary(TypedDict):
    """Type definition for protein domain boundaries."""

    start: int
    end: int


# =============================================================================
# PDB 2H8R Structure Boundaries
# =============================================================================
# PDB 2H8R maps to UniProt P35680 residues 90-308
# Reference: https://www.rcsb.org/structure/2H8R

STRUCTURE_START: int = 90
"""First residue visible in PDB 2H8R structure (UniProt position)."""

STRUCTURE_END: int = 308
"""Last residue visible in PDB 2H8R structure (UniProt position)."""

STRUCTURE_GAP_START: int = 187
"""Start of gap in structure (linker region not resolved in crystal)."""

STRUCTURE_GAP_END: int = 230
"""End of gap in structure (linker region not resolved in crystal)."""


# =============================================================================
# HNF1B Gene Boundaries (GRCh38)
# =============================================================================
# Reference: NCBI Gene ID 6928, https://www.ncbi.nlm.nih.gov/gene/6928

HNF1B_GENE_START: int = 37686430
"""HNF1B gene start position on GRCh38 chromosome 17."""

HNF1B_GENE_END: int = 37745059
"""HNF1B gene end position on GRCh38 chromosome 17."""

HNF1B_CHROMOSOME: str = "17"
"""Chromosome where HNF1B gene is located."""


# =============================================================================
# 17q12 Region Boundaries
# =============================================================================
# The 17q12 microdeletion/microduplication syndrome region
# Reference: OMIM 614527

CHR17Q12_REGION_START: int = 36000000
"""Start of the 17q12 region (GRCh38) for Ensembl API queries."""

CHR17Q12_REGION_END: int = 39900000
"""End of the 17q12 region (GRCh38) for Ensembl API queries."""


# =============================================================================
# Variant Classification Thresholds
# =============================================================================

CNV_SIZE_THRESHOLD: int = 50
"""Size threshold (base pairs) for CNV vs indel classification.

Variants >= this size are classified as CNVs (copy number variants)
rather than small insertions/deletions (indels).
"""

VARIANT_RECODER_BATCH_SIZE: int = 200
"""Maximum batch size for Ensembl Variant Recoder API requests.

The VEP/Variant Recoder API recommends max 200 variants per request
for reliable performance.
"""


# =============================================================================
# Domain Boundaries (UniProt P35680)
# =============================================================================
# HNF1B protein domains from UniProt entry P35680
# Reference: https://www.uniprot.org/uniprotkb/P35680/entry

DOMAIN_BOUNDARIES: Dict[str, DomainBoundary] = {
    "dimerization": {"start": 1, "end": 31},
    "pou_specific": {"start": 88, "end": 173},
    "pou_homeodomain": {"start": 232, "end": 305},
    "transactivation": {"start": 314, "end": 557},
}
"""HNF1B protein domain boundaries in amino acid positions.

Keys match the domain type identifiers used in analysis.
Values are dictionaries with 'start' and 'end' positions.
"""

# Domain boundaries with display names (for UI/API responses)
DOMAIN_BOUNDARIES_DISPLAY: Dict[str, tuple[int, int]] = {
    "Dimerization Domain": (1, 31),
    "POU-Specific Domain": (8, 173),
    "POU Homeodomain": (232, 305),
    "Transactivation Domain": (314, 557),
}
"""HNF1B protein domain boundaries with display names.

Keys are human-readable domain names for UI display.
Values are (start, end) tuples of amino acid positions.

Note: The POU-Specific Domain start differs between sources:
- UniProt P35680 lists 88-173
- RESEARCH.md/UI uses 8-173
Using 8-173 here for consistency with existing UI.
"""


# =============================================================================
# Caching Constants
# =============================================================================

CACHE_MAX_AGE_SECONDS: int = 86400
"""Default HTTP cache max-age for reference data (24 hours).

Used for Cache-Control headers on relatively static endpoints
like reference genome data, gene information, and domains.
"""
