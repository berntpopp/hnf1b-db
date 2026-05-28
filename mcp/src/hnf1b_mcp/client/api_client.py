"""Read-only httpx client restricted to the endpoint allowlist, with a TTL cache."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..contract import (
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
)
from ..services.errors import McpToolError
from .allowlist import assert_allowed

#: Map of upstream query-parameter names → the contract enum that constrains
#: them. Used to surface ``allowed`` values in 422 error envelopes so a calling
#: LLM can self-correct in a single retry.
_FIELD_ALLOWED: dict[str, list[str]] = {
    "classification": sorted(VARIANT_CLASSIFICATION_VALUES),
    "consequence": sorted(MOLECULAR_CONSEQUENCE_VALUES),
    "variant_type": sorted(VARIANT_TYPE_VALUES),
    "domain": sorted(PROTEIN_DOMAIN_VALUES),
}


def _build_422_error(resp: httpx.Response) -> McpToolError:
    """Translate an upstream 422 into an actionable ``invalid_input`` error.

    Parses the FastAPI validation body
    (``{"detail":[{"loc":[...],"msg":"...","input":...}]}``) to name the
    offending field and value, attaching ``field``, ``allowed`` (when the field
    maps to a known contract enum), ``hint``, and the raw ``upstream_detail`` so
    a consuming model can correct its call without fetching raw schemas.

    Args:
        resp: The 422 :class:`httpx.Response` returned by the upstream API.

    Returns:
        A populated :class:`McpToolError` with code ``invalid_input``.
    """
    try:
        body: Any = resp.json()
    except (json.JSONDecodeError, ValueError):
        body = None

    detail = body.get("detail") if isinstance(body, dict) else None

    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        first = detail[0]
        loc = first.get("loc") or []
        field = str(loc[-1]) if loc else "unknown"
        upstream_msg = str(first.get("msg") or "value not permitted by the data API")
        bad_value = first.get("input")
        allowed = _FIELD_ALLOWED.get(field)

        if bad_value is not None:
            message = f"invalid value {bad_value!r} for '{field}': {upstream_msg}"
        else:
            message = f"invalid value for '{field}': {upstream_msg}"

        if allowed is not None:
            hint = f"use one of the allowed values for '{field}'"
        else:
            hint = (
                "check the parameter against hnf1b_get_capabilities filterable_fields"
            )

        return McpToolError(
            "invalid_input",
            message,
            field=field,
            allowed=allowed,
            hint=hint,
            upstream_detail=detail,
        )

    # Unparseable / non-standard body: still surface *something* actionable.
    return McpToolError(
        "invalid_input",
        "the data API rejected the request parameters",
        field="unknown",
        hint="check parameters against hnf1b_get_capabilities filterable_fields",
        upstream_detail=detail if detail is not None else body,
    )


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
            # Domain-framed message only — never echo the internal API route
            # (path leakage). Callers that can name the resource (e.g.
            # get_variant) raise their own more specific not_found upstream.
            raise McpToolError(
                "not_found",
                "the requested record was not found",
                hint=(
                    "verify the identifier via hnf1b_search or"
                    " hnf1b_resolve_terms before fetching"
                ),
            )
        if resp.status_code == 422:
            raise _build_422_error(resp)
        if resp.status_code >= 500:
            raise McpToolError("temporarily_unavailable", "upstream API unavailable")
        resp.raise_for_status()
        data = resp.json()
        self._cache[key] = (now + self._cache_ttl, data)
        return data

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
