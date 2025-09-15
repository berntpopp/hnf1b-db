"""Clinical feature-specific query endpoints for phenopackets."""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/v2/clinical", tags=["clinical-features"])


@router.get("/renal-insufficiency")
async def get_renal_insufficiency_cases(
    stage: Optional[str] = Query(None, description="Filter by CKD stage (e.g., '3', '4', '5')"),
    include_transplant: Optional[bool] = Query(None, description="Include transplant cases"),
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with renal insufficiency, optionally filtered by stage."""
    base_query = """
    SELECT DISTINCT
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        p.phenopacket->'subject'->'timeAtLastEncounter'->'age'->>'iso8601duration' as age,
        feature->'type'->>'label' as feature_label,
        feature->'onset'->'age'->>'iso8601duration' as onset_age,
        jsonb_agg(DISTINCT modifier->>'label') as modifiers
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
        LEFT JOIN LATERAL jsonb_array_elements(COALESCE(feature->'modifiers', '[]'::jsonb)) as modifier ON true
    WHERE 
        feature->'type'->>'id' IN ('HP:0012622', 'HP:0012623', 'HP:0012624', 
                                   'HP:0012625', 'HP:0012626', 'HP:0003774')
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    """

    conditions = []
    if stage:
        conditions.append(f"modifier->>'label' LIKE '%Stage {stage}%'")

    if include_transplant is False:
        # Exclude transplant cases by checking medical actions
        conditions.append(
            """
            NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(p.phenopacket->'medicalActions') as action
                WHERE action->'procedure'->'code'->>'id' = 'NCIT:C157952'
            )
            """
        )

    if conditions:
        base_query += " AND " + " AND ".join(conditions)

    base_query += """
    GROUP BY 
        p.phenopacket_id, p.phenopacket, feature
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(base_query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "age": row.age,
            "feature": row.feature_label,
            "onset_age": row.onset_age,
            "modifiers": [m for m in row.modifiers if m],
        }
        for row in rows
    ]


@router.get("/genital-abnormalities")
async def get_genital_abnormalities(
    sex_filter: Optional[str] = Query(None, enum=["FEMALE", "MALE"], description="Filter by sex"),
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with genital tract abnormalities."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        feature->'type'->>'label' as abnormality_type,
        jsonb_agg(DISTINCT modifier->>'label') as specific_abnormalities
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
        LEFT JOIN LATERAL jsonb_array_elements(COALESCE(feature->'modifiers', '[]'::jsonb)) as modifier ON true
    WHERE 
        feature->'type'->>'id' IN ('HP:0000078', 'HP:0000079', 'HP:0000080', 
                                   'HP:0000119', 'HP:0000062', 'HP:0000008')
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    """

    if sex_filter:
        query += f" AND p.phenopacket->'subject'->>'sex' = '{sex_filter}'"

    query += """
    GROUP BY 
        p.phenopacket_id, p.phenopacket, feature
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "abnormality_type": row.abnormality_type,
            "specific_abnormalities": [a for a in row.specific_abnormalities if a],
        }
        for row in rows
    ]


@router.get("/diabetes")
async def get_diabetes_cases(
    diabetes_type: Optional[str] = Query(
        None,
        enum=["Type 1", "Type 2", "MODY"],
        description="Filter by diabetes type",
    ),
    with_complications: Optional[bool] = Query(None, description="Only cases with complications"),
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with diabetes."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        disease->'term'->>'label' as diabetes_type,
        disease->'onset'->'age'->>'iso8601duration' as onset_age,
        jsonb_agg(DISTINCT stage->>'label') as disease_stages,
        (
            SELECT jsonb_agg(DISTINCT action->'treatment'->'agent'->>'label')
            FROM jsonb_array_elements(p.phenopacket->'medicalActions') as action
            WHERE action->'treatmentTarget'->>'id' LIKE '%diabetes%'
        ) as treatments
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'diseases') as disease
        LEFT JOIN LATERAL jsonb_array_elements(COALESCE(disease->'diseaseStage', '[]'::jsonb)) as stage ON true
    WHERE 
        (disease->'term'->>'label' ILIKE '%diabetes%'
         OR disease->'term'->>'id' IN ('MONDO:0005147', 'MONDO:0005148', 'MONDO:0015967'))
    """

    if diabetes_type:
        type_mapping = {
            "Type 1": "MONDO:0005147",
            "Type 2": "MONDO:0005148",
            "MODY": "MONDO:0015967",
        }
        if diabetes_type in type_mapping:
            query += f" AND disease->'term'->>'id' = '{type_mapping[diabetes_type]}'"

    if with_complications:
        query += """
        AND EXISTS (
            SELECT 1 FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as f
            WHERE f->'type'->>'id' IN ('HP:0000083', 'HP:0000820', 'HP:0100512')
        )
        """

    query += """
    GROUP BY 
        p.phenopacket_id, p.phenopacket, disease
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "diabetes_type": row.diabetes_type,
            "onset_age": row.onset_age,
            "disease_stages": [s for s in row.disease_stages if s],
            "treatments": row.treatments or [],
        }
        for row in rows
    ]


@router.get("/hypomagnesemia")
async def get_hypomagnesemia_cases(
    with_measurements: Optional[bool] = Query(None, description="Only cases with measurements"),
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with hypomagnesemia."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        feature->'type'->>'label' as feature_label,
        (
            SELECT jsonb_agg(jsonb_build_object(
                'assay', m->'assay'->>'label',
                'value', m->'value'->'quantity'->>'value',
                'unit', m->'value'->'quantity'->'unit'->>'label',
                'timestamp', m->'timeObserved'->>'timestamp'
            ))
            FROM jsonb_array_elements(p.phenopacket->'measurements') as m
            WHERE m->'assay'->>'id' = 'LOINC:2601-3'
               OR m->'interpretation'->>'id' = 'HP:0002917'
        ) as magnesium_measurements
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' = 'HP:0002917'
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    """

    if with_measurements:
        query += """
        AND EXISTS (
            SELECT 1 FROM jsonb_array_elements(p.phenopacket->'measurements') as m
            WHERE m->'assay'->>'id' = 'LOINC:2601-3'
        )
        """

    query += """
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "feature": row.feature_label,
            "magnesium_measurements": row.magnesium_measurements or [],
        }
        for row in rows
    ]


@router.get("/pancreatic-abnormalities")
async def get_pancreatic_abnormalities(
    include_diabetes: Optional[bool] = Query(True, description="Include cases with diabetes"),
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with pancreatic abnormalities."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        jsonb_agg(DISTINCT feature->'type'->>'label') as pancreatic_features,
        EXISTS(
            SELECT 1 FROM jsonb_array_elements(p.phenopacket->'diseases') as d
            WHERE d->'term'->>'label' ILIKE '%diabetes%'
        ) as has_diabetes,
        EXISTS(
            SELECT 1 FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as f
            WHERE f->'type'->>'id' = 'HP:0001738'
        ) as has_exocrine_insufficiency
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' IN ('HP:0001732', 'HP:0001733', 'HP:0001738', 
                                   'HP:0001735', 'HP:0001744', 'HP:0100027')
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    """

    if not include_diabetes:
        query += """
        AND NOT EXISTS(
            SELECT 1 FROM jsonb_array_elements(p.phenopacket->'diseases') as d
            WHERE d->'term'->>'label' ILIKE '%diabetes%'
        )
        """

    query += """
    GROUP BY 
        p.phenopacket_id, p.phenopacket
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "pancreatic_features": row.pancreatic_features,
            "has_diabetes": row.has_diabetes,
            "has_exocrine_insufficiency": row.has_exocrine_insufficiency,
        }
        for row in rows
    ]


@router.get("/liver-abnormalities")
async def get_liver_abnormalities(
    db: AsyncSession = Depends(get_db),
):
    """Get all cases with liver abnormalities."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        jsonb_agg(DISTINCT feature->'type'->>'label') as liver_features,
        (
            SELECT jsonb_agg(DISTINCT m->'assay'->>'label')
            FROM jsonb_array_elements(p.phenopacket->'measurements') as m
            WHERE m->'assay'->>'id' IN ('LOINC:1742-6', 'LOINC:1920-8', 
                                        'LOINC:6768-6', 'LOINC:1975-2')
        ) as liver_function_tests
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' IN ('HP:0001392', 'HP:0001394', 'HP:0001395', 
                                   'HP:0001396', 'HP:0001397', 'HP:0001399',
                                   'HP:0002240', 'HP:0001410')
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    GROUP BY 
        p.phenopacket_id, p.phenopacket
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "liver_features": row.liver_features,
            "liver_function_tests": row.liver_function_tests or [],
        }
        for row in rows
    ]


@router.get("/kidney-morphology")
async def get_kidney_morphology(
    morphology_type: Optional[str] = Query(
        None,
        description="Filter by morphology type (cysts, dysplasia, hypoplasia)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get cases with kidney morphological abnormalities."""
    query = """
    SELECT 
        p.phenopacket_id,
        p.phenopacket->'subject'->>'id' as subject_id,
        p.phenopacket->'subject'->>'sex' as sex,
        jsonb_agg(DISTINCT jsonb_build_object(
            'type', feature->'type'->>'label',
            'id', feature->'type'->>'id',
            'excluded', COALESCE((feature->>'excluded')::boolean, false)
        )) as morphology_features
    FROM 
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' IN (
            'HP:0100611',  -- Multiple glomerular cysts
            'HP:0004719',  -- Oligomeganephronia
            'HP:0000110',  -- Renal dysplasia
            'HP:0000089',  -- Renal hypoplasia
            'HP:0000107',  -- Renal cysts
            'HP:0000003',  -- Multicystic kidney dysplasia
            'HP:0000113'   -- Polycystic kidneys
        )
    """

    if morphology_type:
        type_mapping = {
            "cysts": ["HP:0100611", "HP:0000107", "HP:0000113"],
            "dysplasia": ["HP:0000110", "HP:0000003"],
            "hypoplasia": ["HP:0000089", "HP:0004719"],
        }
        if morphology_type.lower() in type_mapping:
            ids = "','".join(type_mapping[morphology_type.lower()])
            query += f" AND feature->'type'->>'id' IN ('{ids}')"

    query += """
    GROUP BY 
        p.phenopacket_id, p.phenopacket
    ORDER BY 
        p.phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "morphology_features": row.morphology_features,
        }
        for row in rows
    ]


@router.get("/multisystem-involvement")
async def get_multisystem_involvement(
    min_systems: int = Query(2, ge=2, le=10, description="Minimum number of systems involved"),
    db: AsyncSession = Depends(get_db),
):
    """Get cases with multiple system involvement."""
    query = f"""
    WITH system_involvement AS (
        SELECT 
            p.phenopacket_id,
            p.phenopacket->'subject'->>'id' as subject_id,
            p.phenopacket->'subject'->>'sex' as sex,
            COUNT(DISTINCT 
                CASE 
                    WHEN feature->'type'->>'id' LIKE 'HP:00126%' THEN 'renal'
                    WHEN feature->'type'->>'id' LIKE 'HP:00000%' AND 
                         feature->'type'->>'id' IN ('HP:0000078', 'HP:0000079') THEN 'genital'
                    WHEN feature->'type'->>'id' IN ('HP:0001732', 'HP:0001738') THEN 'pancreatic'
                    WHEN feature->'type'->>'id' LIKE 'HP:00013%' THEN 'liver'
                    WHEN feature->'type'->>'id' = 'HP:0002917' THEN 'metabolic'
                    WHEN disease->'term'->>'label' ILIKE '%diabetes%' THEN 'endocrine'
                END
            ) as system_count,
            jsonb_agg(DISTINCT 
                CASE 
                    WHEN feature->'type'->>'id' LIKE 'HP:00126%' THEN 'renal'
                    WHEN feature->'type'->>'id' IN ('HP:0000078', 'HP:0000079') THEN 'genital'
                    WHEN feature->'type'->>'id' IN ('HP:0001732', 'HP:0001738') THEN 'pancreatic'
                    WHEN feature->'type'->>'id' LIKE 'HP:00013%' THEN 'liver'
                    WHEN feature->'type'->>'id' = 'HP:0002917' THEN 'metabolic'
                END
            ) FILTER (WHERE feature IS NOT NULL) as affected_systems
        FROM 
            phenopackets p
            LEFT JOIN LATERAL jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature 
                ON NOT COALESCE((feature->>'excluded')::boolean, false)
            LEFT JOIN LATERAL jsonb_array_elements(p.phenopacket->'diseases') as disease ON true
        GROUP BY 
            p.phenopacket_id, p.phenopacket
    )
    SELECT * FROM system_involvement
    WHERE system_count >= {min_systems}
    ORDER BY system_count DESC, phenopacket_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "subject_id": row.subject_id,
            "sex": row.sex,
            "system_count": row.system_count,
            "affected_systems": [s for s in row.affected_systems if s],
        }
        for row in rows
    ]