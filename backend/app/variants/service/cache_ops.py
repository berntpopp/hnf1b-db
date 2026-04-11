"""Database cache read/write operations for VEP annotations.

Extracted during Wave 4 from the monolithic ``variants/service.py``.
Owns the ``variant_annotations`` table SQL — the rest of the service
is a consumer of these helpers.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _get_cached_annotation(
    variant_id: str, db: AsyncSession
) -> Optional[dict]:
    """Check the database cache for a single variant annotation."""
    query = text("""
        SELECT
            variant_id,
            annotation,
            most_severe_consequence,
            impact,
            gene_symbol,
            gene_id,
            transcript_id,
            cadd_score,
            gnomad_af,
            gnomad_af_nfe,
            polyphen_prediction,
            polyphen_score,
            sift_prediction,
            sift_score,
            hgvsc,
            hgvsp,
            assembly,
            data_source,
            vep_version,
            fetched_at,
            fetched_by
        FROM variant_annotations
        WHERE variant_id = :variant_id
    """)
    result = await db.execute(query, {"variant_id": variant_id})
    row = result.fetchone()
    if row:
        return _row_to_dict(row)
    return None


async def _get_cached_annotations_batch(
    variant_ids: List[str], db: AsyncSession
) -> Dict[str, dict]:
    """Check the database cache for many variants in a single round-trip."""
    if not variant_ids:
        return {}
    query = text("""
        SELECT
            variant_id,
            annotation,
            most_severe_consequence,
            impact,
            gene_symbol,
            gene_id,
            transcript_id,
            cadd_score,
            gnomad_af,
            gnomad_af_nfe,
            polyphen_prediction,
            polyphen_score,
            sift_prediction,
            sift_score,
            hgvsc,
            hgvsp,
            assembly,
            data_source,
            vep_version,
            fetched_at,
            fetched_by
        FROM variant_annotations
        WHERE variant_id = ANY(:variant_ids)
    """)
    result = await db.execute(query, {"variant_ids": variant_ids})
    rows = result.fetchall()
    return {row.variant_id: _row_to_dict(row) for row in rows}


def _row_to_dict(row) -> dict:
    """Convert a ``variant_annotations`` row to an annotation dict."""
    return {
        "variant_id": row.variant_id,
        "annotation": row.annotation,
        "most_severe_consequence": row.most_severe_consequence,
        "impact": row.impact,
        "gene_symbol": row.gene_symbol,
        "gene_id": row.gene_id,
        "transcript_id": row.transcript_id,
        "cadd_score": float(row.cadd_score) if row.cadd_score else None,
        "gnomad_af": float(row.gnomad_af) if row.gnomad_af else None,
        "gnomad_af_nfe": float(row.gnomad_af_nfe) if row.gnomad_af_nfe else None,
        "polyphen_prediction": row.polyphen_prediction,
        "polyphen_score": float(row.polyphen_score) if row.polyphen_score else None,
        "sift_prediction": row.sift_prediction,
        "sift_score": float(row.sift_score) if row.sift_score else None,
        "hgvsc": row.hgvsc,
        "hgvsp": row.hgvsp,
        "assembly": row.assembly,
        "data_source": row.data_source,
        "vep_version": row.vep_version,
        "fetched_at": row.fetched_at,
        "fetched_by": row.fetched_by,
    }


async def _store_annotations_batch(
    annotations: List[dict],
    db: AsyncSession,
    fetched_by: Optional[str] = "system",
) -> None:
    """Upsert variant annotations into the database cache.

    Uses ``INSERT ... ON CONFLICT (variant_id) DO UPDATE`` so repeated
    fetches for the same variant refresh the cached row.
    """
    if not annotations:
        return

    query = text("""
        INSERT INTO variant_annotations (
            variant_id, annotation, most_severe_consequence, impact,
            gene_symbol, gene_id, transcript_id, cadd_score,
            gnomad_af, gnomad_af_nfe, polyphen_prediction, polyphen_score,
            sift_prediction, sift_score, hgvsc, hgvsp,
            assembly, data_source, vep_version, fetched_by, fetched_at
        )
        VALUES (
            :variant_id, :annotation, :most_severe_consequence, :impact,
            :gene_symbol, :gene_id, :transcript_id, :cadd_score,
            :gnomad_af, :gnomad_af_nfe, :polyphen_prediction, :polyphen_score,
            :sift_prediction, :sift_score, :hgvsc, :hgvsp,
            :assembly, :data_source, :vep_version, :fetched_by, :fetched_at
        )
        ON CONFLICT (variant_id) DO UPDATE SET
            annotation = EXCLUDED.annotation,
            most_severe_consequence = EXCLUDED.most_severe_consequence,
            impact = EXCLUDED.impact,
            gene_symbol = EXCLUDED.gene_symbol,
            gene_id = EXCLUDED.gene_id,
            transcript_id = EXCLUDED.transcript_id,
            cadd_score = EXCLUDED.cadd_score,
            gnomad_af = EXCLUDED.gnomad_af,
            gnomad_af_nfe = EXCLUDED.gnomad_af_nfe,
            polyphen_prediction = EXCLUDED.polyphen_prediction,
            polyphen_score = EXCLUDED.polyphen_score,
            sift_prediction = EXCLUDED.sift_prediction,
            sift_score = EXCLUDED.sift_score,
            hgvsc = EXCLUDED.hgvsc,
            hgvsp = EXCLUDED.hgvsp,
            vep_version = EXCLUDED.vep_version,
            fetched_by = EXCLUDED.fetched_by,
            fetched_at = EXCLUDED.fetched_at
    """)

    for ann in annotations:
        # DB column is timestamp without tz — strip tzinfo before bind.
        fetched_at = ann.get("fetched_at", datetime.now(timezone.utc))
        if fetched_at.tzinfo is not None:
            fetched_at = fetched_at.replace(tzinfo=None)

        await db.execute(
            query,
            {
                "variant_id": ann["variant_id"],
                "annotation": json.dumps(ann["annotation"]),
                "most_severe_consequence": ann.get("most_severe_consequence"),
                "impact": ann.get("impact"),
                "gene_symbol": ann.get("gene_symbol"),
                "gene_id": ann.get("gene_id"),
                "transcript_id": ann.get("transcript_id"),
                "cadd_score": ann.get("cadd_score"),
                "gnomad_af": ann.get("gnomad_af"),
                "gnomad_af_nfe": ann.get("gnomad_af_nfe"),
                "polyphen_prediction": ann.get("polyphen_prediction"),
                "polyphen_score": ann.get("polyphen_score"),
                "sift_prediction": ann.get("sift_prediction"),
                "sift_score": ann.get("sift_score"),
                "hgvsc": ann.get("hgvsc"),
                "hgvsp": ann.get("hgvsp"),
                "assembly": ann.get("assembly", "GRCh38"),
                "data_source": ann.get("data_source", "Ensembl VEP"),
                "vep_version": ann.get("vep_version", "114"),
                "fetched_by": fetched_by,
                "fetched_at": fetched_at,
            },
        )

    await db.commit()
