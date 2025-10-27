"""Molecular consequence computation from HGVS notation.

This module provides functions to derive molecular consequences (Frameshift, Nonsense,
Missense, etc.) from HGVS protein and transcript notations.
"""

import re
from typing import Optional


def compute_molecular_consequence(
    transcript: Optional[str],
    protein: Optional[str],
    variant_type: Optional[str] = None
) -> Optional[str]:
    """Compute molecular consequence from HGVS notations and variant type.

    Args:
        transcript: HGVS c. notation (e.g., "NM_000458.4:c.1654-2A>T")
        protein: HGVS p. notation (e.g., "NP_000449.3:p.Arg177Ter")
        variant_type: Structural variant type (deletion, duplication, etc.)

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
    # Check variant type first (CNVs)
    if variant_type:
        if variant_type.lower() in ("deletion", "del"):
            return "Copy Number Loss"
        if variant_type.lower() in ("duplication", "dup"):
            return "Copy Number Gain"

    # Extract p. notation from full HGVS string
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

        # Frameshift
        if "fs" in p_lower:
            return "Frameshift"

        # Nonsense (stop gained)
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
        c_lower = c_notation.lower()

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

    # Default: unknown consequence
    return None


def filter_by_consequence(
    variants: list,
    consequence_filter: Optional[str]
) -> list:
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
            variant_type=variant.get("structural_type")
        )
        if computed_consequence == consequence_filter:
            filtered.append(variant)

    return filtered
