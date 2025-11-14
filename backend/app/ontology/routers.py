from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

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

    # Group terms by organ system
    groups = {}
    for row in terms:
        term_dict = dict(row._mapping)
        group_name = term_dict.get("group") or "Other"

        if group_name not in groups:
            groups[group_name] = []

        groups[group_name].append(term_dict)

    return {
        "data": {
            "groups": groups,
            "total_terms": len(terms),
            "total_groups": len(groups),
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
