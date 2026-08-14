"""Database-backed independent-review eligibility policy."""

from __future__ import annotations

from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.review.schemas import (
    ActionCapability,
    ReviewAction,
    ReviewBlockCode,
    ReviewCapabilities,
)

DecisionAction = Literal["request_changes", "approve"]
_CONTENT_EVENTS = ("created", "draft_created", "draft_saved")


class ReviewPolicyError(PermissionError):
    """Typed, content-free independent-review denial."""

    def __init__(
        self,
        code: ReviewBlockCode,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a stable denial suitable for router translation."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context or {}


class ReviewPolicy:
    """Evaluate reviewer independence from immutable server-side audit rows."""

    _MESSAGES: dict[ReviewBlockCode, str] = {
        "self_review_forbidden": "The draft owner cannot review this candidate.",
        "reviewer_submitted": "The candidate submitter cannot review it.",
        "reviewer_contributed": (
            "A content contributor in this edit cycle cannot review the candidate."
        ),
        "review_author_unknown": (
            "Reviewer independence cannot be established from the audit history."
        ),
        "unresolved_review_issues": (
            "All blocking review issues must be resolved before approval."
        ),
        "review_closed": "This candidate is not open for the requested review action.",
    }

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        phenopacket: Phenopacket,
        candidate_revision: PhenopacketRevision,
        actor: User,
        unresolved_count: int,
    ) -> ReviewCapabilities:
        """Return ordered capabilities without exposing candidate content.

        Args:
            db: Transaction-bound async session.
            phenopacket: Locked record whose active cycle is being evaluated.
            candidate_revision: Immutable ``in_review`` submission snapshot.
            actor: Authenticated actor.
            unresolved_count: Server-derived active-cycle blocking issue count.

        Returns:
            Actor-specific ordered review capabilities.
        """
        if not actor.is_active or actor.role not in ("curator", "admin"):
            return ReviewCapabilities(actions=[])

        effective_state, active_revision = await cls._effective_review_state(
            db, phenopacket
        )
        cycle_start = await cls._cycle_start_revision(db, phenopacket)
        candidate_ancestry_unknown = False
        try:
            expected_candidate = await cls.active_candidate(
                db, phenopacket, active_revision
            )
        except ReviewPolicyError as exc:
            expected_candidate = None
            candidate_ancestry_unknown = exc.code == "review_author_unknown"
        candidate_is_active = (
            expected_candidate is not None
            and expected_candidate.id == candidate_revision.id
        )

        ancestry_unknown = (
            candidate_ancestry_unknown
            or cycle_start is False
            or (
                cycle_start is not None
                and candidate_revision.revision_number <= cycle_start
            )
        )
        if phenopacket.draft_owner_id is None or ancestry_unknown:
            common_blockers: list[ReviewBlockCode] = ["review_author_unknown"]
        elif not candidate_is_active:
            common_blockers = ["review_closed"]
        else:
            common_blockers = await cls._independence_blockers(
                db, phenopacket, candidate_revision, actor
            )

        actions: list[ActionCapability] = []
        if effective_state == "in_review":
            actions.append(cls._capability("request_changes", common_blockers))
            approval_blockers = list(common_blockers)
            if unresolved_count > 0:
                approval_blockers.append("unresolved_review_issues")
            actions.append(cls._capability("approve", approval_blockers))
        elif effective_state == "approved":
            actions.append(cls._capability("request_changes", common_blockers))
            if actor.role == "admin":
                actions.append(cls._capability("publish", []))
        else:
            actions.extend(
                [
                    cls._capability("request_changes", ["review_closed"]),
                    cls._capability("approve", ["review_closed"]),
                ]
            )

        return ReviewCapabilities(actions=actions)

    @classmethod
    async def require_independent_reviewer(
        cls,
        db: AsyncSession,
        phenopacket: Phenopacket,
        candidate_revision: PhenopacketRevision,
        actor: User,
        unresolved_count: int,
        *,
        action: DecisionAction,
    ) -> None:
        """Require one allowed independent-review decision capability.

        Raises:
            ReviewPolicyError: With the first stable blocker code and safe context.
        """
        capabilities = await cls.evaluate(
            db,
            phenopacket,
            candidate_revision,
            actor,
            unresolved_count,
        )
        capability = next(
            (item for item in capabilities.actions if item.action == action), None
        )
        if capability is not None and capability.allowed:
            return

        code = (
            capability.blocked_by[0]
            if capability is not None and capability.blocked_by
            else "review_closed"
        )
        context = (
            {"unresolved_count": unresolved_count}
            if code == "unresolved_review_issues"
            else {}
        )
        raise ReviewPolicyError(code, cls._MESSAGES[code], context)

    @staticmethod
    def _capability(
        action: ReviewAction, blockers: list[ReviewBlockCode]
    ) -> ActionCapability:
        """Build a capability while preserving blocker insertion order."""
        return ActionCapability(
            action=action,
            allowed=not blockers,
            blocked_by=tuple(blockers),
        )

    @staticmethod
    async def _effective_review_state(
        db: AsyncSession, phenopacket: Phenopacket
    ) -> tuple[str, PhenopacketRevision | None]:
        """Resolve the authoritative active state without trusting client input."""
        if phenopacket.editing_revision_id is None:
            return phenopacket.state, None
        active_revision = await db.get(
            PhenopacketRevision, phenopacket.editing_revision_id
        )
        if active_revision is None or active_revision.record_id != phenopacket.id:
            return phenopacket.state, None
        return active_revision.state, active_revision

    @classmethod
    async def active_candidate(
        cls,
        db: AsyncSession,
        phenopacket: Phenopacket,
        active_revision: PhenopacketRevision | None,
    ) -> PhenopacketRevision:
        """Resolve the inspected candidate from the active revision's direct chain.

        Raises:
            ReviewPolicyError: When active review ancestry is missing or invalid,
                or when the active state is no longer reviewable.
        """
        if active_revision is None or active_revision.record_id != phenopacket.id:
            raise cls._error("review_author_unknown")
        if active_revision.state == "in_review":
            return active_revision
        if active_revision.state != "approved":
            raise cls._error("review_closed")
        if active_revision.parent_revision_id is None:
            raise cls._error("review_author_unknown")

        candidate = await db.get(
            PhenopacketRevision, active_revision.parent_revision_id
        )
        if (
            candidate is None
            or candidate.record_id != phenopacket.id
            or candidate.state != "in_review"
            or candidate.revision_number >= active_revision.revision_number
        ):
            raise cls._error("review_author_unknown")
        return candidate

    @classmethod
    def _error(cls, code: ReviewBlockCode) -> ReviewPolicyError:
        """Build one typed policy error without duplicating safe messages."""
        return ReviewPolicyError(code, cls._MESSAGES[code])

    @classmethod
    async def _independence_blockers(
        cls,
        db: AsyncSession,
        phenopacket: Phenopacket,
        candidate: PhenopacketRevision,
        actor: User,
    ) -> list[ReviewBlockCode]:
        """Derive ordered owner, submitter, and content-contributor blockers."""
        cycle_start = await cls._cycle_start_revision(db, phenopacket)
        if (
            phenopacket.draft_owner_id is None
            or cycle_start is False
            or (cycle_start is not None and candidate.revision_number <= cycle_start)
        ):
            return ["review_author_unknown"]

        blockers: list[ReviewBlockCode] = []
        if actor.id == phenopacket.draft_owner_id:
            blockers.append("self_review_forbidden")
        if actor.id == candidate.actor_id:
            blockers.append("reviewer_submitted")

        contributor_stmt = select(PhenopacketRevision.id).where(
            PhenopacketRevision.record_id == phenopacket.id,
            PhenopacketRevision.actor_id == actor.id,
            PhenopacketRevision.event_type.in_(_CONTENT_EVENTS),
        )
        if cycle_start is not None:
            contributor_stmt = contributor_stmt.where(
                PhenopacketRevision.revision_number > cycle_start
            )
        contributed = (await db.execute(contributor_stmt.limit(1))).scalar_one_or_none()
        if contributed is not None:
            blockers.append("reviewer_contributed")
        return blockers

    @staticmethod
    async def _cycle_start_revision(
        db: AsyncSession, phenopacket: Phenopacket
    ) -> int | None | Literal[False]:
        """Return the public-head number, ``None`` for new, or False if ambiguous."""
        if phenopacket.head_published_revision_id is None:
            return None
        head = await db.get(PhenopacketRevision, phenopacket.head_published_revision_id)
        if head is None or head.record_id != phenopacket.id:
            return False
        return cast(int, head.revision_number)
