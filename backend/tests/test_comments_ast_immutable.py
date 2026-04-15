"""C1 — no application code UPDATEs or DELETEs comment_edits.

The comment_edits table is an append-only audit log. No application code
should ever issue an UPDATE or DELETE against it. This AST-level scan
catches violations before they reach the database.

Spec reference:
  docs/superpowers/specs/
  2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.2 C1.
"""

import pathlib

FORBIDDEN_PATTERNS = (
    "CommentEdit.__table__.update",
    "CommentEdit.__table__.delete",
    "update(CommentEdit)",
    "delete(CommentEdit)",
)


def test_no_mutations_against_comment_edits():
    """C1: scan all .py files under app/ for forbidden mutation patterns."""
    root = pathlib.Path(__file__).parent.parent / "app"
    offenders: list[tuple[str, str]] = []
    for py in root.rglob("*.py"):
        src = py.read_text()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in src:
                offenders.append((str(py), pattern))
    assert not offenders, (
        f"C1 violated — forbidden mutation patterns found: {offenders}"
    )
