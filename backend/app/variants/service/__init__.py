"""Variants service sub-package.

Split from the old 824-LOC flat module during Wave 4. The public
import path is unchanged, so every caller keeps working::

    from app.variants.service import (
        get_variant_annotation,
        get_variant_annotations_batch,
        VEPError,
        VEPRateLimitError,
        VEPNotFoundError,
        VEPTimeoutError,
        VEPAPIError,
    )

The regression test suites also import private helpers directly from
``app.variants.service`` — ``_format_variant_for_vep``, ``is_cnv_variant``,
``validate_variant_id``, ``_parse_vep_response``. All of these are
re-exported at the package level below.

Submodules:

- ``errors``      — exception hierarchy (``VEPError`` + subclasses)
- ``validators``  — ``is_cnv_variant``, ``validate_variant_id``,
  ``_format_variant_for_vep`` (pure regex, no I/O)
- ``cache_ops``   — ``variant_annotations`` table read/write helpers
- ``vep_api``     — Ensembl VEP REST client + response parser
- ``api``         — public ``get_variant_annotation`` /
  ``get_variant_annotations_batch`` orchestration
"""

from .api import get_variant_annotation, get_variant_annotations_batch
from .cache_ops import (
    _get_cached_annotation,
    _get_cached_annotations_batch,
    _row_to_dict,
    _store_annotations_batch,
)
from .errors import (
    VEPAPIError,
    VEPError,
    VEPNotFoundError,
    VEPRateLimitError,
    VEPTimeoutError,
)
from .validators import _format_variant_for_vep, is_cnv_variant, validate_variant_id
from .vep_api import (
    _extract_gnomad_frequencies,
    _extract_primary_transcript,
    _fetch_from_vep,
    _parse_vep_response,
)

__all__ = [
    # Public API
    "get_variant_annotation",
    "get_variant_annotations_batch",
    # Exception hierarchy
    "VEPError",
    "VEPRateLimitError",
    "VEPNotFoundError",
    "VEPTimeoutError",
    "VEPAPIError",
    # Validators (test-accessed)
    "is_cnv_variant",
    "validate_variant_id",
    "_format_variant_for_vep",
    # VEP response parser (test-accessed)
    "_parse_vep_response",
    "_extract_primary_transcript",
    "_extract_gnomad_frequencies",
    "_fetch_from_vep",
    # Cache helpers
    "_get_cached_annotation",
    "_get_cached_annotations_batch",
    "_row_to_dict",
    "_store_annotations_batch",
]
