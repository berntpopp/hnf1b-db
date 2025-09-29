"""Reusable clinical query patterns using type-safe SQLAlchemy.

Follows DRY/SOLID/KISS principles.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, and_, case, func, literal_column, not_, or_, select
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
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
            Phenopacket.phenopacket["subject"]["timeAtLastEncounter"]["age"][
                "iso8601duration"
            ].astext.label("age"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket,
                "$.phenotypicFeatures[*]",
            ).label("features"),
        ).select_from(Phenopacket)

        # Build JSONB conditions using SQLAlchemy functions
        conditions = []

        # Check for HPO terms existence
        hpo_condition = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            "$.phenotypicFeatures[*] ? (@.type.id == $hpo)",
            func.jsonb_build_object("hpo", func.any_(hpo_terms)),
        )

        # Check for non-excluded features
        excluded_condition = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            "$.phenotypicFeatures[*] ? (@.excluded != true)",
        )

        conditions.extend([hpo_condition, excluded_condition])

        # Add stage filtering if specified
        if stage:
            stage_condition = func.jsonb_path_exists(
                Phenopacket.phenopacket,
                (
                    '$.phenotypicFeatures[*].modifiers[*] ?'
                    f' (@.label like_regex "Stage {stage}")'
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
                '$.medicalActions[*].procedure ? (@.code.id == "NCIT:C157952")',
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
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
        ]

        # Extract features matching the HPO terms
        feature_expr = func.jsonb_path_query_first(
            Phenopacket.phenopacket,
            "$.phenotypicFeatures[*] ? (@.type.id == $hpo)",
            func.jsonb_build_object("hpo", func.any_(hpo_terms)),
        )

        columns.append(feature_expr["type"]["label"].astext.label("feature_label"))

        if include_onset:
            columns.append(
                feature_expr["onset"]["age"]["iso8601duration"].astext.label(
                    "onset_age"
                )
            )

        if include_modifiers:
            columns.append(
                func.jsonb_array_elements(feature_expr["modifiers"]).label("modifiers")
            )

        query = select(*columns).select_from(Phenopacket)

        # Add existence check
        query = query.where(
            func.jsonb_path_exists(
                Phenopacket.phenopacket,
                "$.phenotypicFeatures[*] ? (@.type.id == $hpo && @.excluded != true)",
                func.jsonb_build_object("hpo", func.any_(hpo_terms)),
            )
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
        return query.where(Phenopacket.phenopacket["subject"]["sex"].astext == sex)

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
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket, "$.diseases[*]"
            ).label("diseases"),
        ).select_from(Phenopacket)

        conditions = []

        # Check for disease IDs
        if disease_terms:
            id_condition = func.jsonb_path_exists(
                Phenopacket.phenopacket,
                "$.diseases[*] ? (@.term.id == $id)",
                func.jsonb_build_object("id", func.any_(disease_terms)),
            )
            conditions.append(id_condition)

        # Check for disease labels
        if disease_labels:
            for label in disease_labels:
                label_condition = func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    f'$.diseases[*] ? (@.term.label like_regex "{label}")',
                )
                conditions.append(label_condition)

        if conditions:
            query = query.where(or_(*conditions))

        return query

    @staticmethod
    def get_measurement_cases(
        loinc_codes: List[str],
        interpretation_hpo: Optional[str] = None
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
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket,
                '$.measurements[*] ? (@.assay.id == $loinc)',
                func.jsonb_build_object("loinc", func.any_(loinc_codes))
            ).label("measurements"),
        ).select_from(Phenopacket)

        # Base condition for LOINC codes
        base_condition = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            "$.measurements[*] ? (@.assay.id == $loinc)",
            func.jsonb_build_object("loinc", func.any_(loinc_codes)),
        )

        conditions = [base_condition]

        # Add interpretation filter if provided
        if interpretation_hpo:
            interpretation_condition = func.jsonb_path_exists(
                Phenopacket.phenopacket,
                f'$.measurements[*] ? (@.interpretation.id == "{interpretation_hpo}")',
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
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
            func.jsonb_path_query_array(
                Phenopacket.phenopacket,
                "$.phenotypicFeatures[*] ? (@.type.id == $hpo)",
                func.jsonb_build_object("hpo", func.any_(hpo_terms)),
            ).label("morphology_features"),
        ).select_from(Phenopacket)

        # Add existence condition
        query = query.where(
            func.jsonb_path_exists(
                Phenopacket.phenopacket,
                "$.phenotypicFeatures[*] ? (@.type.id == $hpo)",
                func.jsonb_build_object("hpo", func.any_(hpo_terms)),
            )
        )

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
            '$.phenotypicFeatures[*] ? (@.type.id like_regex "^HP:00126")'
        )

        genital_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            (
                '$.phenotypicFeatures[*] ?'
                ' (@.type.id == "HP:0000078" || @.type.id == "HP:0000079")'
            )
        )

        pancreatic_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            (
                '$.phenotypicFeatures[*] ?'
                ' (@.type.id == "HP:0001732" || @.type.id == "HP:0001738")'
            )
        )

        liver_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            '$.phenotypicFeatures[*] ? (@.type.id like_regex "^HP:00013")'
        )

        metabolic_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            '$.phenotypicFeatures[*] ? (@.type.id == "HP:0002917")'
        )

        endocrine_check = func.jsonb_path_exists(
            Phenopacket.phenopacket,
            '$.diseases[*] ? (@.term.label like_regex "diabetes")'
        )

        # Count systems
        system_count = (
            func.cast(renal_check, Integer) +
            func.cast(genital_check, Integer) +
            func.cast(pancreatic_check, Integer) +
            func.cast(liver_check, Integer) +
            func.cast(metabolic_check, Integer) +
            func.cast(endocrine_check, Integer)
        )

        # Build query
        query = select(
            Phenopacket.phenopacket_id,
            Phenopacket.phenopacket["subject"]["id"].astext.label("subject_id"),
            Phenopacket.phenopacket["subject"]["sex"].astext.label("sex"),
            system_count.label("system_count"),
            func.json_build_array(
                case((renal_check, literal_column("'renal'"))),
                case((genital_check, literal_column("'genital'"))),
                case((pancreatic_check, literal_column("'pancreatic'"))),
                case((liver_check, literal_column("'liver'"))),
                case((metabolic_check, literal_column("'metabolic'"))),
                case((endocrine_check, literal_column("'endocrine'")))
            ).label("affected_systems")
        ).select_from(Phenopacket).where(system_count >= min_systems)

        return query

    @staticmethod
    async def execute_and_format(
        db: AsyncSession,
        query: Select,
        format_func: Optional[callable] = None
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
