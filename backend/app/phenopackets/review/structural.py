"""Typed adapter from structural state guards to public capabilities."""

from __future__ import annotations

from typing import cast

from app.models.user import User
from app.phenopackets.review.schemas import (
    ActionCapability,
    ReviewAction,
    ReviewBlockCode,
)
from app.phenopackets.services.transitions import (
    Role,
    State,
    structural_transition_capabilities,
)


def structural_capabilities(
    actor: User,
    effective_state: str,
    owner_id: int | None,
) -> list[ActionCapability]:
    """Adapt the pure transition guard projection to the public DTO."""
    if not actor.is_active or actor.role not in ("curator", "admin"):
        return []
    projected = structural_transition_capabilities(
        cast(State, effective_state),
        role=cast(Role, actor.role),
        is_owner=owner_id is not None and actor.id == owner_id,
    )
    return [
        ActionCapability(
            action=cast(ReviewAction, item.action),
            allowed=item.allowed,
            blocked_by=tuple(cast(ReviewBlockCode, code) for code in item.blocked_by),
        )
        for item in projected
    ]
