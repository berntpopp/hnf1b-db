"""CommentsService.create happy path and C3 (record integrity)."""

import pytest

from app.comments.service import CommentsService


@pytest.mark.asyncio
async def test_create_happy_path(db_session, published_record, curator_user):
    svc = CommentsService(db_session)

    comment = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="Looks good",
        mention_user_ids=[],
        actor=curator_user,
    )
    assert comment.id is not None
    assert comment.body_markdown == "Looks good"
    assert comment.author_id == curator_user.id
    assert comment.deleted_at is None


@pytest.mark.asyncio
async def test_create_c3_record_not_found(db_session, curator_user):
    import uuid

    svc = CommentsService(db_session)
    with pytest.raises(svc.RecordNotFound):
        await svc.create(
            record_type="phenopacket",
            record_id=uuid.uuid4(),
            body_markdown="orphan",
            mention_user_ids=[],
            actor=curator_user,
        )


@pytest.mark.asyncio
async def test_create_mention_unknown_user_raises(
    db_session, published_record, curator_user
):
    svc = CommentsService(db_session)
    with pytest.raises(svc.MentionUnknownUser):
        await svc.create(
            record_type="phenopacket",
            record_id=published_record.id,
            body_markdown="@phantom",
            mention_user_ids=[999999],
            actor=curator_user,
        )
