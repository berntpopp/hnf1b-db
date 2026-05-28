"""Uniform tool execution wrapper: timing, meta, data_class, error envelopes."""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from .errors import McpToolError
from .shaping import build_meta


async def run_tool(
    handler: Callable[[], Awaitable[dict[str, Any]]],
    *,
    data_class: str,
    response_mode: str,
) -> dict[str, Any]:
    """Execute a service handler, attaching meta/data_class or an error envelope."""
    start = time.monotonic()
    try:
        result = await handler()
    except McpToolError as e:
        env = e.to_envelope()
        env["is_error"] = True
        return env
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    dropped = result.pop("_dropped", None)
    effective_chars = len(json.dumps(result, default=str))
    meta = build_meta(
        response_mode=response_mode,
        effective_chars=effective_chars,
        dropped=dropped,
    )
    meta["elapsed_ms"] = elapsed_ms
    result["data_class"] = data_class
    result["meta"] = meta
    return result
