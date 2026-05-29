"""Database persistence for publication abstracts, passages, and embeddings.

Raw-SQL persistence helpers (mirroring ``app.publications.service``'s ``text()``
style) for the full-text RAG stack. These operate on an injected
:class:`~sqlalchemy.ext.asyncio.AsyncSession`; the caller owns the transaction
boundary (the orchestrator commits once per publication so a publication's
metadata, passages, and embeddings move atomically).

pgvector has no asyncpg type codec here, so embedding vectors are bound as their
canonical text literal (``"[v1,v2,...]"``) and cast with ``::vector`` in SQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.publications.fulltext.types import PassageRow


def _normalize_pmid(pmid: str) -> str:
    """Return the canonical ``"PMID:<digits>"`` form of *pmid*."""
    return f"PMID:{pmid.replace('PMID:', '').strip()}"


def to_vector_literal(embedding: Sequence[float]) -> str:
    """Format a float sequence as a pgvector text literal.

    Args:
        embedding: The embedding components.

    Returns:
        A ``"[v1,v2,...]"`` string suitable for binding and ``::vector`` casting.
    """
    return "[" + ",".join(f"{component:.7g}" for component in embedding) + "]"


async def ensure_metadata_row(db: AsyncSession, pmid: str, *, title: str = "") -> None:
    """Insert a minimal ``publication_metadata`` row if one does not yet exist.

    The full-text orchestration only ever *updates* the new RAG columns, so a
    base row must exist. Normal flows create it via the existing PubMed metadata
    service; this is a defensive backstop (e.g. backfilling a PMID that has no
    cached metadata yet) that never clobbers existing data.

    Args:
        db: The async session.
        pmid: PMID (prefixed or bare).
        title: Placeholder title used only when inserting a new row.
    """
    await db.execute(
        text(
            "INSERT INTO publication_metadata (pmid, title, authors, data_source) "
            "VALUES (:pmid, :title, '[]'::jsonb, 'PubMed') "
            "ON CONFLICT (pmid) DO NOTHING"
        ),
        {"pmid": _normalize_pmid(pmid), "title": title or "Title unavailable"},
    )


async def update_metadata_coverage(
    db: AsyncSession,
    pmid: str,
    *,
    abstract: Optional[str],
    coverage: str,
    license: Optional[str],
    pmcid: Optional[str],
    fulltext_fetched_at: Optional[datetime] = None,
) -> None:
    """Update the abstract + full-text coverage columns on a publication row.

    Args:
        db: The async session.
        pmid: PMID (prefixed or bare).
        abstract: Abstract text to store (``None`` leaves it null).
        coverage: Coverage tier (``full_text|abstract_only|title_only``).
        license: Normalized license token, or ``None``.
        pmcid: PMC accession, or ``None``.
        fulltext_fetched_at: Timestamp of this fetch; defaults to ``now(UTC)``.
    """
    await db.execute(
        text(
            "UPDATE publication_metadata SET "
            "abstract = :abstract, coverage = :coverage, license = :license, "
            "pmcid = :pmcid, fulltext_fetched_at = :fetched_at "
            "WHERE pmid = :pmid"
        ),
        {
            "pmid": _normalize_pmid(pmid),
            "abstract": abstract,
            "coverage": coverage,
            "license": license,
            "pmcid": pmcid,
            "fetched_at": fulltext_fetched_at or datetime.now(timezone.utc),
        },
    )


async def replace_passages(
    db: AsyncSession, pmid: str, passages: Sequence[PassageRow]
) -> int:
    """Replace all stored passages for *pmid* with *passages*.

    Deletes the publication's existing rows (cascading to their embeddings via
    the FK) and inserts the new set. Does not commit — the caller owns the
    transaction so the metadata update and passage replacement are atomic.

    Args:
        db: The async session.
        pmid: PMID (prefixed or bare).
        passages: The new passage rows (may be empty to clear).

    Returns:
        The number of passage rows inserted.
    """
    normalized = _normalize_pmid(pmid)
    await db.execute(
        text("DELETE FROM publication_fulltext WHERE pmid = :pmid"),
        {"pmid": normalized},
    )
    if not passages:
        return 0
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO publication_fulltext "
            "(pmid, passage_id, section, seq, text, char_count, token_count, "
            " source, fetched_at) VALUES "
            "(:pmid, :passage_id, :section, :seq, :text, :char_count, "
            " :token_count, :source, :fetched_at)"
        ),
        [
            {
                "pmid": normalized,
                "passage_id": p.passage_id,
                "section": p.section,
                "seq": p.seq,
                "text": p.text,
                "char_count": p.char_count,
                "token_count": p.token_count,
                "source": p.source,
                "fetched_at": now,
            }
            for p in passages
        ],
    )
    return len(passages)


async def fetch_passages_needing_embedding(
    db: AsyncSession,
    *,
    model_name: str,
    text_hash_of: Callable[[str], str],
    limit: int = 500,
) -> list[tuple[str, str, str]]:
    """Return passages that lack a current embedding for *model_name*.

    A passage needs (re)embedding when no embedding row exists for it under
    *model_name*, or the stored ``text_hash`` differs from the current text's
    hash. The hash comparison is done in Python via *text_hash_of* so the
    hashing stays consistent with the embedding provider layer.

    Args:
        db: The async session.
        model_name: The embedding model identifier.
        text_hash_of: Callable mapping passage text to its SHA-256 hex digest.
        limit: Maximum number of passages to return.

    Returns:
        A list of ``(passage_id, pmid, text)`` tuples to embed.
    """
    result = await db.execute(
        text(
            "SELECT f.passage_id, f.pmid, f.text, e.text_hash AS stored_hash "
            "FROM publication_fulltext f "
            "LEFT JOIN publication_fulltext_embeddings e "
            "  ON e.passage_id = f.passage_id AND e.model_name = :model "
            "ORDER BY f.pmid, f.seq"
        ),
        {"model": model_name},
    )
    out: list[tuple[str, str, str]] = []
    for row in result.fetchall():
        if row.stored_hash == text_hash_of(row.text):
            continue
        out.append((row.passage_id, row.pmid, row.text))
        if len(out) >= limit:
            break
    return out


async def upsert_embedding(
    db: AsyncSession,
    *,
    passage_id: str,
    pmid: str,
    model_name: str,
    embedding: Sequence[float],
    text_hash: str,
) -> None:
    """Insert or update a single passage embedding row.

    Args:
        db: The async session.
        passage_id: The passage's stable identifier.
        pmid: PMID (prefixed or bare) owning the passage.
        model_name: The embedding model identifier (part of the PK).
        embedding: The embedding vector components.
        text_hash: SHA-256 hex digest of the embedded text.
    """
    await db.execute(
        text(
            "INSERT INTO publication_fulltext_embeddings "
            "(passage_id, pmid, model_name, embedding, text_hash, created_at) "
            "VALUES (:passage_id, :pmid, :model, CAST(:embedding AS vector), "
            "        :text_hash, now()) "
            "ON CONFLICT (passage_id, model_name) DO UPDATE SET "
            "  embedding = EXCLUDED.embedding, text_hash = EXCLUDED.text_hash, "
            "  created_at = EXCLUDED.created_at"
        ),
        {
            "passage_id": passage_id,
            "pmid": _normalize_pmid(pmid),
            "model": model_name,
            "embedding": to_vector_literal(embedding),
            "text_hash": text_hash,
        },
    )


async def count_embeddings(db: AsyncSession, *, model_name: str) -> int:
    """Return the number of stored embeddings for *model_name*."""
    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM publication_fulltext_embeddings "
            "WHERE model_name = :model"
        ),
        {"model": model_name},
    )
    return int(result.scalar() or 0)
