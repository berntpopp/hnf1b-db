"""Explicitly configured Google Sheets source adapter with fail-closed fetches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

import httpx

from migration.data_sources.source_adapter import SourceSnapshot
from migration.source_manifest import REQUIRED_SHEETS, build_source_manifest


class SourceFetchError(RuntimeError):
    """A configured remote source could not provide a safe CSV snapshot."""


Fetch = Callable[[str], Awaitable[tuple[int, str, bytes]]]


class GoogleSheetsSourceAdapter:
    """Fetch only configured CSV exports and validate all inputs as one unit."""

    def __init__(
        self,
        *,
        spreadsheet_id: str,
        gids: Mapping[str, str],
        dataset_key: str = "hnf1b-registry",
        timeout_seconds: float = 20.0,
        fetch: Fetch | None = None,
    ) -> None:
        """Bind an explicitly configured spreadsheet and optionally injected fetcher."""
        self.spreadsheet_id = spreadsheet_id
        self.gids = dict(gids)
        self.dataset_key = dataset_key
        self.timeout_seconds = timeout_seconds
        self._fetch = fetch or self._http_fetch

    def _url(self, gid: str) -> str:
        return (
            "https://docs.google.com/spreadsheets/d/"
            f"{self.spreadsheet_id}/export?format=csv&gid={gid}"
        )

    async def _http_fetch(self, url: str) -> tuple[int, str, bytes]:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.get(url)
        return (
            response.status_code,
            response.headers.get("content-type", ""),
            response.content,
        )

    async def load(self) -> SourceSnapshot:
        """Fetch a complete CSV snapshot; any invalid sheet aborts the whole load."""
        if not self.spreadsheet_id.strip():
            raise SourceFetchError("configured spreadsheet ID is required")
        missing_gids = sorted(
            name for name in REQUIRED_SHEETS if not self.gids.get(name)
        )
        if missing_gids:
            raise SourceFetchError(
                f"missing configured GIDs: {', '.join(missing_gids)}"
            )
        raw_sheets: dict[str, bytes] = {}
        for name in sorted(REQUIRED_SHEETS):
            try:
                status, content_type, raw = await self._fetch(
                    self._url(self.gids[name])
                )
            except (httpx.HTTPError, TimeoutError) as exc:
                raise SourceFetchError(
                    f"failed to fetch configured sheet {name}"
                ) from exc
            if status != 200:
                raise SourceFetchError(
                    f"configured sheet {name} returned HTTP {status}"
                )
            if not content_type.casefold().startswith(("text/csv", "application/csv")):
                raise SourceFetchError(
                    f"configured sheet {name} returned unsafe content type"
                )
            if raw.lstrip().casefold().startswith(b"<html"):
                raise SourceFetchError(f"configured sheet {name} returned HTML")
            raw_sheets[name] = raw
        try:
            manifest = build_source_manifest(
                source_system="google_sheets",
                dataset_key=self.dataset_key,
                sheets=raw_sheets,
            )
        except ValueError as exc:
            raise SourceFetchError(
                "configured source failed manifest validation"
            ) from exc
        return SourceSnapshot(manifest=manifest, raw_sheets=raw_sheets)
