"""Comments router smoke test. Full permissions matrix lands in Task 32."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_post_comment_201(async_client, curator_headers, published_record):
    resp = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(published_record.id),
            "body_markdown": "hello",
            "mention_user_ids": [],
        },
        headers=curator_headers,
    )
    assert resp.status_code == 201, resp.json()


@pytest.mark.asyncio
async def test_mutation_router_commits_once_on_success(
    monkeypatch, async_client, db_session, curator_headers, published_record
):
    """A successful mutation commits exactly once after response construction."""
    commit = AsyncMock(wraps=db_session.commit)
    monkeypatch.setattr(db_session, "commit", commit)

    response = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(published_record.id),
            "body_markdown": "router transaction",
            "mention_user_ids": [],
        },
        headers=curator_headers,
    )

    assert response.status_code == 201, response.json()
    assert commit.await_count == 1


@pytest.mark.asyncio
async def test_mutation_router_rolls_back_domain_failure(
    monkeypatch, async_client, db_session, curator_headers, published_record
):
    """Every caught service/domain failure explicitly rolls back the session."""
    rollback = AsyncMock(wraps=db_session.rollback)
    monkeypatch.setattr(db_session, "rollback", rollback)

    response = await async_client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(published_record.id),
            "body_markdown": "stale issue",
            "mention_user_ids": [],
            "record_revision": published_record.revision - 1,
            "review_revision_id": 999999,
        },
        headers=curator_headers,
    )

    assert response.status_code == 409
    assert rollback.await_count == 1
