"""Result dataclasses for reference service operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SyncResult:
    """Result of a sync operation (bulk import/update/skip/error counts)."""

    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] | None = None

    @property
    def total(self) -> int:
        """Total processed items."""
        return self.imported + self.updated + self.skipped + self.errors


@dataclass
class ReferenceDataStatus:
    """Status of reference data in the database.

    Consumed by the admin status endpoints to render the chr17q12
    gene-sync progress row and the "initialized" flag.
    """

    genome_count: int = 0
    gene_count: int = 0
    transcript_count: int = 0
    exon_count: int = 0
    domain_count: int = 0
    has_grch38: bool = False
    has_hnf1b: bool = False
    chr17q12_gene_count: int = 0
    last_updated: Optional[datetime] = None
