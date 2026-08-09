"""Remote source adapter tests use injected bytes only; never a live sheet."""

import pytest

from migration.data_sources.google_sheets_adapter import (
    GoogleSheetsSourceAdapter,
    SourceFetchError,
)


@pytest.mark.asyncio
async def test_adapter_rejects_non_csv_content_before_manifest_parsing():
    """An HTML login/error document cannot become a source snapshot."""

    async def fetch(_url: str):
        return 200, "text/html", b"<html>login</html>"

    adapter = GoogleSheetsSourceAdapter(
        spreadsheet_id="configured-sheet",
        gids={
            "Individuals": "1",
            "Phenotypes": "2",
            "Phenotype_modifier": "3",
            "Publications": "4",
        },
        fetch=fetch,
    )

    with pytest.raises(SourceFetchError, match="content type"):
        await adapter.load()


@pytest.mark.asyncio
async def test_adapter_refuses_missing_configured_gid_without_network_access():
    """Every required sheet must be explicitly bound to a configured GID."""

    async def fetch(_url: str):  # pragma: no cover - must never be reached
        raise AssertionError("fetch must not run")

    adapter = GoogleSheetsSourceAdapter(
        spreadsheet_id="configured-sheet",
        gids={"Individuals": "1"},
        fetch=fetch,
    )

    with pytest.raises(SourceFetchError, match="missing configured GIDs"):
        await adapter.load()
