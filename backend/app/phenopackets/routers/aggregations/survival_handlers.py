"""Backwards-compatibility shim for the survival handlers module.

The old flat ``survival_handlers.py`` module was restructured into a
``survival/handlers/`` sub-package in Wave 3 (commit ``e48d06a``).
This shim re-exports every public symbol at the old import path so
any external caller (notebooks, scripts, downstream consumers) that
still does::

    from app.phenopackets.routers.aggregations.survival_handlers import (
        SurvivalHandlerFactory,
        VariantTypeHandler,
        ...
    )

continues to work. A one-time ``DeprecationWarning`` is raised on
import so the stale import path is visible in CI logs and editors.

**Prefer** the new canonical path for new code::

    from app.phenopackets.routers.aggregations.survival import (
        SurvivalHandlerFactory,
        VariantTypeHandler,
    )

This shim will be removed in a future wave once all known callers
have migrated.
"""

import warnings

from .survival.handlers import (
    DiseaseSubtypeHandler,
    PathogenicityHandler,
    ProteinDomainHandler,
    SurvivalHandler,
    SurvivalHandlerFactory,
    VariantTypeHandler,
)

warnings.warn(
    "`app.phenopackets.routers.aggregations.survival_handlers` has moved to "
    "`app.phenopackets.routers.aggregations.survival.handlers` (Wave 3 "
    "restructure). Update the import — this shim will be removed in a "
    "future wave.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "SurvivalHandler",
    "SurvivalHandlerFactory",
    "VariantTypeHandler",
    "PathogenicityHandler",
    "DiseaseSubtypeHandler",
    "ProteinDomainHandler",
]
