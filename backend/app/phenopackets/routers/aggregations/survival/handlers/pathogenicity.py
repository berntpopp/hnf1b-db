"""Survival handler comparing pathogenicity classifications (P/LP vs VUS)."""

from typing import Dict, List

from app.core.config import settings

from ...sql_fragments import CURRENT_AGE_PATH
from ...sql_fragments.ctes import PUBLIC_FILTER_FRAGMENT
from .base import SurvivalHandler


class PathogenicityHandler(SurvivalHandler):
    """Handler for pathogenicity comparison (P/LP vs VUS)."""

    @property
    def comparison_type(self) -> str:
        return "pathogenicity"

    @property
    def group_names(self) -> List[str]:
        return ["P/LP", "VUS"]

    @property
    def group_definitions(self) -> Dict[str, str]:
        return {
            "P/LP": "P/LP variants per ACMG/AMP guidelines",
            "VUS": (
                "Variants of Uncertain Significance - insufficient evidence "
                "to classify as pathogenic or benign"
            ),
        }

    def get_group_field(self) -> str:
        return "pathogenicity_group"

    def build_current_age_query(self) -> str:
        kidney_failure_terms = settings.hpo_terms.kidney_failure
        ckd_terms = settings.hpo_terms.ckd_stages
        return f"""
        WITH pathogenicity_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                CASE
                    WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                        THEN 'P/LP'
                    WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                        THEN 'VUS'
                    ELSE 'Unknown'
                END AS pathogenicity_group,
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
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
                AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(ckd_terms)}
                )
        )
        SELECT pathogenicity_group, current_age, has_kidney_failure
        FROM pathogenicity_classification
        WHERE pathogenicity_group IN ('P/LP', 'VUS')
        """

    def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
        return f"""
        WITH pathogenicity_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                CASE
                    WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                        THEN 'P/LP'
                    WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                        THEN 'VUS'
                    ELSE 'Unknown'
                END AS pathogenicity_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
        ),
        endpoint_cases AS (
            SELECT
                pc.pathogenicity_group,
                pc.current_age,
                COALESCE(pf->'onset'->>'iso8601duration', pf->'onset'->>'age') as onset_age,
                pf->'onset'->>'label' as onset
            FROM pathogenicity_classification pc
            JOIN phenopackets p ON pc.phenopacket_id = p.phenopacket_id,
                jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
                AND pc.pathogenicity_group IN ('P/LP', 'VUS')
        )
        SELECT pathogenicity_group, current_age, onset_age, onset
        FROM endpoint_cases
        """

    def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
        return f"""
        WITH pathogenicity_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                CASE
                    WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                        THEN 'P/LP'
                    WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                        THEN 'VUS'
                    ELSE 'Unknown'
                END AS pathogenicity_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
        ),
        classified AS (
            SELECT DISTINCT phenopacket_id, pathogenicity_group, current_age
            FROM pathogenicity_classification
            WHERE pathogenicity_group IN ('P/LP', 'VUS')
                AND phenopacket_id NOT IN (
                    SELECT DISTINCT p.phenopacket_id
                    FROM phenopackets p,
                        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                        AND {PUBLIC_FILTER_FRAGMENT}
                )
        )
        SELECT pathogenicity_group, current_age
        FROM classified
        """

    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        return {
            "inclusion_criteria": "P/LP and VUS variants only. Requires CKD data.",
            "exclusion_criteria": (
                "CNVs excluded (lack standard ACMG classification). "
                "Likely Benign and Benign variants excluded."
            ),
        }
