"""Ensembl VEP annotation client used by :class:`VariantValidator`.

Extracted during Wave 4 from ``variant_validator.py``. Owns the
retry + cache + rate-limit logic for the two synchronous endpoints
we hit: ``/vep/human/hgvs`` (for HGVS input) and ``/vep/human/region``
(for VCF input, which needs to be converted to VEP's whitespace-
delimited region format first).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Cache + settings are looked up dynamically through the package
# namespace so that the regression test suite can mock them with
# ``patch("app.phenopackets.validation.variant_validator.cache")``
# and ``patch("app.phenopackets.validation.variant_validator.settings")``.
# The package ``__init__.py`` re-exports both symbols before loading
# this module, so the lookup resolves at call time.
from app.phenopackets.validation import variant_validator as _vv_pkg
from app.phenopackets.validation.variant_validator.format_validators import (
    fallback_validation,
    is_vcf_format,
    vcf_to_vep_format,
)
from app.phenopackets.validation.variant_validator.rate_limiter import (
    RateLimiter,
    check_rate_limit_headers,
)
from app.phenopackets.validation.variant_validator.suggestions import (
    get_notation_suggestions,
)

logger = logging.getLogger(__name__)


class VEPAnnotator:
    """Async client for Ensembl VEP annotation / HGVS validation."""

    def __init__(self, rate_limiter: RateLimiter) -> None:
        """Wire the annotator to a shared rate limiter + config-driven knobs."""
        self._rate_limiter = rate_limiter
        self._max_retries = _vv_pkg.settings.external_apis.vep.max_retries
        self._backoff_factor = _vv_pkg.settings.external_apis.vep.retry_backoff_factor
        self._cache_ttl = _vv_pkg.settings.external_apis.vep.cache_ttl_seconds

    async def validate_with_vep(
        self, hgvs_notation: str
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Validate an HGVS notation via Ensembl VEP.

        Returns ``(is_valid, vep_data, suggestions)`` — ``vep_data`` is
        the first VEP response dict when 200, ``None`` otherwise. The
        caller uses the suggestions list to build a useful 400 response.
        """
        try:
            vep_base_url = _vv_pkg.settings.external_apis.vep.base_url
            vep_timeout = _vv_pkg.settings.external_apis.vep.timeout_seconds
            vep_url = f"{vep_base_url}/vep/human/hgvs/{hgvs_notation}"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    vep_url,
                    headers={"Content-Type": "application/json"},
                    timeout=vep_timeout,
                )
                if response.status_code == 200:
                    vep_data = response.json()
                    return True, vep_data[0] if vep_data else None, []
                if response.status_code == 400:
                    return False, None, get_notation_suggestions(hgvs_notation)
                return False, None, ["VEP service temporarily unavailable"]
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            httpx.RequestError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            logger.debug(
                "VEP validation request failed, falling back to local validation: %s",
                exc,
            )
            return fallback_validation(hgvs_notation), None, []

    async def annotate(
        self,
        variant: str,
        include_annotations: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Annotate a variant via VEP with retry + cache + rate limit.

        Supports both VCF and HGVS input; the VCF path goes through
        the POST ``/vep/human/region`` endpoint while the HGVS path
        goes through GET ``/vep/human/hgvs``. See the module docstring
        for the full contract.
        """
        cache_key = f"vep:annotate:{variant}:{include_annotations}"
        if _vv_pkg.settings.external_apis.vep.cache_enabled:
            cached = await _vv_pkg.cache.get_json(cache_key)
            if cached:
                logger.debug("VEP cache hit for %s", variant)
                return cached

        await self._rate_limiter.acquire()

        is_vcf = is_vcf_format(variant)
        vep_base_url = _vv_pkg.settings.external_apis.vep.base_url
        vep_timeout = _vv_pkg.settings.external_apis.vep.timeout_seconds

        if is_vcf:
            vep_input = vcf_to_vep_format(variant)
            if not vep_input:
                logger.error("Failed to convert VCF variant: %s", variant)
                return None
            endpoint = f"{vep_base_url}/vep/human/region"
            method = "POST"
            json_data: Optional[Dict[str, Any]] = {"variants": [vep_input]}
        else:
            endpoint = f"{vep_base_url}/vep/human/hgvs/{variant}"
            method = "GET"
            json_data = None

        params: Dict[str, Any] = {}
        if include_annotations:
            params.update(
                {
                    "CADD": "1",
                    "hgvs": "1",
                    "mane": "1",
                    "gencode_primary": "1",
                }
            )

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    if method == "POST":
                        response = await client.post(
                            endpoint,
                            json=json_data,
                            params=params,
                            headers={"Content-Type": "application/json"},
                            timeout=vep_timeout,
                        )
                    else:
                        response = await client.get(
                            endpoint,
                            params=params,
                            headers={"Content-Type": "application/json"},
                            timeout=vep_timeout,
                        )

                    check_rate_limit_headers(response.headers)

                    if response.status_code == 200:
                        result = response.json()
                        annotation = result[0] if isinstance(result, list) else result
                        if _vv_pkg.settings.external_apis.vep.cache_enabled:
                            await _vv_pkg.cache.set_json(
                                cache_key, annotation, ttl=self._cache_ttl
                            )
                        logger.info("VEP annotation successful for %s", variant)
                        return annotation

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning("Rate limited, waiting %ss", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 400:
                        logger.error("Invalid variant format: %s", variant)
                        return None

                    if response.status_code in (500, 502, 503, 504):
                        if attempt < self._max_retries - 1:
                            backoff_time = self._backoff_factor**attempt
                            logger.warning(
                                "VEP API error %s, retrying in %ss (attempt %s/%s)",
                                response.status_code,
                                backoff_time,
                                attempt + 1,
                                self._max_retries,
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        logger.error(
                            "VEP API error %s after %s retries",
                            response.status_code,
                            self._max_retries,
                        )
                        return None

                    logger.error("Unexpected VEP API error %s", response.status_code)
                    return None

            except httpx.TimeoutException:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning(
                        "VEP API timeout, retrying in %ss (attempt %s/%s)",
                        backoff_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("VEP API timeout after %s retries", self._max_retries)
                return None

            except httpx.NetworkError as exc:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor**attempt
                    logger.warning(
                        "VEP API network error: %s, retrying in %ss (attempt %s/%s)",
                        exc,
                        backoff_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error(
                    "VEP API network error after %s retries: %s",
                    self._max_retries,
                    exc,
                )
                return None

            except (
                ValueError,
                KeyError,
                AttributeError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                logger.error("Unexpected VEP annotation error: %s", exc, exc_info=True)
                return None

        return None
