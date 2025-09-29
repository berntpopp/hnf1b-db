"""Clinical feature-specific query endpoints for phenopackets."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.phenopackets.clinical_queries import ClinicalQueries
from app.phenopackets.models import Phenopacket

router = APIRouter(prefix="/api/v2/clinical", tags=["clinical-features"])


@router.get("/renal-insufficiency")
async def get_renal_insufficiency_cases(
    stage: Optional[str] = Query(
        None, description="Filter by CKD stage (e.g., '3', '4', '5')"
    ),
    include_transplant: Optional[bool] = Query(
        None, description="Include transplant cases"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with renal insufficiency, optionally filtered by stage."""
    # Renal insufficiency HPO terms
    hpo_terms = ['HP:0012622', 'HP:0012623', 'HP:0012624',
                 'HP:0012625', 'HP:0012626', 'HP:0003774']

    # Build query using reusable components
    query = ClinicalQueries.get_clinical_features_with_details(
        hpo_terms, include_modifiers=True, include_onset=True
    )

    # Apply transplant filtering if specified
    if include_transplant is False:
        query = ClinicalQueries.exclude_transplant_cases(query)

    # Execute and format results
    def format_row(row):
        return {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "feature": row.feature_label if hasattr(row, 'feature_label') else None,
            "onset_age": row.onset_age if hasattr(row, 'onset_age') else None,
            "modifiers": row.modifiers if hasattr(row, 'modifiers') else [],
        }

    return await ClinicalQueries.execute_and_format(db, query, format_row)


@router.get("/genital-abnormalities")
async def get_genital_abnormalities(
    sex_filter: Optional[str] = Query(
        None, enum=["FEMALE", "MALE"], description="Filter by sex"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with genital tract abnormalities."""
    # Genital abnormality HPO terms
    hpo_terms = ['HP:0000078', 'HP:0000079', 'HP:0000080',
                 'HP:0000119', 'HP:0000062', 'HP:0000008']

    # Build query using reusable components
    query = ClinicalQueries.get_clinical_features_with_details(
        hpo_terms, include_modifiers=True, include_onset=False
    )

    # Apply sex filter if specified
    if sex_filter:
        query = ClinicalQueries.filter_by_sex(query, sex_filter)

    # Execute and format results
    def format_row(row):
        return {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "abnormality_type": (
                row.feature_label if hasattr(row, 'feature_label') else None
            ),
            "specific_abnormalities": (
                row.modifiers if hasattr(row, 'modifiers') else []
            ),
        }

    return await ClinicalQueries.execute_and_format(db, query, format_row)


@router.get("/diabetes")
async def get_diabetes_cases(
    diabetes_type: Optional[str] = Query(
        None,
        enum=["Type 1", "Type 2", "MODY"],
        description="Filter by diabetes type",
    ),
    with_complications: Optional[bool] = Query(
        None, description="Only cases with complications"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with diabetes."""
    # Diabetes MONDO IDs
    type_mapping = {
        "Type 1": "MONDO:0005147",
        "Type 2": "MONDO:0005148",
        "MODY": "MONDO:0015967",
    }

    # Build disease terms based on filter
    if diabetes_type and diabetes_type in type_mapping:
        disease_terms = [type_mapping[diabetes_type]]
    else:
        disease_terms = list(type_mapping.values())

    # Build query using reusable components
    query = ClinicalQueries.get_disease_cases(
        disease_terms, disease_labels=["diabetes"]
    )

    # Add complications filter if specified
    if with_complications:
        # Use phenotype query for complications
        complication_hpo = ['HP:0000083', 'HP:0000820', 'HP:0100512']
        from app.phenopackets.models import Phenopacket as P2

        complication_exists = exists(
            select(1).where(
                and_(
                    P2.phenopacket_id == Phenopacket.phenopacket_id,
                    func.jsonb_path_exists(
                        P2.phenopacket,
                        "$.phenotypicFeatures[*] ? (@.type.id == $hpo)",
                        func.jsonb_build_object("hpo", func.any_(complication_hpo))
                    )
                )
            )
        )
        query = query.where(complication_exists)

    # Execute and format results
    result = await db.execute(query)
    rows = result.fetchall()

    formatted_results = []
    for row in rows:
        diseases = row.diseases if hasattr(row, 'diseases') and row.diseases else []
        for disease in diseases:
            formatted_results.append({
                "phenopacket_id": row.phenopacket_id,
                "subject_id": row.subject_id,
                "sex": row.sex,
                "diabetes_type": disease.get('term', {}).get('label'),
                "onset_age": (
                    disease.get('onset', {})
                    .get('age', {})
                    .get('iso8601duration')
                ),
                "disease_stages": [
                    s.get('label') for s in disease.get('diseaseStage', [])
                ],
                "treatments": [],  # Would need separate query for treatments
            })

    return formatted_results


@router.get("/hypomagnesemia")
async def get_hypomagnesemia_cases(
    with_measurements: Optional[bool] = Query(
        None, description="Only cases with measurements"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with hypomagnesemia."""
    # Build combined query for phenotype and measurements
    hpo_term = ['HP:0002917']  # Hypomagnesemia
    loinc_code = ['LOINC:2601-3']  # Magnesium measurement

    # Get phenotype features
    phenotype_query = ClinicalQueries.get_phenotype_features_query(hpo_term)

    if with_measurements:
        # Add measurement filter
        measurement_query = ClinicalQueries.get_measurement_cases(
            loinc_code, interpretation_hpo='HP:0002917'
        )
        # Combine queries with intersection
        query = phenotype_query.intersect(measurement_query)
    else:
        query = phenotype_query

    # Execute query
    result = await db.execute(query)
    rows = result.fetchall()

    # Format results with measurements if available
    formatted_results = []
    for row in rows:
        # Get measurements separately if needed
        measurements = []
        if hasattr(row, 'measurements') and row.measurements:
            for m in row.measurements:
                measurements.append({
                    'assay': m.get('assay', {}).get('label'),
                    'value': m.get('value', {}).get('quantity', {}).get('value'),
                    'unit': (
                        m.get('value', {})
                        .get('quantity', {})
                        .get('unit', {})
                        .get('label')
                    ),
                    'timestamp': m.get('timeObserved', {}).get('timestamp')
                })

        formatted_results.append({
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "feature": "Hypomagnesemia",
            "magnesium_measurements": measurements,
        })

    return formatted_results


@router.get("/pancreatic-abnormalities")
async def get_pancreatic_abnormalities(
    include_diabetes: Optional[bool] = Query(
        True, description="Include cases with diabetes"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with pancreatic abnormalities."""
    # Pancreatic abnormality HPO terms
    hpo_terms = ['HP:0001732', 'HP:0001733', 'HP:0001738',
                 'HP:0001735', 'HP:0001744', 'HP:0100027']

    # Build query using reusable components
    query = ClinicalQueries.get_phenotype_features_query(hpo_terms)

    # Exclude diabetes cases if specified
    if not include_diabetes:
        diabetes_exclusion = not_(
            func.jsonb_path_exists(
                Phenopacket.phenopacket,
                '$.diseases[*] ? (@.term.label like_regex "diabetes")',
            )
        )
        query = query.where(diabetes_exclusion)

    # Execute and format results
    result = await db.execute(query)
    rows = result.fetchall()

    formatted_results = []
    for row in rows:
        # Check for diabetes and exocrine insufficiency

        # Quick check queries
        diabetes_check = await db.scalar(
            select(func.jsonb_path_exists(
                Phenopacket.phenopacket,
                '$.diseases[*] ? (@.term.label like_regex "diabetes")',
            )).where(Phenopacket.phenopacket_id == row.phenopacket_id)
        )

        exocrine_check = await db.scalar(
            select(func.jsonb_path_exists(
                Phenopacket.phenopacket,
                '$.phenotypicFeatures[*] ? (@.type.id == "HP:0001738")',
            )).where(Phenopacket.phenopacket_id == row.phenopacket_id)
        )

        features = row.features if hasattr(row, 'features') else []
        feature_labels = [f.get('type', {}).get('label') for f in features if f]

        formatted_results.append({
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "pancreatic_features": feature_labels,
            "has_diabetes": diabetes_check or False,
            "has_exocrine_insufficiency": exocrine_check or False,
        })

    return formatted_results


@router.get("/liver-abnormalities")
async def get_liver_abnormalities(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get all cases with liver abnormalities."""
    # Liver abnormality HPO terms
    hpo_terms = ['HP:0001392', 'HP:0001394', 'HP:0001395',
                 'HP:0001396', 'HP:0001397', 'HP:0001399',
                 'HP:0002240', 'HP:0001410']

    # Liver function test LOINC codes
    lft_loinc = ['LOINC:1742-6', 'LOINC:1920-8', 'LOINC:6768-6', 'LOINC:1975-2']

    # Build query using reusable components
    query = ClinicalQueries.get_phenotype_features_query(hpo_terms)

    # Execute main query
    result = await db.execute(query)
    rows = result.fetchall()

    formatted_results = []
    for row in rows:
        # Get liver function tests separately

        lft_result = await db.scalar(
            select(
                func.jsonb_path_query_array(
                    Phenopacket.phenopacket,
                    '$.measurements[*] ? (@.assay.id == $loinc)',
                    func.jsonb_build_object('loinc', func.any_(lft_loinc))
                )
            ).where(Phenopacket.phenopacket_id == row.phenopacket_id)
        )

        lft_labels = []
        if lft_result:
            lft_labels = [m.get('assay', {}).get('label') for m in lft_result if m]

        features = row.features if hasattr(row, 'features') else []
        feature_labels = [f.get('type', {}).get('label') for f in features if f]

        formatted_results.append({
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "liver_features": feature_labels,
            "liver_function_tests": lft_labels,
        })

    return formatted_results


@router.get("/kidney-morphology")
async def get_kidney_morphology(
    morphology_type: Optional[str] = Query(
        None,
        description="Filter by morphology type (cysts, dysplasia, hypoplasia)",
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get cases with kidney morphological abnormalities."""
    # Use reusable morphology query
    query = ClinicalQueries.get_morphology_features(morphology_type)

    # Execute and format results
    result = await db.execute(query)
    rows = result.fetchall()

    formatted_results = []
    for row in rows:
        features = (
            row.morphology_features
            if hasattr(row, 'morphology_features')
            else []
        )
        feature_objects = []
        for f in features:
            if f:
                feature_objects.append({
                    'type': f.get('type', {}).get('label'),
                    'id': f.get('type', {}).get('id'),
                    'excluded': f.get('excluded', False)
                })

        formatted_results.append({
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "morphology_features": feature_objects,
        })

    return formatted_results


@router.get("/multisystem-involvement")
async def get_multisystem_involvement(
    min_systems: int = Query(
        2, ge=2, le=10, description="Minimum number of systems involved"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get cases with multiple system involvement."""
    # Use reusable multisystem query
    query = ClinicalQueries.get_multisystem_involvement(min_systems)

    # Execute and format results
    result = await db.execute(query)
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "system_count": row.system_count,
            "affected_systems": (
                [s for s in row.affected_systems if s]
                if hasattr(row, 'affected_systems')
                else []
            ),
        }
        for row in rows
    ]
