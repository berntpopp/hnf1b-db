"""Reference-data status query for admin endpoints."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.reference.models import (
    Exon,
    Gene,
    ProteinDomain,
    ReferenceGenome,
    Transcript,
)

from .types import ReferenceDataStatus


async def get_reference_data_status(db: AsyncSession) -> ReferenceDataStatus:
    """Return the current reference-data snapshot for ``/admin/reference/status``.

    Counts rows in every reference table, flags GRCh38 / HNF1B
    presence, counts chr17q12 genes via a literal raw-SQL ``WHERE``,
    and reports the most recent ``Gene.updated_at`` as a rough "last
    updated" timestamp for the sync progress row.
    """
    status = ReferenceDataStatus()

    genome_result = await db.execute(select(func.count(ReferenceGenome.id)))
    status.genome_count = genome_result.scalar() or 0

    grch38_result = await db.execute(
        select(ReferenceGenome).where(ReferenceGenome.name == "GRCh38")
    )
    status.has_grch38 = grch38_result.scalar_one_or_none() is not None

    gene_result = await db.execute(select(func.count(Gene.id)))
    status.gene_count = gene_result.scalar() or 0

    hnf1b_result = await db.execute(select(Gene).where(Gene.symbol == "HNF1B"))
    status.has_hnf1b = hnf1b_result.scalar_one_or_none() is not None

    transcript_result = await db.execute(select(func.count(Transcript.id)))
    status.transcript_count = transcript_result.scalar() or 0

    exon_result = await db.execute(select(func.count(Exon.id)))
    status.exon_count = exon_result.scalar() or 0

    domain_result = await db.execute(select(func.count(ProteinDomain.id)))
    status.domain_count = domain_result.scalar() or 0

    # Count chr17q12 genes (chr17:36000000-39900000). Uses raw SQL so
    # the ``end`` column name does not collide with SQLAlchemy's
    # reserved word list.
    chr17q12_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM genes
            WHERE chromosome = '17'
              AND start >= 36000000
              AND "end" <= 39900000
        """)
    )
    status.chr17q12_gene_count = chr17q12_result.scalar() or 0

    last_update_result = await db.execute(select(func.max(Gene.updated_at)))
    status.last_updated = last_update_result.scalar()

    return status
