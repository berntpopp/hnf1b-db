"""Input validation for variant search endpoint.

This module provides validation functions for variant search parameters to prevent
SQL injection, validate HGVS formats, and ensure secure query handling.

Security Features:
- Character whitelist enforcement
- HGVS notation format validation
- Length limits (DoS prevention)
- Enum validation for controlled vocabularies
"""

import re
from typing import Optional

from fastapi import HTTPException

# HGVS validation patterns
HGVS_PATTERNS = {
    # c. notation: c.1654-2A>T, c.544+1G>T, c.1621C>T, c.1654_1656del
    "c": re.compile(
        r"^c\."
        r"([\d]+([+-]\d+)?"  # Position (with optional intron offset)
        r"(_[\d]+([+-]\d+)?)?"  # Optional range end
        r"([ACGT]+>[ACGT]+|del|dup|ins[ACGT]*|delins[ACGT]*))$",  # Variation
        re.IGNORECASE
    ),
    # p. notation: p.Arg177Ter, p.(Ser546Phe), p.Gly319del
    "p": re.compile(
        r"^p\."
        r"(\()?([A-Z][a-z]{2}\d+([A-Z][a-z]{2}|Ter|\*|del|dup|ins|fs))+(\))?$"
    ),
    # g. notation: g.36098063A>T, g.36459258_37832869del
    "g": re.compile(
        r"^g\."
        r"(\d+(_\d+)?"  # Position or range
        r"([ACGT]+>[ACGT]+|del|dup|ins[ACGT]*|delins[ACGT]*))$",
        re.IGNORECASE
    ),
}

# HG38 coordinate formats: chr17:36098063, chr17-36098063-A-T, 17:36459258-37832869:DEL
HG38_PATTERN = re.compile(
    r"^(chr)?(\d+|X|Y|MT?)([:-])(\d+)([-:](\d+))?([:-]([A-Z]+(-[A-Z]+)?))?$",
    re.IGNORECASE
)

# Allowed values for controlled vocabularies
ALLOWED_VARIANT_TYPES = {
    "SNV", "deletion", "duplication", "insertion", "indel", "inversion", "CNV"
}
ALLOWED_CLASSIFICATIONS = {
    "PATHOGENIC",
    "LIKELY_PATHOGENIC",
    "UNCERTAIN_SIGNIFICANCE",
    "LIKELY_BENIGN",
    "BENIGN",
}
ALLOWED_GENES = {"HNF1B"}  # Expand as database grows

# Molecular consequence types (computed from HGVS notation)
# Note: CNV-related consequences (Copy Number Loss/Gain) are covered by variant type filters
ALLOWED_CONSEQUENCES = {
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
}


def validate_hgvs_notation(query: str) -> bool:
    """Validate HGVS notation format.

    Args:
        query: User-provided HGVS string (e.g., "c.1654-2A>T")

    Returns:
        True if valid HGVS format, False otherwise

    Note:
        For production, consider using the `hgvs` library for comprehensive validation:
            from hgvs.parser import Parser
            parser = Parser()
            try:
                parser.parse(query)
                return True
            except Exception:
                return False
    """
    for pattern in HGVS_PATTERNS.values():
        if pattern.match(query):
            return True
    return False


def validate_hg38_coordinate(query: str) -> bool:
    """Validate HG38 genomic coordinate format.

    Args:
        query: Genomic coordinate string

    Returns:
        True if valid format, False otherwise

    Examples:
        chr17:36098063         -> True
        chr17-36098063-A-T     -> True
        17:36459258-37832869   -> True (CNV range)
        17:36459258-37832869:DEL -> True (CNV with type)
        invalid:format         -> False
    """
    return bool(HG38_PATTERN.match(query))


def validate_search_query(query: Optional[str]) -> Optional[str]:
    """Validate and sanitize search query input.

    Args:
        query: User-provided search string (HGVS, variant ID, or coordinates)

    Returns:
        Sanitized query string or None

    Raises:
        HTTPException: If query contains invalid characters or is too long

    Security:
        - Enforces length limit (prevents DoS)
        - Character whitelist (prevents SQL injection)
        - Format validation for HGVS and coordinates
    """
    if not query:
        return None

    # Length validation (prevent DoS)
    if len(query) > 200:
        raise HTTPException(
            status_code=400,
            detail="Search query too long (max 200 characters)"
        )

    # Character whitelist: alphanumeric + HGVS/VCF symbols
    # Allowed: A-Z a-z 0-9 . _ : > ( ) + - * /
    if not re.match(r"^[A-Za-z0-9._:>()+=*\-/\s]+$", query):
        raise HTTPException(
            status_code=400,
            detail=(
                "Search query contains invalid characters. "
                "Allowed: A-Z a-z 0-9 . _ : > ( ) + - = * /"
            )
        )

    # Optional: Validate HGVS format if it looks like HGVS
    query_stripped = query.strip()
    if query_stripped.startswith(("c.", "p.", "g.")):
        if not validate_hgvs_notation(query_stripped):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid HGVS notation format: {query_stripped}"
            )

    # Optional: Validate HG38 coordinates if they look like coordinates
    if re.match(r"^(chr)?\d+[:-]", query_stripped):
        if not validate_hg38_coordinate(query_stripped):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid HG38 coordinate format: {query_stripped}"
            )

    return query_stripped


def validate_variant_type(variant_type: Optional[str]) -> Optional[str]:
    """Validate variant type filter.

    Args:
        variant_type: Variant type (e.g., "SNV", "deletion")

    Returns:
        Validated variant type or None

    Raises:
        HTTPException: If variant type is not in allowed list
    """
    if not variant_type:
        return None

    if variant_type not in ALLOWED_VARIANT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid variant type: {variant_type}. "
                f"Allowed: {', '.join(sorted(ALLOWED_VARIANT_TYPES))}"
            )
        )

    return variant_type


def validate_classification(classification: Optional[str]) -> Optional[str]:
    """Validate ACMG pathogenicity classification filter.

    Args:
        classification: ACMG classification (e.g., "PATHOGENIC")

    Returns:
        Validated classification or None

    Raises:
        HTTPException: If classification is not in allowed list
    """
    if not classification:
        return None

    if classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid classification: {classification}. "
                f"Allowed: {', '.join(sorted(ALLOWED_CLASSIFICATIONS))}"
            )
        )

    return classification


def validate_gene(gene: Optional[str]) -> Optional[str]:
    """Validate gene symbol filter.

    Args:
        gene: Gene symbol (e.g., "HNF1B")

    Returns:
        Validated gene symbol or None

    Raises:
        HTTPException: If gene is not in allowed list
    """
    if not gene:
        return None

    if gene not in ALLOWED_GENES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid gene symbol: {gene}. "
                f"Allowed: {', '.join(sorted(ALLOWED_GENES))}"
            )
        )

    return gene


def validate_molecular_consequence(consequence: Optional[str]) -> Optional[str]:
    """Validate molecular consequence filter.

    Args:
        consequence: Molecular consequence (e.g., "Frameshift", "Nonsense")

    Returns:
        Validated consequence or None

    Raises:
        HTTPException: If consequence is not in allowed list
    """
    if not consequence:
        return None

    if consequence not in ALLOWED_CONSEQUENCES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid molecular consequence: {consequence}. "
                f"Allowed: {', '.join(sorted(ALLOWED_CONSEQUENCES))}"
            )
        )

    return consequence
