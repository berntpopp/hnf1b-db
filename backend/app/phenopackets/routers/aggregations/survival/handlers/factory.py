"""Factory for creating survival handlers by comparison type."""

from typing import Dict, List

from .base import SurvivalHandler
from .disease_subtype import DiseaseSubtypeHandler
from .pathogenicity import PathogenicityHandler
from .protein_domain import ProteinDomainHandler
from .variant_type import VariantTypeHandler


class SurvivalHandlerFactory:
    """Factory for creating survival handlers by comparison type."""

    _handlers: Dict[str, type] = {
        "variant_type": VariantTypeHandler,
        "pathogenicity": PathogenicityHandler,
        "disease_subtype": DiseaseSubtypeHandler,
        "protein_domain": ProteinDomainHandler,
    }

    @classmethod
    def get_handler(cls, comparison_type: str) -> SurvivalHandler:
        """Get the appropriate handler for a comparison type.

        Args:
            comparison_type: One of 'variant_type', 'pathogenicity',
                           'disease_subtype', 'protein_domain'

        Returns:
            Instantiated handler for the comparison type

        Raises:
            ValueError: If comparison_type is not recognized
        """
        handler_class = cls._handlers.get(comparison_type)
        if handler_class is None:
            valid = ", ".join(cls._handlers.keys())
            raise ValueError(
                f"Unknown comparison type: {comparison_type}. Valid: {valid}"
            )
        return handler_class()

    @classmethod
    def get_valid_comparison_types(cls) -> List[str]:
        """Get list of valid comparison types."""
        return list(cls._handlers.keys())
