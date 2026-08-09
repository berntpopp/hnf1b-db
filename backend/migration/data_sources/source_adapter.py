"""Closed source-adapter interface for deterministic import inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from migration.source_manifest import SourceManifest


@dataclass(frozen=True)
class SourceSnapshot:
    """Complete validated source bytes plus the content-addressed manifest."""

    manifest: SourceManifest
    raw_sheets: Mapping[str, bytes]


class SourceAdapter(Protocol):
    """Load exactly one complete source snapshot or raise an actionable error."""

    async def load(self) -> SourceSnapshot:
        """Return a full source snapshot; partial results are forbidden."""
