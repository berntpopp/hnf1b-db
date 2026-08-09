from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ontology.schemas import VocabularyItem, VocabularyResponse

router = APIRouter(prefix="/ontology", tags=["ontology"])


@router.get("/hpo/autocomplete")
async def hpo_autocomplete(
    q: str = Query(..., min_length=2, description="Search query for HPO terms"),
    limit: int = Query(
        10, ge=1, le=50, description="Maximum number of results to return"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Fast HPO term autocomplete with fuzzy matching.

    Uses trigram similarity for typo tolerance. Results are ranked by similarity
    score, then by the number of phenopackets associated with the term.

    The similarity threshold is set to 0.15 (down from default 0.3) to allow
    better fuzzy matching for typos and partial word matches.
    """
    # Set lower similarity threshold for better fuzzy matching
    # 0.15 allows matching of partial words (e.g., "magnesium" in "Hypomagnesemia")
    await db.execute(text("SET pg_trgm.similarity_threshold = 0.15"))

    query = text(
        """
        SELECT hpo_id, label, category, description, synonyms,
               recommendation, "group", phenopacket_count,
               similarity(label, :search_term) AS similarity_score
        FROM hpo_terms_lookup
        WHERE label ILIKE :prefix OR label % :search_term
        ORDER BY similarity_score DESC, phenopacket_count DESC
        LIMIT :limit
    """
    )

    result = await db.execute(
        query, {"search_term": q, "prefix": f"%{q}%", "limit": limit}
    )

    terms = result.fetchall()
    return {"data": [dict(row._mapping) for row in terms]}


@router.get("/hpo/grouped")
async def hpo_grouped(
    recommendation: str | None = Query(
        None, description="Filter by recommendation level (required, recommended)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get HPO terms grouped by organ system for phenotype curation UI.

    Returns all curated HNF1B-related HPO terms organized by anatomical/organ
    system groups. Used for building the system-grouped phenotype selection interface.

    Each term includes:
    - hpo_id: HPO identifier (e.g., HP:0000107)
    - label: Human-readable term name
    - group: Organ system (e.g., Kidney, Liver, Pancreas)
    - category: Specific subcategory
    - recommendation: Clinical recommendation level (required, recommended)
    - description: Detailed term description
    - phenopacket_count: Number of phenopackets with this term

    Returns data structure:
    {
        "groups": {
            "Kidney": [...terms...],
            "Liver": [...terms...],
            ...
        },
        "total_terms": N,
        "total_groups": M
    }
    """
    # Build query with optional recommendation filter
    where_clause = ""
    params = {}

    if recommendation:
        where_clause = "WHERE recommendation = :recommendation"
        params["recommendation"] = recommendation

    query = text(
        f"""
        SELECT hpo_id, label, "group", category, recommendation,
               description, phenopacket_count
        FROM hpo_terms_lookup
        {where_clause}
        ORDER BY "group", recommendation DESC, phenopacket_count DESC, label
    """
    )

    result = await db.execute(query, params)
    terms = result.fetchall()

    # CKD stage HPO IDs (mutually exclusive group)
    CKD_STAGE_IDS = {
        "HP:0012623",  # Stage 1 chronic kidney disease
        "HP:0012624",  # Stage 2 chronic kidney disease
        "HP:0012625",  # Stage 3 chronic kidney disease
        "HP:0012626",  # Stage 4 chronic kidney disease
        "HP:0003774",  # Stage 5 chronic kidney disease
    }

    # Group terms by organ system, with special handling for CKD stages
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in terms:
        term_dict = dict(row._mapping)
        hpo_id = term_dict.get("hpo_id")

        # Move CKD stages to their own group
        if hpo_id in CKD_STAGE_IDS:
            group_name = "CKD Stages"
        else:
            group_name = term_dict.get("group") or "Other"

        if group_name not in groups:
            groups[group_name] = []

        groups[group_name].append(term_dict)

    # Ensure groups appear in desired order
    # Left column: Brain, Electrolytes, Genital, Urinary tract, Hormones
    # Right column: CKD Stages, Kidney, Liver, Pancreas, Other
    group_order = [
        "Brain",
        "Electrolytes and uric acid",
        "Genital",
        "Urinary tract",
        "Hormones",
        "CKD Stages",
        "Kidney",
        "Liver",
        "Pancreas",
        "Other",
    ]
    ordered_groups = {k: groups[k] for k in group_order if k in groups}
    # Add any remaining groups not in the predefined order
    for k in groups:
        if k not in ordered_groups:
            ordered_groups[k] = groups[k]

    return {
        "data": {
            "groups": ordered_groups,
            "total_terms": len(terms),
            "total_groups": len(ordered_groups),
        }
    }


@router.get("/vocabularies/sex")
async def get_sex_values(db: AsyncSession = Depends(get_db)):
    """Get all valid sex values from controlled vocabulary."""
    query = text("SELECT value, label, description FROM sex_values ORDER BY sort_order")
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/vocabularies/interpretation-status")
async def get_interpretation_status_values(db: AsyncSession = Depends(get_db)):
    """Get all valid interpretation status values (ACMG classification)."""
    query = text(
        """SELECT value, label, description, category
           FROM interpretation_status_values
           ORDER BY sort_order"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/vocabularies/progress-status")
async def get_progress_status_values(db: AsyncSession = Depends(get_db)):
    """Get all valid progress status values for case interpretation."""
    query = text(
        """SELECT value, label, description
           FROM progress_status_values
           ORDER BY sort_order"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/vocabularies/allelic-state")
async def get_allelic_state_values(db: AsyncSession = Depends(get_db)):
    """Get all valid allelic state values (GENO ontology)."""
    query = text(
        """SELECT id, label, description
           FROM allelic_state_values
           ORDER BY sort_order"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


@router.get("/vocabularies/evidence-code")
async def get_evidence_code_values(db: AsyncSession = Depends(get_db)):
    """Get all valid evidence code values (ECO ontology)."""
    query = text(
        """SELECT id, label, description, category
           FROM evidence_code_values
           ORDER BY sort_order"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}


_CURATION_VOCABULARIES = {
    "cohort": "cohort_values",
    "detection-method": "detection_method_values",
    "segregation": "segregation_values",
    "family-history": "family_history_values",
    "publication-type": "publication_type_values",
    "classification-system": "classification_system_values",
}


async def _fetch_curation_vocabulary(
    db: AsyncSession, table: str
) -> VocabularyResponse:
    """Read one curation reference table in sort_order.

    The table name comes from the module-level mapping, never from user input.
    """
    query = text(
        f"SELECT value, label, description FROM {table} ORDER BY sort_order"  # noqa: S608
    )
    result = await db.execute(query)
    return VocabularyResponse(
        data=[VocabularyItem(**row._mapping) for row in result.fetchall()]
    )


@router.get("/vocabularies/cohort", response_model=VocabularyResponse)
async def get_cohort_values(db: AsyncSession = Depends(get_db)):
    """Get valid cohort values (born / fetus) for hnf1bCuration.cohort."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["cohort"])


@router.get("/vocabularies/detection-method", response_model=VocabularyResponse)
async def get_detection_method_values(db: AsyncSession = Depends(get_db)):
    """Get valid variant detection methods for hnf1bCuration.detectionMethod."""
    return await _fetch_curation_vocabulary(
        db, _CURATION_VOCABULARIES["detection-method"]
    )


@router.get("/vocabularies/segregation", response_model=VocabularyResponse)
async def get_segregation_values(db: AsyncSession = Depends(get_db)):
    """Get valid segregation origins for the variant segregation extension."""
    return await _fetch_curation_vocabulary(db, _CURATION_VOCABULARIES["segregation"])


@router.get("/vocabularies/family-history", response_model=VocabularyResponse)
async def get_family_history_values(db: AsyncSession = Depends(get_db)):
    """Get valid family history statuses for hnf1bCuration.familyHistory."""
    return await _fetch_curation_vocabulary(
        db, _CURATION_VOCABULARIES["family-history"]
    )


@router.get("/vocabularies/publication-type", response_model=VocabularyResponse)
async def get_publication_type_values(db: AsyncSession = Depends(get_db)):
    """Get valid publication types for hnf1bCuration.publicationType."""
    return await _fetch_curation_vocabulary(
        db, _CURATION_VOCABULARIES["publication-type"]
    )


@router.get("/vocabularies/classification-system", response_model=VocabularyResponse)
async def get_classification_system_values(db: AsyncSession = Depends(get_db)):
    """Get valid classification systems for hnf1bCuration.classificationSystem."""
    return await _fetch_curation_vocabulary(
        db, _CURATION_VOCABULARIES["classification-system"]
    )


@router.get("/laterality-policy")
async def get_laterality_policy(db: AsyncSession = Depends(get_db)):
    """Get the HPO modifiers each phenotype term admits.

    Only terms that admit at least one modifier are returned; every other term
    admits none. Consumed by the curation console to decide whether to render a
    laterality control, and by the domain validator on the write path.
    """
    query = text(
        """SELECT hpo_id, allowed_modifiers
           FROM hpo_terms_lookup
           WHERE cardinality(allowed_modifiers) > 0
           ORDER BY hpo_id"""
    )
    result = await db.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}
