"""Aggregation SQL fragments sub-package.

Split from the old 748-LOC flat ``sql_fragments.py`` during Wave 4.
The public import path is unchanged::

    from app.phenopackets.routers.aggregations.sql_fragments import (
        VARIANT_TYPE_CLASSIFICATION_SQL,
        UNIQUE_VARIANTS_CTE,
        get_unique_variants_query,
        HNF1B_PROTEIN_DOMAINS,
        # ... etc.
    )

Submodules:

- ``paths``          — JSONB path constants (``VD_ID``, ``VD_EXTENSIONS``, ...)
- ``classification`` — variant-type classification CASE expressions
- ``ctes``           — common table expressions (``UNIQUE_VARIANTS_CTE``, ...)
- ``protein_domain`` — HNF1B protein-domain classification helpers
"""

from .classification import (
    STRUCTURAL_TYPE_CASE,
    VALID_STRUCTURAL_TYPES,
    VARIANT_TYPE_CASE,
    VARIANT_TYPE_CLASSIFICATION_SQL,
    get_structural_type_filter,
    get_variant_type_classification_sql,
)
from .ctes import (
    INTERNAL_CNV_PATTERN,
    INTERNAL_CNV_VARIANTS_CTE,
    PHENOPACKET_VARIANT_LINK_CTE,
    UNIQUE_VARIANTS_CTE,
    VCF_VARIANT_PATTERNS,
    VCF_VARIANTS_CTE,
    get_pending_variants_count_query,
    get_pending_variants_query,
    get_phenopacket_variant_link_cte,
    get_unique_variants_query,
    get_variant_sync_status_query,
)
from .paths import (
    CURRENT_AGE_PATH,
    INTERP_STATUS_PATH,
    VD_BASE,
    VD_EXPRESSIONS,
    VD_EXTENSIONS,
    VD_ID,
)
from .protein_domain import (
    AMINO_ACID_POSITION_PATTERN,
    HNF1B_PROTEIN_DOMAINS,
    MISSENSE_HGVS_P_PATTERN,
    get_amino_acid_position_sql,
    get_cnv_exclusion_filter,
    get_missense_filter_sql,
    get_protein_domain_classification_sql,
    get_vcf_id_extraction_sql,
)

__all__ = [
    # Paths
    "VD_BASE",
    "VD_ID",
    "VD_EXTENSIONS",
    "VD_EXPRESSIONS",
    "CURRENT_AGE_PATH",
    "INTERP_STATUS_PATH",
    # Classification
    "VARIANT_TYPE_CLASSIFICATION_SQL",
    "VARIANT_TYPE_CASE",
    "STRUCTURAL_TYPE_CASE",
    "VALID_STRUCTURAL_TYPES",
    "get_structural_type_filter",
    "get_variant_type_classification_sql",
    # CTEs
    "PHENOPACKET_VARIANT_LINK_CTE",
    "get_phenopacket_variant_link_cte",
    "VCF_VARIANT_PATTERNS",
    "INTERNAL_CNV_PATTERN",
    "VCF_VARIANTS_CTE",
    "INTERNAL_CNV_VARIANTS_CTE",
    "UNIQUE_VARIANTS_CTE",
    "get_unique_variants_query",
    "get_pending_variants_query",
    "get_pending_variants_count_query",
    "get_variant_sync_status_query",
    # Protein domain
    "HNF1B_PROTEIN_DOMAINS",
    "MISSENSE_HGVS_P_PATTERN",
    "AMINO_ACID_POSITION_PATTERN",
    "get_missense_filter_sql",
    "get_amino_acid_position_sql",
    "get_protein_domain_classification_sql",
    "get_cnv_exclusion_filter",
    "get_vcf_id_extraction_sql",
]
