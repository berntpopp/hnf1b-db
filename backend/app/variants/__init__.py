"""Variant annotation module.

Provides:
- Permanent database storage for VEP annotations
- Batch annotation support
- Rate limiting compliance with Ensembl API
"""

from app.variants.service import (
    VEPAPIError,
    VEPNotFoundError,
    VEPRateLimitError,
    VEPTimeoutError,
    get_variant_annotation,
    get_variant_annotations_batch,
)

__all__ = [
    "get_variant_annotation",
    "get_variant_annotations_batch",
    "VEPAPIError",
    "VEPNotFoundError",
    "VEPRateLimitError",
    "VEPTimeoutError",
]
