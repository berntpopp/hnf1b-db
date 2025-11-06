"""Reusable clinical query patterns using type-safe SQLAlchemy.

Follows DRY/SOLID/KISS principles.
"""

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import (
    Integer,
    and_,
    case,
    func,
    literal_column,
    not_,
    or_,
    select,
    text,
    true,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.phenopackets.models import Phenopacket


class ClinicalQueries:
    """Reusable clinical query patterns - DRY principle."""

    @staticmethod
    def get_phenotype_features_query(
        hpo_terms: List[str], stage: Optional[str] = None
    ) -> Select:
        """Type-safe query for phenotypic features - KISS principle.

        Args:
            hpo_terms: List of HPO term IDs to search for
            stage: Optional CKD stage filter (e.g., '3', '4', '5')

        Returns:
            SQLAlchemy Select query object
        """
        # Base query using SQLAlchemy with proper column selection
        query = select(
            Phenopacket.phenopacket_id,
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "id"
            ).label("subject_id"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "sex"
            ).label("sex"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket,
                "subject",
                "timeAtLastEncounter",
                "age",
                "iso8601duration",
            ).label("age"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket,
                text("'$.phenotypicFeatures[*]'::jsonpath"),
            ).label("features"),
        ).select_from(Phenopacket)

        # Build JSONB conditions using SQLAlchemy functions
        conditions = []

        # Check for HPO terms existence
        # Build OR condition for multiple HPO terms
        hpo_conditions = []
        for term in hpo_terms:
            hpo_conditions.append(
                func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    text(
                        f"'$.phenotypicFeatures[*] ? (@.type.id == \"{term}\")'::jsonpath"
                    ),
                )
            )
        hpo_condition = or_(*hpo_conditions) if hpo_conditions else true()

        # Check for non-excluded features
        excluded_condition = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text("'$.phenotypicFeatures[*] ? (@.excluded != true)'::jsonpath"),
        )

        conditions.extend([hpo_condition, excluded_condition])

        # Add stage filtering if specified
        if stage:
            stage_condition = func.jsonb_path_exists(
                Phenopacket.phenopacket,
                text(
                    f"'$.phenotypicFeatures[*].modifiers[*] ? (@.label like_regex \"Stage {stage}\")'::jsonpath"
                ),
            )
            conditions.append(stage_condition)

        return query.where(and_(*conditions))

    @staticmethod
    def exclude_transplant_cases(query: Select) -> Select:
        """Reusable transplant exclusion - Single Responsibility.

        Args:
            query: Base SQLAlchemy query to filter

        Returns:
            Modified query with transplant exclusion
        """
        transplant_exclusion = not_(
            func.jsonb_path_exists(
                Phenopacket.phenopacket,
                text(
                    "'$.medicalActions[*].procedure ? (@.code.id == \"NCIT:C157952\")'::jsonpath"
                ),
            )
        )
        return query.where(transplant_exclusion)

    @staticmethod
    def get_clinical_features_with_details(
        hpo_terms: List[str],
        include_modifiers: bool = True,
        include_onset: bool = True,
    ) -> Select:
        """Get clinical features with detailed information.

        Args:
            hpo_terms: HPO term IDs to search for
            include_modifiers: Whether to include feature modifiers
            include_onset: Whether to include onset information

        Returns:
            SQLAlchemy query with feature details
        """
        # Build column list dynamically
        columns = [
            Phenopacket.phenopacket_id,
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "id"
            ).label("subject_id"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "sex"
            ).label("sex"),
        ]

        # Extract features matching the HPO terms
        # For simplicity, just get the first phenotypic feature
        # (Since we're filtering by HPO terms anyway)
        feature_expr = func.jsonb_array_element(
            func.jsonb_extract_path(Phenopacket.phenopacket, "phenotypicFeatures"), 0
        )

        columns.append(
            func.jsonb_extract_path_text(feature_expr, "type", "label").label(
                "feature_label"
            )
        )

        if include_onset:
            columns.append(
                func.jsonb_extract_path_text(
                    feature_expr, "onset", "age", "iso8601duration"
                ).label("onset_age")
            )

        if include_modifiers:
            columns.append(
                func.jsonb_extract_path(feature_expr, "modifiers").label("modifiers")
            )

        query = select(*columns).select_from(Phenopacket)

        # Add existence check
        query = query.where(
            or_(
                *[
                    func.jsonb_path_exists(
                        Phenopacket.phenopacket,
                        text(
                            f"'$.phenotypicFeatures[*] ? (@.type.id == \"{term}\" && @.excluded != true)'::jsonpath"
                        ),
                    )
                    for term in hpo_terms
                ]
            )
            if hpo_terms
            else true()
        )

        return query

    @staticmethod
    def filter_by_sex(query: Select, sex: str) -> Select:
        """Filter query by biological sex.

        Args:
            query: Base query
            sex: Sex value ('MALE' or 'FEMALE')

        Returns:
            Filtered query
        """
        return query.where(
            func.jsonb_extract_path_text(Phenopacket.phenopacket, "subject", "sex")
            == sex
        )

    @staticmethod
    def get_disease_cases(
        disease_terms: List[str], disease_labels: Optional[List[str]] = None
    ) -> Select:
        """Get cases with specific diseases using MONDO IDs or labels.

        Args:
            disease_terms: MONDO disease IDs
            disease_labels: Optional disease label patterns

        Returns:
            SQLAlchemy query for disease cases
        """
        query = select(
            Phenopacket.phenopacket_id,
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "id"
            ).label("subject_id"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "sex"
            ).label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket, text("'$.diseases[*]'::jsonpath")
            ).label("diseases"),
        ).select_from(Phenopacket)

        conditions = []

        # Check for disease IDs
        if disease_terms:
            # Build OR condition for multiple disease terms
            for term in disease_terms:
                id_condition = func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    text(f"'$.diseases[*] ? (@.term.id == \"{term}\")'::jsonpath"),
                )
                conditions.append(id_condition)

        # Check for disease labels
        if disease_labels:
            for label in disease_labels:
                label_condition = func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    text(
                        f"'$.diseases[*] ? (@.term.label like_regex \"{label}\")'::jsonpath"
                    ),
                )
                conditions.append(label_condition)

        if conditions:
            query = query.where(or_(*conditions))

        return query

    @staticmethod
    def get_measurement_cases(
        loinc_codes: List[str], interpretation_hpo: Optional[str] = None
    ) -> Select:
        """Get cases with specific measurements by LOINC codes.

        Args:
            loinc_codes: LOINC measurement codes
            interpretation_hpo: Optional HPO term for interpretation

        Returns:
            SQLAlchemy query for measurement cases
        """
        query = select(
            Phenopacket.phenopacket_id,
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "id"
            ).label("subject_id"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "sex"
            ).label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket, text("'$.measurements[*]'::jsonpath")
            ).label("measurements"),
        ).select_from(Phenopacket)

        # Base condition for LOINC codes - OR multiple codes
        conditions = []
        loinc_conditions = []
        for code in loinc_codes:
            loinc_conditions.append(
                func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    text(f"'$.measurements[*] ? (@.assay.id == \"{code}\")'::jsonpath"),
                )
            )
        if loinc_conditions:
            conditions.append(or_(*loinc_conditions))

        # Add interpretation filter if provided
        if interpretation_hpo:
            interpretation_condition = func.jsonb_path_exists(
                Phenopacket.phenopacket,
                text(
                    f"'$.measurements[*] ? (@.interpretation.id == \"{interpretation_hpo}\")'::jsonpath"
                ),
            )
            conditions.append(interpretation_condition)

        return query.where(and_(*conditions))

    @staticmethod
    def get_morphology_features(morphology_type: Optional[str] = None) -> Select:
        """Get kidney morphology cases with optional filtering.

        Args:
            morphology_type: Type of morphology ('cysts', 'dysplasia', 'hypoplasia')

        Returns:
            SQLAlchemy query for morphology cases
        """
        # Define morphology HPO mappings
        all_morphology_hpo = [
            "HP:0100611",  # Multiple glomerular cysts
            "HP:0004719",  # Oligomeganephronia
            "HP:0000110",  # Renal dysplasia
            "HP:0000089",  # Renal hypoplasia
            "HP:0000107",  # Renal cysts
            "HP:0000003",  # Multicystic kidney dysplasia
            "HP:0000113",  # Polycystic kidneys
        ]

        morphology_mappings = {
            "cysts": ["HP:0100611", "HP:0000107", "HP:0000113"],
            "dysplasia": ["HP:0000110", "HP:0000003"],
            "hypoplasia": ["HP:0000089", "HP:0004719"],
        }

        # Select appropriate HPO terms
        if morphology_type and morphology_type.lower() in morphology_mappings:
            hpo_terms = morphology_mappings[morphology_type.lower()]
        else:
            hpo_terms = all_morphology_hpo

        query = select(
            Phenopacket.phenopacket_id,
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "id"
            ).label("subject_id"),
            func.jsonb_extract_path_text(
                Phenopacket.phenopacket, "subject", "sex"
            ).label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket, text("'$.phenotypicFeatures[*]'::jsonpath")
            ).label("morphology_features"),
        ).select_from(Phenopacket)

        # Add existence condition - OR multiple HPO terms
        hpo_conditions = []
        for term in hpo_terms:
            hpo_conditions.append(
                func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    text(
                        f"'$.phenotypicFeatures[*] ? (@.type.id == \"{term}\")'::jsonpath"
                    ),
                )
            )
        if hpo_conditions:
            query = query.where(or_(*hpo_conditions))

        return query

    @staticmethod
    def get_multisystem_involvement(min_systems: int = 2) -> Select:
        """Get cases with multiple system involvement.

        Args:
            min_systems: Minimum number of systems involved

        Returns:
            SQLAlchemy query for multisystem cases
        """
        # Simplified query using existence checks for each system
        renal_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text(
                "'$.phenotypicFeatures[*] ? (@.type.id like_regex \"^HP:00126\")'::jsonpath"
            ),
        )

        genital_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text(
                '\'$.phenotypicFeatures[*] ? (@.type.id == "HP:0000078" || @.type.id == "HP:0000079")\'::jsonpath'
            ),
        )

        pancreatic_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text(
                '\'$.phenotypicFeatures[*] ? (@.type.id == "HP:0001732" || @.type.id == "HP:0001738")\'::jsonpath'
            ),
        )

        liver_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text(
                "'$.phenotypicFeatures[*] ? (@.type.id like_regex \"^HP:00013\")'::jsonpath"
            ),
        )

        metabolic_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text("'$.phenotypicFeatures[*] ? (@.type.id == \"HP:0002917\")'::jsonpath"),
        )

        endocrine_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            text("'$.diseases[*] ? (@.term.label like_regex \"diabetes\")'::jsonpath"),
        )

        # Count systems
        system_count = (
            func.cast(renal_check, Integer)
            + func.cast(genital_check, Integer)
            + func.cast(pancreatic_check, Integer)
            + func.cast(liver_check, Integer)
            + func.cast(metabolic_check, Integer)
            + func.cast(endocrine_check, Integer)
        )

        # Build query
        query = (
            select(
                Phenopacket.phenopacket_id,
                func.jsonb_extract_path_text(
                    Phenopacket.phenopacket, "subject", "id"
                ).label("subject_id"),
                func.jsonb_extract_path_text(
                    Phenopacket.phenopacket, "subject", "sex"
                ).label("sex"),
                system_count.label("system_count"),
                func.json_build_array(
                    case((renal_check, literal_column("'renal'"))),
                    case((genital_check, literal_column("'genital'"))),
                    case((pancreatic_check, literal_column("'pancreatic'"))),
                    case((liver_check, literal_column("'liver'"))),
                    case((metabolic_check, literal_column("'metabolic'"))),
                    case((endocrine_check, literal_column("'endocrine'"))),
                ).label("affected_systems"),
            )
            .select_from(Phenopacket)
            .where(system_count >= min_systems)
        )

        return query

    @staticmethod
    async def execute_and_format(
        db: AsyncSession, query: Select, format_func: Optional[Callable[[Any], Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Execute query and format results - DRY principle.

        Args:
            db: Database session
            query: SQLAlchemy query to execute
            format_func: Optional formatting function for results

        Returns:
            List of formatted results
        """
        result = await db.execute(query)
        rows = result.fetchall()

        if format_func:
            return [format_func(row) for row in rows]

        # Default formatting
        return [dict(row._mapping) for row in rows]
