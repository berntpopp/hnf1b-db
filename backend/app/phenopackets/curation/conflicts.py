"""Explicit, stable conflict values emitted by deterministic projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.phenopackets.curation.hashing import sha256_digest


@dataclass(frozen=True)
class ProjectionConflict:
    """A blocking disagreement with its exact stable candidate set."""

    conflict_key: str
    observation_ids: tuple[str, ...]
    candidates: tuple[tuple[str, Any], ...]

    @property
    def candidate_set_digest(self) -> str:
        """Hash exactly the candidate values a curator must resolve."""
        return sha256_digest(
            {"conflictKey": self.conflict_key, "candidates": self.candidates}
        )
