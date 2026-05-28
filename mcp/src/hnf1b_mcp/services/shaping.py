"""Token-cost controls: response modes, char budgets, meta block."""

from __future__ import annotations

import json
from typing import Any

from .errors import McpToolError

MODES = ("minimal", "compact", "standard", "full")
DEFAULT_MODE = "compact"


def resolve_mode(requested: str | None) -> str:
    """Validate/normalize a requested response_mode.

    Args:
        requested: The response_mode string to validate, or None for default.

    Returns:
        A validated response_mode string.

    Raises:
        McpToolError: If *requested* is not one of the known MODES.
    """
    if requested is None:
        return DEFAULT_MODE
    if requested not in MODES:
        raise McpToolError(
            "invalid_input",
            f"response_mode must be one of {MODES}",
            argument="response_mode",
        )
    return requested


def _size(obj: Any) -> int:
    return len(json.dumps(obj, default=str))


def apply_budget(
    payload: dict[str, Any],
    max_chars: int,
    list_keys: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Trim the largest list fields until payload fits max_chars.

    Args:
        payload: The data dict to potentially trim.
        max_chars: Maximum allowed serialized character count.
        list_keys: Keys in *payload* whose list values may be trimmed.

    Returns:
        A tuple of (shaped_payload, dropped_summary) where dropped_summary
        is None if no trimming was needed.
    """
    if _size(payload) <= max_chars:
        return payload, None
    dropped = 0
    shaped: dict[str, Any] = dict(payload)
    for key in list_keys:
        items = list(shaped.get(key, []))
        while items and _size(shaped) > max_chars:
            items.pop()
            dropped += 1
            shaped[key] = items
    summary: dict[str, Any] | None = (
        {"dropped_records": dropped, "reason": "max_response_chars"}
        if dropped
        else None
    )
    return shaped, summary


def build_meta(
    response_mode: str,
    effective_chars: int,
    dropped: dict[str, Any] | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the meta block echoed in every payload.

    Args:
        response_mode: The resolved response_mode string.
        effective_chars: Number of characters in the shaped payload (the data
            portion plus ``data_class``; the self-referential ``meta`` block is
            excluded).
        dropped: Optional dropped_summary dict from apply_budget. When present a
            ``truncated`` flag is added so a caller never mistakes a budget-
            trimmed payload for a complete one.
        extra: Optional service-supplied meta fields to merge verbatim. Used to
            make otherwise-silent server behavior visible — e.g.
            ``applied_sort`` / ``ignored_params`` for parameters the upstream
            API does not honor, or ``total_available_chars`` for truncation.

    Returns:
        A meta dict with response_mode, effective_chars, optional
        dropped_summary/truncated, and any merged *extra* fields.
    """
    meta: dict[str, Any] = {
        "response_mode": response_mode,
        "effective_chars": effective_chars,
    }
    if extra:
        for key, value in extra.items():
            if value is not None:
                meta[key] = value
    if dropped:
        meta["dropped_summary"] = dropped
        meta["truncated"] = True
    return meta
