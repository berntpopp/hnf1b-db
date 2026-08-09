"""Fail-closed reimport policy before a source row can replace imported evidence."""

from __future__ import annotations

from enum import Enum


class ReimportDisposition(str, Enum):
    """Allowed result of comparing one prior and incoming imported row."""

    NOOP = "noop"
    REPLACE_IMPORTED_OBSERVATION = "replace_imported_observation"


class ReimportConflict(RuntimeError):
    """A changed source row overlaps curator-owned work and must be reviewed."""


def classify_reimport(
    *,
    prior_row_hmac: str,
    incoming_row_hmac: str,
    has_active_draft: bool,
    has_correction: bool,
    has_resolution_dependency: bool,
) -> ReimportDisposition:
    """Apply the no-op/protected-replace policy without silently merging edits."""
    if prior_row_hmac == incoming_row_hmac:
        return ReimportDisposition.NOOP
    if has_active_draft or has_correction or has_resolution_dependency:
        raise ReimportConflict(
            "changed source row overlaps an active draft, correction, or resolution"
        )
    return ReimportDisposition.REPLACE_IMPORTED_OBSERVATION
