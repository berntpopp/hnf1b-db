"""AST-level enforcement test for visibility filter invariants — Wave 7 D.1 Task 15.

Every Python **function or method** under ``app/`` that issues raw SQL
touching the ``phenopackets`` table **must** satisfy one of the
following at the *function* level (not just somewhere in the file):

A. The function body contains a call to ``public_filter(`` (ORM helper).

B. The function body contains all three raw-SQL filter strings:
       deleted_at IS NULL
       state = 'published'
       head_published_revision_id IS NOT NULL

C. The function body contains ``PUBLIC_FILTER_FRAGMENT`` (the shared
   constant that embeds all three conditions).

D. A ``# noqa: visibility`` comment appears on the line immediately
   above the function definition OR as the first comment inside the
   function body.

E. The containing *module* has a ``# noqa: visibility`` comment in its
   first 5 lines (module-level opt-out for intentionally admin-only
   files).

This test was strengthened from file-level to function-level in Wave 7
D.1 Phase 4 to close a gap where sub-functions in a file missed the
filter even though other functions in the same file had it.

TDD note: previously fixed files in REQUIRES_PUBLIC_FILTER have been
replaced by the function-level check; the KNOWN_VIOLATIONS list is now
empty (all gaps closed in D.1 Phase 4).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Union

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).parent.parent / "app"

# The three SQL fragments that together constitute the public filter (I3+I7+I1).
PUBLIC_FILTER_CONDITIONS = [
    "deleted_at IS NULL",
    "state = 'published'",
    "head_published_revision_id IS NOT NULL",
]

# ORM helper sentinel — using this in a function counts as applying the filter.
ORM_FILTER_SENTINEL = "public_filter("

# Shared constant sentinel — using this in a function counts as applying the filter.
FRAGMENT_SENTINEL = "PUBLIC_FILTER_FRAGMENT"

# noqa marker that opts a function (or module) out of the check.
NOQA_MARKER = "noqa: visibility"


# ---------------------------------------------------------------------------
# File-level helpers (module opt-out + table-touching detection)
# ---------------------------------------------------------------------------

def _module_has_noqa_opt_out(path: Path) -> bool:
    """Return True if the module has a ``# noqa: visibility`` in its first 5 lines."""
    first_lines = path.read_text(encoding="utf-8").splitlines()[:5]
    return any(NOQA_MARKER in line for line in first_lines)


def _file_touches_phenopackets_table(path: Path) -> bool:
    """Return True if the file contains raw SQL referencing the phenopackets table.

    We only flag lines where "phenopackets" appears in a clear SQL context:
      - ``FROM phenopackets`` (direct table reference)
      - ``phenopackets p,`` or ``phenopackets p `` (cross-join with alias at line start)

    Plain Python references (imports, class names, docstrings) are excluded
    because they don't match any of the above patterns.
    """
    text = path.read_text(encoding="utf-8")
    sql_table_ref = re.compile(
        r"\bFROM\s+phenopackets\b"           # FROM phenopackets [alias]
        r"|^\s+phenopackets\s+p\s*[,\n]",    # cross-join with alias at line start
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(sql_table_ref.search(text))


# ---------------------------------------------------------------------------
# Function-level AST helpers
# ---------------------------------------------------------------------------

FuncNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]

_SQL_TABLE_RE = re.compile(
    r"\bFROM\s+phenopackets\b"
    r"|^\s+phenopackets\s+p\s*[,\n]",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_function_source(source_lines: list[str], node: FuncNode) -> str:
    """Extract the source text for a single function node.

    Uses line numbers from the AST node (1-indexed).  We grab from the
    ``def``/``async def`` line through ``end_lineno`` inclusive.
    """
    start = node.lineno - 1          # 0-indexed
    end = (node.end_lineno or node.lineno)  # end_lineno is 1-indexed inclusive
    return "\n".join(source_lines[start:end])


def _function_body_selects_phenopacket(func_source: str) -> bool:
    """Return True if the function source contains a raw SQL phenopackets reference."""
    return bool(_SQL_TABLE_RE.search(func_source))


def _function_body_applies_filter(func_source: str) -> bool:
    """Return True if the function source applies the visibility filter."""
    if ORM_FILTER_SENTINEL in func_source:
        return True
    if FRAGMENT_SENTINEL in func_source:
        return True
    return all(cond in func_source for cond in PUBLIC_FILTER_CONDITIONS)


def _function_has_noqa(
    source_lines: list[str],
    node: FuncNode,
) -> bool:
    """Return True if the function has a ``# noqa: visibility`` opt-out.

    Checks:
    1. The line immediately above the ``def`` statement.
    2. The first non-empty line inside the function body (after the
       docstring, if present — we check the raw source lines for the
       comment rather than parsing the AST body to keep it simple).
    """
    def_line = node.lineno - 1  # 0-indexed

    # Check the line immediately above the def
    if def_line > 0 and NOQA_MARKER in source_lines[def_line - 1]:
        return True

    # Check the first few lines of the function body
    body_start = def_line + 1
    body_end = min(body_start + 5, len(source_lines))
    for line in source_lines[body_start:body_end]:
        if NOQA_MARKER in line:
            return True

    return False


def _collect_offending_functions(path: Path) -> list[str]:
    """Return a list of ``path::function_name`` strings that violate the rule.

    A function violates the rule if:
    - It contains a raw SQL reference to ``phenopackets`` AND
    - It does NOT apply the visibility filter AND
    - It does NOT have a ``# noqa: visibility`` opt-out AND
    - The containing module does NOT have a module-level opt-out.
    """
    # Module-level opt-out — all functions in this file are exempt.
    if _module_has_noqa_opt_out(path):
        return []

    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []  # Broken file — syntax errors are caught by other tests.

    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_source = _extract_function_source(source_lines, node)

        if not _function_body_selects_phenopacket(func_source):
            continue  # Function doesn't touch phenopackets — skip.

        if _function_has_noqa(source_lines, node):
            continue  # Explicitly opted out — skip.

        if _function_body_applies_filter(func_source):
            continue  # Filter present — compliant.

        offenders.append(f"{path.relative_to(APP_ROOT)}::{node.name}")

    return offenders


# ---------------------------------------------------------------------------
# KNOWN_VIOLATIONS — must be empty after D.1 Phase 4 sweep.
#
# If a file still has a genuine unresolved gap, add it here with a
# GitHub issue reference. Keep the list lean: remove entries as soon
# as the gap is closed.
# ---------------------------------------------------------------------------

KNOWN_VIOLATIONS: dict[str, str] = {
    # No known violations as of D.1 ship — all gaps closed in Phase 4.
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFunctionLevelVisibilityEnforcement:
    """Every function that touches phenopackets must apply the visibility filter.

    This is a function-level check (not file-level) so that sub-function
    gaps are caught even when sibling functions in the same file are
    already compliant.
    """

    def test_no_unfiltered_phenopacket_functions(self) -> None:
        """Walk all app/ .py files and flag functions that miss the filter."""
        all_offenders: list[str] = []

        for py_file in sorted(APP_ROOT.rglob("*.py")):
            # Quick pre-filter: skip files that don't touch the table at all.
            if not _file_touches_phenopackets_table(py_file):
                continue

            rel = str(py_file.relative_to(APP_ROOT))

            # Files listed as known violations are tracked separately.
            if rel in KNOWN_VIOLATIONS:
                continue

            offenders = _collect_offending_functions(py_file)
            all_offenders.extend(offenders)

        assert not all_offenders, (
            "The following functions touch the phenopackets table with raw SQL\n"
            "but do not apply the full public visibility filter.\n\n"
            "Each function must either:\n"
            "  A. Call public_filter() (ORM helper)\n"
            "  B. Include all three raw-SQL conditions:\n"
            "       deleted_at IS NULL\n"
            "       state = 'published'\n"
            "       head_published_revision_id IS NOT NULL\n"
            "  C. Reference PUBLIC_FILTER_FRAGMENT\n"
            "  D. Have a '# noqa: visibility: <reason>' comment above the def\n"
            "     or as the first comment in the function body\n"
            "  E. Be in a module with '# noqa: visibility' in its first 5 lines\n\n"
            "Offending functions:\n"
            + "\n".join(f"  - {o}" for o in all_offenders)
        )


class TestKnownViolationsStillViolating:
    """Guard: KNOWN_VIOLATIONS entries should still be violations.

    If a file in KNOWN_VIOLATIONS is now clean, remove it from the dict
    to keep the list accurate.

    No known violations as of D.1 ship — parametrize list is empty.
    """

    @pytest.mark.parametrize("rel_path", sorted(KNOWN_VIOLATIONS.keys()))
    def test_known_violation_is_still_a_violation(self, rel_path: str) -> None:
        """File should still have at least one unfiltered function."""
        path = APP_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"File not found (may have been moved): {path}")

        # Module-level opt-out means it's no longer a raw violation.
        if _module_has_noqa_opt_out(path):
            pytest.fail(
                f"{rel_path!r} is in KNOWN_VIOLATIONS but now has a module-level "
                f"noqa opt-out. Remove it from KNOWN_VIOLATIONS."
            )

        offenders = _collect_offending_functions(path)
        if not offenders:
            pytest.fail(
                f"{rel_path!r} is in KNOWN_VIOLATIONS but has no offending "
                f"functions any more. Remove it from KNOWN_VIOLATIONS."
            )
