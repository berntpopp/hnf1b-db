"""Ensembl VEP Variant Recoder client.

Extracted during Wave 4 from ``variant_validator.py``. Owns the
single-variant ``/variant_recoder/human/{id}`` GET path and the
batched ``/variant_recoder/homo_sapiens`` POST path.

The batched path has a hard ``VARIANT_RECODER_BATCH_SIZE`` cap
(200) enforced by the caller — per Ensembl limits. VCF-format
inputs are handled via a per-variant detour through the VEP
annotator because the recoder only accepts HGVS / rsID / SPDI.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

# Cache + settings are looked up dynamically through the package
# namespace so that the regression test suite can mock them with
# ``patch("app.phenopackets.validation.variant_validator.cache")``.
# See the comment in ``vep_annotate.py`` for the rationale.
from app.phenopackets.validation import variant_validator as _vv_pkg
from app.phenopackets.validation.variant_validator.format_validators import (
    is_vcf_format,
)
from app.phenopackets.validation.variant_validator.rate_limiter import (
    RateLimiter,
    check_rate_limit_headers,
)
from app.phenopackets.validation.variant_validator.vep_annotate import (
    VEPAnnotator,
)

logger = logging.getLogger(__name__)

# Maximum batch size for Variant Recoder POST endpoint (per Ensembl docs)
VARIANT_RECODER_BATCH_SIZE = 200


class VEPRecoder:
    """Async client for Ensembl VEP Variant Recoder."""

    def __init__(self, rate_limiter: RateLimiter, annotator: VEPAnnotator) -> None:
        """Wire the recoder to the shared rate limiter and VEP annotator."""
        self._rate_limiter = rate_limiter
        self._annotator = annotator
        self._max_retries = _vv_pkg.settings.external_apis.vep.max_retries
        self._backoff_factor = _vv_pkg.settings.external_apis.vep.retry_backoff_factor
        self._cache_ttl = _vv_pkg.settings.external_apis.vep.cache_ttl_seconds

    async def recode(self, variant: str) -> Optional[Dict[str, Any]]:
        """Recode a single variant via the VEP Variant Recoder.

        VCF-format input cannot be passed directly to the recoder, so
        we first resolve it to a canonical HGVS/rsID via a VEP
        annotation round-trip, then call the recoder with that.
        """
        cache_key = f"vep:recode:{variant}"
        if _vv_pkg.settings.external_apis.vep.cache_enabled:
            cached = await _vv_pkg.cache.get_json(cache_key)
            if cached:
                logger.debug("VEP recode cache hit for %s", variant)
                return cached

        await self._rate_limiter.acquire()

        vep_base_url = _vv_pkg.settings.external_apis.vep.base_url
        vep_timeout = _vv_pkg.settings.external_apis.vep.timeout_seconds

        if is_vcf_format(variant):
            annotation = await self._annotator.annotate(variant)
            if not annotation:
                logger.error("Failed to annotate VCF variant: %s", variant)
                return None
            input_variant = annotation.get("id")
            if not input_variant:
                logger.error("No variant ID in VEP response for: %s", variant)
                return None
        else:
            input_variant = variant

        endpoint = f"{vep_base_url}/variant_recoder/human/{input_variant}"
        params = {
            "fields": "id,hgvsg,hgvsc,hgvsp,spdi",
            "gencode_primary": "1",
        }

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        params=params,
                        headers={"Content-Type": "application/json"},
                        timeout=vep_timeout,
                    )
                    check_rate_limit_headers(response.headers)

                    if response.status_code == 200:
                        result = response.json()
                        if not result or not isinstance(result, list):
                            logger.error(
                                "Invalid VEP recoder response for: %s", variant
                            )
                            return None
                        recoded = result[0] if result else None
                        if not recoded:
                            logger.error("Empty VEP recoder response for: %s", variant)
                            return None
                        if _vv_pkg.settings.external_apis.vep.cache_enabled:
                            await _vv_pkg.cache.set_json(
                                cache_key, recoded, ttl=self._cache_ttl
                            )
                        logger.info("VEP recode successful for %s", variant)
                        return recoded

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning("Rate limited, waiting %ss", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 400:
                        logger.error("Invalid variant format for recoding: %s", variant)
                        return None

                    if response.status_code in (500, 502, 503, 504):
                        if attempt < self._max_retries - 1:
                            backoff_time = self._backoff_factor**attempt
                            logger.warning(
                                "VEP recoder API error %s, retrying in %ss",
                                response.status_code,
                                backoff_time,
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        logger.error(
                            "VEP recoder API error %s after retries",
                            response.status_code,
                        )
                        return None

                    logger.error(
                        "Unexpected VEP recoder API error %s",
                        response.status_code,
                    )
                    return None

            except httpx.TimeoutException:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning(
                        "VEP recoder API timeout, retrying in %ss", backoff_time
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("VEP recoder API timeout after retries")
                return None

            except httpx.NetworkError as exc:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning(
                        "VEP recoder API network error: %s, retrying in %ss",
                        exc,
                        backoff_time,
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("VEP recoder API network error after retries: %s", exc)
                return None

            except (
                ValueError,
                KeyError,
                AttributeError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                logger.error("Unexpected VEP recoder error: %s", exc, exc_info=True)
                return None

        return None

    async def recode_batch(
        self,
        variants: List[str],
        include_vcf: bool = True,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Recode many variants in parallel-friendly batches.

        Splits VCF variants (handled one-by-one via the single-variant
        path) from HGVS/rsID/SPDI variants (handled through the POST
        ``/variant_recoder/homo_sapiens`` endpoint with ``ids=[...]``).
        """
        if not variants:
            return {}

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        vcf_variants: List[str] = []
        non_vcf_variants: List[str] = []

        for v in variants:
            (vcf_variants if is_vcf_format(v) else non_vcf_variants).append(v)

        for vcf_v in vcf_variants:
            try:
                results[vcf_v] = await self.recode(vcf_v)
            except (
                ValueError,
                KeyError,
                AttributeError,
                IndexError,
                TypeError,
                httpx.HTTPError,
                httpx.RequestError,
            ) as exc:
                logger.warning("Failed to recode VCF variant %s: %s", vcf_v, exc)
                results[vcf_v] = None

        if non_vcf_variants:
            for i in range(0, len(non_vcf_variants), VARIANT_RECODER_BATCH_SIZE):
                batch = non_vcf_variants[i : i + VARIANT_RECODER_BATCH_SIZE]
                batch_results = await self._recode_batch_post(batch, include_vcf)
                for v in batch:
                    results[v] = batch_results.get(v)
                if i + VARIANT_RECODER_BATCH_SIZE < len(non_vcf_variants):
                    await asyncio.sleep(0.1)

        return results

    async def _recode_batch_post(
        self,
        variants: List[str],
        include_vcf: bool = True,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Call the Variant Recoder POST endpoint for a pre-filtered batch."""
        if not variants:
            return {}

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        uncached_variants: List[str] = []

        for v in variants:
            cache_key = f"vep:recode:{v}"
            if _vv_pkg.settings.external_apis.vep.cache_enabled:
                cached = await _vv_pkg.cache.get_json(cache_key)
                if cached:
                    results[v] = cached
                    continue
            uncached_variants.append(v)

        if not uncached_variants:
            return results

        await self._rate_limiter.acquire()

        vep_base_url = _vv_pkg.settings.external_apis.vep.base_url
        vep_timeout = _vv_pkg.settings.external_apis.vep.timeout_seconds

        endpoint = f"{vep_base_url}/variant_recoder/homo_sapiens"
        params: Dict[str, Any] = {
            "fields": "id,hgvsg,hgvsc,hgvsp,spdi",
            "gencode_primary": "1",
        }
        if include_vcf:
            params["vcf_string"] = "1"

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json={"ids": uncached_variants},
                        params=params,
                        headers={"Content-Type": "application/json"},
                        timeout=vep_timeout,
                    )
                    check_rate_limit_headers(response.headers)

                    if response.status_code == 200:
                        api_results = response.json()
                        for item in api_results:
                            input_variant = item.get("input")
                            if input_variant:
                                if _vv_pkg.settings.external_apis.vep.cache_enabled:
                                    cache_key = f"vep:recode:{input_variant}"
                                    await _vv_pkg.cache.set_json(
                                        cache_key, item, ttl=self._cache_ttl
                                    )
                                results[input_variant] = item
                        for v in uncached_variants:
                            results.setdefault(v, None)
                        success_count = len([r for r in results.values() if r])
                        logger.info(
                            "Batch recoded %s/%s variants",
                            success_count,
                            len(uncached_variants),
                        )
                        return results

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning("Rate limited, waiting %ss", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 400:
                        logger.error("Invalid variants in batch: %s", uncached_variants)
                        for v in uncached_variants:
                            results[v] = None
                        return results

                    if response.status_code in (500, 502, 503, 504):
                        if attempt < self._max_retries - 1:
                            backoff_time = self._backoff_factor**attempt
                            logger.warning(
                                "VEP recoder API error %s, retrying in %ss",
                                response.status_code,
                                backoff_time,
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        logger.error(
                            "VEP recoder batch failed after retries: %s",
                            response.status_code,
                        )
                        for v in uncached_variants:
                            results[v] = None
                        return results

                    logger.error(
                        "Unexpected VEP recoder error: %s", response.status_code
                    )
                    for v in uncached_variants:
                        results[v] = None
                    return results

            except httpx.TimeoutException:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning("VEP recoder timeout, retrying in %ss", backoff_time)
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("VEP recoder batch timeout after retries")
                for v in uncached_variants:
                    results[v] = None
                return results

            except httpx.NetworkError as exc:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning("VEP recoder network error: %s, retrying", exc)
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("VEP recoder batch network error: %s", exc)
                for v in uncached_variants:
                    results[v] = None
                return results

            except (
                ValueError,
                KeyError,
                AttributeError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                logger.error(
                    "Unexpected VEP recoder batch error: %s", exc, exc_info=True
                )
                for v in uncached_variants:
                    results[v] = None
                return results

        for v in uncached_variants:
            results[v] = None
        return results
