"""C2 — mentions row-set equals latest submission after N edits.

Each call to update_body replaces (not appends to) the comment_mentions
rows atomically. After any sequence of edits the live mention set must equal
exactly the mention_user_ids from the most recent update_body call.

Spec reference:
  docs/superpowers/specs/
  2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.2 C2.
"""

import pytest


@pytest.mark.asyncio
async def test_mentions_replaced_atomically(
    db_session, published_record, curator_user, admin_user, another_curator
):
    """C2: mention set equals the latest submission after N edits."""
    from app.comments.service import CommentsService

    svc = CommentsService(db_session)

    # Create with two mentions: another_curator + admin_user
    c = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="m1",
        mention_user_ids=[another_curator.id, admin_user.id],
        actor=curator_user,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert {u.id for u in mentions} == {another_curator.id, admin_user.id}

    # Edit 1 — reduce to one mention
    await svc.update_body(
        comment_id=c.id,
        body_markdown="m2",
        mention_user_ids=[admin_user.id],
        actor=curator_user,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert {u.id for u in mentions} == {admin_user.id}, (
        "C2: old mention should have been removed by replace"
    )

    # Edit 2 — clear all mentions
    await svc.update_body(
        comment_id=c.id,
        body_markdown="m3",
        mention_user_ids=[],
        actor=curator_user,
    )
    mentions = (await svc.load_mentions([c.id]))[c.id]
    assert mentions == [], (
        "C2: all mentions should have been cleared by replace with empty list"
    )
