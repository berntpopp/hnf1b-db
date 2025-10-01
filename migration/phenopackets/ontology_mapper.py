"""Abstract interface for ontology mapping following Dependency Inversion Principle."""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class OntologyMapper(ABC):
    """Abstract interface for ontology term mapping.

    This abstraction allows high-level modules to depend on an interface
    rather than concrete implementations, following the Dependency Inversion Principle.

    Benefits:
    - Testable: Can inject mock mappers for testing
    - Extensible: Can add API-based mappers (e.g., OLS, BioPortal) later
    - Flexible: Easy to switch between different mapping strategies
    """

    @abstractmethod
    def get_hpo_term(self, phenotype_key: str) -> Optional[Dict[str, str]]:
        """Get HPO term for a phenotype key.

        Args:
            phenotype_key: Normalized phenotype key

        Returns:
            Dictionary with 'id' and 'label' keys, or None if not found
        """
        pass

    @abstractmethod
    def get_all_mappings(self) -> Dict[str, Dict[str, str]]:
        """Get all available HPO mappings.

        Returns:
            Dictionary mapping phenotype keys to HPO terms
        """
        pass

    @abstractmethod
    def normalize_key(self, key: str) -> str:
        """Normalize a phenotype key for lookup.

        Args:
            key: Raw phenotype key

        Returns:
            Normalized key
        """
        pass