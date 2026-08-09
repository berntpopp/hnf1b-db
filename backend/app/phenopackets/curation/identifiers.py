"""Stable, source-derived identifiers and privacy-preserving row fingerprints."""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID, uuid5

CURATION_NAMESPACE = UUID("7159684a-d9e6-5033-9b6d-dc37015dcb5e")


def _canonical_component(value: str) -> str:
    """Return the source-preserving canonical spelling used in identity tuples."""
    canonical = value.strip()
    if not canonical:
        raise ValueError("stable identity components must not be blank")
    return canonical


def _framed_name(*values: str) -> str:
    """Frame components to prevent delimiter-containing source keys colliding."""
    return "".join(
        f"{len(_canonical_component(value).encode('utf-8'))}:{_canonical_component(value)}"
        for value in values
    )


def observation_id_for(source_system: str, dataset_id: str, report_id: str) -> str:
    """Derive a UUIDv5 observation identity from durable source identifiers."""
    name = _framed_name(source_system, dataset_id, report_id)
    return str(uuid5(CURATION_NAMESPACE, name))


def assessment_id_for(
    observation_id: str, assessment_kind: str, source_field: str, stable_key: str
) -> str:
    """Derive an assessment UUIDv5 without row position or mutable content."""
    name = _framed_name(observation_id, assessment_kind, source_field, stable_key)
    return str(uuid5(CURATION_NAMESPACE, name))


def row_hmac_sha256(row_bytes: bytes, key: bytes) -> str:
    """Fingerprint source row content without exposing a low-entropy plain hash."""
    if not key:
        raise ValueError("row HMAC key must not be empty")
    digest = hmac.new(key, row_bytes, hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"
