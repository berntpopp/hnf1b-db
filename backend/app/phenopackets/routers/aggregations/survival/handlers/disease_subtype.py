"""Survival handler comparing disease subtypes (CAKUT vs CAKUT/MODY vs MODY vs Other)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.phenopackets.survival_analysis import parse_iso8601_age

from ...sql_fragments import CURRENT_AGE_PATH, INTERP_STATUS_PATH
from .base import SurvivalHandler


class DiseaseSubtypeHandler(SurvivalHandler):
    """Handler for disease subtype comparison (CAKUT vs CAKUT/MODY vs MODY vs Other)."""

    @property
    def comparison_type(self) -> str:
        return "disease_subtype"

    @property
    def group_names(self) -> List[str]:
        return ["CAKUT", "CAKUT/MODY", "MODY", "Other"]

    @property
    def group_definitions(self) -> Dict[str, str]:
        return {
            "CAKUT": "Congenital anomalies of kidney/urinary tract without diabetes",
            "CAKUT/MODY": "Both CAKUT and MODY phenotypes present",
            "MODY": "Maturity-onset diabetes of the young without CAKUT",
            "Other": "Other HNF1B-related phenotypes without CAKUT or MODY",
        }

    def get_group_field(self) -> str:
        return "disease_group"

    def _build_disease_classification_sql(self) -> str:
        """Build SQL CASE for disease subtype classification."""
        return """
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') pf
                WHERE (
                    pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                    OR pf->'type'->>'id' = :genital_hpo
                )
                AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') pf
                WHERE pf->'type'->>'id' = :mody_hpo
                AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) THEN 'CAKUT/MODY'
            WHEN EXISTS (
                SELECT 1
                FROM jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') pf
                WHERE (
                    pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                    OR pf->'type'->>'id' = :genital_hpo
                )
                AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) THEN 'CAKUT'
            WHEN EXISTS (
                SELECT 1
                FROM jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') pf
                WHERE pf->'type'->>'id' = :mody_hpo
                AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) THEN 'MODY'
            ELSE 'Other'
        END
        """

    def build_current_age_query(self) -> str:
        disease_case = self._build_disease_classification_sql()
        kidney_failure = settings.hpo_terms.kidney_failure

        return f"""
        WITH disease_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                p.phenopacket as phenopacket_data,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        classified AS (
            SELECT
                dc.phenopacket_id,
                {disease_case} AS disease_group,
                dc.current_age,
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(kidney_failure)}
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_kidney_failure
            FROM disease_classification dc
        )
        SELECT disease_group, current_age, has_kidney_failure
        FROM classified
        """

    def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
        disease_case = self._build_disease_classification_sql()

        return f"""
        WITH disease_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                p.phenopacket as phenopacket_data,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        classified AS (
            SELECT
                dc.phenopacket_id,
                {disease_case} AS disease_group,
                dc.current_age,
                dc.phenopacket_data
            FROM disease_classification dc
        ),
        endpoint_cases AS (
            SELECT
                c.disease_group,
                c.current_age,
                COALESCE(pf->'onset'->>'iso8601duration', pf->'onset'->>'age') as onset_age,
                pf->'onset'->>'label' as onset
            FROM classified c,
                jsonb_array_elements(c.phenopacket_data->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
        )
        SELECT disease_group, current_age, onset_age, onset
        FROM endpoint_cases
        """

    def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
        disease_case = self._build_disease_classification_sql()

        return f"""
        WITH disease_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                p.phenopacket as phenopacket_data,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        classified AS (
            SELECT
                dc.phenopacket_id,
                {disease_case} AS disease_group,
                dc.current_age
            FROM disease_classification dc
            WHERE dc.phenopacket_id NOT IN (
                SELECT DISTINCT p.phenopacket_id
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            )
        )
        SELECT disease_group, current_age
        FROM classified
        """

    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        return {
            "inclusion_criteria": (
                "Pathogenic (P) and Likely Pathogenic (LP) variants only. "
                "Groups based on phenotype presentation."
            ),
            "exclusion_criteria": (
                "VUS, Likely Benign, and Benign variants excluded. "
                "Classification based on HPO terms present in phenotypicFeatures."
            ),
        }

    async def handle(
        self,
        db: AsyncSession,
        endpoint_label: str,
        endpoint_hpo_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Override to add HPO term parameters for disease classification."""
        # Disease classification parameters consumed by the CASE expression
        # inside _build_disease_classification_sql. Only the three keys below
        # are referenced by the generated SQL. `any_kidney_hpo_terms` used to
        # be passed here as well, but it was never bound by any query in this
        # handler — a carry-over from the deleted legacy _handle_*
        # functions. Dropped in Wave 3 to match the actual SQL (Copilot #2).
        params = {
            "cakut_hpo_terms": settings.hpo_terms.cakut,
            "genital_hpo": settings.hpo_terms.genital,
            "mody_hpo": settings.hpo_terms.mody,
        }

        if endpoint_hpo_terms is None:
            return await self._handle_current_age_with_params(
                db, endpoint_label, params
            )
        return await self._handle_standard_with_params(
            db, endpoint_label, endpoint_hpo_terms, params
        )

    async def _handle_current_age_with_params(
        self,
        db: AsyncSession,
        endpoint_label: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle current_age with disease classification params."""
        query = self.build_current_age_query()
        result = await db.execute(text(query), params)
        rows = result.fetchall()

        groups = self._init_groups()

        for row in rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                groups[row.disease_group].append((current_age, row.has_kidney_failure))

        return self._build_result(
            endpoint_label,
            groups,
            self._get_current_age_metadata(),
        )

    async def _handle_standard_with_params(
        self,
        db: AsyncSession,
        endpoint_label: str,
        endpoint_hpo_terms: List[str],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle standard endpoint with disease classification params."""
        params["endpoint_hpo_terms"] = endpoint_hpo_terms

        query = self.build_standard_query(endpoint_hpo_terms)
        result = await db.execute(text(query), params)
        rows = result.fetchall()

        groups = self._init_groups()

        for row in rows:
            onset_age = None
            if row.onset_age:
                onset_age = parse_iso8601_age(row.onset_age)
            elif row.onset:
                onset_age = parse_iso8601_age(row.onset)

            if onset_age is not None:
                groups[row.disease_group].append((onset_age, True))

        # Add censored cases
        censored_query = self._build_censored_query(endpoint_hpo_terms)
        censored_result = await db.execute(text(censored_query), params)
        censored_rows = censored_result.fetchall()

        for row in censored_rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                groups[row.disease_group].append((current_age, False))

        return self._build_result(
            endpoint_label,
            groups,
            self._get_standard_metadata(endpoint_label),
        )
