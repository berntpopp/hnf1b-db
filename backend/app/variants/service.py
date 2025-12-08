"""VEP variant annotation service with permanent database storage.

This module provides variant annotation fetching from Ensembl VEP with:
- Permanent database storage (fetched once, stored forever)
- Batch annotation support (up to 50 variants per request)
- Rate limiting compliance (15 req/sec per Ensembl guidelines)
- Comprehensive error handling with retry logic
- Provenance tracking

Note:
    Configuration is loaded from app.core.config.settings.
    Uses the same pattern as publications/service.py for consistency.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


# Custom exceptions (matching publications pattern)
class VEPError(Exception):
    """Base exception for VEP API errors."""

    pass


class VEPRateLimitError(VEPError):
    """Rate limit exceeded (429)."""

    pass


class VEPNotFoundError(VEPError):
    """Variant not found or invalid format (400/404)."""

    pass


class VEPTimeoutError(VEPError):
    """API request timed out."""

    pass


class VEPAPIError(VEPError):
    """General API error."""

    pass


def is_cnv_variant(variant_id: str) -> bool:
    """Check if variant is a CNV/structural variant.

    CNV formats supported:
    - VCF-style with symbolic allele: 17-36459258-A-<DEL>, 17-36459258-A-<DUP>
    - Region format: 17-36459258-37832869-DEL, 17:36459258-37832869:DEL

    Args:
        variant_id: Variant identifier

    Returns:
        True if variant is a CNV/structural variant
    """
    sv_types = r"(DEL|DUP|INS|INV|CNV)"
    cnv_pattern = rf"<{sv_types}>|-{sv_types}$|:{sv_types}$"
    return bool(re.search(cnv_pattern, variant_id, re.IGNORECASE))


def validate_variant_id(variant_id: str, allow_cnv: bool = True) -> str:
    """Validate and normalize variant ID format.

    Security: Prevents SQL injection by validating format with regex.

    Supports formats:
    1. SNV/indel: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)
    2. CNV symbolic (4-part): CHR-POS-REF-<SV_TYPE> (e.g., 17-36459258-A-<DEL>)
    3. CNV with END (5-part): CHR-POS-END-REF-<SV_TYPE>
       (e.g., 17-36459258-37832869-C-<DEL>)
    4. CNV region: CHR-START-END-SV_TYPE (e.g., 17-36459258-37832869-DEL)

    Args:
        variant_id: Variant in VCF format
        allow_cnv: If True, also accept CNV/structural variant formats

    Returns:
        Normalized variant ID without chr prefix

    Raises:
        ValueError: If variant format is invalid

    Examples:
        >>> validate_variant_id("17-36459258-A-G")
        '17-36459258-A-G'
        >>> validate_variant_id("chr17-36459258-A-<DEL>")
        '17-36459258-A-<DEL>'
        >>> validate_variant_id("17-36459258-37832869-C-<DEL>")
        '17-36459258-37832869-C-<DEL>'
        >>> validate_variant_id("17-36459258-37832869-DEL")
        '17-36459258-37832869-DEL'
    """
    # Remove chr prefix if present
    normalized = re.sub(r"^chr", "", variant_id, flags=re.IGNORECASE)

    # Normalize colon separators to dashes for region format
    # e.g., 17:36459258-37832869:DEL -> 17-36459258-37832869-DEL
    if ":" in normalized and "-" in normalized:
        normalized = normalized.replace(":", "-")

    # Pattern 1: Standard SNV/indel - CHR-POS-REF-ALT (ACGT bases only)
    snv_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-[ACGT]+$"

    # Pattern 2: CNV with symbolic allele (4-part) - CHR-POS-REF-<SV_TYPE>
    cnv_symbolic_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"

    # Pattern 3: CNV with END position (5-part) - CHR-POS-END-REF-<SV_TYPE>
    # Per VCF 4.3 spec: symbolic alleles need END for unique CNV identification
    cnv_with_end_pattern = r"^[0-9XYM]+-\d+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"

    # Pattern 4: CNV region format - CHR-START-END-SV_TYPE
    cnv_region_pattern = r"^[0-9XYM]+-\d+-\d+-(DEL|DUP|INS|INV|CNV)$"

    is_snv = bool(re.match(snv_pattern, normalized, re.IGNORECASE))
    is_cnv_symbolic = bool(re.match(cnv_symbolic_pattern, normalized, re.IGNORECASE))
    is_cnv_with_end = bool(re.match(cnv_with_end_pattern, normalized, re.IGNORECASE))
    is_cnv_region = bool(re.match(cnv_region_pattern, normalized, re.IGNORECASE))

    if is_snv:
        return normalized.upper()

    if allow_cnv and (is_cnv_symbolic or is_cnv_with_end or is_cnv_region):
        return normalized.upper()

    raise ValueError(
        f"Invalid variant format: {variant_id}. "
        "Expected: CHR-POS-REF-ALT (e.g., 17-36459258-A-G) or "
        "CHR-POS-END-REF-<TYPE> for CNVs (e.g., 17-36459258-37832869-C-<DEL>)"
    )


async def get_variant_annotation(
    variant_id: str, db: AsyncSession, fetched_by: Optional[str] = "system"
) -> Optional[dict]:
    """Fetch variant annotation with database caching.

    Flow:
    1. Validate variant format (security)
    2. Check database cache
    3. If cache miss, fetch from VEP API
    4. Store in cache and return

    Args:
        variant_id: Variant in VCF format (e.g., "17-36459258-A-G")
        db: Database session
        fetched_by: User or system identifier for audit trail

    Returns:
        dict|None: Variant annotation with VEP data, or None if not found

    Raises:
        ValueError: If variant format is invalid
        VEPAPIError: If VEP API fails
    """
    # Validate variant format (prevents SQL injection)
    variant_id = validate_variant_id(variant_id)
    logger.info(f"Fetching annotation for {variant_id}")

    # Check cache
    cached = await _get_cached_annotation(variant_id, db)
    if cached:
        logger.info(f"Cache hit for {variant_id}")
        return cached

    # Cache miss - fetch from VEP
    logger.info(f"Cache miss for {variant_id}, fetching from VEP")
    annotation = await _fetch_from_vep([variant_id])

    if not annotation or variant_id not in annotation:
        return None

    # Store in cache
    await _store_annotations_batch([annotation[variant_id]], db, fetched_by)
    logger.info(f"Cached annotation for {variant_id}")

    return annotation[variant_id]


async def get_variant_annotations_batch(
    variant_ids: List[str],
    db: AsyncSession,
    fetched_by: Optional[str] = "system",
    batch_size: int = 200,
) -> Dict[str, Optional[dict]]:
    """Fetch variant annotations for multiple variants with batching.

    Efficiently fetches annotations for multiple variants:
    1. Check database cache for all variants
    2. Batch fetch missing variants from VEP (50 per request)
    3. Store results in database
    4. Return all annotations

    Args:
        variant_ids: List of variants in VCF format
        db: Database session
        fetched_by: User or system identifier
        batch_size: Variants per VEP batch (default: 200, per Ensembl limits)

    Returns:
        Dict mapping variant_id to annotation (or None if not found)
    """
    # Validate all variants first
    validated_ids = []
    for vid in variant_ids:
        try:
            validated_ids.append(validate_variant_id(vid))
        except ValueError as e:
            logger.warning(f"Skipping invalid variant: {e}")

    if not validated_ids:
        return {}

    # Get cached annotations
    cached = await _get_cached_annotations_batch(validated_ids, db)
    results = {vid: cached.get(vid) for vid in validated_ids}

    # Find missing variants
    missing = [vid for vid in validated_ids if vid not in cached]

    if not missing:
        logger.info(f"All {len(validated_ids)} variants found in cache")
        return results

    logger.info(f"Fetching {len(missing)} variants from VEP (batch size: {batch_size})")

    # Batch fetch from VEP
    for i in range(0, len(missing), batch_size):
        batch = missing[i : i + batch_size]
        try:
            batch_results = await _fetch_from_vep(batch)

            # Store successful results
            to_store = [
                batch_results[vid] for vid in batch if vid in batch_results
            ]
            if to_store:
                await _store_annotations_batch(to_store, db, fetched_by)

            # Update results
            for vid in batch:
                if vid in batch_results:
                    results[vid] = batch_results[vid]

            # Rate limiting between batches
            if i + batch_size < len(missing):
                await asyncio.sleep(0.1)

        except VEPRateLimitError:
            logger.warning("Rate limited, waiting 60s before retry")
            await asyncio.sleep(60)
            # Retry the batch
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
            except Exception as e:
                logger.error(f"Batch failed after rate limit retry: {e}")

        except Exception as e:
            logger.error(f"Batch annotation failed: {e}")

    return results


async def _get_cached_annotation(
    variant_id: str, db: AsyncSession
) -> Optional[dict]:
    """Check database cache for variant annotation."""
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
    """Check database cache for multiple variants."""
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
    """Convert database row to annotation dict."""
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


def _format_variant_for_vep(variant_id: str) -> Optional[str]:
    """Format a variant ID for VEP POST API.

    Handles variant types:
    1. SNV/indel: Convert CHR-POS-REF-ALT to VCF format "CHROM POS ID REF ALT . . ."
    2. CNV region: Convert CHR-START-END-TYPE to VEP SV format
    3. CNV symbolic (4-part): CHR-POS-REF-<TYPE> - use POS for both start/end
    4. CNV with END (5-part): CHR-POS-END-REF-<TYPE> - use actual coordinates
    5. Internal CNV format: var:GENE:CHROM:START-END:TYPE

    Args:
        variant_id: Normalized variant ID

    Returns:
        VEP-formatted string or None if format not recognized

    Examples:
        >>> _format_variant_for_vep("17-36459258-A-G")
        '17 36459258 17-36459258-A-G A G . . .'
        >>> _format_variant_for_vep("17-36459258-37832869-DEL")
        '17 36459258 37832869 DEL + 17-36459258-37832869-DEL'
        >>> _format_variant_for_vep("17-36459258-A-<DEL>")
        '17 36459258 36459258 DEL + 17-36459258-A-<DEL>'
        >>> _format_variant_for_vep("17-36459258-37832869-C-<DEL>")
        '17 36459258 37832869 DEL + 17-36459258-37832869-C-<DEL>'
        >>> _format_variant_for_vep("var:HNF1B:17:36459258-37832869:DEL")
        '17 36459258 37832869 DEL + var:HNF1B:17:36459258-37832869:DEL'
    """
    # Check for internal CNV format: var:GENE:CHROM:START-END:TYPE
    # e.g., var:HNF1B:17:36459258-37832869:DEL
    internal_cnv_pattern = (
        r"^var:([A-Z0-9]+):([0-9XYM]+):(\d+)-(\d+):(DEL|DUP|INS|INV|CNV)$"
    )
    internal_match = re.match(internal_cnv_pattern, variant_id, re.IGNORECASE)
    if internal_match:
        _gene, chrom, start, end, sv_type = internal_match.groups()
        # VEP SV format: "CHROM START END SV_TYPE STRAND ID"
        return f"{chrom} {start} {end} {sv_type.upper()} + {variant_id}"

    parts = variant_id.split("-")

    # Check for CNV with END position (5-part): CHR-POS-END-REF-<TYPE>
    # e.g., 17-37733556-37733821-C-<DEL>
    cnv_with_end_pattern = r"^[0-9XYM]+-\d+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    if re.match(cnv_with_end_pattern, variant_id, re.IGNORECASE):
        chrom, start, end, _ref, alt = parts
        # Extract SV type from <DEL> format
        sv_type = alt.strip("<>").upper()
        # VEP SV format: "CHROM START END SV_TYPE STRAND ID"
        return f"{chrom} {start} {end} {sv_type} + {variant_id}"

    # Check for CNV region format: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)
    cnv_region_pattern = r"^[0-9XYM]+-\d+-\d+-(DEL|DUP|INS|INV|CNV)$"
    if re.match(cnv_region_pattern, variant_id, re.IGNORECASE):
        chrom, start, end, sv_type = parts
        # VEP SV format: "CHROM START END SV_TYPE STRAND ID"
        return f"{chrom} {start} {end} {sv_type.upper()} + {variant_id}"

    # Check for CNV symbolic format (4-part): CHR-POS-REF-<TYPE>
    # e.g., 17-36459258-A-<DEL>
    cnv_symbolic_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    if re.match(cnv_symbolic_pattern, variant_id, re.IGNORECASE):
        chrom, pos, _ref, alt = parts
        # Extract SV type from <DEL> format
        sv_type = alt.strip("<>").upper()
        # For symbolic alleles without end position, use same start/end
        # VEP will interpret based on the SV type
        return f"{chrom} {pos} {pos} {sv_type} + {variant_id}"

    # Standard SNV/indel format: CHR-POS-REF-ALT
    if len(parts) == 4:
        chrom, pos, ref, alt = parts
        # VCF format: "CHROM POS ID REF ALT QUAL FILTER INFO"
        return f"{chrom} {pos} {variant_id} {ref} {alt} . . ."

    return None


async def _fetch_from_vep(variant_ids: List[str]) -> Dict[str, dict]:
    """Fetch annotations from Ensembl VEP API.

    Uses POST /vep/homo_sapiens/region with appropriate format for each variant type:
    - SNV/indels: VCF format "CHROM POS ID REF ALT QUAL FILTER INFO"
    - CNV/SVs: VEP default SV format "CHROM START END SV_TYPE STRAND ID"

    See:
    - https://rest.ensembl.org/documentation/info/vep_region_post
    - https://www.ensembl.org/info/docs/tools/vep/vep_formats.html

    Args:
        variant_ids: List of variants in VCF or CNV format

    Returns:
        Dict mapping variant_id to annotation dict

    Raises:
        VEPRateLimitError: If rate limit exceeded (429)
        VEPAPIError: For other API errors
    """
    if not variant_ids:
        return {}

    # Format variants for VEP API
    vep_variants = []
    for vid in variant_ids:
        formatted = _format_variant_for_vep(vid)
        if formatted:
            vep_variants.append(formatted)
        else:
            logger.warning(f"Skipping unrecognized variant format: {vid}")

    if not vep_variants:
        return {}

    # Get VEP config
    vep_base_url = settings.external_apis.vep.base_url
    vep_timeout = settings.external_apis.vep.timeout_seconds
    max_retries = settings.external_apis.vep.max_retries
    backoff_factor = settings.external_apis.vep.retry_backoff_factor

    endpoint = f"{vep_base_url}/vep/homo_sapiens/region"
    params = {
        "CADD": "1",
        "hgvs": "1",
        "mane": "1",
        "gencode_primary": "1",
    }

    for attempt in range(max_retries):
        try:
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

                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"VEP rate limited, retry after {retry_after}s")
                    raise VEPRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds"
                    )

                elif response.status_code == 400:
                    logger.error(f"Invalid variant format: {variant_ids}")
                    raise VEPNotFoundError("Invalid variant format")

                elif response.status_code in (500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        backoff_time = backoff_factor ** attempt
                        logger.warning(
                            f"VEP API error {response.status_code}, "
                            f"retrying in {backoff_time}s"
                        )
                        await asyncio.sleep(backoff_time)
                        continue
                    raise VEPAPIError(f"VEP API error: {response.status_code}")

                else:
                    raise VEPAPIError(f"Unexpected VEP error: {response.status_code}")

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                backoff_time = backoff_factor ** attempt
                logger.warning(f"VEP timeout, retrying in {backoff_time}s")
                await asyncio.sleep(backoff_time)
                continue
            raise VEPTimeoutError("VEP API timeout")

        except httpx.NetworkError as e:
            if attempt < max_retries - 1:
                backoff_time = backoff_factor ** attempt
                logger.warning(f"VEP network error: {e}, retrying in {backoff_time}s")
                await asyncio.sleep(backoff_time)
                continue
            raise VEPAPIError(f"Network error: {e}")

    return {}


def _parse_vep_response(
    results: List[Dict[str, Any]], original_ids: List[str]
) -> Dict[str, dict]:
    """Parse VEP API response and match to original variant IDs.

    Matching strategy (in order of preference):
    1. Use 'id' field from VEP response (we pass variant ID as VCF ID)
    2. Parse from 'input' field (contains our original VCF-style input)
    3. Reconstruct from coordinates (fallback for edge cases)

    Args:
        results: VEP API response (list of annotations)
        original_ids: Original variant IDs for matching

    Returns:
        Dict mapping variant_id to parsed annotation
    """
    parsed = {}
    original_ids_upper = {vid.upper(): vid for vid in original_ids}

    for result in results:
        matched_id = None

        # Strategy 1: Try to get ID from VEP 'id' field (we passed variant ID here)
        vep_id = result.get("id", "")
        if vep_id and vep_id.upper() in original_ids_upper:
            matched_id = original_ids_upper[vep_id.upper()]

        # Strategy 2: Parse from 'input' field
        # Format: "CHROM POS ID REF ALT . . ." where ID is our variant ID
        if not matched_id:
            input_str = result.get("input", "")
            if input_str:
                parts = input_str.split()
                if len(parts) >= 5:
                    # ID is in position 2 (0-indexed)
                    input_id = parts[2]
                    if input_id.upper() in original_ids_upper:
                        matched_id = original_ids_upper[input_id.upper()]

        # Strategy 3: Reconstruct from VEP coordinates (fallback)
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
            logger.warning(f"Could not match VEP result to original ID: {input_val}")
            continue

        # Extract primary transcript (MANE select preferred)
        primary = _extract_primary_transcript(result)

        # Extract gnomAD frequencies from colocated_variants
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
            "polyphen_prediction": primary.get("polyphen_prediction") if primary else None,  # noqa: E501
            "polyphen_score": primary.get("polyphen_score") if primary else None,
            "sift_prediction": primary.get("sift_prediction") if primary else None,
            "sift_score": primary.get("sift_score") if primary else None,
            "hgvsc": primary.get("hgvsc") if primary else None,
            "hgvsp": primary.get("hgvsp") if primary else None,
            "assembly": result.get("assembly_name", "GRCh38"),
            "data_source": "Ensembl VEP",
            "vep_version": "114",  # Current Ensembl release
            "fetched_at": datetime.utcnow(),  # Timezone-naive for TIMESTAMP column
        }

        parsed[matched_id] = annotation

    return parsed


def _extract_primary_transcript(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract primary transcript consequence (MANE select preferred)."""
    transcript_consequences = result.get("transcript_consequences", [])

    if not transcript_consequences:
        return None

    # Prefer MANE select
    for tc in transcript_consequences:
        if tc.get("mane_select"):
            return tc

    # Fallback to canonical
    for tc in transcript_consequences:
        if tc.get("canonical"):
            return tc

    # Fallback to first
    return transcript_consequences[0]


def _extract_gnomad_frequencies(
    result: Dict[str, Any]
) -> tuple[Optional[float], Optional[float]]:
    """Extract gnomAD frequencies from colocated_variants."""
    gnomad_af = None
    gnomad_af_nfe = None

    colocated = result.get("colocated_variants", [])
    if colocated:
        gnomad_af = colocated[0].get("gnomad_af")
        gnomad_af_nfe = colocated[0].get("gnomad_af_nfe")

    return gnomad_af, gnomad_af_nfe


async def _store_annotations_batch(
    annotations: List[dict],
    db: AsyncSession,
    fetched_by: Optional[str] = "system",
) -> None:
    """Store variant annotations in database cache.

    Uses upsert (INSERT ... ON CONFLICT) to handle duplicates.

    Args:
        annotations: List of annotation dicts
        db: Database session
        fetched_by: User or system identifier
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
                "fetched_at": ann.get("fetched_at", datetime.utcnow()),
            },
        )

    await db.commit()
