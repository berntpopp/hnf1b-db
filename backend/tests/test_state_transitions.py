"""Pure structural guard matrix — no I/O.

Actor-specific reviewer independence is intentionally tested at the policy and
state-service layers rather than duplicated here.
"""

import pytest

from app.phenopackets.services.transitions import (
    Role,
    StateTransition,
    TransitionError,
    allowed_transitions,
    check_transition,
    structural_transition_capabilities,
)

CURATOR: Role = "curator"
ADMIN: Role = "admin"
VIEWER: Role = "viewer"


@pytest.mark.parametrize(
    "from_state,to_state,role,is_owner,expected_ok",
    [
        # --- happy paths ---
        ("draft", "in_review", CURATOR, True, True),
        ("in_review", "draft", CURATOR, True, True),  # withdraw
        ("in_review", "changes_requested", ADMIN, False, True),
        ("in_review", "approved", ADMIN, False, True),
        ("in_review", "changes_requested", CURATOR, False, True),
        ("in_review", "approved", CURATOR, False, True),
        ("in_review", "changes_requested", CURATOR, True, True),
        ("in_review", "approved", CURATOR, True, True),
        ("changes_requested", "in_review", CURATOR, True, True),  # resubmit
        ("approved", "changes_requested", CURATOR, False, True),
        ("approved", "changes_requested", ADMIN, False, True),
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
        check_transition("approved", "published", role=CURATOR, is_owner=True)
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


def test_allowed_review_transitions_for_nonowner_curator():
    """The pure matrix leaves independence decisions to the locked service."""
    assert allowed_transitions("in_review", role=CURATOR, is_owner=False) == {
        "changes_requested",
        "approved",
    }
    assert allowed_transitions("approved", role=CURATOR, is_owner=False) == {
        "changes_requested"
    }


def test_pure_matrix_does_not_claim_reviewer_independence():
    """Owner status is deliberately ignored for structurally valid decisions."""
    rule = check_transition("in_review", "approved", role=CURATOR, is_owner=True)

    assert rule.requires_admin is False
    assert rule.requires_ownership_or_admin is False


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


def test_structural_capabilities_are_derived_from_the_guard_matrix() -> None:
    """Draft owners get submit while archive remains a server-explained denial."""
    capabilities = structural_transition_capabilities(
        "draft", role=CURATOR, is_owner=True
    )

    assert [(item.action, item.allowed, item.blocked_by) for item in capabilities] == [
        ("submit", True, ()),
        ("archive", False, ("forbidden_role",)),
    ]


def test_structural_capabilities_distinguish_resubmit_and_ownership_denial() -> None:
    """Changes-requested projects resubmit without recreating ownership policy."""
    capabilities = structural_transition_capabilities(
        "changes_requested", role=CURATOR, is_owner=False
    )

    assert [(item.action, item.allowed, item.blocked_by) for item in capabilities] == [
        ("resubmit", False, ("forbidden_not_owner",)),
        ("archive", False, ("forbidden_role",)),
    ]


def test_structural_capabilities_preserve_published_admin_archive() -> None:
    """Published records still expose their one payload-compatible action."""
    capabilities = structural_transition_capabilities(
        "published", role=ADMIN, is_owner=False
    )

    assert [(item.action, item.allowed, item.blocked_by) for item in capabilities] == [
        ("archive", True, ())
    ]
