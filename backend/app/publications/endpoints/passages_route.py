"""``GET /api/v2/publications/passages`` — hybrid passage retrieval for RAG."""
# ruff: noqa: E501 - long Query descriptions read better unwrapped

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.publications.fulltext.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.publications.fulltext.retrieval import (
    VALID_MODES,
    VALID_RERANK,
    search_passages,
)

from .schemas import PassageHit, PassagesMeta, PassagesResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])

# Lazily-built, process-wide embedding provider. Building it loads the model
# (seconds), so we cache the single instance. ``None`` means the optional [rag]
# stack is not installed and the dense leg is disabled (lexical-only retrieval).
_PROVIDER_CACHE: dict[str, Optional[EmbeddingProvider]] = {}


def _shared_provider() -> Optional[EmbeddingProvider]:
    """Return the cached embedding provider (or ``None`` when [rag] is absent)."""
    if "provider" not in _PROVIDER_CACHE:
        rag = settings.publications_rag
        _PROVIDER_CACHE["provider"] = get_embedding_provider(
            model_name=rag.embedding_model,
            query_prefix=rag.embedding_query_prefix,
            batch_size=rag.embedding_batch_size,
            dim=rag.embedding_dim,
        )
    return _PROVIDER_CACHE["provider"]


def _csv(value: Optional[str]) -> Optional[list[str]]:
    """Split a comma-separated query value into a trimmed list, or ``None``."""
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return items or None


@router.get(
    "/passages",
    response_model=PassagesResponse,
    summary="Hybrid passage retrieval over publication full text (RAG)",
    description="""
    Rank stored open-access passages for a free-text query using hybrid retrieval:
    PostgreSQL full-text search (always) fused with optional pgvector semantic
    search via Reciprocal Rank Fusion.

    **Read-only and public.** Returns license-gated open-access passages only.

    - `q`: free-text query (required).
    - `pmids`: comma-separated PMID filter (prefixed or bare).
    - `sections`: comma-separated canonical section filter
      (title, abstract, intro, methods, results, discussion, conclusion, table).
    - `rerank`: `rrf` (lexical+dense when embeddings exist), `lexical`, or `off`.
    - `mode`: `full` (passage text, budgeted by `max_chars`), `brief`
      (highlighted snippet), or `ids_only`.
    - `limit`, `snippet_chars`, `max_chars`: result sizing / token budgeting.

    Each hit carries a stable `passage_id` to cite. The response `meta` block
    reports which rerank strategy actually ran and candidate counts.
    """,
)
async def search_publication_passages(
    q: str = Query(..., min_length=1, description="Free-text query"),
    pmids: Optional[str] = Query(None, description="Comma-separated PMID filter"),
    sections: Optional[str] = Query(None, description="Comma-separated section filter"),
    rerank: str = Query("rrf", description="rrf | lexical | off"),
    mode: str = Query("full", description="full | brief | ids_only"),
    limit: int = Query(10, ge=1, le=100, description="Max passages to return"),
    snippet_chars: int = Query(
        240, ge=40, le=2000, description="Brief-mode snippet length"
    ),
    max_chars: Optional[int] = Query(
        None, ge=100, description="Full-mode total char budget"
    ),
    db: AsyncSession = Depends(get_db),
) -> PassagesResponse:
    """Retrieve ranked publication passages for a query."""
    if rerank not in VALID_RERANK:
        raise HTTPException(400, f"invalid rerank {rerank!r}; expected {VALID_RERANK}")
    if mode not in VALID_MODES:
        raise HTTPException(400, f"invalid mode {mode!r}; expected {VALID_MODES}")

    provider = _shared_provider() if rerank == "rrf" else None

    result = await search_passages(
        db,
        q,
        pmids=_csv(pmids),
        sections=_csv(sections),
        rerank=rerank,
        mode=mode,
        limit=limit,
        snippet_chars=snippet_chars,
        max_chars=max_chars,
        provider=provider,
    )

    hits = [
        PassageHit(
            passage_id=p.passage_id,
            pmid=p.pmid,
            section=p.section,
            seq=p.seq,
            score=p.score,
            source=p.source,
            char_count=p.char_count,
            token_count=p.token_count,
            text=p.text,
            snippet=p.snippet,
            lexical_rank=p.lexical_rank,
            dense_rank=p.dense_rank,
        )
        for p in result.passages
    ]

    logger.info(
        "Passage search",
        extra={
            "query": q,
            "rerank_used": result.rerank_used,
            "returned": len(hits),
        },
    )

    return PassagesResponse(
        passages=hits,
        meta=PassagesMeta(
            query=q,
            mode=mode,
            rerank_used=result.rerank_used,
            total=len(hits),
            lexical_candidate_count=result.lexical_candidate_count,
            dense_candidate_count=result.dense_candidate_count,
            embedding_dim=result.embedding_dim,
            embeddings_available=result.embeddings_available,
            truncated=result.truncated,
            notes=list(result.notes),
        ),
    )
