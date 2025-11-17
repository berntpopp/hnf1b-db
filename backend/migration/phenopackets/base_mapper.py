"""Abstract base class for Google Sheets data mappers.

This module provides a common base class for all mapper implementations
(PublicationMapper, ReviewerMapper, etc.) to promote code reuse and
maintain consistent patterns across the migration system.

Design Principles:
- DRY: Extract common mapping logic
- SOLID: Single Responsibility, Open/Closed
- Template Method Pattern: Define skeleton, let subclasses implement details
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class SheetMapper(ABC):
    """Abstract base class for Google Sheets data mappers.

    Provides common functionality for mapping Google Sheets rows to
    domain-specific data structures. Subclasses must implement the
    abstract methods to define mapper-specific behavior.

    Attributes:
        data_map: Dictionary mapping keys to row data
        map_name: Human-readable name for logging (e.g., "publication", "reviewer")
    """

    def __init__(self, dataframe: Optional[pd.DataFrame] = None):
        """Initialize mapper with optional DataFrame.

        Args:
            dataframe: DataFrame containing sheet data. If None, mapper is empty.
        """
        self.data_map: Dict[str, Any] = {}
        self.map_name = self._get_map_name()

        if dataframe is not None and not dataframe.empty:
            self._build_map(dataframe)

    @abstractmethod
    def _get_map_name(self) -> str:
        """Get human-readable name for this mapper (for logging).

        Returns:
            Mapper name (e.g., "publication", "reviewer")
        """
        pass

    @abstractmethod
    def _get_key_columns(self) -> List[str]:
        """Get list of column names to use as map keys.

        Rows will be indexed by all specified columns (e.g., both
        publication_id and publication_alias).

        Returns:
            List of column names to use as keys
        """
        pass

    def _build_map(self, dataframe: pd.DataFrame) -> None:
        """Build internal map from DataFrame.

        Iterates through DataFrame rows and indexes them by all key columns
        specified in _get_key_columns(). Non-null keys are converted to strings.

        Args:
            dataframe: DataFrame containing sheet data
        """
        key_columns = self._get_key_columns()

        for _, row in dataframe.iterrows():
            # Index row by all specified key columns
            for key_col in key_columns:
                key_value = row.get(key_col)
                if key_value and pd.notna(key_value):
                    # Convert to string for consistent lookup
                    self.data_map[str(key_value).strip()] = row

        logger.info(
            f"Created {self.map_name} map with {len(self.data_map)} entries "
            f"from {len(dataframe)} rows"
        )

    def get(self, key: str) -> Optional[pd.Series]:
        """Get row data by key.

        Args:
            key: Lookup key (will be converted to string and stripped)

        Returns:
            Row data as pandas Series, or None if not found
        """
        if not key or not self.data_map:
            return None

        return self.data_map.get(str(key).strip())

    def get_as_dict(self, key: str) -> Optional[Dict[str, Any]]:
        """Get row data as dictionary.

        Args:
            key: Lookup key

        Returns:
            Row data as dictionary, or None if not found
        """
        row = self.get(key)
        if row is None:
            return None

        # Convert Series to dict
        return row.to_dict() if hasattr(row, "to_dict") else row

    def contains(self, key: str) -> bool:
        """Check if key exists in map.

        Args:
            key: Lookup key

        Returns:
            True if key exists, False otherwise
        """
        return str(key).strip() in self.data_map

    def __len__(self) -> int:
        """Return number of entries in map.

        Returns:
            Number of entries
        """
        return len(self.data_map)

    def __bool__(self) -> bool:
        """Return True if map is not empty.

        Returns:
            True if map contains entries, False otherwise
        """
        return bool(self.data_map)
