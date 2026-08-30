"""Comments router smoke test. Full permissions matrix lands in Task 32."""

from unittest.mock import AsyncMock

import pytest

from app.comments.service import CommentsService


def _assert_error_envelope(response, status_code: int, error_code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"detail", "error_code", "request_id"}
    assert body["error_code"] == error_code
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


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
    body = resp.json()
    assert body["review_revision_id"] is None
    assert body["is_blocking_issue"] is False
    assert body["resolution_events"] == []


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


@pytest.mark.asyncio
async def test_post_comment_runtime_errors_use_exact_shared_envelope(
    monkeypatch,
    async_client,
    curator_headers,
    viewer_headers,
    published_record,
):
    """Every documented create failure is emitted by the shared runtime handler."""
    payload = {
        "record_type": "phenopacket",
        "record_id": str(published_record.id),
        "body_markdown": "Envelope contract",
        "mention_user_ids": [],
    }

    unauthenticated = await async_client.post("/api/v2/comments", json=payload)
    _assert_error_envelope(unauthenticated, 401, "http_401")

    forbidden = await async_client.post(
        "/api/v2/comments", json=payload, headers=viewer_headers
    )
    _assert_error_envelope(forbidden, 403, "http_403")

    invalid = await async_client.post(
        "/api/v2/comments", json={}, headers=curator_headers
    )
    _assert_error_envelope(invalid, 422, "validation_error")

    create = AsyncMock(
        side_effect=[
            CommentsService.RecordNotFound("Record missing"),
            CommentsService.RevisionMismatch("Revision changed"),
            RuntimeError("private database detail"),
        ]
    )
    monkeypatch.setattr(CommentsService, "create", create)

    not_found = await async_client.post(
        "/api/v2/comments", json=payload, headers=curator_headers
    )
    not_found_body = _assert_error_envelope(not_found, 404, "http_404")
    assert not_found_body["detail"]["code"] == "record_not_found"

    conflict = await async_client.post(
        "/api/v2/comments", json=payload, headers=curator_headers
    )
    conflict_body = _assert_error_envelope(conflict, 409, "http_409")
    assert conflict_body["detail"]["code"] == "revision_mismatch"

    internal = await async_client.post(
        "/api/v2/comments", json=payload, headers=curator_headers
    )
    internal_body = _assert_error_envelope(internal, 500, "http_500")
    assert internal_body["detail"] == {
        "code": "internal_error",
        "message": "Internal server error",
    }
    assert "private database detail" not in internal.text
