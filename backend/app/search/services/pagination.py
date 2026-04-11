"""Pagination helper for the search services.

Extracted from the monolithic ``search/services.py`` during Wave 4.
Small enough that no other file needs to own it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaginationParams:
    """Offset-pagination parameters for global search."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Calculate offset for SQL OFFSET clause."""
        return (self.page - 1) * self.page_size
