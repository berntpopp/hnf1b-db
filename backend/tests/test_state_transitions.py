"""Pure-function guard matrix — no I/O.

Wave 7 D.1 Task 6: tests for ``app.phenopackets.services.transitions``.
Spec reference: docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §4.1.
"""

import pytest

from app.phenopackets.services.transitions import (
    StateTransition,
    TransitionError,
    allowed_transitions,
    check_transition,
)

CURATOR = "curator"
ADMIN = "admin"
VIEWER = "viewer"


@pytest.mark.parametrize(
    "from_state,to_state,role,is_owner,expected_ok",
    [
        # --- happy paths ---
        ("draft", "in_review", CURATOR, True, True),
        ("in_review", "draft", CURATOR, True, True),  # withdraw
        ("in_review", "changes_requested", ADMIN, False, True),
        ("in_review", "approved", ADMIN, False, True),
        ("changes_requested", "in_review", CURATOR, True, True),  # resubmit
        ("approved", "published", ADMIN, False, True),
        ("published", "archived", ADMIN, False, True),
        # admin can also archive from other non-archived states
        ("draft", "archived", ADMIN, False, True),
        ("in_review", "archived", ADMIN, False, True),
        ("changes_requested", "archived", ADMIN, False, True),
        ("approved", "archived", ADMIN, False, True),
        # admin bypasses ownership for ownership-required transitions
        ("draft", "in_review", ADMIN, False, True),
        ("in_review", "draft", ADMIN, False, True),
        ("changes_requested", "in_review", ADMIN, False, True),
        # --- role/ownership rejections ---
        ("draft", "in_review", CURATOR, False, False),  # not owner
        ("in_review", "approved", CURATOR, True, False),  # curator can't approve
        (
            "in_review",
            "changes_requested",
            CURATOR,
            True,
            False,
        ),  # curator can't request_changes
        ("approved", "published", CURATOR, False, False),  # curator can't publish
        ("draft", "in_review", VIEWER, True, False),  # viewer blocked everywhere
        ("in_review", "draft", CURATOR, False, False),  # withdraw requires ownership
        (
            "changes_requested",
            "in_review",
            CURATOR,
            False,
            False,
        ),  # resubmit requires ownership
        ("draft", "archived", CURATOR, True, False),  # archive requires admin
        ("in_review", "archived", CURATOR, True, False),
        # --- invalid transition pairs ---
        ("draft", "approved", ADMIN, False, False),
        ("draft", "published", ADMIN, False, False),
        ("draft", "changes_requested", ADMIN, False, False),
        ("published", "draft", ADMIN, False, False),
        ("archived", "draft", ADMIN, False, False),
        ("archived", "published", ADMIN, False, False),
        ("archived", "in_review", ADMIN, False, False),
        ("approved", "draft", ADMIN, False, False),
        ("approved", "in_review", ADMIN, False, False),
    ],
)
def test_guard_matrix(from_state, to_state, role, is_owner, expected_ok):
    """Every cell of the §4.1 guard matrix has the correct outcome."""
    if expected_ok:
        result = check_transition(from_state, to_state, role=role, is_owner=is_owner)
        assert isinstance(result, StateTransition)
    else:
        with pytest.raises(TransitionError):
            check_transition(from_state, to_state, role=role, is_owner=is_owner)


def test_transition_error_has_code_attribute():
    """TransitionError.code is one of the three documented strings."""
    with pytest.raises(TransitionError) as exc_info:
        check_transition("draft", "published", role=ADMIN, is_owner=False)
    assert exc_info.value.code == "invalid_transition"

    with pytest.raises(TransitionError) as exc_info:
        check_transition("in_review", "approved", role=CURATOR, is_owner=True)
    assert exc_info.value.code == "forbidden_role"

    with pytest.raises(TransitionError) as exc_info:
        check_transition("draft", "in_review", role=CURATOR, is_owner=False)
    assert exc_info.value.code == "forbidden_not_owner"


def test_allowed_transitions_curator_owner_on_draft():
    """Curator-owner on draft: only submit (→ in_review) is legal."""
    legal = allowed_transitions("draft", role=CURATOR, is_owner=True)
    assert legal == {"in_review"}


def test_allowed_transitions_admin_on_in_review():
    """Admin on in_review: can approve, request_changes, withdraw, or archive."""
    legal = allowed_transitions("in_review", role=ADMIN, is_owner=False)
    assert legal == {"draft", "changes_requested", "approved", "archived"}


def test_allowed_transitions_nonowner_curator_on_draft():
    """Non-owner curator on draft: nothing (ownership required for submit)."""
    legal = allowed_transitions("draft", role=CURATOR, is_owner=False)
    assert legal == set()


def test_allowed_transitions_curator_owner_on_changes_requested():
    """Curator-owner on changes_requested: can only resubmit (→ in_review)."""
    legal = allowed_transitions("changes_requested", role=CURATOR, is_owner=True)
    assert legal == {"in_review"}


def test_viewer_sees_nothing_everywhere():
    """Viewer role has zero legal transitions from any state."""
    for state in ["draft", "in_review", "changes_requested", "approved", "published"]:
        assert allowed_transitions(state, role=VIEWER, is_owner=True) == set()


def test_archived_is_terminal():
    """No outbound transitions from archived for any role."""
    for role in [ADMIN, CURATOR, VIEWER]:
        assert allowed_transitions("archived", role=role, is_owner=True) == set()
        assert allowed_transitions("archived", role=role, is_owner=False) == set()


def test_admin_bypass_ownership_withdraw():
    """Admin can withdraw even when not the draft owner (is_owner=False)."""
    result = check_transition("in_review", "draft", role=ADMIN, is_owner=False)
    assert result.to_state == "draft"


def test_check_transition_returns_state_transition_dataclass():
    """check_transition returns a StateTransition on success."""
    rule = check_transition("draft", "in_review", role=CURATOR, is_owner=True)
    assert rule.from_state == "draft"
    assert rule.to_state == "in_review"
    assert rule.requires_admin is False
    assert rule.requires_ownership_or_admin is True
