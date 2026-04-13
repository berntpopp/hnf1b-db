"""Survival handler comparing HNF1B protein domains (POU-S vs POU-H vs TAD vs Other)."""

from typing import Any, Dict, List

from app.core.config import settings

from ...sql_fragments import (
    CURRENT_AGE_PATH,
    HNF1B_PROTEIN_DOMAINS,
    get_cnv_exclusion_filter,
    get_missense_filter_sql,
    get_protein_domain_classification_sql,
)
from ...sql_fragments.ctes import PUBLIC_FILTER_FRAGMENT
from .base import SurvivalHandler


class ProteinDomainHandler(SurvivalHandler):
    """Handler for protein domain comparison (POU-S vs POU-H vs TAD vs Other).

    Stratifies missense variants by their location within HNF1B functional
    domains based on amino acid position extracted from HGVS.p notation.

    Note: Only includes missense variants with valid HGVS.p notation.
    CNVs, deletions, and truncating variants are excluded.
    """

    # Variation descriptor path for genomic interpretation queries
    _VD_PATH = "gi->'variantInterpretation'->'variationDescriptor'"

    @property
    def comparison_type(self) -> str:
        return "protein_domain"

    @property
    def group_names(self) -> List[str]:
        return ["POU-S", "POU-H", "TAD", "Other"]

    @property
    def group_definitions(self) -> Dict[str, str]:
        return {
            "POU-S": (
                f"POU-specific domain (aa {HNF1B_PROTEIN_DOMAINS['POU-S']['start']}-"
                f"{HNF1B_PROTEIN_DOMAINS['POU-S']['end']}): DNA binding domain 1"
            ),
            "POU-H": (
                f"POU-homeodomain (aa {HNF1B_PROTEIN_DOMAINS['POU-H']['start']}-"
                f"{HNF1B_PROTEIN_DOMAINS['POU-H']['end']}): DNA binding domain 2"
            ),
            "TAD": (
                f"Transactivation domain (aa {HNF1B_PROTEIN_DOMAINS['TAD']['start']}-"
                f"{HNF1B_PROTEIN_DOMAINS['TAD']['end']}): Coactivator recruitment"
            ),
            "Other": "Variants outside defined domains or with unclassified position",
        }

    def get_group_field(self) -> str:
        return "domain_group"

    def build_current_age_query(self) -> str:
        kidney_failure_terms = settings.hpo_terms.kidney_failure
        ckd_terms = settings.hpo_terms.ckd_stages
        domain_sql = get_protein_domain_classification_sql(self._VD_PATH)
        missense_filter = get_missense_filter_sql(self._VD_PATH)
        cnv_exclusion = get_cnv_exclusion_filter()

        # Note: We use gi->>'interpretationStatus' directly since we unnest
        # genomicInterpretations into gi, unlike INTERP_STATUS_PATH which assumes
        # the interp alias structure.
        return f"""
        WITH domain_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {domain_sql} AS domain_group,
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
                AND gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                AND {missense_filter}
                AND {cnv_exclusion}
                AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(ckd_terms)}
                )
        )
        SELECT domain_group, current_age, has_kidney_failure
        FROM domain_classification
        """

    def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
        domain_sql = get_protein_domain_classification_sql(self._VD_PATH)
        missense_filter = get_missense_filter_sql(self._VD_PATH)
        cnv_exclusion = get_cnv_exclusion_filter()

        return f"""
        WITH domain_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {domain_sql} AS domain_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                AND {missense_filter}
                AND {cnv_exclusion}
        ),
        endpoint_cases AS (
            SELECT
                dc.domain_group,
                dc.current_age,
                COALESCE(pf->'onset'->>'iso8601duration', pf->'onset'->>'age') as onset_age,
                pf->'onset'->>'label' as onset
            FROM domain_classification dc
            JOIN phenopackets p ON dc.phenopacket_id = p.phenopacket_id,
                jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
        )
        SELECT domain_group, current_age, onset_age, onset
        FROM endpoint_cases
        """

    def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
        domain_sql = get_protein_domain_classification_sql(self._VD_PATH)
        missense_filter = get_missense_filter_sql(self._VD_PATH)
        cnv_exclusion = get_cnv_exclusion_filter()

        return f"""
        WITH domain_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {domain_sql} AS domain_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            WHERE {PUBLIC_FILTER_FRAGMENT}
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                AND {missense_filter}
                AND {cnv_exclusion}
        ),
        classified AS (
            SELECT DISTINCT phenopacket_id, domain_group, current_age
            FROM domain_classification
            WHERE phenopacket_id NOT IN (
                SELECT DISTINCT p.phenopacket_id
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
                    AND {PUBLIC_FILTER_FRAGMENT}
            )
        )
        SELECT domain_group, current_age
        FROM classified
        """

    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        return {
            "inclusion_criteria": (
                "Missense variants with valid HGVS.p notation only. "
                "Pathogenic (P) and Likely Pathogenic (LP) classification. "
                "Requires CKD assessment data."
            ),
            "exclusion_criteria": (
                "CNVs and large deletions excluded (no amino acid position). "
                "Truncating variants excluded (frameshift, nonsense, splice). "
                "VUS, Likely Benign, and Benign variants excluded."
            ),
        }

    def _get_current_age_metadata(self) -> Dict[str, Any]:
        """Override to add domain-specific metadata."""
        base_metadata = super()._get_current_age_metadata()
        base_metadata["domain_boundaries"] = {
            name: {"start": domain["start"], "end": domain["end"]}
            for name, domain in HNF1B_PROTEIN_DOMAINS.items()
        }
        base_metadata["references"] = [
            "UniProt P35680",
            "doi:10.3390/ijms251910609",
        ]
        return base_metadata

    def _get_standard_metadata(self, endpoint_label: str) -> Dict[str, Any]:
        """Override to add domain-specific metadata."""
        base_metadata = super()._get_standard_metadata(endpoint_label)
        base_metadata["domain_boundaries"] = {
            name: {"start": domain["start"], "end": domain["end"]}
            for name, domain in HNF1B_PROTEIN_DOMAINS.items()
        }
        base_metadata["references"] = [
            "UniProt P35680",
            "doi:10.3390/ijms251910609",
        ]
        return base_metadata
