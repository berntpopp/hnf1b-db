"""Two-connection PostgreSQL races for issue gating and approval."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.comments.models import Comment, CommentResolutionEvent
from app.comments.service import CommentsService
from app.database import engine
from app.phenopackets.models import Phenopacket, PhenopacketRevision


async def _seed_candidate(db_session, owner, submitter):
    packet = Phenopacket(
        phenopacket_id="sql-race",
        phenopacket={"id": "sql-race"},
        state="draft",
        revision=0,
        draft_owner_id=owner.id,
        created_by_id=owner.id,
    )
    db_session.add(packet)
    await db_session.flush()
    root = PhenopacketRevision(
        record_id=packet.id,
        revision_number=1,
        state="draft",
        content_jsonb=packet.phenopacket,
        change_reason="create",
        actor_id=owner.id,
        from_state=None,
        to_state="draft",
        event_type="created",
    )
    db_session.add(root)
    await db_session.flush()
    candidate = PhenopacketRevision(
        record_id=packet.id,
        parent_revision_id=root.id,
        revision_number=2,
        state="in_review",
        content_jsonb=packet.phenopacket,
        change_reason="submit",
        actor_id=submitter.id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(candidate)
    await db_session.flush()
    packet.state = "in_review"
    packet.revision = 2
    packet.editing_revision_id = candidate.id
    await db_session.commit()
    return packet.id, candidate.id


async def _insert_issue(connection, record_id, candidate_id, actor_id):
    return await connection.scalar(
        text(
            """
            INSERT INTO comments
                (record_type, record_id, author_id, body_markdown,
                 review_revision_id)
            VALUES ('phenopacket', :record_id, :actor_id, 'race issue', :candidate_id)
            RETURNING id
            """
        ),
        {"record_id": record_id, "candidate_id": candidate_id, "actor_id": actor_id},
    )


async def _approve(connection, record_id, candidate_id, actor_id):
    approved_id = await connection.scalar(
        text(
            """
            INSERT INTO phenopacket_revisions
                (record_id, parent_revision_id, revision_number, state,
                 content_jsonb, change_reason, actor_id, actor_role,
                 from_state, to_state, event_type)
            VALUES (:record_id, :candidate_id, 3, 'approved',
                    '{"id":"sql-race"}'::jsonb, 'approve', :actor_id,
                    'curator', 'in_review', 'approved', 'state_transition')
            RETURNING id
            """
        ),
        {"record_id": record_id, "candidate_id": candidate_id, "actor_id": actor_id},
    )
    await connection.execute(
        text(
            """
            UPDATE phenopackets
            SET state='approved', revision=3, editing_revision_id=:approved_id
            WHERE id=:record_id
            """
        ),
        {"approved_id": approved_id, "record_id": record_id},
    )
    return approved_id


async def _reopen(connection, issue_id, actor_id):
    await connection.execute(
        text(
            """
            INSERT INTO comment_resolution_events
                (comment_id, action, disposition, rationale, actor_id, actor_role)
            VALUES (:issue_id, 'reopened', NULL, 'race reopen', :actor_id, 'curator')
            """
        ),
        {"issue_id": issue_id, "actor_id": actor_id},
    )
    await connection.execute(
        text(
            """
            UPDATE comments SET resolved_at=NULL, resolved_by_id=NULL
            WHERE id=:issue_id
            """
        ),
        {"issue_id": issue_id},
    )


async def _wait_until_blocked(observer, winner_pid: int, loser_pid: int) -> None:
    """Poll lock metadata through yielding SQL calls; no time-based sleeps."""
    for _ in range(200):
        blockers = await observer.scalar(
            text("SELECT pg_blocking_pids(:loser_pid)"), {"loser_pid": loser_pid}
        )
        if winner_pid in blockers:
            return
    raise AssertionError(
        f"backend {loser_pid} never blocked behind expected winner {winner_pid}"
    )


async def _race(
    db_session,
    owner,
    reviewer,
    *,
    issue_operation: str,
    issue_wins: bool,
) -> None:
    record_id, candidate_id = await _seed_candidate(db_session, owner, owner)
    issue_id = None
    if issue_operation == "reopen":
        service = CommentsService(db_session)
        issue = await service.create(
            record_type="phenopacket",
            record_id=record_id,
            body_markdown="resolved seed",
            mention_user_ids=[],
            actor=reviewer,
            record_revision=2,
            review_revision_id=candidate_id,
        )
        issue = await service.resolve(
            comment_id=issue.id,
            actor=reviewer,
            issue_input={
                "record_revision": 2,
                "disposition": "addressed",
                "rationale": "seed resolution",
            },
        )
        issue_id = issue.id
        await db_session.commit()

    async with (
        engine.connect() as issue_conn,
        engine.connect() as approval_conn,
        engine.connect() as observer,
    ):
        issue_tx = await issue_conn.begin()
        approval_tx = await approval_conn.begin()
        issue_pid = int(await issue_conn.scalar(text("SELECT pg_backend_pid()")))
        approval_pid = int(await approval_conn.scalar(text("SELECT pg_backend_pid()")))
        loser_started = asyncio.Event()
        try:

            async def issue_statement():
                loser_started.set()
                if issue_operation == "insert":
                    return await _insert_issue(
                        issue_conn, record_id, candidate_id, reviewer.id
                    )
                assert issue_id is not None
                await _reopen(issue_conn, issue_id, reviewer.id)
                return issue_id

            async def approval_statement():
                loser_started.set()
                return await _approve(
                    approval_conn, record_id, candidate_id, reviewer.id
                )

            if issue_wins:
                if issue_operation == "insert":
                    issue_id = await _insert_issue(
                        issue_conn, record_id, candidate_id, reviewer.id
                    )
                else:
                    assert issue_id is not None
                    await _reopen(issue_conn, issue_id, reviewer.id)
                loser_task = asyncio.create_task(approval_statement())
                await asyncio.wait_for(loser_started.wait(), timeout=5)
                await asyncio.wait_for(
                    _wait_until_blocked(observer, issue_pid, approval_pid), timeout=5
                )
                await issue_tx.commit()
                with pytest.raises(DBAPIError, match="unresolved_review_issues"):
                    await asyncio.wait_for(loser_task, timeout=5)
                await approval_tx.rollback()
            else:
                approved_id = await _approve(
                    approval_conn, record_id, candidate_id, reviewer.id
                )
                loser_task = asyncio.create_task(issue_statement())
                await asyncio.wait_for(loser_started.wait(), timeout=5)
                await asyncio.wait_for(
                    _wait_until_blocked(observer, approval_pid, issue_pid), timeout=5
                )
                await approval_tx.commit()
                with pytest.raises(DBAPIError, match="review_closed"):
                    await asyncio.wait_for(loser_task, timeout=5)
                await issue_tx.rollback()
                assert approved_id is not None
        finally:
            if issue_tx.is_active:
                await issue_tx.rollback()
            if approval_tx.is_active:
                await approval_tx.rollback()

    db_session.expire_all()
    packet = await db_session.get(Phenopacket, record_id)
    assert packet is not None
    issue_count = int(
        await db_session.scalar(
            select(func.count(Comment.id)).where(Comment.record_id == record_id)
        )
    )
    if issue_wins:
        assert packet.editing_revision_id == candidate_id
        assert issue_count == 1
        assert (
            await db_session.scalar(
                select(Comment.resolved_at).where(Comment.record_id == record_id)
            )
            is None
        )
    else:
        assert packet.editing_revision_id != candidate_id
        if issue_operation == "insert":
            assert issue_count == 0
        else:
            assert issue_count == 1
            assert (
                await db_session.scalar(
                    select(Comment.resolved_at).where(Comment.id == issue_id)
                )
                is not None
            )
            reopen_events = int(
                await db_session.scalar(
                    select(func.count(CommentResolutionEvent.id)).where(
                        CommentResolutionEvent.comment_id == issue_id,
                        CommentResolutionEvent.action == "reopened",
                    )
                )
            )
            assert reopen_events == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("issue_operation", "issue_wins"),
    [
        ("insert", True),
        ("insert", False),
        ("reopen", True),
        ("reopen", False),
    ],
    ids=[
        "issue-insert-wins-approval-loses",
        "approval-wins-issue-insert-loses",
        "issue-reopen-wins-approval-loses",
        "approval-wins-issue-reopen-loses",
    ],
)
async def test_review_issue_approval_races_commit_one_consistent_winner(
    db_session, curator_user, another_curator, issue_operation, issue_wins
):
    await _race(
        db_session,
        curator_user,
        another_curator,
        issue_operation=issue_operation,
        issue_wins=issue_wins,
    )
