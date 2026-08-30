"""Async SQL repository for review queue and coherent review context reads."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Sequence, cast
from uuid import UUID

from sqlalchemy import case, exists, func, literal, or_, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.comments.models import (
    Comment,
    CommentEdit,
    CommentMention,
    CommentResolutionEvent,
)
from app.comments.schemas import (
    CommentMentionOut,
    CommentResolutionEventOut,
)
from app.models.user import User
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.review.policy import ReviewPolicy, ReviewPolicyFacts
from app.phenopackets.review.schemas import (
    ActorSummary,
    DiscussionSummary,
    ReviewAudit,
    ReviewContext,
    ReviewIssue,
    ReviewQueueQuery,
    ReviewQueueRow,
    ReviewRevision,
    ReviewRevisionSummary,
    ReviewState,
    StateCounts,
)
from app.phenopackets.review.service import ReviewService

_CONTENT_EVENTS = ("created", "draft_created", "draft_saved")
_QUEUE_STATES = ("draft", "in_review", "changes_requested", "approved")


def _actor_summary(actor: User | None) -> ActorSummary | None:
    if actor is None:
        return None
    return ActorSummary(
        id=actor.id,
        username=actor.username,
        display_name=actor.full_name,
    )


class ReviewRepository:
    """Read-only review projections sharing the caller-owned transaction."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the repository with the caller-owned async session."""
        self.db = db

    @staticmethod
    def effective_state_expression(active_revision: Any) -> Any:
        """Return the one SQL effective-state authority used by queue queries."""
        return func.coalesce(active_revision.state, Phenopacket.state)

    def _queue_base(self, actor: User) -> Any:
        """Build one CTE containing every row/filter/policy fact for the queue."""
        active = aliased(PhenopacketRevision, name="active_revision")
        head = aliased(PhenopacketRevision, name="published_head")
        owner = aliased(User, name="draft_owner")
        submission_actor = aliased(User, name="submission_actor")
        revision = aliased(PhenopacketRevision, name="cycle_revision")
        issue_revision = aliased(PhenopacketRevision, name="issue_revision")
        effective_state = self.effective_state_expression(active)
        after_head = or_(
            head.id.is_(None), revision.revision_number > head.revision_number
        )

        submission = (
            select(
                revision.id.label("id"),
                revision.revision_number.label("revision_number"),
                revision.content_sha256.label("content_sha256"),
                revision.content_jsonb.label("content_jsonb"),
                revision.actor_id.label("actor_id"),
                revision.created_at.label("created_at"),
            )
            .where(
                revision.record_id == Phenopacket.id,
                revision.state == "in_review",
                after_head,
            )
            .order_by(revision.revision_number.desc(), revision.id.desc())
            .limit(1)
            .correlate(Phenopacket, head)
            .lateral("submission")
        )
        approved_revision = aliased(PhenopacketRevision, name="approved_cycle_revision")
        approved = (
            select(
                approved_revision.id.label("id"),
                approved_revision.content_sha256.label("content_sha256"),
            )
            .where(
                approved_revision.record_id == Phenopacket.id,
                approved_revision.state == "approved",
                or_(
                    head.id.is_(None),
                    approved_revision.revision_number > head.revision_number,
                ),
            )
            .order_by(
                approved_revision.revision_number.desc(), approved_revision.id.desc()
            )
            .limit(1)
            .correlate(Phenopacket, head)
            .lateral("approved_revision")
        )

        open_issue_count = (
            select(func.count(Comment.id))
            .join(issue_revision, issue_revision.id == Comment.review_revision_id)
            .where(
                Comment.record_type == "phenopacket",
                Comment.record_id == Phenopacket.id,
                Comment.review_revision_id.is_not(None),
                Comment.resolved_at.is_(None),
                Comment.deleted_at.is_(None),
                or_(
                    head.id.is_(None),
                    issue_revision.revision_number > head.revision_number,
                ),
            )
            .correlate(Phenopacket, head)
            .scalar_subquery()
        )
        change_count = (
            select(
                func.coalesce(
                    func.sum(func.jsonb_array_length(revision.change_patch)), 0
                )
            )
            .where(revision.record_id == Phenopacket.id, after_head)
            .correlate(Phenopacket, head)
            .scalar_subquery()
        )
        actor_contributed = exists(
            select(literal(1)).where(
                revision.record_id == Phenopacket.id,
                revision.actor_id == actor.id,
                revision.event_type.in_(_CONTENT_EVENTS),
                after_head,
            )
        ).correlate(Phenopacket, head)
        candidate_id = case(
            (effective_state == "draft", active.id), else_=submission.c.id
        )
        candidate_digest = case(
            (effective_state == "draft", active.content_sha256),
            else_=submission.c.content_sha256,
        )
        candidate_content = func.cast(
            case(
                (effective_state == "draft", active.content_jsonb),
                else_=submission.c.content_jsonb,
            ),
            JSONB,
        )
        subject_label = func.coalesce(
            candidate_content["subject"]["label"].astext,
            candidate_content["subject"]["id"].astext,
            Phenopacket.phenopacket_id,
        )

        return (
            select(
                Phenopacket.id.label("record_id"),
                Phenopacket.phenopacket_id,
                Phenopacket.state.label("physical_state"),
                effective_state.label("effective_state"),
                Phenopacket.revision.label("record_revision"),
                Phenopacket.head_published_revision_id,
                owner.id.label("owner_id"),
                owner.username.label("owner_username"),
                owner.full_name.label("owner_display_name"),
                submission_actor.id.label("submitter_id"),
                submission_actor.username.label("submitter_username"),
                submission_actor.full_name.label("submitter_display_name"),
                submission.c.created_at.label("submitted_at"),
                candidate_id.label("candidate_revision_id"),
                candidate_digest.label("candidate_content_sha256"),
                approved.c.id.label("approved_revision_id"),
                approved.c.content_sha256.label("approved_content_sha256"),
                subject_label.label("subject_label"),
                change_count.label("active_cycle_change_count"),
                open_issue_count.label("open_issue_count"),
                actor_contributed.label("actor_contributed"),
            )
            .select_from(Phenopacket)
            .outerjoin(active, active.id == Phenopacket.editing_revision_id)
            .outerjoin(head, head.id == Phenopacket.head_published_revision_id)
            .outerjoin(owner, owner.id == Phenopacket.draft_owner_id)
            .outerjoin(submission, true())
            .outerjoin(submission_actor, submission_actor.id == submission.c.actor_id)
            .outerjoin(approved, true())
            .where(
                Phenopacket.deleted_at.is_(None),
                Phenopacket.state != "archived",
                effective_state.in_(_QUEUE_STATES),
            )
            .cte("review_queue_base")
        )

    @staticmethod
    def _apply_queue_filters(
        statement: Any,
        base: Any,
        actor: User,
        query: ReviewQueueQuery,
        *,
        include_state: bool,
    ) -> Any:
        """Apply identical visibility/non-state predicates to all queue queries."""
        if include_state:
            statement = statement.where(base.c.effective_state == query.state)
        if query.owner == "mine":
            statement = statement.where(base.c.owner_id == actor.id)
        elif query.owner is not None:
            statement = statement.where(base.c.owner_id == int(query.owner))
        if query.eligibility == "reviewable_by_me":
            statement = statement.where(
                base.c.effective_state.in_(("in_review", "approved")),
                base.c.owner_id.is_not(None),
                base.c.submitter_id.is_not(None),
                base.c.candidate_revision_id.is_not(None),
                base.c.owner_id != actor.id,
                base.c.submitter_id != actor.id,
                base.c.actor_contributed.is_(False),
            )
        if query.issues == "open":
            statement = statement.where(base.c.open_issue_count > 0)
        elif query.issues == "none":
            statement = statement.where(base.c.open_issue_count == 0)
        if query.q:
            pattern = f"%{query.q.strip()}%"
            statement = statement.where(
                or_(
                    base.c.phenopacket_id.ilike(pattern),
                    base.c.subject_label.ilike(pattern),
                )
            )
        return statement

    @staticmethod
    def _queue_order(base: Any, query: ReviewQueueQuery) -> Sequence[Any]:
        """Parse the strict queue-local sort allowlist with a record tie-breaker."""
        allowed = {
            "submitted_at": base.c.submitted_at,
            "phenopacket_id": base.c.phenopacket_id,
            "subject_label": base.c.subject_label,
            "effective_state": base.c.effective_state,
            "change_count": base.c.active_cycle_change_count,
            "open_issue_count": base.c.open_issue_count,
        }
        if not query.sort:
            if query.state == "in_review":
                return (
                    base.c.submitted_at.asc().nullslast(),
                    base.c.record_id.asc(),
                )
            return (
                base.c.submitted_at.desc().nullslast(),
                base.c.record_id.asc(),
            )

        order: list[Any] = []
        for value in query.sort.split(","):
            field = value.strip()
            descending = field.startswith("-")
            name = field[1:] if descending else field
            if name not in allowed:
                raise ValueError(f"invalid review queue sort field: {name}")
            column = allowed[name]
            order.append(column.desc() if descending else column.asc())
        order.append(base.c.record_id.asc())
        return order

    async def list_queue(
        self, actor: User, query: ReviewQueueQuery
    ) -> tuple[list[ReviewQueueRow], int, StateCounts]:
        """Return a filtered page, exact count, and same-filter state facets."""
        base = self._queue_base(actor)
        data_stmt = self._apply_queue_filters(
            select(base), base, actor, query, include_state=True
        )
        data_stmt = (
            data_stmt.order_by(*self._queue_order(base, query))
            .offset((query.page_number - 1) * query.page_size)
            .limit(query.page_size)
        )
        count_stmt = self._apply_queue_filters(
            select(func.count()).select_from(base),
            base,
            actor,
            query,
            include_state=True,
        )
        facets_stmt = self._apply_queue_filters(
            select(base.c.effective_state, func.count()).select_from(base),
            base,
            actor,
            query,
            include_state=False,
        ).group_by(base.c.effective_state)

        raw_rows = (await self.db.execute(data_stmt)).mappings().all()
        total = int((await self.db.execute(count_stmt)).scalar_one())
        facet_rows = (await self.db.execute(facets_stmt)).all()
        counts = {state: 0 for state in _QUEUE_STATES}
        counts.update({str(state): int(count) for state, count in facet_rows})

        rows: list[ReviewQueueRow] = []
        for row in raw_rows:
            effective_state = cast(ReviewState, row.effective_state)
            facts = ReviewPolicyFacts(
                effective_state=effective_state,
                owner_id=row.owner_id,
                submitter_id=row.submitter_id,
                actor_contributed=bool(row.actor_contributed),
                unresolved_count=int(row.open_issue_count),
                candidate_is_active=row.candidate_revision_id is not None,
                authors_known=(
                    row.owner_id is not None and row.submitter_id is not None
                ),
            )
            capabilities = ReviewPolicy.evaluate_facts(actor, facts).actions
            rows.append(
                ReviewQueueRow(
                    record_id=row.record_id,
                    phenopacket_id=row.phenopacket_id,
                    subject_label=row.subject_label,
                    physical_state=row.physical_state,
                    effective_state=effective_state,
                    owner=(
                        ActorSummary(
                            id=row.owner_id,
                            username=row.owner_username,
                            display_name=row.owner_display_name,
                        )
                        if row.owner_id is not None
                        else None
                    ),
                    submitted_by=(
                        ActorSummary(
                            id=row.submitter_id,
                            username=row.submitter_username,
                            display_name=row.submitter_display_name,
                        )
                        if row.submitter_id is not None
                        else None
                    ),
                    submitted_at=row.submitted_at,
                    record_revision=row.record_revision,
                    candidate_revision_id=row.candidate_revision_id,
                    candidate_content_sha256=row.candidate_content_sha256,
                    approved_revision_id=row.approved_revision_id,
                    approved_content_sha256=row.approved_content_sha256,
                    active_cycle_change_count=int(row.active_cycle_change_count),
                    open_issue_count=int(row.open_issue_count),
                    has_published_head=row.head_published_revision_id is not None,
                    capabilities=capabilities,
                )
            )
        return (
            rows,
            total,
            StateCounts(
                draft=counts["draft"],
                in_review=counts["in_review"],
                changes_requested=counts["changes_requested"],
                approved=counts["approved"],
            ),
        )

    async def get_context(self, record_id: str, actor: User) -> ReviewContext | None:
        """Read one coherent review snapshot under a writer-compatible share lock."""
        identity_clause: Any = Phenopacket.phenopacket_id == record_id
        try:
            identity_clause = or_(identity_clause, Phenopacket.id == UUID(record_id))
        except ValueError:
            pass
        record = (
            await self.db.execute(
                select(Phenopacket)
                .where(
                    identity_clause,
                    Phenopacket.deleted_at.is_(None),
                    Phenopacket.state != "archived",
                )
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        if record is None:
            return None

        revision_rows = (
            await self.db.execute(
                select(PhenopacketRevision, User)
                .join(User, User.id == PhenopacketRevision.actor_id)
                .where(PhenopacketRevision.record_id == record.id)
                .order_by(
                    PhenopacketRevision.revision_number.asc(),
                    PhenopacketRevision.id.asc(),
                )
            )
        ).all()
        revisions = [row[0] for row in revision_rows]
        actors_by_revision = {row[0].id: row[1] for row in revision_rows}
        revisions_by_id = {revision.id: revision for revision in revisions}
        active = revisions_by_id.get(record.editing_revision_id)
        head = revisions_by_id.get(record.head_published_revision_id)
        effective_state = cast(
            ReviewState, active.state if active is not None else record.state
        )
        if effective_state not in _QUEUE_STATES:
            return None
        cycle_start = head.revision_number if head is not None else 0
        cycle_revisions = [
            revision for revision in revisions if revision.revision_number > cycle_start
        ]
        submissions = [
            revision for revision in cycle_revisions if revision.state == "in_review"
        ]
        submission = submissions[-1] if submissions else None
        approvals = [
            revision for revision in cycle_revisions if revision.state == "approved"
        ]
        approval = approvals[-1] if approvals else None
        candidate = active if effective_state == "draft" else submission
        if candidate is None:
            return None

        comment_author = aliased(User, name="comment_author")
        resolved_actor = aliased(User, name="resolved_actor")
        comment_rows = (
            await self.db.execute(
                select(Comment, comment_author, resolved_actor)
                .join(comment_author, comment_author.id == Comment.author_id)
                .outerjoin(
                    resolved_actor,
                    resolved_actor.id == Comment.resolved_by_id,
                )
                .where(
                    Comment.record_type == "phenopacket",
                    Comment.record_id == record.id,
                    Comment.deleted_at.is_(None),
                )
                .order_by(Comment.created_at.asc(), Comment.id.asc())
            )
        ).all()
        comments = [row[0] for row in comment_rows]
        authors = {row[0].id: row[1] for row in comment_rows}
        resolved_actors = {
            row[0].id: row[2] for row in comment_rows if row[2] is not None
        }
        comment_ids = [comment.id for comment in comments]
        mentions_by_comment: dict[int, list[User]] = defaultdict(list)
        if comment_ids:
            mention_rows = (
                await self.db.execute(
                    select(CommentMention.comment_id, User)
                    .join(User, User.id == CommentMention.user_id)
                    .where(CommentMention.comment_id.in_(comment_ids))
                    .order_by(CommentMention.comment_id.asc(), User.id.asc())
                )
            ).all()
            for comment_id, mentioned_user in mention_rows:
                mentions_by_comment[comment_id].append(mentioned_user)
            edited_ids = set(
                (
                    await self.db.execute(
                        select(CommentEdit.comment_id)
                        .where(CommentEdit.comment_id.in_(comment_ids))
                        .group_by(CommentEdit.comment_id)
                    )
                ).scalars()
            )
            event_rows = (
                await self.db.execute(
                    select(CommentResolutionEvent, User)
                    .join(User, User.id == CommentResolutionEvent.actor_id)
                    .where(CommentResolutionEvent.comment_id.in_(comment_ids))
                    .order_by(
                        CommentResolutionEvent.created_at.asc(),
                        CommentResolutionEvent.id.asc(),
                    )
                )
            ).all()
        else:
            edited_ids = set()
            event_rows = []
        events_by_comment: dict[int, list[CommentResolutionEventOut]] = defaultdict(
            list
        )
        for event, event_actor in event_rows:
            events_by_comment[event.comment_id].append(
                CommentResolutionEventOut(
                    id=event.id,
                    action=cast(Any, event.action),
                    disposition=cast(Any, event.disposition),
                    rationale=event.rationale,
                    actor_id=event.actor_id,
                    actor_username=event_actor.username,
                    actor_role=cast(Any, event.actor_role),
                    created_at=event.created_at,
                )
            )

        active_revision_ids = {revision.id for revision in cycle_revisions}
        issues = [
            comment
            for comment in comments
            if comment.review_revision_id in active_revision_ids
        ]
        issues.sort(
            key=lambda comment: (
                comment.resolved_at is not None,
                comment.created_at,
                comment.id,
            )
        )
        open_issue_count = sum(issue.resolved_at is None for issue in issues)
        actor_contributed = any(
            revision.actor_id == actor.id and revision.event_type in _CONTENT_EVENTS
            for revision in cycle_revisions
        )
        facts = ReviewPolicyFacts(
            effective_state=effective_state,
            owner_id=record.draft_owner_id,
            submitter_id=submission.actor_id if submission is not None else None,
            actor_contributed=actor_contributed,
            unresolved_count=open_issue_count,
            candidate_is_active=active is not None,
            authors_known=(
                record.draft_owner_id is not None and submission is not None
            ),
        )
        context_capabilities = [
            ReviewPolicy.issue_capability_from_facts(
                actor, facts, action="create_issue"
            ),
            *ReviewPolicy.evaluate_facts(actor, facts).actions,
        ]
        issue_dtos: list[ReviewIssue] = []
        user_by_id = {user.id: user for _revision, user in revision_rows}
        user_by_id.update({user.id: user for user in authors.values()})
        for issue in issues:
            issue_revision_id = cast(int, issue.review_revision_id)
            issue_revision = revisions_by_id.get(issue_revision_id)
            issue_facts = ReviewPolicyFacts(
                effective_state=effective_state,
                owner_id=record.draft_owner_id,
                submitter_id=(
                    issue_revision.actor_id if issue_revision is not None else None
                ),
                actor_contributed=actor_contributed,
                unresolved_count=open_issue_count,
                candidate_is_active=issue_revision is not None,
                authors_known=(
                    record.draft_owner_id is not None and issue_revision is not None
                ),
            )
            action: Literal["resolve", "reopen"] = (
                "resolve" if issue.resolved_at is None else "reopen"
            )
            capability = ReviewPolicy.issue_capability_from_facts(
                actor,
                issue_facts,
                action=action,
                issue_is_current=issue_revision_id in active_revision_ids,
            )
            resolved_by = resolved_actors.get(issue.id)
            issue_author = authors[issue.id]
            issue_dtos.append(
                ReviewIssue(
                    id=issue.id,
                    record_type=issue.record_type,
                    record_id=str(issue.record_id),
                    author_id=issue.author_id,
                    author_username=issue_author.username,
                    author_display_name=issue_author.full_name,
                    body_markdown=issue.body_markdown,
                    mentions=[
                        CommentMentionOut(
                            user_id=user.id,
                            username=user.username,
                            display_name=user.full_name,
                            is_active=user.is_active,
                        )
                        for user in mentions_by_comment[issue.id]
                    ],
                    edited=issue.id in edited_ids,
                    resolved_at=issue.resolved_at,
                    resolved_by_id=issue.resolved_by_id,
                    resolved_by_username=(
                        resolved_by.username if resolved_by is not None else None
                    ),
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    deleted_at=issue.deleted_at,
                    deleted_by_id=issue.deleted_by_id,
                    review_revision_id=issue.review_revision_id,
                    is_blocking_issue=True,
                    resolution_events=events_by_comment[issue.id],
                    capabilities=[capability],
                )
            )

        owner = user_by_id.get(record.draft_owner_id)
        contributors: list[ActorSummary] = []
        seen_contributors: set[int] = set()
        for revision in cycle_revisions:
            if (
                revision.event_type not in _CONTENT_EVENTS
                or revision.actor_id in seen_contributors
            ):
                continue
            contributor = actors_by_revision[revision.id]
            seen_contributors.add(contributor.id)
            contributor_summary = _actor_summary(contributor)
            if contributor_summary is not None:
                contributors.append(contributor_summary)

        def revision_summary(
            revision: PhenopacketRevision | None,
        ) -> ReviewRevisionSummary | None:
            if revision is None:
                return None
            return ReviewRevisionSummary(
                id=revision.id,
                revision_number=revision.revision_number,
                state=revision.state,
                content_sha256=revision.content_sha256,
                created_at=revision.created_at,
                actor=cast(
                    ActorSummary, _actor_summary(actors_by_revision[revision.id])
                ),
            )

        def snapshot(revision: PhenopacketRevision | None) -> ReviewRevision | None:
            summary = revision_summary(revision)
            if revision is None or summary is None:
                return None
            return ReviewRevision(
                **summary.model_dump(), content=revision.content_jsonb
            )

        candidate_snapshot = snapshot(candidate)
        assert candidate_snapshot is not None
        baseline_snapshot = snapshot(head)
        approved_snapshot = snapshot(approval)
        candidate_content = candidate.content_jsonb
        baseline_content = head.content_jsonb if head is not None else None
        subject = candidate_content.get("subject", {})
        subject_label = subject.get("label") or subject.get("id")
        subject_label = subject_label or record.phenopacket_id
        return ReviewContext(
            record_id=record.id,
            phenopacket_id=record.phenopacket_id,
            subject_label=str(subject_label),
            physical_state=record.state,
            effective_state=effective_state,
            record_revision=record.revision,
            has_published_head=head is not None,
            owner=_actor_summary(owner),
            candidate=candidate_snapshot,
            baseline=baseline_snapshot,
            approved=approved_snapshot,
            semantic_changes=ReviewService.semantic_changes(
                baseline_content, candidate_content
            ),
            audit=ReviewAudit(
                owner=_actor_summary(owner),
                submission=revision_summary(submission),
                contributors=contributors,
                approval=revision_summary(approval),
                publication=revision_summary(head),
            ),
            discussion_summary=DiscussionSummary(
                total_comments=len(comments),
                ordinary_comments=sum(
                    comment.review_revision_id is None for comment in comments
                ),
                blocking_issues=len(issues),
                open_blocking_issues=open_issue_count,
            ),
            issues=issue_dtos,
            capabilities=context_capabilities,
        )
