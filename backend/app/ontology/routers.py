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
