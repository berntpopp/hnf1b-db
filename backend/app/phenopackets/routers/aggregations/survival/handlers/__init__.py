"""Survival analysis handlers sub-package.

Re-exports the abstract base class, the four concrete handler classes,
and the factory so that callers can do either::

    from ...survival.handlers import SurvivalHandlerFactory
    from ...survival.handlers import VariantTypeHandler

The handlers are split by comparison family to keep each file under
500 LOC.
"""

from .base import SurvivalHandler
from .disease_subtype import DiseaseSubtypeHandler
from .factory import SurvivalHandlerFactory
from .pathogenicity import PathogenicityHandler
from .protein_domain import ProteinDomainHandler
from .variant_type import VariantTypeHandler

__all__ = [
    "SurvivalHandler",
    "SurvivalHandlerFactory",
    "VariantTypeHandler",
    "PathogenicityHandler",
    "DiseaseSubtypeHandler",
    "ProteinDomainHandler",
]
