"""Code-enforced allowlist of read-only, side-effect-free /api/v2 paths."""
from __future__ import annotations

import re

# (regex, discovery_only). discovery_only paths must be used for IDs/counts only.
_RULES: list[tuple[re.Pattern[str], bool]] = [
    (re.compile(r"^/phenopackets/batch$"), False),
    (re.compile(r"^/phenopackets/search$"), True),
    (re.compile(r"^/phenopackets/search/facets$"), True),
    (re.compile(r"^/phenopackets/aggregate/[a-z-]+$"), False),
    (re.compile(r"^/phenopackets/by-variant/[^/]+$"), False),
    (re.compile(r"^/phenopackets/by-publication/[^/]+$"), False),
    (re.compile(r"^/phenopackets/?$"), False),
    # GET /{id} — keep last among /phenopackets rules
    (re.compile(r"^/phenopackets/[^/]+$"), False),
    (re.compile(r"^/reference/genomes$"), False),
    (re.compile(r"^/reference/genes$"), False),
    (re.compile(r"^/reference/genes/[^/]+$"), False),
    (re.compile(r"^/reference/genes/[^/]+/(domains|transcripts)$"), False),
    (re.compile(r"^/reference/regions/[^/]+$"), False),
    (re.compile(r"^/publications/?$"), False),
    (re.compile(r"^/ontology/hpo/autocomplete$"), False),
    (re.compile(r"^/ontology/hpo/grouped$"), False),
    (re.compile(r"^/ontology/vocabularies/[a-z-]+$"), False),
    # Unified search (safe ONLY after Task A4 fixes the global_search_index MV).
    (re.compile(r"^/search/global$"), True),
    (re.compile(r"^/search/autocomplete$"), True),
]

# Explicit denylist guards (defense-in-depth; also fail the catch-all below).
# NOTE: we do NOT blanket-deny /search/* — /search/global & /search/autocomplete
# are allowlisted above. Only side-effecting / privileged paths are denied.
_DENY = [re.compile(p) for p in (
    r"^/publications/[^/]+/metadata$", r"^/admin", r"^/auth", r"^/dev",
)]

ALLOWED = [r.pattern for r, _ in _RULES]


def _match(path: str) -> tuple[re.Pattern[str], bool] | None:
    if any(d.search(path) for d in _DENY):
        return None
    for rule, disc in _RULES:
        if rule.match(path):
            return rule, disc
    return None


def is_allowed(path: str) -> bool:
    """Return True if the API path is on the allowlist."""
    return _match(path) is not None


def is_discovery_only(path: str) -> bool:
    """Return True if the path may be used for IDs/counts only.

    Discovery-only paths are not authoritative content sources.
    """
    m = _match(path)
    return bool(m and m[1])


def assert_allowed(path: str) -> None:
    """Raise PermissionError if the path is not allowlisted."""
    if not is_allowed(path):
        raise PermissionError(f"path not allowlisted: {path}")
