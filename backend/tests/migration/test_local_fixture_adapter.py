"""Pinned local source fixtures cannot drift into a migration input."""

import pytest

from migration.data_sources.local_fixture_adapter import (
    LocalFixtureSourceAdapter,
    LocalFixtureSourceError,
)
from migration.source_manifest import EXPECTED_HEADERS


@pytest.mark.asyncio
async def test_local_fixture_requires_expected_snapshot_digest(tmp_path):
    for name, headers in EXPECTED_HEADERS.items():
        (tmp_path / f"{name}.csv").write_text(",".join(headers) + "\n")

    adapter = LocalFixtureSourceAdapter(tmp_path, expected_manifest_sha256="a" * 64)

    with pytest.raises(LocalFixtureSourceError, match="digest"):
        await adapter.load()
