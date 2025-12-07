# app/core/patterns.py
"""Centralized regex patterns for variant and identifier validation.

All patterns are pre-compiled for performance.
Import from here instead of defining inline patterns.

Usage:
    from app.core.patterns import VCF_PATTERN, is_vcf_format

    # Use pre-compiled pattern directly
    if VCF_PATTERN.match(variant):
        ...

    # Or use convenience function
    if is_vcf_format(variant):
        ...
"""

import re
from typing import List, Pattern

# =============================================================================
# VCF Format Patterns
# =============================================================================

# Comprehensive VCF: chr17-36459258-A-G or 17-36459258-A-G
# Supports chromosomes 1-22, X, Y, M and structural variant symbols
VCF_PATTERN: Pattern[str] = re.compile(
    r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-[ATCG]+-([ATCG]+|<[A-Z]+>)$",
    re.IGNORECASE,
)

# Simple VCF check (for quick validation)
VCF_SIMPLE_PATTERN: Pattern[str] = re.compile(
    r"^(chr)?[\dXYM]+-\d+-[ACGT]+-[ACGT]+$",
    re.IGNORECASE,
)


# =============================================================================
# CNV/Structural Variant Patterns
# =============================================================================

# GA4GH CNV notation: 17:36459258-37832869:DEL
CNV_PATTERN: Pattern[str] = re.compile(
    r"^([1-9]|1[0-9]|2[0-2]|X|Y):\d+-\d+:(DEL|DUP|INS|INV)$",
)


# =============================================================================
# HGVS Patterns
# =============================================================================

# HGVS c. notation patterns (ordered by specificity)
HGVS_C_PATTERNS: List[Pattern[str]] = [
    # With transcript: NM_000458.4:c.544+1G>A (substitution)
    re.compile(r"^(NM_\d+\.\d+:)?c\.([+\-*]?\d+[+\-]?\d*)([ATCG]>[ATCG])$"),
    # Deletion: c.123del or c.123_456del
    re.compile(r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?del([ATCG]+)?$"),
    # Duplication: c.123dup or c.123_456dup
    re.compile(r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?dup([ATCG]+)?$"),
    # Insertion: c.123_124insATG
    re.compile(r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?ins([ATCG]+)$"),
    # Intronic: c.544+1G>A
    re.compile(r"^(NM_\d+\.\d+:)?c\.\d+[+\-]\d+[ATCG]>[ATCG]$"),
    # Delins: c.123delinsAT
    re.compile(r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?delins[ATCG]+$", re.IGNORECASE),
]

# Comprehensive c. pattern for search validation
HGVS_C_SEARCH_PATTERN: Pattern[str] = re.compile(
    r"^c\."
    r"([\d]+([+-]\d+)?"
    r"(_[\d]+([+-]\d+)?)?"
    r"([ACGT]+>[ACGT]+|del|dup|ins[ACGT]*|delins[ACGT]*))$",
    re.IGNORECASE,
)

# HGVS p. notation: p.Arg181*, p.Val123Phe, p.(Ser546Phe)
HGVS_P_PATTERN: Pattern[str] = re.compile(
    r"^(NP_\d+\.\d+:)?p\.(\()?([A-Z][a-z]{2}\d+([A-Z][a-z]{2}|Ter|\*|del|dup|ins|fs))+(\))?$"
)

# HGVS p. search pattern (more permissive)
HGVS_P_SEARCH_PATTERN: Pattern[str] = re.compile(
    r"^p\."
    r"(\()?([A-Z][a-z]{2}\d+([A-Z][a-z]{2}|Ter|\*|del|dup|ins|fs))+(\))?$"
)

# HGVS g. notation: NC_000017.11:g.36459258A>G
HGVS_G_PATTERN: Pattern[str] = re.compile(r"^NC_\d+\.\d+:g\.\d+[ATCG]>[ATCG]$")

# Comprehensive g. pattern for search
HGVS_G_SEARCH_PATTERN: Pattern[str] = re.compile(
    r"^g\."
    r"(\d+(_\d+)?"
    r"([ACGT]+>[ACGT]+|del|dup|ins[ACGT]*|delins[ACGT]*))$",
    re.IGNORECASE,
)


# =============================================================================
# HG38 Coordinate Patterns
# =============================================================================

# Genomic coordinates: chr17:36098063, 17:36459258-37832869:DEL
HG38_PATTERN: Pattern[str] = re.compile(
    r"^(chr)?(\d+|X|Y|MT?)([:-])(\d+)([-:](\d+))?([:-]([A-Z]+(-[A-Z]+)?))?$",
    re.IGNORECASE,
)

# Simple coordinate check for quick validation
HG38_SIMPLE_PATTERN: Pattern[str] = re.compile(r"^(chr)?\d+[:-]")


# =============================================================================
# Identifier Patterns
# =============================================================================

# PMID: PMID:12345678
PMID_PATTERN: Pattern[str] = re.compile(r"^PMID:\d{1,8}$")

# SPDI: NC_000017.11:36459257:A:G
SPDI_PATTERN: Pattern[str] = re.compile(r"^NC_\d+\.\d+:\d+:[ATCG]*:[ATCG]+$")


# =============================================================================
# Ontology Patterns
# =============================================================================

HPO_PATTERN: Pattern[str] = re.compile(r"^HP:\d{7}$")
MONDO_PATTERN: Pattern[str] = re.compile(r"^MONDO:\d{7}$")
LOINC_PATTERN: Pattern[str] = re.compile(r"^\d{1,8}-\d$")


# =============================================================================
# Security Patterns
# =============================================================================

# Character whitelist for search queries (SQL injection prevention)
# Allowed: A-Z a-z 0-9 . _ : > ( ) + - = * /
SEARCH_WHITELIST_PATTERN: Pattern[str] = re.compile(r"^[A-Za-z0-9._:>()+=*\-/\s]+$")


# =============================================================================
# Validation Functions
# =============================================================================


def is_vcf_format(value: str) -> bool:
    """Check if value is VCF format.

    Args:
        value: String to validate

    Returns:
        True if valid VCF format (e.g., "17-36459258-A-G")

    Examples:
        >>> is_vcf_format("17-36459258-A-G")
        True
        >>> is_vcf_format("chr17-36459258-A-G")
        True
        >>> is_vcf_format("invalid")
        False
    """
    return bool(VCF_PATTERN.match(value))


def is_cnv_format(value: str) -> bool:
    """Check if value is CNV/structural variant notation.

    Args:
        value: String to validate

    Returns:
        True if valid CNV format (e.g., "17:36459258-37832869:DEL")

    Examples:
        >>> is_cnv_format("17:36459258-37832869:DEL")
        True
        >>> is_cnv_format("X:1000-2000:DUP")
        True
    """
    return bool(CNV_PATTERN.match(value))


def is_hgvs_c(value: str) -> bool:
    """Check if value is valid HGVS c. notation.

    Args:
        value: String to validate

    Returns:
        True if valid HGVS c. notation

    Examples:
        >>> is_hgvs_c("c.544+1G>A")
        True
        >>> is_hgvs_c("NM_000458.4:c.544+1G>A")
        True
        >>> is_hgvs_c("c.123del")
        True
    """
    return any(p.match(value) for p in HGVS_C_PATTERNS)


def is_hgvs_p(value: str) -> bool:
    """Check if value is valid HGVS p. notation.

    Args:
        value: String to validate

    Returns:
        True if valid HGVS p. notation

    Examples:
        >>> is_hgvs_p("p.Arg181Ter")
        True
        >>> is_hgvs_p("p.(Ser546Phe)")
        True
    """
    return bool(HGVS_P_PATTERN.match(value))


def is_hgvs_g(value: str) -> bool:
    """Check if value is valid HGVS g. notation.

    Args:
        value: String to validate

    Returns:
        True if valid HGVS g. notation

    Examples:
        >>> is_hgvs_g("NC_000017.11:g.36459258A>G")
        True
    """
    return bool(HGVS_G_PATTERN.match(value))


def is_hg38_coordinate(value: str) -> bool:
    """Check if value is valid HG38 genomic coordinate.

    Args:
        value: String to validate

    Returns:
        True if valid HG38 coordinate

    Examples:
        >>> is_hg38_coordinate("chr17:36098063")
        True
        >>> is_hg38_coordinate("17:36459258-37832869")
        True
    """
    return bool(HG38_PATTERN.match(value))


def is_valid_pmid(value: str) -> bool:
    """Check if value is valid PMID format.

    Args:
        value: String to validate (with or without PMID: prefix)

    Returns:
        True if valid PMID format

    Examples:
        >>> is_valid_pmid("PMID:12345678")
        True
        >>> is_valid_pmid("PMID:123")
        True
        >>> is_valid_pmid("12345678")  # Missing prefix
        False
    """
    return bool(PMID_PATTERN.match(value))


def is_safe_search_query(value: str) -> bool:
    """Check if search query contains only safe characters.

    This is used to prevent SQL injection by ensuring only
    whitelisted characters are present in user input.

    Args:
        value: Search query string

    Returns:
        True if query contains only safe characters

    Examples:
        >>> is_safe_search_query("c.544+1G>A")
        True
        >>> is_safe_search_query("test; DROP TABLE")
        False
    """
    return bool(SEARCH_WHITELIST_PATTERN.match(value))


def normalize_pmid(pmid: str) -> str:
    """Normalize PMID to standard format.

    Args:
        pmid: PMID string (with or without prefix)

    Returns:
        Normalized PMID in format "PMID:12345678"

    Raises:
        ValueError: If PMID format is invalid

    Examples:
        >>> normalize_pmid("12345678")
        'PMID:12345678'
        >>> normalize_pmid("PMID:12345678")
        'PMID:12345678'
    """
    # Add prefix if missing
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format
    if not PMID_PATTERN.match(pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")

    return pmid
