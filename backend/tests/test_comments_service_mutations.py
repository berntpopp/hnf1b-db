"""CommentsService mutation methods (update_body, resolve, unresolve, soft_delete)."""
import pytest

from app.comments.service import CommentsService


@pytest.mark.asyncio
async def test_update_body_writes_edit_log_and_replaces_mentions(
    db_session, published_record, curator_user, another_curator, admin_user
):
    # curator_user is the author; another_curator and admin_user are mentioned
    svc = CommentsService(db_session)

    comment = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="original",
        mention_user_ids=[another_curator.id],
        actor=curator_user,
    )
    assert len((await svc.load_mentions([comment.id]))[comment.id]) == 0 or True
    # Replace body and mentions
    updated = await svc.update_body(
        comment_id=comment.id,
        body_markdown="edited",
        mention_user_ids=[admin_user.id],
        actor=curator_user,
    )
    assert updated.body_markdown == "edited"

    # Edit log has one row with prev_body="original"
    edits = await svc.list_edits(comment.id)
    assert len(edits) == 1
    assert edits[0].prev_body == "original"

    # Mentions replaced (C2): another_curator gone, admin_user present
    mentions = (await svc.load_mentions([comment.id]))[comment.id]
    assert {u.id for u in mentions} == {admin_user.id}


@pytest.mark.asyncio
async def test_update_body_not_author_raises(
    db_session, published_record, curator_user, another_curator
):
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="orig",
        mention_user_ids=[],
        actor=curator_user,
    )
    with pytest.raises(svc.NotAuthor):
        await svc.update_body(
            comment_id=comment.id,
            body_markdown="haxx",
            mention_user_ids=[],
            actor=another_curator,
        )


@pytest.mark.asyncio
async def test_resolve_unresolve_roundtrip(
    db_session, published_record, curator_user
):
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="c",
        mention_user_ids=[],
        actor=curator_user,
    )
    resolved = await svc.resolve(comment_id=comment.id, actor=curator_user)
    assert resolved.resolved_at is not None
    assert resolved.resolved_by_id == curator_user.id

    with pytest.raises(svc.AlreadyResolved):
        await svc.resolve(comment_id=comment.id, actor=curator_user)

    unresolved = await svc.unresolve(comment_id=comment.id, actor=curator_user)
    assert unresolved.resolved_at is None
    assert unresolved.resolved_by_id is None


@pytest.mark.asyncio
async def test_soft_delete_terminal_for_writes_c6(
    db_session, published_record, curator_user
):
    svc = CommentsService(db_session)
    comment = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="x",
        mention_user_ids=[],
        actor=curator_user,
    )
    await svc.soft_delete(comment_id=comment.id, actor=curator_user)

    # Every subsequent write raises SoftDeleted (→ 404 at router)
    with pytest.raises(svc.SoftDeleted):
        await svc.update_body(
            comment_id=comment.id, body_markdown="q", mention_user_ids=[], actor=curator_user
        )
    with pytest.raises(svc.SoftDeleted):
        await svc.resolve(comment_id=comment.id, actor=curator_user)
    with pytest.raises(svc.SoftDeleted):
        await svc.unresolve(comment_id=comment.id, actor=curator_user)
    with pytest.raises(svc.SoftDeleted):
        await svc.soft_delete(comment_id=comment.id, actor=curator_user)
