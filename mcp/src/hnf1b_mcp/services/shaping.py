"""Token-cost controls: response modes, char budgets, meta block."""

from __future__ import annotations

import json
from typing import Any, Literal, TypeVar

from .errors import McpToolError

_T = TypeVar("_T")

MODES = ("minimal", "compact", "standard", "full")
DEFAULT_MODE = "compact"

#: Schema-visible enum for the ``response_mode`` parameter shared by every tool.
#: Typing a tool param with this Literal makes the four valid values appear in
#: the tool's JSON input schema (so a client/agent can autocomplete and a typo is
#: rejected at validation time), instead of an opaque ``string``. Kept in lockstep
#: with :data:`MODES` by a drift-guard test (``set(get_args(ResponseMode)) ==
#: set(MODES)``); ``resolve_mode`` remains the runtime guard (Literal is a ``str``
#: subtype, so the two compose).
ResponseMode = Literal["minimal", "compact", "standard", "full"]

# Default cap for an inline id list (carrier ids, citing-individual ids, …) shown
# without an explicit opt-in. A heavily-populated list (e.g. the recurrent 17q12
# deletion carries ~379 individuals ≈ 7.5 KB of bare ids, or a foundational
# publication cited by ~75 individuals) would otherwise dump the ENTIRE list in
# every response mode with no opt-out, blowing the token budget the rest of the
# server respects. Callers recover the full set via the tool's include_* flag.
DEFAULT_SAMPLE_SIZE = 10


def sample_with_signal(
    items: list[_T],
    total: int,
    *,
    key_prefix: str,
    note: str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> tuple[list[_T], dict[str, Any]]:
    """Down-sample an inline list to a bounded sample with a meta signal.

    The reusable sample/signal pattern shared by every tool that ships an inline
    id list (carrier ids, citing-individual ids, …): when *items* exceeds
    *sample_size*, return only the first *sample_size* entries plus a
    machine-readable meta block (``{key_prefix}_total`` / ``{key_prefix}_returned``
    / ``{key_prefix}_truncated`` / ``{key_prefix}_note``) that tells the agent the
    omission happened and exactly how to recover the full set. When the list
    already fits (``len(items) <= sample_size``) it is returned whole with an
    EMPTY signal, so the caller never emits a spurious truncation flag.

    Args:
        items: The full list of items (or whatever subset was fetched).
        total: The authoritative total count; used for the ``{key_prefix}_total``
            signal and the *note*, which may exceed ``len(items)`` if the upstream
            fetch itself was bounded.
        key_prefix: The meta-key prefix (e.g. ``"carriers"`` →
            ``carriers_total``/``carriers_returned``/``carriers_truncated``/
            ``carriers_note``).
        note: The recovery-pointer prose. Supports ``{sample}``/``{total}``
            ``str.format`` placeholders, filled with the sampled length and
            *total*.
        sample_size: Maximum number of entries to keep
            (default :data:`DEFAULT_SAMPLE_SIZE`).

    Returns:
        ``(sampled, signal)`` — *sampled* is the (possibly shortened) list and
        *signal* is the meta dict to merge (empty when no truncation occurred).
    """
    if len(items) <= sample_size:
        return items, {}
    sampled = items[:sample_size]
    return sampled, {
        f"{key_prefix}_total": total,
        f"{key_prefix}_returned": len(sampled),
        f"{key_prefix}_truncated": True,
        f"{key_prefix}_note": note.format(sample=len(sampled), total=total),
    }


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
    *,
    keep_min: int = 0,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Trim the largest list fields until payload fits max_chars.

    Args:
        payload: The data dict to potentially trim.
        max_chars: Maximum allowed serialized character count.
        list_keys: Keys in *payload* whose list values may be trimmed.
        keep_min: Minimum number of items to retain in EACH trimmed list, even
            when a single item already exceeds ``max_chars``. Guards the
            "never empty when a real match exists" contract — e.g. a retrieval
            endpoint must still return its top-ranked hit (with a truncation
            signal) rather than an empty list. Defaults to 0 (unbounded trim).

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
        while len(items) > keep_min and _size(shaped) > max_chars:
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
