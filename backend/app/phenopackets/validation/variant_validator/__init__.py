"""Variant format validation sub-package.

Split from the old 1,008-LOC flat module during Wave 4. The public
import path is unchanged::

    from app.phenopackets.validation.variant_validator import VariantValidator

Submodules:

- ``format_validators``  — pure regex format checks (HGVS/VCF/SPDI/CNV/VRS)
- ``suggestions``        — fuzzy-match helper for error messages
- ``rate_limiter``       — Ensembl 15-req/sec async rate limiter
- ``vep_annotate``       — Ensembl VEP annotation / HGVS validation client
- ``vep_recoder``        — Ensembl VEP Variant Recoder client (single + batch)
- ``validator``          — the ``VariantValidator`` facade class

Backwards-compat note on ``cache`` and ``settings``
---------------------------------------------------

The pre-Wave-4 flat module imported ``cache`` and ``settings`` at module
top, which let the test suite patch them via
``patch("app.phenopackets.validation.variant_validator.cache")``. We
preserve that patch target here by re-exporting both names at the
package level *before* loading any submodule, and by making the
submodules (``vep_annotate``, ``vep_recoder``) read the names through
this package at call time rather than binding them at import time.
That way the 1,671-line regression test suite keeps working unchanged.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.cache import CacheService
    from app.core.config import Settings

    cache: CacheService
    settings: Settings

# The validator facade pulls in the submodules. ``cache`` and
# ``settings`` are resolved dynamically via ``__getattr__`` so they stay
# aligned with the current ``app.core`` module state even if tests
# reload ``app.core.config``.
from .validator import VariantValidator

__all__ = ["VariantValidator", "cache", "settings"]


def __getattr__(name: str) -> Any:
    """Resolve compat re-exports lazily.

    Returning the live objects instead of binding them once at import
    time keeps ``variant_validator.settings`` aligned with
    ``app.core.config.settings`` after module reloads in the test suite,
    while still preserving legacy patch targets at the package root.
    """
    if name == "cache":
        from app.core.cache import cache

        return cache
    if name == "settings":
        from app.core.config import settings

        return settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
