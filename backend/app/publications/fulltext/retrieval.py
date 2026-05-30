"""Hybrid (lexical + optional semantic) passage retrieval over ``publication_fulltext``.

The lexical leg always runs: a three-``tsquery`` candidate query
(``phraseto`` x3 + ``websearch`` x2 + recall ``to_tsquery`` x1) ranked by
``ts_rank_cd``. When an embedding provider is supplied and embeddings exist, a
dense pgvector leg (HNSW cosine) is run and fused with the lexical leg via
Reciprocal Rank Fusion (:func:`app.publications.fulltext.rrf.rrf_fuse`) plus
per-section boosts. ``rerank`` selects the strategy and degrades gracefully to
lexical when semantics are unavailable.

All SQL is parameterized; the free-text query reaches Postgres only through
``phraseto_tsquery`` / ``websearch_to_tsquery`` / a sanitized alnum
``to_tsquery`` string, never via string interpolation.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.publications.fulltext.embeddings import EmbeddingProvider
from app.publications.fulltext.persistence import to_vector_literal
from app.publications.fulltext.rrf import rrf_fuse
from app.publications.fulltext.types import RetrievalResult, RetrievedPassage

#: Modes controlling how much passage text is returned.
VALID_MODES = ("full", "brief", "ids_only")
#: Reranking strategies.
VALID_RERANK = ("rrf", "lexical", "off")

_ALNUM_RE = re.compile(r"[A-Za-z0-9]+")
#: Approximate characters per token, used to size ``ts_headline`` snippets.
_CHARS_PER_WORD = 6


def _or_query(query: str) -> str:
    """Return a sanitized ``to_tsquery`` OR-string of alnum terms (may be empty)."""
    return " | ".join(_ALNUM_RE.findall(query))


def _row_to_passage(row: Any, score: float) -> RetrievedPassage:
    """Build a :class:`RetrievedPassage` from a DB row (text filled later)."""
    return RetrievedPassage(
        pmid=row.pmid,
        passage_id=row.passage_id,
        section=row.section,
        seq=row.seq,
        char_count=row.char_count,
        token_count=row.token_count,
        source=row.source,
        score=score,
    )


async def _lexical_candidates(
    db: AsyncSession,
    query: str,
    *,
    pmids: Optional[Sequence[str]],
    sections: Optional[Sequence[str]],
    limit: int,
) -> list[Any]:
    """Run the three-tsquery lexical candidate query, ranked best-first."""
    or_text = _or_query(query)
    where = ["(f.search_vector @@ q.qp OR f.search_vector @@ q.qw"]
    select_rank = [
        "ts_rank_cd(f.search_vector, q.qp) * 3.0",
        "ts_rank_cd(f.search_vector, q.qw) * 2.0",
    ]
    q_ctes = [
        "phraseto_tsquery('english', :qtext) AS qp",
        "websearch_to_tsquery('english', :qtext) AS qw",
    ]
    params: dict[str, Any] = {"qtext": query, "lex_limit": limit}
    if or_text:
        q_ctes.append("to_tsquery('english', :qor) AS qo")
        select_rank.append("ts_rank_cd(f.search_vector, q.qo) * 1.0")
        where.append(" OR f.search_vector @@ q.qo")
        params["qor"] = or_text
    where.append(")")

    filter_sql, params = _apply_filters(params, pmids, sections)

    sql = (
        f"WITH q AS (SELECT {', '.join(q_ctes)}) "
        "SELECT f.pmid, f.passage_id, f.section, f.seq, f.text, "
        "f.char_count, f.token_count, f.source, "
        f"GREATEST({', '.join(select_rank)}) AS lex_score "
        "FROM publication_fulltext f, q "
        f"WHERE {''.join(where)}{filter_sql} "
        "ORDER BY lex_score DESC, f.pmid, f.seq "
        "LIMIT :lex_limit"
    )
    stmt = _with_filter_bindparams(text(sql), pmids, sections)
    result = await db.execute(stmt, params)
    return list(result.fetchall())


async def _dense_candidates(
    db: AsyncSession,
    qvec: Sequence[float],
    *,
    model_name: str,
    pmids: Optional[Sequence[str]],
    sections: Optional[Sequence[str]],
    limit: int,
) -> list[Any]:
    """Return rows (passage_id, section) ordered by cosine distance (best-first).

    The ``section`` is returned alongside so section boosts can be applied to
    dense-only passages too (those not present in the lexical leg), before the
    full passage rows are materialized.
    """
    params: dict[str, Any] = {
        "model": model_name,
        "qvec": to_vector_literal(qvec),
        "dense_limit": limit,
    }
    filter_sql, params = _apply_filters(params, pmids, sections)
    sql = (
        "SELECT e.passage_id, f.section "
        "FROM publication_fulltext_embeddings e "
        "JOIN publication_fulltext f "
        "  ON f.pmid = e.pmid AND f.passage_id = e.passage_id "
        f"WHERE e.model_name = :model{filter_sql} "
        "ORDER BY e.embedding <=> CAST(:qvec AS vector) "
        "LIMIT :dense_limit"
    )
    stmt = _with_filter_bindparams(text(sql), pmids, sections)
    result = await db.execute(stmt, params)
    return list(result.fetchall())


def _apply_filters(
    params: dict[str, Any],
    pmids: Optional[Sequence[str]],
    sections: Optional[Sequence[str]],
) -> tuple[str, dict[str, Any]]:
    """Append pmid/section filter SQL + params (expanding IN bindparams)."""
    sql = ""
    if pmids:
        sql += " AND f.pmid IN :pmids"
        params["pmids"] = [f"PMID:{p.replace('PMID:', '')}" for p in pmids]
    if sections:
        sql += " AND f.section IN :sections"
        params["sections"] = list(sections)
    return sql, params


def _with_filter_bindparams(
    stmt: Any, pmids: Optional[Sequence[str]], sections: Optional[Sequence[str]]
) -> Any:
    """Declare expanding bindparams for any active IN filters."""
    expanding: list[Any] = []
    if pmids:
        expanding.append(bindparam("pmids", expanding=True))
    if sections:
        expanding.append(bindparam("sections", expanding=True))
    return stmt.bindparams(*expanding) if expanding else stmt


async def _embeddings_present(db: AsyncSession, model_name: str) -> bool:
    """Return whether any embedding row exists for *model_name*."""
    result = await db.execute(
        text(
            "SELECT 1 FROM publication_fulltext_embeddings "
            "WHERE model_name = :model LIMIT 1"
        ),
        {"model": model_name},
    )
    return result.first() is not None


async def _fetch_missing_rows(
    db: AsyncSession, passage_ids: Sequence[str]
) -> dict[str, Any]:
    """Fetch full passage rows for *passage_ids* (for dense-only candidates)."""
    if not passage_ids:
        return {}
    stmt = text(
        "SELECT pmid, passage_id, section, seq, text, char_count, "
        "token_count, source FROM publication_fulltext WHERE passage_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    result = await db.execute(stmt, {"ids": list(passage_ids)})
    return {row.passage_id: row for row in result.fetchall()}


async def _apply_brief_snippets(
    db: AsyncSession, passages: list[RetrievedPassage], query: str, snippet_chars: int
) -> None:
    """Populate ``snippet`` on each passage via ``ts_headline`` (in place)."""
    if not passages:
        return
    max_words = max(5, snippet_chars // _CHARS_PER_WORD)
    options = f"MaxFragments=2, MinWords=3, MaxWords={max_words}, ShortWord=2"
    stmt = text(
        "SELECT passage_id, ts_headline('english', text, "
        "websearch_to_tsquery('english', :qtext), :opts) AS snippet "
        "FROM publication_fulltext WHERE passage_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    result = await db.execute(
        stmt,
        {
            "qtext": query,
            "opts": options,
            "ids": [p.passage_id for p in passages],
        },
    )
    snippets = {row.passage_id: row.snippet for row in result.fetchall()}
    for passage in passages:
        passage.snippet = snippets.get(passage.passage_id)


async def search_passages(
    db: AsyncSession,
    query: str,
    *,
    pmids: Optional[Sequence[str]] = None,
    sections: Optional[Sequence[str]] = None,
    rerank: str = "rrf",
    mode: str = "full",
    limit: int = 10,
    snippet_chars: int = 240,
    max_chars: Optional[int] = None,
    provider: Optional[EmbeddingProvider] = None,
    rrf_k: Optional[int] = None,
    section_boosts: Optional[Mapping[str, float]] = None,
    lexical_candidate_limit: Optional[int] = None,
    dense_candidate_limit: Optional[int] = None,
    model_name: Optional[str] = None,
) -> RetrievalResult:
    """Retrieve ranked passages for *query* via hybrid lexical + semantic search.

    Args:
        db: The async session.
        query: Free-text search query.
        pmids: Optional PMID filter (prefixed or bare); ``None`` = all.
        sections: Optional canonical-section filter; ``None`` = all.
        rerank: ``rrf`` (fuse lexical + dense when available), ``lexical``
            (lexical-only with section boosts), or ``off`` (raw ts_rank order).
        mode: ``full`` (passage text, budgeted by ``max_chars``), ``brief``
            (``ts_headline`` snippet only), or ``ids_only`` (no text).
        limit: Maximum number of passages to return.
        snippet_chars: Target snippet length for ``brief`` mode.
        max_chars: Total character budget for ``full`` mode text; when exceeded
            the result is truncated and ``truncated`` is set. The top-ranked
            passage is always returned even if it alone exceeds the budget (so a
            query never yields an empty result when a match exists); a
            diagnostic note is added in that case.
        provider: Embedding provider for the dense leg; ``None`` disables it.
        rrf_k: RRF constant (defaults to config).
        section_boosts: Section boost map (defaults to config).
        lexical_candidate_limit: Lexical candidate pool size (defaults to config).
        dense_candidate_limit: Dense candidate pool size (defaults to config).
        model_name: Embedding model name for the dense leg (defaults to config).

    Returns:
        A :class:`RetrievalResult` with ranked passages and ``_meta`` diagnostics.

    Raises:
        ValueError: If ``rerank`` or ``mode`` is not a recognized value.
    """
    if rerank not in VALID_RERANK:
        raise ValueError(f"invalid rerank {rerank!r}; expected one of {VALID_RERANK}")
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; expected one of {VALID_MODES}")

    cfg = settings.publications_rag
    rrf_k = rrf_k if rrf_k is not None else cfg.rrf_k
    if section_boosts is None:
        section_boosts = cfg.section_boosts
    lex_limit = lexical_candidate_limit or cfg.lexical_candidate_limit
    dense_limit = dense_candidate_limit or cfg.dense_candidate_limit
    # The dense leg must query embeddings produced by the SAME model as the
    # query embedding, so the active provider's model name is authoritative;
    # fall back to an explicit override or the configured default.
    if model_name is None:
        model_name = (
            provider.model_name if provider is not None else cfg.embedding_model
        )

    notes: list[str] = []

    lexical_rows = await _lexical_candidates(
        db, query, pmids=pmids, sections=sections, limit=lex_limit
    )
    lexical_ids = [r.passage_id for r in lexical_rows]
    rows_by_id: dict[str, Any] = {r.passage_id: r for r in lexical_rows}
    lexical_rank = {pid: i + 1 for i, pid in enumerate(lexical_ids)}

    # --- dense leg (optional) ---
    dense_ids: list[str] = []
    dense_rank: dict[str, int] = {}
    embedding_dim: Optional[int] = None
    rerank_used = rerank

    # Section lookup for boosts — seeded from the lexical leg and extended with
    # the dense leg below so dense-ONLY passages are boosted too (the dense query
    # returns each candidate's section for exactly this reason).
    section_by_id: dict[str, str] = {r.passage_id: r.section for r in lexical_rows}

    want_dense = rerank == "rrf"
    if want_dense and provider is None:
        rerank_used = "lexical"
        notes.append("dense disabled: no embedding provider available")
    elif want_dense and not await _embeddings_present(db, model_name):
        rerank_used = "lexical"
        notes.append("dense disabled: no embeddings stored for model")
    elif want_dense:
        qvec = (await provider.embed([query], is_query=True))[0]  # type: ignore[union-attr]
        embedding_dim = len(qvec)
        dense_rows = await _dense_candidates(
            db,
            qvec,
            model_name=model_name,
            pmids=pmids,
            sections=sections,
            limit=dense_limit,
        )
        dense_ids = [r.passage_id for r in dense_rows]
        dense_rank = {pid: i + 1 for i, pid in enumerate(dense_ids)}
        for r in dense_rows:
            section_by_id.setdefault(r.passage_id, r.section)

    # --- fuse ---
    if rerank_used == "off":
        ordered_ids = lexical_ids
        scores = {pid: float(len(lexical_ids) - i) for i, pid in enumerate(lexical_ids)}
    else:
        fused = rrf_fuse(
            lexical_ids,
            dense_ids if rerank_used == "rrf" else [],
            k=rrf_k,
            section_by_id=section_by_id or None,
            section_boosts=section_boosts or None,
        )
        ordered_ids = [pid for pid, _ in fused]
        scores = dict(fused)

    # Materialize rows for any dense-only ids not already loaded.
    missing = [pid for pid in ordered_ids if pid not in rows_by_id]
    rows_by_id.update(await _fetch_missing_rows(db, missing))

    # --- assemble, applying limit + (full-mode) char budget ---
    passages: list[RetrievedPassage] = []
    used_chars = 0
    truncated = False
    for pid in ordered_ids:
        row = rows_by_id.get(pid)
        if row is None:
            continue
        if len(passages) >= limit:
            truncated = True
            break
        # full-mode char budget: stop once adding this passage would exceed
        # max_chars. The TOP-ranked passage is always returned even if it alone
        # exceeds the budget, so a query never yields an empty result when a
        # match exists (the caller sees truncated=True + a diagnostic note).
        if mode == "full" and max_chars is not None and passages:
            if used_chars + row.char_count > max_chars:
                truncated = True
                break
        if (
            mode == "full"
            and max_chars is not None
            and not passages
            and row.char_count > max_chars
        ):
            notes.append("top passage exceeds max_chars; returned in full anyway")
        passage = _row_to_passage(row, scores.get(pid, 0.0))
        passage.lexical_rank = lexical_rank.get(pid)
        passage.dense_rank = dense_rank.get(pid)
        if mode == "full":
            passage.text = row.text
            used_chars += row.char_count
        passages.append(passage)

    if mode == "brief":
        await _apply_brief_snippets(db, passages, query, snippet_chars)

    return RetrievalResult(
        passages=passages,
        rerank_used=rerank_used,
        lexical_candidate_count=len(lexical_ids),
        dense_candidate_count=len(dense_ids),
        embedding_dim=embedding_dim,
        truncated=truncated,
        notes=tuple(notes),
    )
