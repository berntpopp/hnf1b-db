"""Immutable local fixture adapter used by tests and dry runs."""

from __future__ import annotations

from pathlib import Path

from migration.data_sources.source_adapter import SourceSnapshot
from migration.source_manifest import REQUIRED_SHEETS, build_source_manifest


class LocalFixtureSourceAdapter:
    """Read named CSV fixtures from disk without any network capability."""

    def __init__(self, root: Path, *, dataset_key: str = "hnf1b-registry") -> None:
        """Bind the adapter to an immutable directory of named CSV fixtures."""
        self.root = root
        self.dataset_key = dataset_key

    async def load(self) -> SourceSnapshot:
        """Read all required fixture bytes and validate their manifest."""
        raw_sheets = {
            name: (self.root / f"{name}.csv").read_bytes() for name in REQUIRED_SHEETS
        }
        return SourceSnapshot(
            manifest=build_source_manifest(
                source_system="local_fixture",
                dataset_key=self.dataset_key,
                sheets=raw_sheets,
            ),
            raw_sheets=raw_sheets,
        )
