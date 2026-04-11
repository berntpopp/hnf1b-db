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

# Re-export cache + settings at the package level first, so that
# submodules imported below (and test-suite patches targeting
# ``app.phenopackets.validation.variant_validator.cache``) can both see
# the same attribute.
from app.core.cache import cache  # noqa: F401 (re-export)
from app.core.config import settings  # noqa: F401 (re-export)

# The validator facade pulls in the submodules — order matters: cache
# and settings must be in the package namespace first.
from .validator import VariantValidator

__all__ = ["VariantValidator", "cache", "settings"]
