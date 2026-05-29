"""Code-enforced allowlist of read-only, side-effect-free /api/v2 paths.

SECURITY BOUNDARY — the runtime regex enforcement, the hand-curated deny-list, and
the discovery-only flags below are deliberate and must not be auto-derived. DRY
Layer 2 only *validates* this allowlist against the generated API contract: the
contract test (``tests/test_contract.py``) asserts that every path this allowlist
allows exists in ``hnf1b_mcp.contract._generated_paths.ALL_PATHS`` and that every
generated path is either allowed here or explicitly denied — forcing an explicit
allow/deny decision whenever the backend adds a route.
"""

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
    # Read-only hybrid passage retrieval over license-gated open-access full text.
    (re.compile(r"^/publications/passages/?$"), False),
    (re.compile(r"^/ontology/hpo/autocomplete$"), False),
    (re.compile(r"^/ontology/hpo/grouped$"), False),
    (re.compile(r"^/ontology/vocabularies/[a-z-]+$"), False),
    # Unified search (safe ONLY after Task A4 fixes the global_search_index MV).
    (re.compile(r"^/search/global$"), True),
    (re.compile(r"^/search/autocomplete$"), True),
]

# Explicit denylist guards (defense-in-depth; also fail the catch-all below).
# NOTE: we do NOT blanket-deny /search/* — /search/global & /search/autocomplete
# are allowlisted above. Only side-effecting / privileged / out-of-scope paths are
# denied. Every backend route NOT in _RULES above is denied here explicitly so the
# contract test can prove there are no silent gaps (see tests/test_contract.py).
_DENY = [
    re.compile(p)
    for p in (
        # Privileged / side-effecting (original guards).
        r"^/publications/[^/]+/metadata$",
        r"^/admin",
        r"^/auth",
        r"^/dev",
        # Live PubMed fetch + DB write.
        r"^/publications/sync$",
        # Clinical aggregation routes — not part of the curated MCP statistics surface.
        r"^/clinical/",
        # Curation collaboration surface (comments, edits, resolve) — write/privileged.
        r"^/comments",
        # Duplicate / legacy HPO routes — MCP uses /ontology/hpo/* only.
        r"^/hpo/",
        # Build/version info — not data.
        r"^/info$",
        # Per-phenopacket workflow/audit/revision routes — curation internals.
        r"^/phenopackets/[^/]+/(audit|revisions|timeline|transitions)(/|$)",
        # Statistical-comparison endpoint — not in the curated metric set.
        r"^/phenopackets/compare/",
        # SEO sitemaps — XML, not data.
        r"^/seo/",
        # User directory — privileged.
        r"^/users/",
        # Variant annotation / recoding / validation — live external tooling, writes.
        r"^/variants/",
    )
]

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


def is_denied(path: str) -> bool:
    """Return True if the path matches an explicit deny rule.

    Used by the contract test to confirm that every generated backend path is
    either allowed or *explicitly* denied (no silent gaps).
    """
    return any(d.search(path) for d in _DENY)


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
