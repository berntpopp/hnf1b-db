"""Public VEP annotation API: single + batch fetch.

Orchestrates the cache layer (``cache_ops``) and the Ensembl VEP
client (``vep_api``) behind a small public surface. Extracted during
Wave 4 from the monolithic ``variants/service.py``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from .cache_ops import (
    _get_cached_annotation,
    _get_cached_annotations_batch,
    _store_annotations_batch,
)
from .errors import VEPError, VEPRateLimitError
from .validators import validate_variant_id
from .vep_api import _fetch_from_vep

logger = logging.getLogger(__name__)


async def get_variant_annotation(
    variant_id: str, db: AsyncSession, fetched_by: Optional[str] = "system"
) -> Optional[dict]:
    """Fetch a single variant annotation with database caching.

    Flow:

    1. Validate the variant format (security gate for raw SQL).
    2. Check the database cache.
    3. On a cache miss, fetch from VEP.
    4. Store the new annotation and return it.
    """
    variant_id = validate_variant_id(variant_id)
    logger.info("Fetching annotation for %s", variant_id)

    cached = await _get_cached_annotation(variant_id, db)
    if cached:
        logger.info("Cache hit for %s", variant_id)
        return cached

    logger.info("Cache miss for %s, fetching from VEP", variant_id)
    annotation = await _fetch_from_vep([variant_id])

    if not annotation or variant_id not in annotation:
        return None

    await _store_annotations_batch([annotation[variant_id]], db, fetched_by)
    logger.info("Cached annotation for %s", variant_id)
    return annotation[variant_id]


async def get_variant_annotations_batch(
    variant_ids: List[str],
    db: AsyncSession,
    fetched_by: Optional[str] = "system",
    batch_size: Optional[int] = None,
) -> Dict[str, Optional[dict]]:
    """Fetch annotations for many variants with batching and caching.

    Flow:

    1. Validate every variant format (skipping invalid ones with a warning).
    2. Load cached annotations for all validated ids.
    3. Batch-fetch the missing variants from VEP (configurable batch size).
    4. Store the new annotations and merge them into the result.

    Returns a dict keyed by the validated variant id; missing/failed
    variants map to ``None``.
    """
    if batch_size is None:
        batch_size = settings.external_apis.vep.batch_size

    validated_ids: List[str] = []
    for vid in variant_ids:
        try:
            validated_ids.append(validate_variant_id(vid))
        except ValueError as exc:
            logger.warning("Skipping invalid variant: %s", exc)

    if not validated_ids:
        return {}

    cached = await _get_cached_annotations_batch(validated_ids, db)
    results: Dict[str, Optional[dict]] = {
        vid: cached.get(vid) for vid in validated_ids
    }

    missing = [vid for vid in validated_ids if vid not in cached]

    if not missing:
        logger.info("All %s variants found in cache", len(validated_ids))
        return results

    logger.info(
        "Fetching %s variants from VEP (batch size: %s)", len(missing), batch_size
    )

    for i in range(0, len(missing), batch_size):
        batch = missing[i : i + batch_size]
        try:
            batch_results = await _fetch_from_vep(batch)
            to_store = [batch_results[vid] for vid in batch if vid in batch_results]
            if to_store:
                await _store_annotations_batch(to_store, db, fetched_by)
            for vid in batch:
                if vid in batch_results:
                    results[vid] = batch_results[vid]

            if i + batch_size < len(missing):
                await asyncio.sleep(0.1)

        except VEPRateLimitError:
            logger.warning("Rate limited, waiting 60s before retry")
            await asyncio.sleep(60)
            try:
                batch_results = await _fetch_from_vep(batch)
                to_store = [
                    batch_results[vid] for vid in batch if vid in batch_results
                ]
                if to_store:
                    await _store_annotations_batch(to_store, db, fetched_by)
                for vid in batch:
                    if vid in batch_results:
                        results[vid] = batch_results[vid]
            except (VEPError, httpx.HTTPError, SQLAlchemyError) as exc:
                logger.error("Batch failed after rate limit retry: %s", exc)

        except (VEPError, httpx.HTTPError, SQLAlchemyError) as exc:
            logger.error("Batch annotation failed: %s", exc)

    return results
