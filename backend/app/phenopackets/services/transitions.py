"""Pure-function transition guard matrix for Wave 7/D.1.

No I/O. Feeds both the endpoint handler (which validates before mutating)
and the frontend-mirrored decision-making in TransitionMenu.vue (via an
API-exposed version of ``allowed_transitions``).

Spec reference:
  docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §4.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

State = Literal[
    "draft",
    "in_review",
    "changes_requested",
    "approved",
    "published",
    "archived",
]
Role = Literal["admin", "curator", "viewer"]


class TransitionError(ValueError):
    """Raised when a proposed transition violates the guard matrix.

    ``code`` is one of:

    - ``invalid_transition`` — the (from_state, to_state) pair is not in the
      rule table.
    - ``forbidden_role`` — the caller's role is not allowed for this transition.
    - ``forbidden_not_owner`` — curator must be the draft owner for this
      transition.
    """

    def __init__(self, code: str, message: str) -> None:
        """Initialise with a machine-readable error code and a human message."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StateTransition:
    """Describes one legal state transition and its authorization requirements."""

    from_state: State
    to_state: State
    requires_admin: bool
    # curator must be draft_owner_id or role == admin
    requires_ownership_or_admin: bool = False
    is_archive: bool = False


# ---------------------------------------------------------------------------
# Enumerated rule table — every legal (from_state, to_state) pair from §4.1.
# Any pair NOT in this dict is an invalid transition.
# ---------------------------------------------------------------------------

_RULES: dict[tuple[State, State], StateTransition] = {
    # draft → in_review  (submit): curator must own OR admin
    ("draft", "in_review"): StateTransition(
        "draft",
        "in_review",
        requires_admin=False,
        requires_ownership_or_admin=True,
    ),
    # in_review → draft  (withdraw): curator must own OR admin
    ("in_review", "draft"): StateTransition(
        "in_review",
        "draft",
        requires_admin=False,
        requires_ownership_or_admin=True,
    ),
    # in_review → changes_requested  (request_changes): admin only
    ("in_review", "changes_requested"): StateTransition(
        "in_review",
        "changes_requested",
        requires_admin=True,
    ),
    # in_review → approved  (approve): admin only
    ("in_review", "approved"): StateTransition(
        "in_review",
        "approved",
        requires_admin=True,
    ),
    # changes_requested → in_review  (resubmit): curator must own OR admin
    ("changes_requested", "in_review"): StateTransition(
        "changes_requested",
        "in_review",
        requires_admin=False,
        requires_ownership_or_admin=True,
    ),
    # approved → published  (publish): admin only; triggers head-swap §6.2
    ("approved", "published"): StateTransition(
        "approved",
        "published",
        requires_admin=True,
    ),
}

# archive is available from every non-archived state; admin only (terminal)
for _s in ("draft", "in_review", "changes_requested", "approved", "published"):
    _RULES[(_s, "archived")] = StateTransition(
        _s,
        "archived",
        requires_admin=True,
        is_archive=True,
    )


def check_transition(
    from_state: State,
    to_state: State,
    *,
    role: Role,
    is_owner: bool,
) -> StateTransition:
    """Validate a proposed state transition and return its rule on success.

    Args:
        from_state: Current state of the phenopacket.
        to_state: Requested next state.
        role: Role of the actor (``"admin"``, ``"curator"``, or ``"viewer"``).
        is_owner: True when the actor's user id equals ``draft_owner_id``.

    Returns:
        The matching :class:`StateTransition` rule.

    Raises:
        TransitionError: ``.code`` is one of ``invalid_transition``,
            ``forbidden_role``, or ``forbidden_not_owner``.
    """
    rule = _RULES.get((from_state, to_state))
    if rule is None:
        raise TransitionError(
            "invalid_transition",
            f"{from_state!r} -> {to_state!r} is not a legal transition",
        )

    # Viewer role can never perform any transition.
    if role not in ("admin", "curator"):
        raise TransitionError(
            "forbidden_role",
            f"role {role!r} is not permitted to perform state transitions",
        )

    # Admin-only transitions reject non-admin callers outright.
    if rule.requires_admin and role != "admin":
        raise TransitionError(
            "forbidden_role",
            f"transition to {to_state!r} requires admin role",
        )

    # Ownership-or-admin: admin always passes; curator must own.
    if rule.requires_ownership_or_admin and role != "admin" and not is_owner:
        raise TransitionError(
            "forbidden_not_owner",
            f"curator must be the draft owner (or admin) to transition to {to_state!r}",
        )

    return rule


def allowed_transitions(
    from_state: State,
    *,
    role: Role,
    is_owner: bool,
) -> set[State]:
    """Return the set of ``to_state`` values legal for (role, ownership).

    Args:
        from_state: Current state of the phenopacket.
        role: Role of the actor.
        is_owner: True when the actor is the draft owner.

    Returns:
        A (possibly empty) set of legal target states.
    """
    out: set[State] = set()
    for f, t in _RULES:
        if f != from_state:
            continue
        try:
            check_transition(from_state, t, role=role, is_owner=is_owner)
            out.add(t)
        except TransitionError:
            pass
    return out
