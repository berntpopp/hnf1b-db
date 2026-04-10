"""Survival analysis sub-package.

Public API re-exports mirror the old flat-file module paths so that
any existing ``from app.phenopackets.routers.aggregations.survival
import ...`` callers keep working without edits.
"""

from .handlers import (
    DiseaseSubtypeHandler,
    PathogenicityHandler,
    ProteinDomainHandler,
    SurvivalHandler,
    SurvivalHandlerFactory,
    VariantTypeHandler,
)
from .router import router

__all__ = [
    "router",
    "SurvivalHandler",
    "SurvivalHandlerFactory",
    "VariantTypeHandler",
    "PathogenicityHandler",
    "DiseaseSubtypeHandler",
    "ProteinDomainHandler",
]
