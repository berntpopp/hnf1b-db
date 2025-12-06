# app/core/__init__.py
"""Core module for configuration, caching, and common utilities."""

from app.core.cache import cache, close_cache, init_cache
from app.core.config import get_settings, settings
from app.core.patterns import (
    CNV_PATTERN,
    HG38_PATTERN,
    HGVS_C_PATTERNS,
    HGVS_C_SEARCH_PATTERN,
    HGVS_G_PATTERN,
    HGVS_G_SEARCH_PATTERN,
    HGVS_P_PATTERN,
    HPO_PATTERN,
    LOINC_PATTERN,
    MONDO_PATTERN,
    PMID_PATTERN,
    SEARCH_WHITELIST_PATTERN,
    SPDI_PATTERN,
    VCF_PATTERN,
    VCF_SIMPLE_PATTERN,
    is_cnv_format,
    is_hg38_coordinate,
    is_hgvs_c,
    is_hgvs_g,
    is_hgvs_p,
    is_safe_search_query,
    is_valid_pmid,
    is_vcf_format,
)

__all__ = [
    # Cache
    "cache",
    "init_cache",
    "close_cache",
    # Config
    "settings",
    "get_settings",
    # Patterns
    "VCF_PATTERN",
    "VCF_SIMPLE_PATTERN",
    "CNV_PATTERN",
    "HGVS_C_PATTERNS",
    "HGVS_C_SEARCH_PATTERN",
    "HGVS_P_PATTERN",
    "HGVS_G_PATTERN",
    "HGVS_G_SEARCH_PATTERN",
    "HG38_PATTERN",
    "PMID_PATTERN",
    "SPDI_PATTERN",
    "HPO_PATTERN",
    "MONDO_PATTERN",
    "LOINC_PATTERN",
    "SEARCH_WHITELIST_PATTERN",
    # Validation functions
    "is_vcf_format",
    "is_cnv_format",
    "is_hgvs_c",
    "is_hgvs_p",
    "is_hgvs_g",
    "is_hg38_coordinate",
    "is_valid_pmid",
    "is_safe_search_query",
]
