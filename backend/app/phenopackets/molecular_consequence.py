"""Molecular consequence computation from HGVS notation and VEP annotations.

This module provides functions to derive molecular consequences (Frameshift, Nonsense,
Missense, etc.) from VEP annotations (primary) or HGVS protein and transcript notations
(fallback).
"""

import re
from typing import Optional

# VEP consequence to display name mapping
# Maps Sequence Ontology terms to human-readable labels
VEP_CONSEQUENCE_MAP = {
    # High impact
    "stop_gained": "Nonsense",
    "frameshift_variant": "Frameshift",
    "stop_lost": "Stop Lost",
    "start_lost": "Start Lost",
    "splice_acceptor_variant": "Splice Acceptor",
    "splice_donor_variant": "Splice Donor",
    # Moderate impact
    "missense_variant": "Missense",
    "inframe_deletion": "In-frame Deletion",
    "inframe_insertion": "In-frame Insertion",
    "splice_region_variant": "Splice Region",
    "splice_donor_5th_base_variant": "Splice Donor (5th base)",
    # Low impact
    "synonymous_variant": "Synonymous",
    "intron_variant": "Intronic Variant",
    "5_prime_UTR_variant": "5' UTR Variant",
    "3_prime_UTR_variant": "3' UTR Variant",
    # Structural
    "copy_number_loss": "Copy Number Loss",
    "copy_number_gain": "Copy Number Gain",
}


def extract_vep_consequence(vep_extensions: Optional[list]) -> Optional[str]:
    """Extract VEP most_severe_consequence from phenopacket extensions.

    Args:
        vep_extensions: List of extension objects from variationDescriptor

    Returns:
        Most severe consequence from VEP or None
    """
    if not vep_extensions:
        return None

    for ext in vep_extensions:
        if ext.get("name") == "vep_annotation":
            vep_data = ext.get("value", {})
            vep_consequence = vep_data.get("most_severe_consequence")
            if vep_consequence:
                # Map VEP term to display name
                return VEP_CONSEQUENCE_MAP.get(
                    vep_consequence, vep_consequence.replace("_", " ").title()
                )

    return None


def compute_molecular_consequence(
    transcript: Optional[str],
    protein: Optional[str],
    variant_type: Optional[str] = None,
    vep_extensions: Optional[list] = None,
) -> Optional[str]:
    """Compute molecular consequence from VEP annotations or HGVS notations.

    Uses VEP annotations as primary source (if available), falling back to
    regex-based parsing of HGVS notations.

    Args:
        transcript: HGVS c. notation (e.g., "NM_000458.4:c.1654-2A>T")
        protein: HGVS p. notation (e.g., "NP_000449.3:p.Arg177Ter")
        variant_type: Structural variant type (deletion, duplication, etc.)
        vep_extensions: List of extension objects from variationDescriptor

    Returns:
        Molecular consequence string or None

    Examples:
        >>> compute_molecular_consequence(None, "NP_xxx:p.Arg177Ter", None)
        "Nonsense"
        >>> compute_molecular_consequence(None, "NP_xxx:p.Arg177fs", None)
        "Frameshift"
        >>> compute_molecular_consequence("NM_xxx:c.544+1G>T", None, None)
        "Splice Donor"
        >>> compute_molecular_consequence(None, None, "deletion")
        "Copy Number Loss"
    """
    # Try VEP annotation first (most accurate)
    if vep_extensions:
        vep_consequence = extract_vep_consequence(vep_extensions)
        if vep_consequence:
            return vep_consequence
    # Extract p. notation from full HGVS string first
    # IMPORTANT: Check protein-level consequences BEFORE structural type
    # A small deletion can be a frameshift, not just "Copy Number Loss"
    p_notation = None
    if protein:
        match = re.search(r":?(p\..+)$", protein)
        if match:
            p_notation = match.group(1)
        else:
            p_notation = protein

    # Protein-level consequence determination
    if p_notation:
        p_lower = p_notation.lower()

        # Frameshift (must check BEFORE nonsense, as frameshifts often contain "Ter")
        # Example: p.Gln243SerfsTer22 - contains both "fs" and "Ter"
        if "fs" in p_lower:
            return "Frameshift"

        # Nonsense (stop gained) - only if not a frameshift
        # Example: p.Arg177Ter (stop codon without frameshift)
        if "ter" in p_lower or "*" in p_notation:
            return "Nonsense"

        # Missense (amino acid substitution)
        # Pattern: p.Arg177Cys or p.(Arg177Cys)
        missense_pattern = r"p\.?\(?[A-Z][a-z]{2}\d+[A-Z][a-z]{2}\)?"
        if re.search(missense_pattern, p_notation) and "=" not in p_notation:
            return "Missense"

        # In-frame deletion
        if "del" in p_lower and "fs" not in p_lower:
            return "In-frame Deletion"

        # In-frame insertion
        if "ins" in p_lower and "fs" not in p_lower:
            return "In-frame Insertion"

        # Synonymous (silent)
        if "=" in p_notation:
            return "Synonymous"

    # Extract c. notation from full HGVS string
    c_notation = None
    if transcript:
        match = re.search(r":?(c\..+)$", transcript)
        if match:
            c_notation = match.group(1)
        else:
            c_notation = transcript

    # Transcript-level consequence determination (when protein not available)
    if c_notation:
        # Splice site detection
        # Pattern: c.544+1G>T (donor) or c.1654-2A>T (acceptor)
        splice_match = re.search(r"([+-])(\d+)", c_notation)
        if splice_match:
            sign = splice_match.group(1)
            position = int(splice_match.group(2))

            # Splice donor: +1 to +6 positions
            if sign == "+" and 1 <= position <= 6:
                return "Splice Donor"

            # Splice acceptor: -1 to -3 positions
            if sign == "-" and 1 <= position <= 3:
                return "Splice Acceptor"

            # Other intronic positions
            return "Intronic Variant"

        # If we have c. notation but no splice site, assume coding sequence variant
        if c_notation.startswith("c."):
            return "Coding Sequence Variant"

    # Check variant type last (only for CNVs without protein consequences)
    # This ensures small deletions/insertions with frameshift are not misclassified
    if variant_type:
        if variant_type.lower() in ("deletion", "del"):
            return "Copy Number Loss"
        if variant_type.lower() in ("duplication", "dup"):
            return "Copy Number Gain"

    # Default: unknown consequence
    return None


def filter_by_consequence(variants: list, consequence_filter: Optional[str]) -> list:
    """Filter variants list by molecular consequence.

    Args:
        variants: List of variant dictionaries
        consequence_filter: Consequence to filter by (e.g., "Frameshift")

    Returns:
        Filtered list of variants

    Note:
        This is used for post-query filtering since molecular consequence
        is computed from HGVS notations, not stored in database.
    """
    if not consequence_filter:
        return variants

    filtered = []
    for variant in variants:
        computed_consequence = compute_molecular_consequence(
            transcript=variant.get("transcript"),
            protein=variant.get("protein"),
            variant_type=variant.get("structural_type"),
        )
        if computed_consequence == consequence_filter:
            filtered.append(variant)

    return filtered
