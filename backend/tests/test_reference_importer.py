"""Reference-data importer: idempotency + HNF1B gene cross-ref self-heal.

Guards the bootstrap contract that `get_gene_context` depends on: the reference
chain (GRCh38 + HNF1B gene/transcript/exons/domains) is created on demand, the
init is safe to run on every container start, and a gene left without
NCBI/HGNC/OMIM cross-references by the chr17q12 region sync is healed rather
than skipped.
"""

from __future__ import annotations

import uuid

import pytest

from app.reference.models import Gene
from app.reference.service.hnf1b_importer import (
    get_gene_by_symbol,
    get_or_create_grch38_genome,
    import_hnf1b_gene,
    initialize_reference_data,
)
from app.reference.service.status import get_reference_data_status


@pytest.mark.asyncio
async def test_initialize_reference_data_populates_full_chain(db_session):
    """A single init seeds genome + gene (with xrefs) + transcript + exons + domains."""
    await initialize_reference_data(db_session)
    status = await get_reference_data_status(db_session)

    assert status.has_grch38 is True
    assert status.has_hnf1b is True
    assert status.transcript_count >= 1
    assert status.exon_count >= 9
    assert status.domain_count >= 4

    genome = await get_or_create_grch38_genome(db_session)
    gene = await get_gene_by_symbol(db_session, "HNF1B", genome[0].id)
    assert gene is not None
    assert gene.ncbi_gene_id == "6928"
    assert gene.hgnc_id == "HGNC:11630"
    assert gene.omim_id == "189907"


@pytest.mark.asyncio
async def test_initialize_reference_data_is_idempotent(db_session):
    """Running init twice creates nothing new the second time and never errors."""
    await initialize_reference_data(db_session)
    second = await initialize_reference_data(db_session)
    assert second.errors == 0
    assert second.imported == 0


@pytest.mark.asyncio
async def test_import_hnf1b_gene_heals_missing_xrefs(db_session):
    """A region-synced HNF1B row with empty xrefs is healed, not skipped.

    Reproduces the real bug: the chr17q12 Ensembl sync creates the HNF1B gene
    with coordinates + ensembl_id but blank NCBI/HGNC/OMIM, and the importer
    used to early-return without enriching it — leaving get_gene_context
    reporting degraded cross_references forever.
    """
    genome, _ = await get_or_create_grch38_genome(db_session)
    existing = await get_gene_by_symbol(db_session, "HNF1B", genome.id)
    if existing is None:
        existing = Gene(
            id=uuid.uuid4(),
            symbol="HNF1B",
            name="HNF1 homeobox B",
            chromosome="17",
            start=37686431,
            end=37745091,
            strand="-",
            genome_id=genome.id,
            ensembl_id="ENSG00000275410",
            source="Ensembl REST API",
        )
        db_session.add(existing)
    # Force the "region-synced, no cross-refs" state.
    existing.ncbi_gene_id = None
    existing.hgnc_id = None
    existing.omim_id = None
    await db_session.flush()

    healed, created = await import_hnf1b_gene(db_session, genome.id)

    assert created is False  # the row already existed
    assert healed.ncbi_gene_id == "6928"
    assert healed.hgnc_id == "HGNC:11630"
    assert healed.omim_id == "189907"
