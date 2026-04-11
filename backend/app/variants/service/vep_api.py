"""Ensembl VEP REST client for the variants service.

Extracted during Wave 4 from the monolithic ``variants/service.py``.
Owns the HTTP round-trip (``_fetch_from_vep``) and the response
parsing (``_parse_vep_response`` + two small extractors). All of
these functions are re-exported at the package level so the
``tests/test_variant_annotation_vep.py`` regression suite, which
imports ``_parse_vep_response`` directly, keeps working unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

from .errors import (
    VEPAPIError,
    VEPNotFoundError,
    VEPRateLimitError,
    VEPTimeoutError,
)
from .validators import _format_variant_for_vep

logger = logging.getLogger(__name__)


async def _fetch_from_vep(variant_ids: List[str]) -> Dict[str, dict]:
    """Fetch annotations from the Ensembl VEP REST API.

    Uses ``POST /vep/homo_sapiens/region`` with the correct input
    format per variant type:

    - SNV/indels: VCF format ``CHROM POS ID REF ALT QUAL FILTER INFO``
    - CNV/SVs: VEP default SV format ``CHROM START END SV_TYPE STRAND ID``

    Implements exponential backoff + jitter through the shared
    :func:`app.core.retry.retry_async` helper.

    Raises:
        VEPRateLimitError: 429 responses.
        VEPNotFoundError: 400 (invalid variant format) — non-retryable.
        VEPTimeoutError: timeout after all retries exhausted.
        VEPAPIError: other server errors (5xx), wrapped for retry.
    """
    from app.core.retry import RetryConfig, retry_async

    if not variant_ids:
        return {}

    vep_variants: List[str] = []
    for vid in variant_ids:
        formatted = _format_variant_for_vep(vid)
        if formatted:
            vep_variants.append(formatted)
        else:
            logger.warning("Skipping unrecognized variant format: %s", vid)

    if not vep_variants:
        return {}

    vep_base_url = settings.external_apis.vep.base_url
    vep_timeout = settings.external_apis.vep.timeout_seconds
    max_retries = settings.external_apis.vep.max_retries
    base_delay = settings.external_apis.vep.retry_backoff_factor

    endpoint = f"{vep_base_url}/vep/homo_sapiens/region"
    params = {
        "CADD": "1",
        "hgvs": "1",
        "mane": "1",
        "gencode_primary": "1",
    }

    retry_config = RetryConfig(
        max_attempts=max_retries,
        base_delay=base_delay,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(
            httpx.TimeoutException,
            httpx.NetworkError,
            VEPAPIError,
        ),
        non_retryable_exceptions=(
            VEPNotFoundError,
            VEPRateLimitError,
        ),
    )

    def on_retry(exc: Exception, attempt: int, delay: float) -> None:
        logger.warning(
            "VEP request failed (attempt %s/%s): %s. Retrying in %.1fs",
            attempt + 1,
            max_retries,
            type(exc).__name__,
            delay,
        )

    async def make_vep_request() -> Dict[str, dict]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                json={"variants": vep_variants},
                params=params,
                headers={"Content-Type": "application/json"},
                timeout=vep_timeout,
            )

            if response.status_code == 200:
                results = response.json()
                return _parse_vep_response(results, variant_ids)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning("VEP rate limited, retry after %ss", retry_after)
                raise VEPRateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )

            if response.status_code == 400:
                logger.error("Invalid variant format: %s", variant_ids)
                raise VEPNotFoundError("Invalid variant format")

            if response.status_code in (500, 502, 503, 504):
                raise VEPAPIError(f"VEP server error: {response.status_code}")

            raise VEPAPIError(f"Unexpected VEP error: {response.status_code}")

    try:
        return await retry_async(
            make_vep_request, config=retry_config, on_retry=on_retry
        )
    except httpx.TimeoutException as exc:
        raise VEPTimeoutError("VEP API timeout after all retries") from exc
    except httpx.NetworkError as exc:
        raise VEPAPIError(f"Network error after all retries: {exc}") from exc


def _parse_vep_response(
    results: List[Dict[str, Any]], original_ids: List[str]
) -> Dict[str, dict]:
    """Parse a VEP API response and match it back to the original ids.

    Matching strategy, in order of preference:

    1. Use the ``id`` field from the VEP response (we pass the variant
       id as the VCF ID column).
    2. Parse the id from the ``input`` field.
    3. Reconstruct from ``seq_region_name`` / ``start`` / ``allele_string``
       as a fallback for edge cases where neither ``id`` nor ``input``
       round-trips.
    """
    parsed: Dict[str, dict] = {}
    original_ids_upper = {vid.upper(): vid for vid in original_ids}

    for result in results:
        matched_id: Optional[str] = None

        # Strategy 1: VEP ``id`` field.
        vep_id = result.get("id", "")
        if vep_id and vep_id.upper() in original_ids_upper:
            matched_id = original_ids_upper[vep_id.upper()]

        # Strategy 2: parse from the ``input`` field.
        if not matched_id:
            input_str = result.get("input", "")
            if input_str:
                parts = input_str.split()
                if len(parts) >= 5:
                    input_id = parts[2]
                    if input_id.upper() in original_ids_upper:
                        matched_id = original_ids_upper[input_id.upper()]

        # Strategy 3: reconstruct from VEP coordinates.
        if not matched_id:
            chrom = result.get("seq_region_name", "")
            start = result.get("start", "")
            allele_string = result.get("allele_string", "")
            if "/" in allele_string:
                ref, alt = allele_string.split("/")
                reconstructed_id = f"{chrom}-{start}-{ref}-{alt}".upper()
                if reconstructed_id in original_ids_upper:
                    matched_id = original_ids_upper[reconstructed_id]
                else:
                    matched_id = reconstructed_id

        if not matched_id:
            input_val = result.get("input", "unknown")
            logger.warning("Could not match VEP result to original ID: %s", input_val)
            continue

        primary = _extract_primary_transcript(result)
        gnomad_af, gnomad_af_nfe = _extract_gnomad_frequencies(result)

        annotation = {
            "variant_id": matched_id,
            "annotation": result,  # Full VEP response
            "most_severe_consequence": result.get("most_severe_consequence"),
            "impact": primary.get("impact") if primary else None,
            "gene_symbol": primary.get("gene_symbol") if primary else None,
            "gene_id": primary.get("gene_id") if primary else None,
            "transcript_id": primary.get("transcript_id") if primary else None,
            "cadd_score": primary.get("cadd_phred") if primary else None,
            "gnomad_af": gnomad_af,
            "gnomad_af_nfe": gnomad_af_nfe,
            "polyphen_prediction": (
                primary.get("polyphen_prediction") if primary else None
            ),
            "polyphen_score": primary.get("polyphen_score") if primary else None,
            "sift_prediction": primary.get("sift_prediction") if primary else None,
            "sift_score": primary.get("sift_score") if primary else None,
            "hgvsc": primary.get("hgvsc") if primary else None,
            "hgvsp": primary.get("hgvsp") if primary else None,
            "assembly": result.get("assembly_name", "GRCh38"),
            "data_source": "Ensembl VEP",
            "vep_version": "114",  # Current Ensembl release
            "fetched_at": datetime.now(timezone.utc),
        }

        parsed[matched_id] = annotation

    return parsed


def _extract_primary_transcript(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the primary transcript consequence (MANE select preferred)."""
    transcript_consequences = result.get("transcript_consequences", [])
    if not transcript_consequences:
        return None

    for tc in transcript_consequences:
        if tc.get("mane_select"):
            return tc

    for tc in transcript_consequences:
        if tc.get("canonical"):
            return tc

    return transcript_consequences[0]


def _extract_gnomad_frequencies(
    result: Dict[str, Any],
) -> tuple[Optional[float], Optional[float]]:
    """Extract gnomAD allele frequencies from the ``colocated_variants`` list."""
    gnomad_af: Optional[float] = None
    gnomad_af_nfe: Optional[float] = None

    colocated = result.get("colocated_variants", [])
    if colocated:
        gnomad_af = colocated[0].get("gnomad_af")
        gnomad_af_nfe = colocated[0].get("gnomad_af_nfe")

    return gnomad_af, gnomad_af_nfe
