"""``GET /api/v2/publications/passages`` — hybrid passage retrieval for RAG."""
# ruff: noqa: E501 - long Query descriptions read better unwrapped

from __future__ import annotations

import asyncio
import logging
import re
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.ontology.conformance import _snapshot
from app.publications.fulltext.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.publications.fulltext.retrieval import (
    VALID_MODES,
    VALID_RERANK,
    search_passages,
)

from .schemas import (
    PassageHit,
    PassagesMeta,
    PassagesResponse,
    PhenotypeSuggestionItem,
    PhenotypeSuggestionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])

# Lazily-built, process-wide embedding provider. Building it loads the model
# (seconds), so we cache the single instance. ``None`` means the optional
# embedding backend is not installed and the dense leg is disabled.
_PROVIDER_CACHE: dict[str, Optional[EmbeddingProvider]] = {}
_PROVIDER_LOCK: Optional[asyncio.Lock] = None


async def _shared_provider() -> Optional[EmbeddingProvider]:
    """Return the cached embedding provider, or ``None`` when unavailable."""
    global _PROVIDER_LOCK
    if "provider" not in _PROVIDER_CACHE:
        if _PROVIDER_LOCK is None:
            _PROVIDER_LOCK = asyncio.Lock()
        async with _PROVIDER_LOCK:
            if "provider" not in _PROVIDER_CACHE:
                rag = settings.publications_rag
                _PROVIDER_CACHE["provider"] = await asyncio.to_thread(
                    get_embedding_provider,
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

    provider = await _shared_provider() if rerank == "rrf" else None

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


_CLAUSE_BREAK_REGEX = re.compile(
    r"[,;:]|\b(?:but|however|whereas|while|although|except)\b",
    re.IGNORECASE,
)
_PRE_NEGATION_REGEX = re.compile(
    r"\b(?:no|not|without|absent|absence of|normal|negative for|excluded|ruled out|lack of|free of)\b",
    re.IGNORECASE,
)
_POST_NEGATION_REGEX = re.compile(
    r"^\s*(?:was|were|is|are)?\s*(?:not\s+\w+|absent|excluded|negative|normal|ruled out)\b",
    re.IGNORECASE,
)


def _is_match_negated(sentence: str, start: int, end: int) -> bool:
    """Return whether a phenotype match at [start, end) is negated in its local clause."""
    clause_start = 0
    for m in _CLAUSE_BREAK_REGEX.finditer(sentence, 0, start):
        clause_start = m.end()

    clause_end = len(sentence)
    m_after = _CLAUSE_BREAK_REGEX.search(sentence, end)
    if m_after is not None:
        clause_end = m_after.start()

    prefix = sentence[max(clause_start, start - 65) : start]
    if _PRE_NEGATION_REGEX.search(prefix):
        return True

    suffix = sentence[end : min(clause_end, end + 40)]
    if _POST_NEGATION_REGEX.search(suffix):
        return True

    return False


@lru_cache(maxsize=1)
def _get_hpo_terms_for_suggestion() -> list[tuple[re.Pattern[str], str, str]]:
    """Return precompiled (pattern, hpo_id, canonical_name) tuples for HP terms.

    Sorted by candidate phrase length descending so longer phrases match first.
    """
    snapshot = _snapshot()
    candidates: list[tuple[str, str, str]] = []
    for term_id, term_data in snapshot.items():
        if not term_id.startswith("HP:"):
            continue
        canonical_name = term_data.get("name") or ""
        if len(canonical_name) >= 4:
            candidates.append((canonical_name, term_id, canonical_name))
        for syn in term_data.get("synonyms") or []:
            if len(syn) >= 4:
                candidates.append((syn, term_id, canonical_name))

    # Sort descending by length of phrase
    candidates.sort(key=lambda c: len(c[0]), reverse=True)

    compiled: list[tuple[re.Pattern[str], str, str]] = []
    for phrase, term_id, canonical_name in candidates:
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
        compiled.append((pattern, term_id, canonical_name))
    return compiled


@router.get(
    "/passages/suggest-phenotypes",
    response_model=PhenotypeSuggestionResponse,
    summary="Suggest HPO phenotypes from publication passages or metadata",
    description="Scan stored passages (or metadata fallback) for a PMID against curated HPO terms and negation cues.",
)
async def suggest_phenotypes_from_pmid(
    pmid: str = Query(..., min_length=1, description="PubMed identifier"),
    db: AsyncSession = Depends(get_db),
) -> PhenotypeSuggestionResponse:
    """Extract candidate HPO phenotypes from publication passages or metadata."""
    clean_pmid = pmid.strip()
    if clean_pmid.upper().startswith("PMID:"):
        clean_pmid = clean_pmid[5:].strip()

    prefixed_pmid = f"PMID:{clean_pmid}"
    bare_pmid = clean_pmid

    # 1. Query publication_fulltext
    stmt_fulltext = text(
        "SELECT passage_id, section, text FROM publication_fulltext "
        "WHERE pmid = :prefixed OR pmid = :bare "
        "ORDER BY seq ASC"
    )
    result = await db.execute(
        stmt_fulltext, {"prefixed": prefixed_pmid, "bare": bare_pmid}
    )
    rows = result.fetchall()

    passages_to_scan: list[dict[str, str]] = []
    if rows:
        for row in rows:
            passages_to_scan.append(
                {
                    "passage_id": row.passage_id,
                    "section": row.section,
                    "text": row.text or "",
                }
            )
    else:
        # Fallback to publication_metadata (abstract / title)
        stmt_meta = text(
            "SELECT title, abstract FROM publication_metadata "
            "WHERE pmid = :prefixed OR pmid = :bare"
        )
        meta_result = await db.execute(
            stmt_meta, {"prefixed": prefixed_pmid, "bare": bare_pmid}
        )
        meta_row = meta_result.fetchone()
        if meta_row:
            if meta_row.title:
                passages_to_scan.append(
                    {
                        "passage_id": f"PMID:{clean_pmid}:title",
                        "section": "title",
                        "text": meta_row.title,
                    }
                )
            if meta_row.abstract:
                passages_to_scan.append(
                    {
                        "passage_id": f"PMID:{clean_pmid}:abstract",
                        "section": "abstract",
                        "text": meta_row.abstract,
                    }
                )

    hpo_candidates = _get_hpo_terms_for_suggestion()
    suggestions: list[PhenotypeSuggestionItem] = []
    seen_keys: set[tuple[str, bool]] = set()

    for passage in passages_to_scan:
        passage_text = passage["text"]
        if not passage_text:
            continue
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", passage_text)
        for sentence in raw_sentences:
            s_clean = sentence.strip()
            if not s_clean:
                continue
            matched_in_sentence: set[str] = set()

            for pattern, term_id, canonical_name in hpo_candidates:
                if term_id in matched_in_sentence:
                    continue
                match = pattern.search(s_clean)
                if match:
                    matched_in_sentence.add(term_id)
                    is_negated = _is_match_negated(s_clean, match.start(), match.end())
                    dedup_key = (term_id, is_negated)
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        suggestions.append(
                            PhenotypeSuggestionItem(
                                hpo_id=term_id,
                                label=canonical_name,
                                excluded=is_negated,
                                section=passage["section"],
                                passage_id=passage["passage_id"],
                                sentence=s_clean,
                                score=1.0,
                            )
                        )

    return PhenotypeSuggestionResponse(
        pmid=clean_pmid,
        suggestions=suggestions,
    )
