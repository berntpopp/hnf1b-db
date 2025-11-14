"""Variant format validation for HGVS, VCF, VRS, and CNV notations."""

import asyncio
import logging
import re
import time
from collections import OrderedDict
from difflib import get_close_matches
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class VariantValidator:
    """Validates variant formats including HGVS, VCF, VRS, and CNV notations."""

    def __init__(self):
        """Initialize validator with configurable cache and rate limiting."""
        # LRU cache with size limit (OrderedDict for simplicity)
        self._vep_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_size_limit = settings.VEP_CACHE_SIZE_LIMIT

        # Rate limiting state (configurable via settings)
        self._last_request_time = 0.0
        self._request_count = 0
        self._requests_per_second = settings.VEP_RATE_LIMIT_REQUESTS_PER_SECOND

        # Retry configuration
        self._max_retries = settings.VEP_MAX_RETRIES
        self._backoff_factor = settings.VEP_RETRY_BACKOFF_FACTOR

    async def validate_variant_with_vep(
        self, hgvs_notation: str
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Validate variant using Ensembl VEP API.

        Args:
            hgvs_notation: HGVS notation to validate

        Returns:
            Tuple of (is_valid, vep_data, suggestions)
        """
        try:
            vep_url = f"https://rest.ensembl.org/vep/human/hgvs/{hgvs_notation}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    vep_url, headers={"Content-Type": "application/json"}, timeout=10.0
                )

                if response.status_code == 200:
                    vep_data = response.json()
                    return True, vep_data[0] if vep_data else None, []
                elif response.status_code == 400:
                    suggestions = self._get_notation_suggestions(hgvs_notation)
                    return False, None, suggestions
                else:
                    return False, None, ["VEP service temporarily unavailable"]

        except Exception:
            return self._fallback_validation(hgvs_notation), None, []

    def validate_variant_formats(self, variant_descriptor: Dict[str, Any]) -> List[str]:
        """Validate variant formats in a variation descriptor.

        Args:
            variant_descriptor: Variation descriptor from phenopacket

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not variant_descriptor.get("id"):
            errors.append("Variant descriptor missing 'id' field")

        expressions = variant_descriptor.get("expressions", [])
        for expr in expressions:
            syntax = expr.get("syntax", "")
            value = expr.get("value", "")

            if syntax == "hgvs.c":
                if not self._validate_hgvs_c(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS c. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "hgvs.p":
                if not self._validate_hgvs_p(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS p. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "hgvs.g":
                if not self._validate_hgvs_g(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS g. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "vcf":
                if not self._validate_vcf(value):
                    errors.append(f"Invalid VCF format: {value}")
            elif syntax == "spdi":
                if not self._validate_spdi(value):
                    errors.append(f"Invalid SPDI format: {value}")

        if "vrsAllele" in variant_descriptor:
            vrs_errors = self._validate_vrs_allele(variant_descriptor["vrsAllele"])
            errors.extend(vrs_errors)

        if "structuralType" in variant_descriptor:
            has_valid_cnv = False
            for expr in expressions:
                if expr.get("syntax") == "iscn" or self._is_ga4gh_cnv_notation(
                    expr.get("value", "")
                ):
                    has_valid_cnv = True
                    break
            if not has_valid_cnv:
                errors.append("Structural variant missing valid CNV notation")

        return errors

    def validate_variants_in_phenopacket(
        self, phenopacket: Dict[str, Any]
    ) -> List[str]:
        """Validate all variants in a phenopacket.

        Args:
            phenopacket: Complete phenopacket document

        Returns:
            List of all variant validation errors
        """
        all_errors = []

        for interpretation in phenopacket.get("interpretations", []):
            genomic_interps = interpretation.get("diagnosis", {}).get(
                "genomicInterpretations", []
            )
            for gi in genomic_interps:
                variant_descriptor = gi.get("variantInterpretation", {}).get(
                    "variationDescriptor", {}
                )
                if variant_descriptor:
                    errors = self.validate_variant_formats(variant_descriptor)
                    if errors:
                        subject_id = gi.get("subjectOrBiosampleId", "unknown")
                        all_errors.extend(
                            [f"Subject {subject_id}: {e}" for e in errors]
                        )

        return all_errors

    def _get_notation_suggestions(self, invalid_notation: str) -> List[str]:
        """Generate suggestions for fixing invalid notation.

        Args:
            invalid_notation: The invalid notation string

        Returns:
            List of suggestions
        """
        suggestions = []

        common_patterns = [
            "NM_000458.4:c.544+1G>A",
            "NM_000458.4:c.1234A>T",
            "NM_000458.4:c.123del",
            "NM_000458.4:c.123_456dup",
            "chr17:g.36459258A>G",
            "17:36459258-37832869:DEL",
        ]

        if "c." in invalid_notation or "p." in invalid_notation:
            if not invalid_notation.startswith("NM_"):
                suggestions.append(
                    "Did you mean to include a transcript? Try: NM_000458.4:"
                    + invalid_notation
                )

            if re.match(r"^c\d+", invalid_notation) or re.match(
                r"^p[A-Z]", invalid_notation
            ):
                suggestions.append(
                    f"Missing dot notation. Did you mean: {invalid_notation[0]}.{invalid_notation[1:]}?"
                )

        if re.match(r"^\d+[-:]\d+[-:][ATCG]+[-:][ATCG]+$", invalid_notation):
            parts = re.split(r"[-:]", invalid_notation)
            if len(parts) >= 4:
                suggestions.append(
                    f"For VCF format, use: chr17-{parts[0]}-{parts[2]}-{parts[3]}"
                )
                suggestions.append(
                    f"For HGVS genomic, use: NC_000017.11:g.{parts[0]}{parts[2]}>{parts[3]}"
                )

        notation_lower = invalid_notation.lower()
        if re.search(r"\b(del|dup|deletion|duplication)\b", notation_lower):
            if ":" not in invalid_notation:
                suggestions.append(
                    "For CNVs, use format: 17:start-end:DEL or 17:start-end:DUP"
                )

        close_matches = get_close_matches(
            invalid_notation, common_patterns, n=3, cutoff=0.6
        )
        if close_matches:
            suggestions.append(f"Similar valid formats: {', '.join(close_matches)}")

        if not suggestions:
            suggestions.append(
                "Valid formats: NM_000458.4:c.123A>G, chr17:g.36459258A>G, 17:start-end:DEL"
            )

        return suggestions

    def _fallback_validation(self, notation: str) -> bool:
        """Fallback validation using regex when VEP is unavailable."""
        return (
            self._validate_hgvs_c(notation)
            or self._validate_hgvs_p(notation)
            or self._validate_hgvs_g(notation)
            or self._validate_vcf(notation)
            or self._is_ga4gh_cnv_notation(notation)
        )

    def _validate_hgvs_c(self, value: str) -> bool:
        """Validate HGVS c. notation.

        Examples: NM_000458.4:c.544+1G>A, c.1234A>T, c.123_456del
        """
        patterns = [
            r"^(NM_\d+\.\d+:)?c\.([+\-*]?\d+[+\-]?\d*)([ATCG]>[ATCG])$",  # Substitution
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?del([ATCG]+)?$",  # Deletion
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?dup([ATCG]+)?$",  # Duplication
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?ins([ATCG]+)$",  # Insertion
            r"^(NM_\d+\.\d+:)?c\.\d+[+\-]\d+[ATCG]>[ATCG]$",  # Intronic
        ]
        return any(bool(re.match(pattern, value)) for pattern in patterns)

    def _validate_hgvs_p(self, value: str) -> bool:
        """Validate HGVS p. notation.

        Examples: NP_000449.3:p.Arg181*, p.Val123Phe
        """
        pattern = r"^(NP_\d+\.\d+:)?p\.([A-Z][a-z]{2}\d+[A-Z][a-z]{2}|[A-Z][a-z]{2}\d+\*|[A-Z][a-z]{2}\d+[A-Z][a-z]{2}fs|\?)$"
        return bool(re.match(pattern, value))

    def _validate_hgvs_g(self, value: str) -> bool:
        """Validate HGVS g. notation.

        Examples: NC_000017.11:g.36459258A>G
        """
        pattern = r"^NC_\d+\.\d+:g\.\d+[ATCG]>[ATCG]$"
        return bool(re.match(pattern, value))

    def _validate_vcf(self, value: str) -> bool:
        """Validate VCF format.

        Examples: chr17-36459258-A-G, 17-36459258-A-G
        """
        pattern = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-[ATCG]+-([ATCG]+|<[A-Z]+>)$"
        return bool(re.match(pattern, value, re.IGNORECASE))

    def _validate_spdi(self, value: str) -> bool:
        """Validate SPDI notation.

        Examples: NC_000017.11:36459257:A:G
        """
        pattern = r"^NC_\d+\.\d+:\d+:[ATCG]*:[ATCG]+$"
        return bool(re.match(pattern, value))

    def _is_ga4gh_cnv_notation(self, value: str) -> bool:
        """Check if value matches GA4GH CNV notation.

        Examples: 17:36459258-37832869:DEL, 17:36459258-37832869:DUP
        """
        pattern = r"^([1-9]|1[0-9]|2[0-2]|X|Y):\d+-\d+:(DEL|DUP|INS|INV)$"
        return bool(re.match(pattern, value))

    def _validate_vrs_allele(self, vrs_allele: Dict[str, Any]) -> List[str]:
        """Validate VRS 2.0 allele structure."""
        errors = []

        if vrs_allele.get("type") != "Allele":
            errors.append("VRS allele must have type 'Allele'")

        location = vrs_allele.get("location", {})
        if not location:
            errors.append("VRS allele missing 'location' field")
        elif location.get("type") != "SequenceLocation":
            errors.append("VRS location must have type 'SequenceLocation'")

        state = vrs_allele.get("state", {})
        if not state:
            errors.append("VRS allele missing 'state' field")
        elif state.get("type") not in [
            "LiteralSequenceExpression",
            "ReferenceLengthExpression",
        ]:
            errors.append(
                "VRS state must be LiteralSequenceExpression or ReferenceLengthExpression"
            )

        return errors

    async def annotate_variant_with_vep(
        self,
        variant: str,
        include_annotations: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Annotate variant with VEP including CADD, gnomAD, consequences.

        Supports both VCF and HGVS formats:
        - VCF: "17-36459258-A-G" or "chr17-36459258-A-G"
        - HGVS: "NM_000458.4:c.544+1G>A"

        Args:
            variant: Variant in VCF or HGVS format
            include_annotations: Include CADD, gnomAD, etc.

        Returns:
            VEP annotation dict with:
            - most_severe_consequence
            - transcript_consequences (with CADD scores)
            - colocated_variants (with gnomAD frequencies)
            - assembly_name, seq_region_name, start, end, allele_string

        Example:
            annotation = await validator.annotate_variant_with_vep("17-36459258-A-G")
            consequence = annotation["most_severe_consequence"]
            cadd = annotation["transcript_consequences"][0]["cadd_phred"]
            gnomad_af = annotation["colocated_variants"][0]["gnomad_af"]
        """
        # Check cache first (if enabled)
        cache_key = f"{variant}:{include_annotations}"
        if settings.VEP_CACHE_ENABLED and cache_key in self._vep_cache:
            logger.debug(f"VEP cache hit for {variant}")
            # Move to end (LRU)
            self._vep_cache.move_to_end(cache_key)
            return self._vep_cache[cache_key]

        # Rate limiting (configurable per Ensembl guidelines)
        await self._rate_limit()

        # Determine format and build request
        is_vcf = self._is_vcf_format(variant)

        if is_vcf:
            # VCF format: use POST /vep/human/region
            vep_input = self._vcf_to_vep_format(variant)
            if not vep_input:
                logger.error(f"Failed to convert VCF variant: {variant}")
                return None

            endpoint = f"{settings.VEP_API_BASE_URL}/vep/human/region"
            method = "POST"
            json_data = {"variants": [vep_input]}
        else:
            # HGVS format: use GET /vep/human/hgvs
            endpoint = f"{settings.VEP_API_BASE_URL}/vep/human/hgvs/{variant}"
            method = "GET"
            json_data = None

        # Build query parameters
        params = {}
        if include_annotations:
            params.update({
                "CADD": "1",            # CADD scores
                "hgvs": "1",            # HGVS notations
                "mane": "1",            # MANE select transcripts
                "gencode_primary": "1", # GENCODE primary (2025 best practice)
            })

        # Retry with exponential backoff
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    if method == "POST":
                        response = await client.post(
                            endpoint,
                            json=json_data,
                            params=params,
                            headers={"Content-Type": "application/json"},
                            timeout=settings.VEP_REQUEST_TIMEOUT_SECONDS,
                        )
                    else:
                        response = await client.get(
                            endpoint,
                            params=params,
                            headers={"Content-Type": "application/json"},
                            timeout=settings.VEP_REQUEST_TIMEOUT_SECONDS,
                        )

                    # Check rate limit headers
                    self._check_rate_limit_headers(response.headers)

                    # Handle response
                    if response.status_code == 200:
                        result = response.json()
                        annotation = result[0] if isinstance(result, list) else result

                        # Cache successful result (LRU eviction)
                        if settings.VEP_CACHE_ENABLED:
                            self._cache_annotation(cache_key, annotation)

                        logger.info(f"VEP annotation successful for {variant}")
                        return annotation

                    elif response.status_code == 429:
                        # Rate limited - respect Retry-After header
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue  # Don't count as retry attempt

                    elif response.status_code == 400:
                        # Invalid variant format - don't retry
                        logger.error(f"Invalid variant format: {variant}")
                        return None

                    elif response.status_code in (500, 502, 503, 504):
                        # Server error - retry with backoff
                        if attempt < self._max_retries - 1:
                            backoff_time = self._backoff_factor ** attempt
                            logger.warning(
                                f"VEP API error {response.status_code}, "
                                f"retrying in {backoff_time}s (attempt {attempt + 1}/{self._max_retries})"
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        else:
                            logger.error(
                                f"VEP API error {response.status_code} after {self._max_retries} retries"
                            )
                            return None

                    else:
                        logger.error(f"Unexpected VEP API error {response.status_code}")
                        return None

            except httpx.TimeoutException:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor ** attempt
                    logger.warning(
                        f"VEP API timeout, retrying in {backoff_time}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"VEP API timeout after {self._max_retries} retries")
                    return None

            except httpx.NetworkError as e:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor ** attempt
                    logger.warning(
                        f"VEP API network error: {e}, retrying in {backoff_time}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"VEP API network error after {self._max_retries} retries: {e}")
                    return None

            except Exception as e:
                logger.error(f"Unexpected VEP annotation error: {e}", exc_info=True)
                return None

        return None

    def _cache_annotation(self, cache_key: str, annotation: Dict[str, Any]) -> None:
        """Cache annotation with LRU eviction.

        Args:
            cache_key: Cache key
            annotation: Annotation data to cache
        """
        # Add to cache
        self._vep_cache[cache_key] = annotation

        # LRU eviction if over limit
        if len(self._vep_cache) > self._cache_size_limit:
            # Remove oldest (first) item
            self._vep_cache.popitem(last=False)
            logger.debug(f"VEP cache evicted oldest entry (size: {len(self._vep_cache)})")

    async def _rate_limit(self):
        """Implement Ensembl rate limiting (15 requests/second).

        Per Ensembl guidelines: https://github.com/Ensembl/ensembl-rest/wiki/Rate-Limits
        - 55,000 requests per hour
        - Average 15 requests per second
        - Must respect Retry-After header on 429 responses
        """
        current_time = time.time()

        # Reset counter every second
        if current_time - self._last_request_time >= 1.0:
            self._request_count = 0
            self._last_request_time = current_time

        # If at limit, wait until next second
        if self._request_count >= self._requests_per_second:
            sleep_time = 1.0 - (current_time - self._last_request_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self._request_count = 0
            self._last_request_time = time.time()

        self._request_count += 1

    def _check_rate_limit_headers(self, headers):
        """Check X-RateLimit-* headers and warn if approaching limit."""
        remaining = headers.get("X-RateLimit-Remaining")
        limit = headers.get("X-RateLimit-Limit")

        if remaining and limit:
            remaining_int = int(remaining)
            limit_int = int(limit)

            # Warn if < 10% remaining
            if remaining_int < limit_int * 0.1:
                print(f"⚠️  Rate limit warning: {remaining}/{limit} requests remaining")

    @staticmethod
    def _is_vcf_format(variant: str) -> bool:
        """Check if variant is VCF format (chr-pos-ref-alt)."""
        return bool(re.match(r"^(chr)?[\dXYM]+-\d+-[ACGT]+-[ACGT]+$", variant, re.I))

    @staticmethod
    def _vcf_to_vep_format(vcf_variant: str) -> Optional[str]:
        """Convert VCF variant to VEP POST format.

        Input: "17-36459258-A-G" or "chr17-36459258-A-G"
        Output: "17 36459258 . A G . . ."
        """
        # Remove "chr" prefix if present
        vcf_variant = vcf_variant.replace("chr", "").replace("Chr", "").replace("CHR", "")

        # Parse components
        parts = vcf_variant.split("-")
        if len(parts) != 4:
            return None

        chrom, pos, ref, alt = parts

        # Validate
        if not pos.isdigit():
            return None

        # Format for VEP: "chrom pos . ref alt . . ."
        return f"{chrom} {pos} . {ref} {alt} . . ."

    async def recode_variant_with_vep(
        self, variant: str
    ) -> Optional[Dict[str, Any]]:
        """Recode variant to all possible representations using VEP Variant Recoder.

        Converts between different variant representations:
        - HGVS (c., p., g. notations)
        - VCF (chr-pos-ref-alt)
        - SPDI (genomic coordinates)
        - Variant IDs (rsIDs)
        - GA4GH VRS notation

        Args:
            variant: Variant in any supported format (HGVS, VCF, rsID, SPDI)

        Returns:
            Dict with all possible variant representations:
            - hgvsg: Genomic HGVS (list)
            - hgvsc: Coding HGVS (list)
            - hgvsp: Protein HGVS (list)
            - spdi: SPDI notation (dict)
            - vcf_string: VCF representation (string)
            - id: Variant IDs (rsIDs, etc.)

        Example:
            result = await validator.recode_variant_with_vep("17-36459258-A-G")
            hgvsc = result["hgvsc"][0]  # ["NM_000458.4:c.544G>A"]
        """
        # Check cache first
        cache_key = f"recode:{variant}"
        if settings.VEP_CACHE_ENABLED and cache_key in self._vep_cache:
            logger.debug(f"VEP recode cache hit for {variant}")
            self._vep_cache.move_to_end(cache_key)
            return self._vep_cache[cache_key]

        # Rate limiting
        await self._rate_limit()

        # Convert VCF format to genomic HGVS for variant_recoder
        # VEP variant_recoder doesn't accept our VCF format (17-pos-ref-alt)
        # It needs HGVS or rsID
        if self._is_vcf_format(variant):
            # For VCF, we need to use the regular VEP API first to get HGVS
            annotation = await self.annotate_variant_with_vep(variant)
            if not annotation:
                logger.error(f"Failed to annotate VCF variant: {variant}")
                return None

            # Extract genomic HGVS from annotation
            input_variant = annotation.get("id")
            if not input_variant:
                logger.error(f"No variant ID in VEP response for: {variant}")
                return None
        else:
            input_variant = variant

        endpoint = f"{settings.VEP_API_BASE_URL}/variant_recoder/human/{input_variant}"

        # Build query parameters
        params = {
            "fields": "id,hgvsg,hgvsc,hgvsp,spdi",
            "gencode_primary": "1",  # Limit to primary transcripts
        }

        # Retry with exponential backoff
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        params=params,
                        headers={"Content-Type": "application/json"},
                        timeout=settings.VEP_REQUEST_TIMEOUT_SECONDS,
                    )

                    # Check rate limit headers
                    self._check_rate_limit_headers(response.headers)

                    # Handle response
                    if response.status_code == 200:
                        result = response.json()

                        # VEP returns array of results
                        if not result or not isinstance(result, list):
                            logger.error(f"Invalid VEP recoder response for: {variant}")
                            return None

                        # Take first result
                        recoded = result[0] if result else None

                        if not recoded:
                            logger.error(f"Empty VEP recoder response for: {variant}")
                            return None

                        # Cache successful result
                        if settings.VEP_CACHE_ENABLED:
                            self._cache_annotation(cache_key, recoded)

                        logger.info(f"VEP recode successful for {variant}")
                        return recoded

                    elif response.status_code == 429:
                        # Rate limited
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    elif response.status_code == 400:
                        logger.error(f"Invalid variant format for recoding: {variant}")
                        return None

                    elif response.status_code in (500, 502, 503, 504):
                        if attempt < self._max_retries - 1:
                            backoff_time = self._backoff_factor ** attempt
                            logger.warning(
                                f"VEP recoder API error {response.status_code}, "
                                f"retrying in {backoff_time}s"
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        else:
                            logger.error(
                                f"VEP recoder API error {response.status_code} after retries"
                            )
                            return None

                    else:
                        logger.error(
                            f"Unexpected VEP recoder API error {response.status_code}"
                        )
                        return None

            except httpx.TimeoutException:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor ** attempt
                    logger.warning(
                        f"VEP recoder API timeout, retrying in {backoff_time}s"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    logger.error("VEP recoder API timeout after retries")
                    return None

            except httpx.NetworkError as e:
                if attempt < self._max_retries - 1:
                    backoff_time = self._backoff_factor ** attempt
                    logger.warning(
                        f"VEP recoder API network error: {e}, retrying in {backoff_time}s"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"VEP recoder API network error after retries: {e}")
                    return None

            except Exception as e:
                logger.error(f"Unexpected VEP recoder error: {e}", exc_info=True)
                return None

        return None
