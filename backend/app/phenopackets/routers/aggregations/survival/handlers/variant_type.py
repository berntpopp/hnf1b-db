"""Survival handler comparing variant types (CNV vs Truncating vs Non-truncating)."""

from typing import Dict, List

from app.core.config import settings

from ...sql_fragments import (
    CURRENT_AGE_PATH,
    INTERP_STATUS_PATH,
    get_variant_type_classification_sql,
    get_vcf_id_extraction_sql,
)
from ...sql_fragments.ctes import PUBLIC_FILTER_FRAGMENT
from .base import SurvivalHandler


class VariantTypeHandler(SurvivalHandler):
    """Handler for variant type comparison (CNV vs Truncating vs Non-truncating)."""

    @property
    def comparison_type(self) -> str:
        return "variant_type"

    @property
    def group_names(self) -> List[str]:
        return ["CNV", "Truncating", "Non-truncating"]

    @property
    def group_definitions(self) -> Dict[str, str]:
        return {
            "CNV": (
                "Copy number variants: deletions or duplications ≥50kb "
                "(17q12 deletion/duplication syndrome)"
            ),
            "Truncating": (
                "Frameshift, nonsense (stop gained), splice site variants, "
                "or intragenic deletions <50kb"
            ),
            "Non-truncating": (
                "Missense variants and other variants with MODERATE impact"
            ),
        }

    def get_group_field(self) -> str:
        return "variant_group"

    def build_current_age_query(self) -> str:
        kidney_failure_terms = settings.hpo_terms.kidney_failure
        ckd_terms = settings.hpo_terms.ckd_stages
        variant_type_sql = get_variant_type_classification_sql()
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {variant_type_sql} AS variant_group,
                {CURRENT_AGE_PATH} as current_age,
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(kidney_failure_terms)}
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_kidney_failure
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            LEFT JOIN variant_annotations va ON va.variant_id = ({get_vcf_id_extraction_sql()})
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(ckd_terms)}
                )
        )
        SELECT variant_group, current_age, has_kidney_failure
        FROM variant_classification
        """

    def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
        variant_type_sql = get_variant_type_classification_sql()
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {variant_type_sql} AS variant_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            LEFT JOIN variant_annotations va ON va.variant_id = ({get_vcf_id_extraction_sql()})
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        endpoint_cases AS (
            SELECT
                vc.variant_group,
                vc.current_age,
                COALESCE(pf->'onset'->>'iso8601duration', pf->'onset'->>'age') as onset_age,
                pf->'onset'->>'label' as onset
            FROM variant_classification vc
            JOIN phenopackets p ON vc.phenopacket_id = p.phenopacket_id,
                jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
        )
        SELECT variant_group, current_age, onset_age, onset
        FROM endpoint_cases
        """

    def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
        variant_type_sql = get_variant_type_classification_sql()
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {variant_type_sql} AS variant_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            LEFT JOIN variant_annotations va ON va.variant_id = ({get_vcf_id_extraction_sql()})
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        classified AS (
            SELECT DISTINCT phenopacket_id, variant_group, current_age
            FROM variant_classification
            WHERE phenopacket_id NOT IN (
                SELECT DISTINCT p.phenopacket_id
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
                    AND {PUBLIC_FILTER_FRAGMENT}
            )
        )
        SELECT variant_group, current_age
        FROM classified
        """

    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        return {
            "inclusion_criteria": (
                "Pathogenic (P) and Likely Pathogenic (LP) variants only. "
                "Requires CKD assessment data."
            ),
            "exclusion_criteria": "VUS, Likely Benign, and Benign variants excluded",
        }
