"""AST-level enforcement test for visibility filter invariants — Wave 7 D.1 Task 15.

Every Python file under ``app/`` that issues raw SQL touching the
``phenopackets`` table **must** satisfy one of the following:

A. It applies the full public filter:
       deleted_at IS NULL
       AND state = 'published'
       AND head_published_revision_id IS NOT NULL

B. It uses the ORM ``public_filter()`` helper (which embeds the same
   three conditions).

C. It carries an explicit ``# noqa: visibility`` opt-out comment on
   the module's first line (reserved for admin-only endpoints that
   intentionally show all states to authenticated privileged users).

D. It is listed in ``KNOWN_VIOLATIONS`` below — files that still use
   only ``deleted_at IS NULL`` and are tracked for a follow-up sweep.
   Each entry must have a GitHub issue / task reference in its comment.

This test fails if:
  - A file in ``REQUIRES_PUBLIC_FILTER`` does NOT contain all three
    public-filter conditions.
  - A file in ``KNOWN_VIOLATIONS`` has already been fixed (remove it
    from the set to keep the list lean).

TDD note: this test was added as part of Phase 4 / Task 15.  Files that
are not yet fixed land in ``KNOWN_VIOLATIONS``; move them to
``REQUIRES_PUBLIC_FILTER`` as each follow-up sweep is completed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).parent.parent / "app"

# The three SQL fragments that together constitute the public filter (I3+I7+I1).
PUBLIC_FILTER_CONDITIONS = [
    "deleted_at IS NULL",
    "state = 'published'",
    "head_published_revision_id IS NOT NULL",
]

# ORM helper — using this counts as applying the filter.
ORM_FILTER_SENTINEL = "public_filter("


def _file_uses_public_filter(path: Path) -> bool:
    """Return True if the file applies the full public filter."""
    text = path.read_text(encoding="utf-8")
    if ORM_FILTER_SENTINEL in text:
        return True
    return all(cond in text for cond in PUBLIC_FILTER_CONDITIONS)


def _file_has_noqa_opt_out(path: Path) -> bool:
    """Return True if the file has an explicit # noqa: visibility opt-out."""
    first_lines = path.read_text(encoding="utf-8").splitlines()[:5]
    return any("noqa: visibility" in line for line in first_lines)


def _file_touches_phenopackets_table(path: Path) -> bool:
    """Return True if the file contains raw SQL referencing the phenopackets table.

    We only flag lines where "phenopackets" appears in a clear SQL context:
      - ``FROM phenopackets`` (direct table reference)
      - ``phenopackets,`` followed by whitespace (cross-join without alias)
      - ``phenopackets p,`` or ``phenopackets p `` (cross-join with alias)

    Plain Python references (imports, class names, docstrings) are excluded
    because they don't match any of the above patterns.
    """
    text = path.read_text(encoding="utf-8")
    # SQL table references only — not Python identifiers or import paths.
    # We match:
    #   1. "FROM phenopackets" — unambiguous SQL table reference
    #   2. Cross-join: a line that starts with optional whitespace then
    #      "phenopackets p," (with an alias) — SQL cross-join pattern
    # We deliberately exclude "phenopackets," without an alias (too broad —
    # matches docstring prose like "phenopackets, publications").
    sql_table_ref = re.compile(
        r"\bFROM\s+phenopackets\b"          # FROM phenopackets [alias]
        r"|^\s+phenopackets\s+p\s*[,\n]",   # cross-join with alias at line start
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(sql_table_ref.search(text))


# ---------------------------------------------------------------------------
# Files that MUST have the full public filter applied.
# These are public-facing endpoints fixed in Wave 7 D.1 Phase 4.
# ---------------------------------------------------------------------------

REQUIRES_PUBLIC_FILTER: set[str] = {
    # Tasks 12-13: search, comparisons, aggregations
    "phenopackets/routers/search.py",
    "phenopackets/routers/comparisons/query.py",
    "phenopackets/routers/crud_related.py",
    "phenopackets/routers/aggregations/features.py",
    "phenopackets/routers/aggregations/demographics.py",
    "phenopackets/routers/aggregations/diseases.py",
    "phenopackets/routers/aggregations/publications.py",
    "phenopackets/routers/aggregations/summary.py",
    # Task 14: publications list, sitemap
    "publications/endpoints/list_route.py",
    "seo/sitemap.py",
    # search repository (used by Tasks 12+)
    "search/repositories.py",
    "search/services/facet.py",
}

# ---------------------------------------------------------------------------
# Files that still need a follow-up sweep.
# Each entry: relative path → reason / tracking note.
# ---------------------------------------------------------------------------

KNOWN_VIOLATIONS: dict[str, str] = {
    # Admin-only endpoints intentionally show all states to privileged users.
    # These should get a noqa:visibility marker once the admin auth guard is
    # confirmed (tracked in Wave 7 D.2 / admin hardening).
    "api/admin/queries.py": "admin-only queries — intentional, pending noqa opt-out",
    # Survival analysis handlers — complex multi-CTE queries, follow-up sweep.
    "phenopackets/routers/aggregations/survival/handlers/disease_subtype.py": (
        "survival handler, follow-up sweep planned"
    ),
    "phenopackets/routers/aggregations/survival/handlers/protein_domain.py": (
        "survival handler, follow-up sweep planned"
    ),
    "phenopackets/routers/aggregations/survival/handlers/pathogenicity.py": (
        "survival handler, follow-up sweep planned"
    ),
    "phenopackets/routers/aggregations/survival/handlers/variant_type.py": (
        "survival handler, follow-up sweep planned"
    ),
    # Variant aggregation queries — follow-up sweep.
    "phenopackets/routers/aggregations/variants.py": (
        "variant aggregation, follow-up sweep planned"
    ),
    # Shared SQL fragment CTEs used by survival/comparison queries — follow-up sweep.
    "phenopackets/routers/aggregations/sql_fragments/ctes.py": (
        "shared SQL fragments, follow-up sweep planned"
    ),
    # Variant query builder used by comparison endpoints — follow-up sweep.
    "phenopackets/routers/aggregations/variant_query_builder.py": (
        "variant query builder, follow-up sweep planned"
    ),
    # Publication sync route is admin-triggered — intentional, pending noqa opt-out.
    "publications/endpoints/sync_route.py": (
        "admin-triggered sync endpoint — intentional, pending noqa opt-out"
    ),
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublicFilterEnforcement:
    """Verify public-filter conditions are present in all fixed files."""

    @pytest.mark.parametrize("rel_path", sorted(REQUIRES_PUBLIC_FILTER))
    def test_file_has_public_filter(self, rel_path: str) -> None:
        """File must apply the full public filter (ORM helper or raw SQL)."""
        path = APP_ROOT / rel_path
        assert path.exists(), f"Expected file not found: {path}"
        assert _file_uses_public_filter(path), (
            f"{rel_path!r} is missing the full public filter.\n"
            f"Required conditions: {PUBLIC_FILTER_CONDITIONS}\n"
            f"Or use the ORM helper: public_filter(stmt)"
        )


class TestKnownViolationsStillViolating:
    """Guard against KNOWN_VIOLATIONS entries that have already been fixed.

    If a file in KNOWN_VIOLATIONS now passes the public-filter check AND
    no longer has a noqa opt-out, this test fails to remind the developer
    to remove it from KNOWN_VIOLATIONS and add it to REQUIRES_PUBLIC_FILTER.
    """

    @pytest.mark.parametrize("rel_path", sorted(KNOWN_VIOLATIONS.keys()))
    def test_known_violation_is_still_a_violation(self, rel_path: str) -> None:
        """File should NOT yet have the full filter (it's a known todo)."""
        path = APP_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"File not found (may have been moved): {path}")

        already_fixed = _file_uses_public_filter(path)
        has_opt_out = _file_has_noqa_opt_out(path)

        if already_fixed or has_opt_out:
            pytest.fail(
                f"{rel_path!r} is listed in KNOWN_VIOLATIONS but is already fixed.\n"
                f"Remove it from KNOWN_VIOLATIONS and add it to "
                f"REQUIRES_PUBLIC_FILTER (or add # noqa: visibility if intentional)."
            )


class TestNoUncataloguedGaps:
    """Every file that touches the phenopackets table must be accounted for.

    A file is "accounted for" if it:
      - Is in REQUIRES_PUBLIC_FILTER (and passing that check), OR
      - Is in KNOWN_VIOLATIONS, OR
      - Has a # noqa: visibility opt-out comment.

    This test enumerates all app/ .py files that reference the phenopackets
    table and flags any that fall into none of the above categories.
    """

    def test_no_uncatalogued_gaps(self) -> None:
        """No phenopackets-touching file should be silently unaccounted for."""
        all_accounted = set(REQUIRES_PUBLIC_FILTER) | set(KNOWN_VIOLATIONS.keys())

        gaps: list[str] = []
        for py_file in sorted(APP_ROOT.rglob("*.py")):
            rel = str(py_file.relative_to(APP_ROOT))
            if not _file_touches_phenopackets_table(py_file):
                continue
            if rel in all_accounted:
                continue
            if _file_has_noqa_opt_out(py_file):
                continue
            # Also skip files that already fully implement the public filter —
            # they are compliant even if not listed.
            if _file_uses_public_filter(py_file):
                continue
            gaps.append(rel)

        assert not gaps, (
            "The following files touch the phenopackets table with raw SQL but\n"
            "are neither in REQUIRES_PUBLIC_FILTER, KNOWN_VIOLATIONS, nor do\n"
            "they have a # noqa: visibility opt-out AND they don't apply the\n"
            "full public filter:\n\n"
            + "\n".join(f"  - {g}" for g in gaps)
            + "\n\nAdd them to REQUIRES_PUBLIC_FILTER (if fixed) or "
            "KNOWN_VIOLATIONS (if pending)."
        )
