"""Public :class:`VariantValidator` facade.

Re-assembles the pieces split out during Wave 4 into a single class
that preserves the pre-refactor public API. Existing callers that
did ``from app.phenopackets.validation.variant_validator import
VariantValidator`` continue to work unchanged — the top-level
``__init__.py`` re-exports this class from the same import path.

The facade keeps the method names the pre-refactor test suite
(1,671-line ``test_variant_validator_enhanced.py``) and the
VEP endpoint (``test_variant_annotation_vep.py``) expect:

- ``validate_variant_with_vep``
- ``validate_variant_formats``
- ``validate_variants_in_phenopacket``
- ``annotate_variant_with_vep``
- ``recode_variant_with_vep``
- ``recode_variants_batch``

The private ``_`` helpers the tests still reach into (to exercise
individual format validators, cache behaviour, and rate limiting)
are preserved on the class — they just forward to the extracted
module-level functions / components.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple

# Looked up dynamically through the package so that tests patching
# ``app.phenopackets.validation.variant_validator.settings`` affect the
# values read when a new ``VariantValidator`` is constructed after the
# patch. See the longer comment in ``vep_annotate.py``.
from app.phenopackets.validation import variant_validator as _vv_pkg

from . import format_validators
from .rate_limiter import RateLimiter, check_rate_limit_headers
from .suggestions import get_notation_suggestions
from .vep_annotate import VEPAnnotator
from .vep_recoder import VEPRecoder

logger = logging.getLogger(__name__)


class VariantValidator:
    """Validates variant formats and orchestrates VEP round-trips.

    Public API is unchanged from the pre-Wave-4 flat module. Internals
    delegate to four extracted components: the ``format_validators``
    module of pure regex checks, ``suggestions`` for the fuzzy-match
    helper, ``RateLimiter`` for the Ensembl 15-req/sec budget, and
    the ``VEPAnnotator`` / ``VEPRecoder`` HTTP clients.
    """

    def __init__(self) -> None:
        """Initialise the validator with configurable rate limiting.

        Cache is handled by the centralized Redis cache service. The
        component wiring is deliberately synchronous so tests can
        monkey-patch ``_annotator`` / ``_recoder`` directly. Settings
        are read through ``_vv_pkg.settings`` so that tests patching
        ``app.phenopackets.validation.variant_validator.settings``
        affect every ``VariantValidator`` constructed after the patch.
        """
        _s = _vv_pkg.settings

        self._rate_limiter = RateLimiter(
            requests_per_second=_s.rate_limiting.vep.requests_per_second,
        )
        self._annotator = VEPAnnotator(self._rate_limiter)
        self._recoder = VEPRecoder(self._rate_limiter, self._annotator)

    # ----------------------------------------------------------------
    # Legacy attribute surface.
    #
    # The pre-Wave-4 ``VariantValidator`` had these fields directly on
    # the instance. The 1,671-line regression test suite still reads —
    # and in a few places mutates — them. We expose them as properties
    # that delegate to the sub-components so the old tests keep
    # working without modification.
    # ----------------------------------------------------------------

    @property
    def _requests_per_second(self) -> int:
        """Read-only proxy to the shared rate limiter's rps cap."""
        return self._rate_limiter._requests_per_second

    @_requests_per_second.setter
    def _requests_per_second(self, value: int) -> None:
        """Write-through to the rate limiter."""
        self._rate_limiter._requests_per_second = value

    @property
    def _last_request_time(self) -> float:
        """Proxy to ``RateLimiter._last_request_time`` (legacy field)."""
        return self._rate_limiter._last_request_time

    @_last_request_time.setter
    def _last_request_time(self, value: float) -> None:
        self._rate_limiter._last_request_time = value

    @property
    def _request_count(self) -> int:
        """Proxy to ``RateLimiter._request_count`` (legacy field)."""
        return self._rate_limiter._request_count

    @_request_count.setter
    def _request_count(self, value: int) -> None:
        self._rate_limiter._request_count = value

    @property
    def _max_retries(self) -> int:
        """Proxy to the VEP annotator's retry cap.

        Setting this attribute (which some fast-path tests do to speed
        up retry-exhaustion flows) syncs the value to both the annotator
        and the recoder so the change takes effect on either path.
        """
        return self._annotator._max_retries

    @_max_retries.setter
    def _max_retries(self, value: int) -> None:
        self._annotator._max_retries = value
        self._recoder._max_retries = value

    @property
    def _backoff_factor(self) -> float:
        """Proxy to the VEP annotator's exponential backoff factor."""
        return self._annotator._backoff_factor

    @_backoff_factor.setter
    def _backoff_factor(self, value: float) -> None:
        self._annotator._backoff_factor = value
        self._recoder._backoff_factor = value

    @property
    def _cache_ttl(self) -> int:
        """Proxy to the VEP annotator's cache TTL (seconds)."""
        return self._annotator._cache_ttl

    @_cache_ttl.setter
    def _cache_ttl(self, value: int) -> None:
        self._annotator._cache_ttl = value
        self._recoder._cache_ttl = value

    # ======================================================================
    # Public API (unchanged from pre-Wave-4)
    # ======================================================================

    async def validate_variant_with_vep(
        self, hgvs_notation: str
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Validate variant using Ensembl VEP API (delegates to annotator)."""
        return await self._annotator.validate_with_vep(hgvs_notation)

    def validate_variant_formats(self, variant_descriptor: Dict[str, Any]) -> List[str]:
        """Validate variant formats in a variation descriptor.

        Returns a list of human-readable error strings (empty if valid).
        """
        errors: List[str] = []

        if not variant_descriptor.get("id"):
            errors.append("Variant descriptor missing 'id' field")

        expressions = variant_descriptor.get("expressions", [])
        for expr in expressions:
            syntax = expr.get("syntax", "")
            value = expr.get("value", "")

            if syntax == "hgvs.c":
                if not format_validators.validate_hgvs_c(value):
                    errors.append(self._format_error("HGVS c. notation", value))
            elif syntax == "hgvs.p":
                if not format_validators.validate_hgvs_p(value):
                    errors.append(self._format_error("HGVS p. notation", value))
            elif syntax == "hgvs.g":
                if not format_validators.validate_hgvs_g(value):
                    errors.append(self._format_error("HGVS g. notation", value))
            elif syntax == "vcf":
                if not format_validators.validate_vcf(value):
                    errors.append(f"Invalid VCF format: {value}")
            elif syntax == "spdi":
                if not format_validators.validate_spdi(value):
                    errors.append(f"Invalid SPDI format: {value}")

        if "vrsAllele" in variant_descriptor:
            errors.extend(
                format_validators.validate_vrs_allele(variant_descriptor["vrsAllele"])
            )

        if "structuralType" in variant_descriptor:
            has_valid_cnv = any(
                expr.get("syntax") == "iscn"
                or format_validators.is_ga4gh_cnv_notation(expr.get("value", ""))
                for expr in expressions
            )
            if not has_valid_cnv:
                errors.append("Structural variant missing valid CNV notation")

        return errors

    def validate_variants_in_phenopacket(
        self, phenopacket: Dict[str, Any]
    ) -> List[str]:
        """Validate every variant descriptor inside a phenopacket."""
        all_errors: List[str] = []
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

    async def annotate_variant_with_vep(
        self,
        variant: str,
        include_annotations: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Annotate variant with VEP (delegates to :class:`VEPAnnotator`)."""
        return await self._annotator.annotate(variant, include_annotations)

    async def recode_variant_with_vep(self, variant: str) -> Optional[Dict[str, Any]]:
        """Recode variant via VEP Variant Recoder (delegates to VEPRecoder)."""
        return await self._recoder.recode(variant)

    async def recode_variants_batch(
        self,
        variants: List[str],
        include_vcf: bool = True,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Batch recode via VEP Variant Recoder POST endpoint."""
        return await self._recoder.recode_batch(variants, include_vcf=include_vcf)

    # ======================================================================
    # Private helpers preserved for test compatibility
    #
    # The 1,671-line test suite still reaches into these in places —
    # keeping them around as thin forwarders means we do not have to
    # modify any test code during the split.
    # ======================================================================

    def _get_notation_suggestions(self, invalid_notation: str) -> List[str]:
        """Proxy to the module-level :func:`get_notation_suggestions`."""
        return get_notation_suggestions(invalid_notation)

    def _fallback_validation(self, notation: str) -> bool:
        """Proxy to the module-level :func:`fallback_validation`."""
        return format_validators.fallback_validation(notation)

    def _validate_hgvs_c(self, value: str) -> bool:
        """Proxy to the module-level :func:`validate_hgvs_c`."""
        return format_validators.validate_hgvs_c(value)

    def _validate_hgvs_p(self, value: str) -> bool:
        """Proxy to the module-level :func:`validate_hgvs_p`."""
        return format_validators.validate_hgvs_p(value)

    def _validate_hgvs_g(self, value: str) -> bool:
        """Proxy to the module-level :func:`validate_hgvs_g`."""
        return format_validators.validate_hgvs_g(value)

    def _validate_vcf(self, value: str) -> bool:
        """Proxy to the module-level :func:`validate_vcf`."""
        return format_validators.validate_vcf(value)

    def _validate_spdi(self, value: str) -> bool:
        """Proxy to the module-level :func:`validate_spdi`."""
        return format_validators.validate_spdi(value)

    def _is_ga4gh_cnv_notation(self, value: str) -> bool:
        """Proxy to the module-level :func:`is_ga4gh_cnv_notation`."""
        return format_validators.is_ga4gh_cnv_notation(value)

    def _validate_vrs_allele(self, vrs_allele: Dict[str, Any]) -> List[str]:
        """Proxy to the module-level :func:`validate_vrs_allele`."""
        return format_validators.validate_vrs_allele(vrs_allele)

    @staticmethod
    def _is_vcf_format(variant: str) -> bool:
        """Proxy to the module-level :func:`is_vcf_format`."""
        return format_validators.is_vcf_format(variant)

    @staticmethod
    def _vcf_to_vep_format(vcf_variant: str) -> Optional[str]:
        """Proxy to the module-level :func:`vcf_to_vep_format`."""
        return format_validators.vcf_to_vep_format(vcf_variant)

    async def _rate_limit(self) -> None:
        """Proxy to the shared :class:`RateLimiter`."""
        await self._rate_limiter.acquire()

    def _check_rate_limit_headers(self, headers: Mapping[str, str]) -> None:
        """Proxy to the module-level :func:`check_rate_limit_headers`."""
        check_rate_limit_headers(headers)

    @staticmethod
    def _format_error(kind: str, value: str) -> str:
        """Build the ``Invalid X: Y | Suggestions: ...`` error string."""
        suggestions = get_notation_suggestions(value)
        message = f"Invalid {kind}: {value}"
        if suggestions:
            message += f" | Suggestions: {'; '.join(suggestions)}"
        return message
