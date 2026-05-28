"""Read-only httpx client restricted to the endpoint allowlist, with a TTL cache."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..services.errors import McpToolError
from .allowlist import assert_allowed


class ApiClient:
    """Async client for the public /api/v2 surface (allowlisted GETs only)."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        cache_ttl: int = 300,
    ) -> None:
        """Initialize the client with a base URL, request timeout, and cache TTL.

        Args:
            base_url: Base URL for the API (e.g. ``http://host/api/v2``).
            timeout: HTTP request timeout in seconds.
            cache_ttl: Time-to-live for cached responses in seconds.
        """
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET an allowlisted path and return the parsed JSON body.

        Args:
            path: The API path relative to ``base_url`` (must be allowlisted).
            params: Optional query parameters forwarded to the request.

        Returns:
            The deserialized JSON response body.

        Raises:
            PermissionError: If *path* is not on the allowlist.
            McpToolError: On 404 (``not_found``), 422 (``invalid_input``),
                5xx (``temporarily_unavailable``), or network errors.
        """
        assert_allowed(path)
        key = path + "?" + json.dumps(params or {}, sort_keys=True)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
        try:
            resp = await self._client.get(path, params=params)
        except httpx.TimeoutException as e:
            raise McpToolError(
                "temporarily_unavailable", "upstream API timed out"
            ) from e
        except httpx.HTTPError as e:
            raise McpToolError("temporarily_unavailable", "upstream API error") from e
        if resp.status_code == 404:
            raise McpToolError("not_found", f"resource not found: {path}")
        if resp.status_code == 422:
            raise McpToolError("invalid_input", "upstream rejected parameters")
        if resp.status_code >= 500:
            raise McpToolError("temporarily_unavailable", "upstream API unavailable")
        resp.raise_for_status()
        data = resp.json()
        self._cache[key] = (now + self._cache_ttl, data)
        return data

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
