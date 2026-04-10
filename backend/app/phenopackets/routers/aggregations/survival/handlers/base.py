"""Abstract base class and shared helpers for survival analysis handlers."""

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


class SurvivalHandler(ABC):
    """Abstract base class for survival analysis handlers.

    Each concrete handler implements a specific comparison strategy
    (variant_type, pathogenicity, disease_subtype, protein_domain) while
    sharing common processing logic.
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

    @staticmethod
    def _sql_list(terms: List[str]) -> str:
        """Convert a Python list of HPO terms to a SQL IN-clause literal.

        Shared helper used by every concrete subclass when embedding a
        dynamic list of terms into an otherwise parameterised SQL query.
        """
        quoted = ", ".join(f"'{t}'" for t in terms)
        return f"({quoted})"

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
                f"Kidney failure: CKD Stage 4 ({settings.hpo_terms.ckd_stage_4}) "
                f"or Stage 5/ESRD ({settings.hpo_terms.ckd_stage_5})"
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
