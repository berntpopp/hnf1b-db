"""Survival analysis handlers using Strategy pattern.

This module provides a clean abstraction for survival analysis comparison
strategies, eliminating code duplication across handler functions.

Usage:
    handler = SurvivalHandlerFactory.get_handler("variant_type")
    result = await handler.handle(db, endpoint_label, endpoint_hpo_terms)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.phenopackets.survival_analysis import (
    apply_bonferroni_correction,
    calculate_kaplan_meier,
    calculate_log_rank_test,
    parse_iso8601_age,
)

from .sql_fragments import (
    CURRENT_AGE_PATH,
    INTERP_STATUS_PATH,
    VARIANT_TYPE_CLASSIFICATION_SQL,
)


class SurvivalHandler(ABC):
    """Abstract base class for survival analysis handlers.

    Each concrete handler implements a specific comparison strategy
    (variant_type, pathogenicity, disease_subtype) while sharing common
    processing logic.
    """

    @property
    @abstractmethod
    def comparison_type(self) -> str:
        """Return the comparison type identifier."""
        pass

    @property
    @abstractmethod
    def group_names(self) -> List[str]:
        """Return the list of group names for this comparison."""
        pass

    @property
    @abstractmethod
    def group_definitions(self) -> Dict[str, str]:
        """Return descriptions for each group."""
        pass

    @abstractmethod
    def build_current_age_query(self) -> str:
        """Build SQL query for current_age endpoint."""
        pass

    @abstractmethod
    def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
        """Build SQL query for standard CKD endpoint."""
        pass

    def get_group_field(self) -> str:
        """Return the field name containing group classification."""
        return f"{self.comparison_type}_group"

    async def handle(
        self,
        db: AsyncSession,
        endpoint_label: str,
        endpoint_hpo_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute survival analysis for this comparison type.

        Args:
            db: Database session
            endpoint_label: Human-readable endpoint description
            endpoint_hpo_terms: HPO terms defining the endpoint (None for current_age)

        Returns:
            Complete survival analysis response
        """
        if endpoint_hpo_terms is None:
            return await self._handle_current_age(db, endpoint_label)
        return await self._handle_standard(db, endpoint_label, endpoint_hpo_terms)

    async def _handle_current_age(
        self,
        db: AsyncSession,
        endpoint_label: str,
    ) -> Dict[str, Any]:
        """Handle current_age endpoint (event = kidney failure)."""
        query = self.build_current_age_query()
        result = await db.execute(text(query))
        rows = result.fetchall()

        groups = self._init_groups()
        group_field = self.get_group_field()

        for row in rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                group_name = getattr(row, group_field)
                if group_name in groups:
                    groups[group_name].append((current_age, row.has_kidney_failure))

        return self._build_result(
            endpoint_label,
            groups,
            self._get_current_age_metadata(),
        )

    async def _handle_standard(
        self,
        db: AsyncSession,
        endpoint_label: str,
        endpoint_hpo_terms: List[str],
    ) -> Dict[str, Any]:
        """Handle standard CKD endpoint (event = phenotype onset)."""
        query = self.build_standard_query(endpoint_hpo_terms)
        result = await db.execute(
            text(query),
            {"endpoint_hpo_terms": endpoint_hpo_terms},
        )
        rows = result.fetchall()

        groups = self._init_groups()
        group_field = self.get_group_field()

        # Process event cases (onset found)
        for row in rows:
            onset_age = None
            if row.onset_age:
                onset_age = parse_iso8601_age(row.onset_age)
            elif row.onset:
                onset_age = parse_iso8601_age(row.onset)

            if onset_age is not None:
                group_name = getattr(row, group_field)
                if group_name in groups:
                    groups[group_name].append((onset_age, True))

        # Add censored cases (no onset)
        censored_query = self._build_censored_query(endpoint_hpo_terms)
        censored_result = await db.execute(
            text(censored_query),
            {"endpoint_hpo_terms": endpoint_hpo_terms},
        )
        censored_rows = censored_result.fetchall()

        for row in censored_rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                group_name = getattr(row, group_field)
                if group_name in groups:
                    groups[group_name].append((current_age, False))

        return self._build_result(
            endpoint_label,
            groups,
            self._get_standard_metadata(endpoint_label),
        )

    def _init_groups(self) -> Dict[str, List[tuple]]:
        """Initialize empty groups dictionary."""
        return {name: [] for name in self.group_names}

    def _build_result(
        self,
        endpoint_label: str,
        groups: Dict[str, List[tuple]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the standard survival analysis response."""
        survival_curves = self._calculate_survival_curves(groups)
        statistical_tests = self._calculate_statistical_tests(groups)

        return {
            "comparison_type": self.comparison_type,
            "endpoint": endpoint_label,
            "groups": [
                {
                    "name": group_name,
                    "n": len(event_times),
                    "events": sum(1 for _, event in event_times if event),
                    "survival_data": survival_curves[group_name],
                }
                for group_name, event_times in groups.items()
                if event_times
            ],
            "statistical_tests": statistical_tests,
            "metadata": metadata,
        }

    def _calculate_survival_curves(
        self, groups: Dict[str, List[tuple]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate Kaplan-Meier curves for all groups."""
        survival_curves = {}
        for group_name, event_times in groups.items():
            if event_times:
                survival_curves[group_name] = calculate_kaplan_meier(event_times)
            else:
                survival_curves[group_name] = []
        return survival_curves

    def _calculate_statistical_tests(
        self, groups: Dict[str, List[tuple]]
    ) -> List[Dict[str, Any]]:
        """Calculate pairwise log-rank tests with Bonferroni correction."""
        statistical_tests = []
        group_names = [g for g in groups.keys() if groups[g]]

        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                test_result = calculate_log_rank_test(groups[group1], groups[group2])
                statistical_tests.append(
                    {"group1": group1, "group2": group2, **test_result}
                )

        return apply_bonferroni_correction(statistical_tests)

    def _get_current_age_metadata(self) -> Dict[str, Any]:
        """Get metadata for current_age endpoint."""
        return {
            "event_definition": (
                "Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"
            ),
            "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
            "censoring": (
                "Patients without kidney failure are "
                "censored at their last reported age"
            ),
            "group_definitions": self.group_definitions,
            **self._get_inclusion_exclusion_criteria(),
        }

    def _get_standard_metadata(self, endpoint_label: str) -> Dict[str, Any]:
        """Get metadata for standard CKD endpoint."""
        return {
            "event_definition": f"Onset of {endpoint_label}",
            "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
            "censoring": (
                "Patients without the endpoint are censored at their last reported age"
            ),
            "group_definitions": self.group_definitions,
            **self._get_inclusion_exclusion_criteria(),
        }

    @abstractmethod
    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        """Return inclusion/exclusion criteria specific to this comparison."""
        pass

    @abstractmethod
    def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
        """Build query for censored cases (no event)."""
        pass


class VariantTypeHandler(SurvivalHandler):
    """Handler for variant type comparison (CNV vs Truncating vs Non-truncating)."""

    @property
    def comparison_type(self) -> str:  # noqa: D102
        return "variant_type"

    @property
    def group_names(self) -> List[str]:  # noqa: D102
        return ["CNV", "Truncating", "Non-truncating"]

    @property
    def group_definitions(self) -> Dict[str, str]:  # noqa: D102
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

    def get_group_field(self) -> str:  # noqa: D102
        return "variant_group"

    def build_current_age_query(self) -> str:  # noqa: D102
        kidney_failure_terms = settings.hpo_terms.kidney_failure
        ckd_terms = settings.hpo_terms.ckd_stages
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
                {CURRENT_AGE_PATH} as current_age,
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {self._sql_list(kidney_failure_terms)}
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_kidney_failure
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
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
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        endpoint_cases AS (
            SELECT
                vc.variant_group,
                vc.current_age,
                pf->>'onset' as onset_age,
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
        return f"""
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
                {CURRENT_AGE_PATH} as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
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

    @staticmethod
    def _sql_list(terms: List[str]) -> str:
        """Convert Python list to SQL IN clause format."""
        quoted = ", ".join(f"'{t}'" for t in terms)
        return f"({quoted})"


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
                    WHERE pf->'type'->>'id' IN {VariantTypeHandler._sql_list(kidney_failure_terms)}
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_kidney_failure
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
                AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') pf
                    WHERE pf->'type'->>'id' IN {VariantTypeHandler._sql_list(ckd_terms)}
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
            WHERE p.deleted_at IS NULL
                AND {CURRENT_AGE_PATH} IS NOT NULL
                AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
        ),
        endpoint_cases AS (
            SELECT
                pc.pathogenicity_group,
                pc.current_age,
                pf->>'onset' as onset_age,
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
            WHERE p.deleted_at IS NULL
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
                    WHERE pf->'type'->>'id' IN {VariantTypeHandler._sql_list(kidney_failure)}
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
                pf->>'onset' as onset_age,
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
        # Add disease classification parameters
        params = {
            "cakut_hpo_terms": settings.hpo_terms.cakut,
            "genital_hpo": settings.hpo_terms.genital,
            "any_kidney_hpo_terms": settings.hpo_terms.any_kidney,
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


class SurvivalHandlerFactory:
    """Factory for creating survival handlers by comparison type."""

    _handlers: Dict[str, type] = {
        "variant_type": VariantTypeHandler,
        "pathogenicity": PathogenicityHandler,
        "disease_subtype": DiseaseSubtypeHandler,
    }

    @classmethod
    def get_handler(cls, comparison_type: str) -> SurvivalHandler:
        """Get the appropriate handler for a comparison type.

        Args:
            comparison_type: One of 'variant_type', 'pathogenicity', 'disease_subtype'

        Returns:
            Instantiated handler for the comparison type

        Raises:
            ValueError: If comparison_type is not recognized
        """
        handler_class = cls._handlers.get(comparison_type)
        if handler_class is None:
            valid = ", ".join(cls._handlers.keys())
            raise ValueError(
                f"Unknown comparison type: {comparison_type}. Valid: {valid}"
            )
        return handler_class()

    @classmethod
    def get_valid_comparison_types(cls) -> List[str]:
        """Get list of valid comparison types."""
        return list(cls._handlers.keys())
