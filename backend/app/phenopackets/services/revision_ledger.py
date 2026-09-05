"""Canonical payload and digest helpers for version-two revision ledgers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.phenopackets.curation.hashing import sha256_digest


def content_sha256(content: Mapping[str, Any]) -> str:
    """Return the canonical digest of the complete revision content mapping."""
    return sha256_digest(content)


def build_ledger_v2_payload(
    *,
    parent_revision_id: int | None,
    revision_number: int,
    state: str,
    event_type: str,
    from_state: str | None,
    to_state: str,
    change_reason: str | None,
    change_patch: Any | None,
    content_sha256: str,
    projection_hash: str | None,
    actor_id: int,
    actor_role: str | None,
    decision_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the complete canonical evidence payload for a v2 revision ledger."""
    return {
        "ledger_version": 2,
        "parent_revision_id": parent_revision_id,
        "revision_number": revision_number,
        "state": state,
        "event_type": event_type,
        "from_state": from_state,
        "to_state": to_state,
        "change_reason": change_reason,
        "change_patch": change_patch,
        "content_sha256": content_sha256,
        "projection_hash": projection_hash,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "decision_metadata": (
            dict(decision_metadata) if decision_metadata is not None else None
        ),
    }


def ledger_sha256(payload: Mapping[str, Any]) -> str:
    """Return the canonical digest of a complete version-two ledger payload."""
    return sha256_digest(payload)
