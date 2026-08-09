"""Canonical hashing helpers for deterministic source-ledger projection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.phenopackets.curation.models import ReportObservation

_VOLATILE_SOURCE_KEYS = {
    "rowNumber",
    "importRunId",
    "importedAt",
    "manifestSha256",
    "rowHmacSha256",
}


def canonical_json(value: Any) -> str:
    """Encode semantic content deterministically for digesting and comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: Any) -> str:
    """Return the namespaced SHA-256 digest of canonical JSON content."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def semantic_observation(observation: ReportObservation) -> dict[str, Any]:
    """Return an observation with volatile import-audit fields removed."""
    value = observation.model_dump(by_alias=True, mode="json")
    for key in _VOLATILE_SOURCE_KEYS:
        value["source"].pop(key, None)
    return value


def observation_digest(observations: list[ReportObservation]) -> str:
    """Hash observations after sorting by stable observation identity."""
    return sha256_digest(
        [
            semantic_observation(observation)
            for observation in sorted(
                observations, key=lambda item: item.observation_id
            )
        ]
    )
