"""Survival analysis endpoint for phenopackets.

Provides Kaplan-Meier survival analysis with multiple comparison strategies.
Supports variant type, pathogenicity, and disease subtype comparisons.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


# HPO term constants for disease classification
CAKUT_HPO_TERMS = [
    "HP:0000003",  # Multicystic kidney dysplasia
    "HP:0000122",  # Unilateral renal agenesis
    "HP:0000089",  # Renal hypoplasia
    "HP:0012210",  # Abnormal renal morphology
]

GENITAL_HPO = "HP:0000078"  # Abnormality of the genital system

ANY_KIDNEY_HPO_TERMS = [
    "HP:0012622",  # Chronic kidney disease (unspecified)
    "HP:0012623",  # Stage 1 chronic kidney disease
    "HP:0012624",  # Stage 2 chronic kidney disease
    "HP:0012625",  # Stage 3 chronic kidney disease
    "HP:0012626",  # Stage 4 chronic kidney disease
    "HP:0003774",  # Stage 5 chronic kidney disease
    "HP:0000003",  # Multicystic kidney dysplasia
    "HP:0000089",  # Renal hypoplasia
    "HP:0000107",  # Renal cyst
    "HP:0000122",  # Unilateral renal agenesis
    "HP:0012210",  # Abnormal renal morphology
    "HP:0033133",  # Renal cortical hyperechogenicity
    "HP:0000108",  # Multiple glomerular cysts
    "HP:0001970",  # Oligomeganephronia
]

MODY_HPO = "HP:0004904"  # Maturity-onset diabetes of the young

CKD_STAGE_HPO_TERMS = [
    "HP:0012622",  # Chronic kidney disease (unspecified)
    "HP:0012623",  # Stage 1 CKD
    "HP:0012624",  # Stage 2 CKD
    "HP:0012625",  # Stage 3 CKD
    "HP:0012626",  # Stage 4 CKD
    "HP:0003774",  # Stage 5 CKD
]

KIDNEY_FAILURE_HPO_TERMS = ["HP:0012626", "HP:0003774"]  # Stage 4 and Stage 5 CKD


# Endpoint configuration
ENDPOINT_CONFIG: Dict[str, Dict[str, Any]] = {
    "ckd_stage_3_plus": {
        "hpo_terms": [
            "HP:0012625",  # Stage 3 CKD
            "HP:0012626",  # Stage 4 CKD
            "HP:0003774",  # Stage 5 CKD
        ],
        "label": "CKD Stage 3+ (GFR <60)",
    },
    "stage_5_ckd": {
        "hpo_terms": ["HP:0003774"],  # Stage 5 CKD
        "label": "Stage 5 CKD (ESRD)",
    },
    "any_ckd": {
        "hpo_terms": CKD_STAGE_HPO_TERMS,
        "label": "Any CKD",
    },
    "current_age": {
        "hpo_terms": None,  # Special case: use current age
        "label": "Age at Last Follow-up",
    },
}


# JSONB path constants for SQL queries (DRY)
_VD_BASE = (
    "diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor"
)
_VD_ID = "interp.value#>>'{" + _VD_BASE + ",id}'"
_VD_EXT = "interp.value#>'{" + _VD_BASE + ",extensions}'"
_VD_EXPR = "interp.value#>'{" + _VD_BASE + ",expressions}'"
# Subject age path (used in survival queries)
_CURRENT_AGE = "p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration'"
# Interpretation status path (used for P/LP filtering)
_INTERP_STATUS = (
    "interp.value->'diagnosis'->'genomicInterpretations'"
    "->0->>'interpretationStatus'"
)

# SQL fragment for variant type classification (CNV vs Truncating vs Non-truncating)
# fmt: off
VARIANT_TYPE_CLASSIFICATION_SQL = f"""
CASE
    -- CNVs: Large deletions or duplications >= 50kb
    WHEN {_VD_ID} ~ ':(DEL|DUP)'
        AND COALESCE(
            (SELECT (ext#>>'{{value,length}}')::bigint
             FROM jsonb_array_elements({_VD_EXT}) AS ext
             WHERE ext->>'name' = 'coordinates'
            ), 0) >= 50000
        THEN 'CNV'
    -- Non-truncating: VEP IMPACT = MODERATE
    WHEN EXISTS (
        SELECT 1
        FROM jsonb_array_elements({_VD_EXT}) AS ext
        WHERE ext->>'name' = 'vep_annotation'
          AND ext#>>'{{value,impact}}' = 'MODERATE'
    ) THEN 'Non-truncating'
    -- Truncating variants
    WHEN (
        -- Intragenic deletions/duplications < 50kb
        (
            {_VD_ID} ~ ':(DEL|DUP)'
            AND COALESCE(
                (SELECT (ext#>>'{{value,length}}')::bigint
                 FROM jsonb_array_elements({_VD_EXT}) AS ext
                 WHERE ext->>'name' = 'coordinates'
                ), 0) < 50000
        )
        OR
        -- VEP IMPACT = HIGH
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({_VD_EXT}) AS ext
            WHERE ext->>'name' = 'vep_annotation'
              AND ext#>>'{{value,impact}}' = 'HIGH'
        )
        OR
        -- VEP IMPACT = LOW/MODIFIER (P/LP filtered)
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({_VD_EXT}) AS ext
            WHERE ext->>'name' = 'vep_annotation'
              AND ext#>>'{{value,impact}}' IN ('LOW', 'MODIFIER')
        )
        OR
        -- No VEP and not DEL/DUP (P/LP filtered)
        (
            NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements({_VD_EXT}) AS ext
                WHERE ext->>'name' = 'vep_annotation'
            )
            AND NOT {_VD_ID} ~ ':(DEL|DUP)'
        )
        OR
        -- HGVS pattern fallback
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({_VD_EXPR}) AS expr
            WHERE (
                (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                OR (expr->>'syntax' = 'hgvs.p'
                    AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
            )
        )
    ) THEN 'Truncating'
    ELSE 'Non-truncating'
END
"""
# fmt: on


def _calculate_survival_curves(
    groups: Dict[str, List[tuple]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Calculate Kaplan-Meier curves for all groups."""
    from app.phenopackets.survival_analysis import calculate_kaplan_meier

    survival_curves = {}
    for group_name, event_times in groups.items():
        if event_times:
            survival_curves[group_name] = calculate_kaplan_meier(event_times)
        else:
            survival_curves[group_name] = []
    return survival_curves


def _calculate_statistical_tests(
    groups: Dict[str, List[tuple]],
) -> List[Dict[str, Any]]:
    """Calculate pairwise log-rank tests with Bonferroni correction."""
    from app.phenopackets.survival_analysis import (
        apply_bonferroni_correction,
        calculate_log_rank_test,
    )

    statistical_tests = []
    group_names = [g for g in groups.keys() if groups[g]]

    for i in range(len(group_names)):
        for j in range(i + 1, len(group_names)):
            group1 = group_names[i]
            group2 = group_names[j]
            test_result = calculate_log_rank_test(groups[group1], groups[group2])
            statistical_tests.append(
                {
                    "group1": group1,
                    "group2": group2,
                    **test_result,
                }
            )

    return apply_bonferroni_correction(statistical_tests)


def _build_response(
    comparison_type: str,
    endpoint_label: str,
    groups: Dict[str, List[tuple]],
    survival_curves: Dict[str, List[Dict[str, Any]]],
    statistical_tests: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the standard survival analysis response."""
    return {
        "comparison_type": comparison_type,
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


async def _handle_variant_type_current_age(
    db: AsyncSession,
    endpoint_label: str,
) -> Dict[str, Any]:
    """Handle variant type comparison with current_age endpoint."""
    from app.phenopackets.survival_analysis import parse_iso8601_age

    query = f"""
    WITH variant_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
            {_CURRENT_AGE} as current_age,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_kidney_failure
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp
        WHERE p.deleted_at IS NULL
            AND {_CURRENT_AGE} IS NOT NULL
            AND {_INTERP_STATUS}
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN (
                    'HP:0012622', 'HP:0012623', 'HP:0012624',
                    'HP:0012625', 'HP:0012626', 'HP:0003774'
                )
            )
    )
    SELECT variant_group, current_age, has_kidney_failure
    FROM variant_classification
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {
        "CNV": [],
        "Truncating": [],
        "Non-truncating": [],
    }

    for row in rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.variant_group].append((current_age, row.has_kidney_failure))

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": (
            "Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"
        ),
        "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
        "censoring": (
            "Patients without kidney failure are censored at their last reported age"
        ),
        "group_definitions": {
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
        },
        "inclusion_criteria": (
            "Pathogenic (P) and Likely Pathogenic (LP) variants only. "
            "Requires CKD assessment data."
        ),
        "exclusion_criteria": "VUS, Likely Benign, and Benign variants excluded",
    }

    return _build_response(
        "variant_type",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


async def _handle_variant_type_standard(
    db: AsyncSession,
    endpoint_label: str,
    endpoint_hpo_terms: List[str],
) -> Dict[str, Any]:
    """Handle variant type comparison with standard CKD endpoint."""
    from app.phenopackets.survival_analysis import (
        parse_iso8601_age,
        parse_onset_ontology,
    )

    # Event cases query
    query = f"""
    WITH variant_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
            p.phenopacket as phenopacket_data
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp
        WHERE p.deleted_at IS NULL
            AND {_INTERP_STATUS}
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
    ),
    endpoint_cases AS (
        SELECT
            vc.phenopacket_id,
            vc.variant_group,
            vc.current_age,
            pf->'onset' as onset,
            pf->'onset'->>'age' as onset_age
        FROM variant_classification vc,
            jsonb_array_elements(vc.phenopacket_data->'phenotypicFeatures') as pf
        WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
            AND COALESCE((pf->>'excluded')::boolean, false) = false
    )
    SELECT variant_group, current_age, onset_age, onset
    FROM endpoint_cases
    """

    result = await db.execute(text(query), {"endpoint_hpo_terms": endpoint_hpo_terms})
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {
        "CNV": [],
        "Truncating": [],
        "Non-truncating": [],
    }

    for row in rows:
        onset_age = None
        if row.onset_age:
            onset_age = parse_iso8601_age(row.onset_age)
        elif row.onset:
            onset_age = parse_onset_ontology(dict(row.onset))

        if onset_age is not None:
            groups[row.variant_group].append((onset_age, True))

    # Censored cases query
    censored_query = f"""
    WITH variant_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            {VARIANT_TYPE_CLASSIFICATION_SQL} AS variant_group,
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp
        WHERE p.deleted_at IS NULL
            AND {_INTERP_STATUS}
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            )
            AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
    )
    SELECT variant_group, current_age
    FROM variant_classification
    """

    censored_result = await db.execute(
        text(censored_query), {"endpoint_hpo_terms": endpoint_hpo_terms}
    )
    censored_rows = censored_result.fetchall()

    for row in censored_rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.variant_group].append((current_age, False))

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": f"Onset of {endpoint_label}",
        "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
        "censoring": (
            "Patients without the endpoint phenotype are censored at their "
            "last reported age (timeAtLastEncounter)"
        ),
        "group_definitions": {
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
        },
        "inclusion_criteria": "Pathogenic (P) and Likely Pathogenic (LP) variants only",
        "exclusion_criteria": "VUS, Likely Benign, and Benign variants excluded",
    }

    return _build_response(
        "variant_type",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


async def _handle_pathogenicity_current_age(
    db: AsyncSession,
    endpoint_label: str,
) -> Dict[str, Any]:
    """Handle pathogenicity comparison with current_age endpoint."""
    from app.phenopackets.survival_analysis import parse_iso8601_age

    query = """
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
            {_CURRENT_AGE} as current_age,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_kidney_failure
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        WHERE p.deleted_at IS NULL
            AND {_CURRENT_AGE} IS NOT NULL
            AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN (
                    'HP:0012622', 'HP:0012623', 'HP:0012624',
                    'HP:0012625', 'HP:0012626', 'HP:0003774'
                )
            )
    )
    SELECT pathogenicity_group, current_age, has_kidney_failure
    FROM pathogenicity_classification
    WHERE pathogenicity_group IN ('P/LP', 'VUS')
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {"P/LP": [], "VUS": []}

    for row in rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.pathogenicity_group].append(
                (current_age, row.has_kidney_failure)
            )

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": (
            "Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"
        ),
        "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
        "censoring": (
            "Patients without kidney failure are censored at their last reported age"
        ),
        "group_definitions": {
            "P/LP": (
                "P/LP variants per ACMG/AMP guidelines"
            ),
            "VUS": (
                "Variants of Uncertain Significance - insufficient evidence "
                "to classify as pathogenic or benign"
            ),
        },
        "inclusion_criteria": "P/LP and VUS variants only. Requires CKD data.",
        "exclusion_criteria": (
            "CNVs excluded (lack standard ACMG classification). "
            "Likely Benign and Benign variants excluded."
        ),
    }

    return _build_response(
        "pathogenicity",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


async def _handle_pathogenicity_standard(
    db: AsyncSession,
    endpoint_label: str,
    endpoint_hpo_terms: List[str],
) -> Dict[str, Any]:
    """Handle pathogenicity comparison with standard CKD endpoint."""
    from app.phenopackets.survival_analysis import (
        parse_iso8601_age,
        parse_onset_ontology,
    )

    query = """
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
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
            p.phenopacket as phenopacket_data
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        WHERE p.deleted_at IS NULL
            AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN (
                    'HP:0012622', 'HP:0012623', 'HP:0012624',
                    'HP:0012625', 'HP:0012626', 'HP:0003774'
                )
            )
    ),
    endpoint_cases AS (
        SELECT
            pc.phenopacket_id,
            pc.pathogenicity_group,
            pc.current_age,
            pf->'onset' as onset,
            pf->'onset'->>'age' as onset_age
        FROM pathogenicity_classification pc,
            jsonb_array_elements(pc.phenopacket_data->'phenotypicFeatures') as pf
        WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
            AND COALESCE((pf->>'excluded')::boolean, false) = false
    )
    SELECT pathogenicity_group, current_age, onset_age, onset
    FROM endpoint_cases
    WHERE pathogenicity_group IN ('P/LP', 'VUS')
    """

    result = await db.execute(text(query), {"endpoint_hpo_terms": endpoint_hpo_terms})
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {"P/LP": [], "VUS": []}

    for row in rows:
        onset_age = None
        if row.onset_age:
            onset_age = parse_iso8601_age(row.onset_age)
        elif row.onset:
            onset_age = parse_onset_ontology(dict(row.onset))

        if onset_age is not None:
            groups[row.pathogenicity_group].append((onset_age, True))

    # Censored cases
    censored_query = """
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
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        WHERE p.deleted_at IS NULL
            AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN (
                    'HP:0012622', 'HP:0012623', 'HP:0012624',
                    'HP:0012625', 'HP:0012626', 'HP:0003774'
                )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            )
            AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
    )
    SELECT pathogenicity_group, current_age
    FROM pathogenicity_classification
    WHERE pathogenicity_group IN ('P/LP', 'VUS')
    """

    censored_result = await db.execute(
        text(censored_query), {"endpoint_hpo_terms": endpoint_hpo_terms}
    )
    censored_rows = censored_result.fetchall()

    for row in censored_rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.pathogenicity_group].append((current_age, False))

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": (
            "Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"
        ),
        "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
        "censoring": (
            "Patients without kidney failure are censored at their last reported age"
        ),
        "group_definitions": {
            "P/LP": (
                "P/LP variants per ACMG/AMP guidelines"
            ),
            "VUS": (
                "Variants of Uncertain Significance - insufficient evidence "
                "to classify as pathogenic or benign"
            ),
        },
        "inclusion_criteria": "P/LP and VUS variants only. Requires CKD data.",
        "exclusion_criteria": (
            "CNVs excluded (lack standard ACMG classification). "
            "Likely Benign and Benign variants excluded."
        ),
    }

    return _build_response(
        "pathogenicity",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


async def _handle_disease_subtype_current_age(
    db: AsyncSession,
    endpoint_label: str,
) -> Dict[str, Any]:
    """Handle disease subtype comparison with current_age endpoint."""
    from app.phenopackets.survival_analysis import parse_iso8601_age

    query = """
    WITH disease_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_direct_cakut,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :genital_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_genital,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_any_kidney,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :mody_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_mody,
            {_CURRENT_AGE} as current_age,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_kidney_failure
        FROM phenopackets p
        WHERE p.deleted_at IS NULL
            AND {_CURRENT_AGE} IS NOT NULL
    ),
    classified AS (
        SELECT
            phenopacket_id,
            current_age,
            has_kidney_failure,
            (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
            has_mody as is_mody
        FROM disease_classification
    )
    SELECT
        CASE
            WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
            WHEN is_cakut THEN 'CAKUT'
            WHEN is_mody THEN 'MODY'
            ELSE 'Other'
        END AS disease_group,
        current_age,
        has_kidney_failure
    FROM classified
    """

    result = await db.execute(
        text(query),
        {
            "cakut_hpo_terms": CAKUT_HPO_TERMS,
            "genital_hpo": GENITAL_HPO,
            "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
            "mody_hpo": MODY_HPO,
        },
    )
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {
        "CAKUT": [],
        "CAKUT/MODY": [],
        "MODY": [],
        "Other": [],
    }

    for row in rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.disease_group].append((current_age, row.has_kidney_failure))

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": (
            "Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"
        ),
        "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
        "censoring": (
            "Patients without kidney failure are censored at their last reported age"
        ),
        "group_definitions": {
            "CAKUT": (
                "Multicystic kidney dysplasia (HP:0000003), OR "
                "Unilateral renal agenesis (HP:0000122), OR "
                "Renal hypoplasia (HP:0000089), OR "
                "Abnormal renal morphology (HP:0012210), OR "
                "(Genital abnormality AND any kidney involvement)"
            ),
            "MODY": "Maturity-onset diabetes of the young (HP:0004904)",
            "CAKUT/MODY": "Meets criteria for both CAKUT and MODY",
            "Other": "Does not meet criteria for CAKUT or MODY",
        },
        "inclusion_criteria": "All patients with P/LP/VUS variants and reported age",
        "exclusion_criteria": "Likely Benign and Benign variants excluded",
    }

    return _build_response(
        "disease_subtype",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


async def _handle_disease_subtype_standard(
    db: AsyncSession,
    endpoint_label: str,
    endpoint_hpo_terms: List[str],
) -> Dict[str, Any]:
    """Handle disease subtype comparison with standard CKD endpoint."""
    from app.phenopackets.survival_analysis import (
        parse_iso8601_age,
        parse_onset_ontology,
    )

    query = """
    WITH disease_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_direct_cakut,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :genital_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_genital,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_any_kidney,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :mody_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_mody,
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
            p.phenopacket as phenopacket_data
        FROM phenopackets p
        WHERE p.deleted_at IS NULL
    ),
    classified AS (
        SELECT
            phenopacket_id,
            current_age,
            phenopacket_data,
            (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
            has_mody as is_mody
        FROM disease_classification
    ),
    with_disease_group AS (
        SELECT
            phenopacket_id,
            CASE
                WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
                WHEN is_cakut THEN 'CAKUT'
                WHEN is_mody THEN 'MODY'
                ELSE 'Other'
            END AS disease_group,
            current_age,
            phenopacket_data
        FROM classified
    ),
    endpoint_cases AS (
        SELECT
            dc.phenopacket_id,
            dc.disease_group,
            dc.current_age,
            pf->'onset' as onset,
            pf->'onset'->>'age' as onset_age
        FROM with_disease_group dc,
            jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') as pf
        WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
            AND COALESCE((pf->>'excluded')::boolean, false) = false
    )
    SELECT disease_group, current_age, onset_age, onset
    FROM endpoint_cases
    """

    result = await db.execute(
        text(query),
        {
            "cakut_hpo_terms": CAKUT_HPO_TERMS,
            "genital_hpo": GENITAL_HPO,
            "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
            "mody_hpo": MODY_HPO,
            "endpoint_hpo_terms": endpoint_hpo_terms,
        },
    )
    rows = result.fetchall()

    groups: Dict[str, List[tuple]] = {
        "CAKUT": [],
        "CAKUT/MODY": [],
        "MODY": [],
        "Other": [],
    }

    for row in rows:
        onset_age = None
        if row.onset_age:
            onset_age = parse_iso8601_age(row.onset_age)
        elif row.onset:
            onset_age = parse_onset_ontology(dict(row.onset))

        if onset_age is not None:
            groups[row.disease_group].append((onset_age, True))

    # Censored cases
    censored_query = """
    WITH disease_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_direct_cakut,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :genital_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_genital,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_any_kidney,
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = :mody_hpo
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            ) as has_mody,
            p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
        FROM phenopackets p
        WHERE p.deleted_at IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            )
            AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
    ),
    classified AS (
        SELECT
            phenopacket_id,
            current_age,
            (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
            has_mody as is_mody
        FROM disease_classification
    )
    SELECT
        CASE
            WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
            WHEN is_cakut THEN 'CAKUT'
            WHEN is_mody THEN 'MODY'
            ELSE 'Other'
        END AS disease_group,
        current_age
    FROM classified
    """

    censored_result = await db.execute(
        text(censored_query),
        {
            "cakut_hpo_terms": CAKUT_HPO_TERMS,
            "genital_hpo": GENITAL_HPO,
            "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
            "mody_hpo": MODY_HPO,
            "endpoint_hpo_terms": endpoint_hpo_terms,
        },
    )
    censored_rows = censored_result.fetchall()

    for row in censored_rows:
        current_age = parse_iso8601_age(row.current_age)
        if current_age is not None:
            groups[row.disease_group].append((current_age, False))

    survival_curves = _calculate_survival_curves(groups)
    statistical_tests = _calculate_statistical_tests(groups)

    metadata = {
        "event_definition": f"Onset of {endpoint_label}",
        "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
        "censoring": (
            "Patients without the endpoint phenotype are censored at their "
            "last reported age (timeAtLastEncounter)"
        ),
        "group_definitions": {
            "CAKUT": (
                "Multicystic kidney dysplasia (HP:0000003), OR "
                "Unilateral renal agenesis (HP:0000122), OR "
                "Renal hypoplasia (HP:0000089), OR "
                "Abnormal renal morphology (HP:0012210), OR "
                "(Genital abnormality AND any kidney involvement)"
            ),
            "MODY": "Maturity-onset diabetes of the young (HP:0004904)",
            "CAKUT/MODY": "Meets criteria for both CAKUT and MODY",
            "Other": "Does not meet criteria for CAKUT or MODY",
        },
        "inclusion_criteria": "All patients with P/LP/VUS variants",
        "exclusion_criteria": "Likely Benign and Benign variants excluded",
    }

    return _build_response(
        "disease_subtype",
        endpoint_label,
        groups,
        survival_curves,
        statistical_tests,
        metadata,
    )


@router.get("/survival-data", response_model=Dict[str, Any])
async def get_survival_data(
    comparison: str = Query(
        ...,
        description="Comparison type: variant_type, disease_subtype, or pathogenicity",
    ),
    endpoint: str = Query(
        "ckd_stage_3_plus",
        description=(
            "Clinical endpoint: ckd_stage_3_plus (default), "
            "stage_5_ckd, any_ckd, current_age"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get Kaplan-Meier survival data with configurable clinical endpoints.

    Compares survival curves using different grouping strategies:
    - variant_type: CNV vs Truncating vs Non-truncating
    - disease_subtype: CAKUT vs CAKUT+MODY vs MODY
    - pathogenicity: P/LP vs VUS vs LB

    Supports multiple clinical endpoints:
    - ckd_stage_3_plus: CKD Stage 3+ (GFR <60)
    - stage_5_ckd: Stage 5 CKD (ESRD)
    - any_ckd: Any CKD diagnosis
    - current_age: Age at last follow-up (universal endpoint)

    Returns:
        Survival curves with Kaplan-Meier estimates, 95% CIs, and log-rank tests
    """
    if endpoint not in ENDPOINT_CONFIG:
        valid_options = ", ".join(ENDPOINT_CONFIG.keys())
        raise ValueError(
            f"Unknown endpoint: {endpoint}. Valid options: {valid_options}"
        )

    config = ENDPOINT_CONFIG[endpoint]
    endpoint_hpo_terms: Optional[List[str]] = config["hpo_terms"]
    endpoint_label: str = config["label"]

    # Dispatch to appropriate handler based on comparison type and endpoint
    if comparison == "variant_type":
        if endpoint_hpo_terms is None:
            return await _handle_variant_type_current_age(db, endpoint_label)
        return await _handle_variant_type_standard(
            db, endpoint_label, endpoint_hpo_terms
        )

    elif comparison == "pathogenicity":
        if endpoint_hpo_terms is None:
            return await _handle_pathogenicity_current_age(db, endpoint_label)
        return await _handle_pathogenicity_standard(
            db, endpoint_label, endpoint_hpo_terms
        )

    elif comparison == "disease_subtype":
        if endpoint_hpo_terms is None:
            return await _handle_disease_subtype_current_age(db, endpoint_label)
        return await _handle_disease_subtype_standard(
            db, endpoint_label, endpoint_hpo_terms
        )

    else:
        raise ValueError(
            f"Unknown comparison type: {comparison}. "
            "Valid options: variant_type, disease_subtype, pathogenicity"
        )
