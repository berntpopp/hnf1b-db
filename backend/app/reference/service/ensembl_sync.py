"""Ensembl REST sync for the chr17q12 region.

Fetches genes in the chr17q12 region from Ensembl and upserts them
into the local ``genes`` table. Extracted during Wave 4 from the
monolithic ``reference/service.py``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.reference.models import Gene

from .constants import (
    CHR17Q12_REGION,
    ENSEMBL_API_BASE,
    ENSEMBL_RATE_LIMIT_DELAY,
    VALID_BIOTYPES,
)
from .hnf1b_importer import get_gene_by_symbol, get_or_create_grch38_genome
from .types import SyncResult

logger = logging.getLogger(__name__)


async def fetch_genes_from_ensembl(
    region: str = CHR17Q12_REGION,
    timeout: int = 30,
) -> list[dict]:
    """Fetch genes in a genomic region from the Ensembl REST API.

    Respects the Ensembl rate limit by sleeping for
    :data:`ENSEMBL_RATE_LIMIT_DELAY` seconds after each successful
    request. Raises ``httpx.HTTPError`` on non-200 responses.
    """
    url = f"{ENSEMBL_API_BASE}/overlap/region/human/{region}"
    params = {"feature": "gene", "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info("Fetching genes from Ensembl: %s", region)
        response = await client.get(url, params=params)
        response.raise_for_status()

        await asyncio.sleep(ENSEMBL_RATE_LIMIT_DELAY)

        data = response.json()
        logger.info("Received %s features from Ensembl", len(data))
        return data


def parse_gene_from_ensembl(feature: dict) -> dict | None:
    """Parse a single Ensembl feature dict into a gene row.

    Returns ``None`` for unwanted biotypes (pseudogenes etc.).
    """
    biotype = feature.get("biotype")
    if biotype not in VALID_BIOTYPES:
        return None

    return {
        "symbol": feature.get("external_name") or feature.get("id"),
        "name": feature.get("description", ""),
        "ensembl_id": feature.get("id"),
        "start": feature.get("start"),
        "end": feature.get("end"),
        "strand": "+" if feature.get("strand") == 1 else "-",
        "biotype": biotype,
        "version": feature.get("version"),
    }


async def sync_chr17q12_genes(
    db: AsyncSession,
    region: str = CHR17Q12_REGION,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> SyncResult:
    """Sync chr17q12 region genes from the Ensembl REST API.

    Creates or updates genes in the local ``genes`` table.
    ``dry_run=True`` rolls back at the end instead of committing.
    ``limit`` caps the number of genes processed for testing.
    """
    result = SyncResult(error_messages=[])

    try:
        genome, _ = await get_or_create_grch38_genome(db)
        features = await fetch_genes_from_ensembl(region)

        genes_data: list[dict] = []
        for feature in features:
            gene_data = parse_gene_from_ensembl(feature)
            if gene_data:
                genes_data.append(gene_data)

        if limit:
            genes_data = genes_data[:limit]

        logger.info("Processing %s valid genes", len(genes_data))

        for gene_data in genes_data:
            symbol = gene_data["symbol"]
            existing = await get_gene_by_symbol(db, symbol, genome.id)

            if existing:
                if not dry_run:
                    existing.name = gene_data["name"]
                    existing.start = gene_data["start"]
                    existing.end = gene_data["end"]
                    existing.strand = gene_data["strand"]
                    existing.ensembl_id = gene_data.get("ensembl_id")
                    existing.source = "Ensembl REST API"
                    existing.source_version = "GRCh38"
                    existing.extra_data = {
                        "ensembl_id": gene_data.get("ensembl_id"),
                        "biotype": gene_data.get("biotype"),
                        "version": gene_data.get("version"),
                    }
                result.updated += 1
                logger.debug("Updated: %s", symbol)
            else:
                if not gene_data.get("start") or not gene_data.get("end"):
                    result.skipped += 1
                    logger.warning("Skipped %s: missing coordinates", symbol)
                    continue

                if not dry_run:
                    gene = Gene(
                        id=uuid.uuid4(),
                        symbol=symbol,
                        name=gene_data["name"],
                        chromosome="17",
                        start=gene_data["start"],
                        end=gene_data["end"],
                        strand=gene_data["strand"],
                        genome_id=genome.id,
                        ensembl_id=gene_data.get("ensembl_id"),
                        source="Ensembl REST API",
                        source_version="GRCh38",
                        extra_data={
                            "biotype": gene_data.get("biotype"),
                            "version": gene_data.get("version"),
                        },
                    )
                    db.add(gene)
                result.imported += 1
                logger.debug("Imported: %s", symbol)

        if not dry_run:
            await db.commit()
            logger.info(
                "chr17q12 sync completed: %s imported, %s updated, %s skipped",
                result.imported,
                result.updated,
                result.skipped,
            )
        else:
            await db.rollback()
            logger.info("chr17q12 dry run: would process %s genes", result.total)

    except httpx.HTTPError as exc:
        result.errors += 1
        if result.error_messages is not None:
            result.error_messages.append(f"HTTP error: {exc}")
        logger.error("Failed to fetch from Ensembl: %s", exc)
    except (SQLAlchemyError, ValueError, KeyError) as exc:
        await db.rollback()
        result.errors += 1
        if result.error_messages is not None:
            result.error_messages.append(str(exc))
        logger.error("Failed to sync chr17q12 genes: %s", exc)

    return result
