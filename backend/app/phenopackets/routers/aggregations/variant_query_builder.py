"""Variant query builder for constructing filtered SQL queries.

This module provides a builder pattern for constructing variant aggregation
queries with various filters, eliminating code duplication and improving
maintainability.

Usage:
    builder = VariantQueryBuilder()
    builder.with_text_search("HNF1B")
    builder.with_variant_type("missense")
    builder.with_gene_filter("HNF1B")
    sql, params = builder.build()
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .sql_fragments import STRUCTURAL_TYPE_CASE


@dataclass
class VariantQueryBuilder:
    """Builder for constructing variant aggregation SQL queries.

    Provides a fluent interface for adding filters and constructing
    the final query with parameters.

    Attributes:
        _where_clauses: List of WHERE clause conditions
        _params: Dictionary of query parameters
        _validated_query: Text search query (if any)
    """

    _where_clauses: List[str] = field(default_factory=list)
    _params: Dict[str, Any] = field(default_factory=dict)
    _validated_query: Optional[str] = None

    # SQL clause templates for variant type filtering
    _VARIANT_TYPE_CLAUSES = {
        "CNV": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'value' ~ ':\\d+-\\d+:'
        )""",
        "indel": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'del|ins|delins'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "deletion": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'del'
                AND NOT (elem->>'value' ~ 'delins')
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "insertion": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ 'ins'
            AND NOT (elem->>'value' ~ 'delins')
        )""",
        "missense": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~ '^p\\.[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}$'
        )""",
        "nonsense": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~ 'Ter$|\\*$'
        )""",
        "frameshift": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~ 'fs'
        )""",
        "splicing": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ '[+-]\\d+[ACGT]>[ACGT]'
        )""",
        "start_lost": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~ '^p\\.Met1'
        )""",
        "regulatory": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ '^c\\.-\\d+'
        )""",
    }

    # SQL clause templates for pathogenicity classification
    _CLASSIFICATION_CLAUSES = {
        "pathogenic": """(
            COALESCE(vi->>'acmgPathogenicityClassification', '') = 'PATHOGENIC'
            OR gi->>'interpretationStatus' = 'CAUSATIVE'
        )""",
        "likely_pathogenic": """(
            COALESCE(vi->>'acmgPathogenicityClassification', '') = 'LIKELY_PATHOGENIC'
            OR gi->>'interpretationStatus' = 'CONTRIBUTORY'
        )""",
        "vus": """(
            COALESCE(vi->>'acmgPathogenicityClassification', '') =
                'UNCERTAIN_SIGNIFICANCE'
            OR (
                gi->>'interpretationStatus' NOT IN ('CAUSATIVE', 'CONTRIBUTORY')
                AND COALESCE(vi->>'acmgPathogenicityClassification', '') = ''
            )
        )""",
    }

    # Molecular consequence SQL templates
    _CONSEQUENCE_CLAUSES = {
        "lof": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                AND (elem->>'value' ~ 'Ter$|\\*$' OR elem->>'value' ~ 'fs')
            )
            OR EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'extensions') ext,
                     jsonb_array_elements(ext->'value') impact_val
                WHERE ext->>'name' = 'vep_impact'
                AND impact_val->>'value' = 'HIGH'
            )
            OR EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "missense": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                AND elem->>'value' ~ '^p\\.[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}$'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                AND (elem->>'value' ~ 'Ter$|\\*$' OR elem->>'value' ~ 'fs')
            )
        )""",
        "splicing": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ '[+-]\\d+[ACGT]>[ACGT]'
        )""",
        "inframe": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'del|ins|delins'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                AND elem->>'value' ~ 'fs'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "other": """(
            NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                AND (
                    elem->>'value' ~ 'Ter$|\\*$'
                    OR elem->>'value' ~ 'fs'
                    OR elem->>'value' ~ '^p\\.[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}$'
                )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ '[+-]\\d+[ACGT]>[ACGT]'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
    }

    def with_text_search(self, query: str) -> "VariantQueryBuilder":
        """Add text search filter.

        Args:
            query: The search query string

        Returns:
            Self for method chaining
        """
        self._validated_query = query
        search_clause = """(
            vd->>'id' ILIKE :query
            OR vd->>'label' ILIKE :query
            OR vd->>'description' ILIKE :query
            OR EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') AS expr
                WHERE expr->>'value' ILIKE :query
            )
            OR COALESCE(
                NULLIF(CONCAT(
                    COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'alt', '')
                ), ':::'),
                ''
            ) ILIKE :query
        )"""
        self._where_clauses.append(search_clause)
        self._params["query"] = f"%{query}%"

        # Add simple_id query param for VarXXX searches
        if query.lower().startswith("var"):
            self._params["simple_id_query"] = f"%{query}%"

        return self

    def with_variant_type(self, variant_type: str) -> "VariantQueryBuilder":
        """Add variant type filter.

        Args:
            variant_type: The variant type to filter by

        Returns:
            Self for method chaining
        """
        if variant_type in self._VARIANT_TYPE_CLAUSES:
            self._where_clauses.append(self._VARIANT_TYPE_CLAUSES[variant_type])
        return self

    def with_classification(self, classification: str) -> "VariantQueryBuilder":
        """Add pathogenicity classification filter.

        Args:
            classification: The classification to filter by

        Returns:
            Self for method chaining
        """
        if classification in self._CLASSIFICATION_CLAUSES:
            self._where_clauses.append(self._CLASSIFICATION_CLAUSES[classification])
        return self

    def with_gene_filter(self, gene: str) -> "VariantQueryBuilder":
        """Add gene symbol filter.

        Args:
            gene: The gene symbol to filter by

        Returns:
            Self for method chaining
        """
        self._where_clauses.append("vd->'geneContext'->>'symbol' = :gene")
        self._params["gene"] = gene
        return self

    def with_consequence(self, consequence: str) -> "VariantQueryBuilder":
        """Add molecular consequence filter.

        Args:
            consequence: The molecular consequence to filter by

        Returns:
            Self for method chaining
        """
        if consequence in self._CONSEQUENCE_CLAUSES:
            self._where_clauses.append(self._CONSEQUENCE_CLAUSES[consequence])
        return self

    def with_domain_filter(
        self, domain_start: int, domain_end: int
    ) -> "VariantQueryBuilder":
        """Add protein domain position filter.

        Args:
            domain_start: Start position of the domain
            domain_end: End position of the domain

        Returns:
            Self for method chaining
        """
        domain_clause = """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND (regexp_match(elem->>'value', 'p\\.[A-Z][a-z]{2}(\\d+)'))[1]::int
                BETWEEN :domain_start AND :domain_end
        )"""
        self._where_clauses.append(domain_clause)
        self._params["domain_start"] = domain_start
        self._params["domain_end"] = domain_end
        return self

    def build_where_sql(self) -> str:
        """Build the WHERE clause SQL fragment.

        Returns:
            SQL string with AND-prefixed conditions
        """
        if not self._where_clauses:
            return ""
        return "AND " + "\nAND ".join(self._where_clauses)

    def build_params(self) -> Dict[str, Any]:
        """Get the query parameters dictionary.

        Returns:
            Dictionary of parameter name to value
        """
        return self._params.copy()

    def get_validated_query(self) -> Optional[str]:
        """Get the validated text search query.

        Returns:
            The text search query or None
        """
        return self._validated_query

    def build(
        self,
        order_by: str = "phenopacket_count DESC, variant_id ASC",
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        """Build the complete variant query with pagination.

        Args:
            order_by: ORDER BY clause
            limit: Maximum rows to return
            offset: Number of rows to skip

        Returns:
            Tuple of (SQL query string, parameters dict)
        """
        where_sql = self.build_where_sql()
        simple_id_filter = (
            "AND CONCAT('Var', simple_id::text) ILIKE :simple_id_query"
            if self._validated_query and self._validated_query.lower().startswith("var")
            else ""
        )

        params = self.build_params()
        params["limit"] = limit
        params["offset"] = offset

        sql = f"""
        WITH all_variants_unfiltered AS (
            SELECT DISTINCT ON (vd->>'id', p.id)
                vd->>'id' as variant_id,
                vd->'geneContext'->>'symbol' as gene_symbol,
                p.id as phenopacket_id
            FROM
                phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') gi,
                LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
                LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
            WHERE
                vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
        ),
        all_variants_agg AS (
            SELECT
                variant_id,
                MAX(gene_symbol) as gene_symbol,
                COUNT(DISTINCT phenopacket_id) as phenopacket_count
            FROM all_variants_unfiltered
            GROUP BY variant_id
        ),
        all_variants_with_stable_id AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY phenopacket_count DESC, gene_symbol ASC, variant_id ASC
                ) as simple_id,
                variant_id
            FROM all_variants_agg
        ),
        variant_raw AS (
            SELECT DISTINCT ON (vd->>'id', p.id)
                vd->>'id' as variant_id,
                vd->>'label' as label,
                vd->'geneContext'->>'symbol' as gene_symbol,
                vd->'geneContext'->>'valueId' as gene_id,
                {STRUCTURAL_TYPE_CASE} as structural_type,
                COALESCE(
                    vi->>'acmgPathogenicityClassification',
                    gi->>'interpretationStatus'
                ) as pathogenicity,
                COALESCE(
                    NULLIF(CONCAT(
                        COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'alt', '')
                    ), ':::'),
                    (
                        SELECT elem->>'value'
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' IN ('vcf', 'ga4gh', 'text')
                        LIMIT 1
                    ),
                    vd->>'description'
                ) as hg38,
                (
                    SELECT elem->>'value'
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    LIMIT 1
                ) as transcript,
                (
                    SELECT elem->>'value'
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    LIMIT 1
                ) as protein,
                vd->'extensions' as vep_extensions,
                p.id as phenopacket_id
            FROM
                phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') gi,
                LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
                LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
            WHERE
                vi_lateral.vi IS NOT NULL
                AND vd_lateral.vd IS NOT NULL
                {where_sql}
        ),
        variant_agg AS (
            SELECT
                variant_id,
                MAX(label) as label,
                MAX(gene_symbol) as gene_symbol,
                MAX(gene_id) as gene_id,
                MAX(structural_type) as structural_type,
                MAX(pathogenicity) as pathogenicity,
                MAX(hg38) as hg38,
                MAX(transcript) as transcript,
                MAX(protein) as protein,
                (ARRAY_AGG(vep_extensions))[1] as vep_extensions,
                COUNT(DISTINCT phenopacket_id) as phenopacket_count
            FROM variant_raw
            GROUP BY variant_id
        ),
        variant_with_stable_id AS (
            SELECT
                avwsi.simple_id,
                va.variant_id,
                va.label,
                va.gene_symbol,
                va.gene_id,
                va.structural_type,
                va.pathogenicity,
                va.phenopacket_count,
                va.hg38,
                va.transcript,
                va.protein,
                va.vep_extensions
            FROM variant_agg va
            JOIN all_variants_with_stable_id avwsi
                ON va.variant_id = avwsi.variant_id
        ),
        filtered AS (
            SELECT *
            FROM variant_with_stable_id
            WHERE 1=1
                {simple_id_filter}
        )
        SELECT *, COUNT(*) OVER() as total_count
        FROM filtered
        ORDER BY {order_by}
        LIMIT :limit
        OFFSET :offset
        """

        return sql, params
