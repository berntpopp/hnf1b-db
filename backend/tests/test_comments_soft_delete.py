"""?include=deleted read semantics for soft-deleted comments."""

import pytest


async def _seed_comment(client, headers, record_id, body="x"):
    resp = await client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(record_id),
            "body_markdown": body,
            "mention_user_ids": [],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_soft_deleted_hidden_by_default(
    async_client, curator_headers, published_record
):
    comment = await _seed_comment(async_client, curator_headers, published_record.id)
    cid = comment["id"]

    # Soft-delete
    del_resp = await async_client.delete(
        f"/api/v2/comments/{cid}",
        headers=curator_headers,
    )
    assert del_resp.status_code == 204

    # List without include — soft-deleted comment must not appear
    resp = await async_client.get(
        "/api/v2/comments",
        params={
            "filter[record_type]": "phenopacket",
            "filter[record_id]": str(published_record.id),
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["data"]]
    assert cid not in ids

    # Detail without include → 404
    detail = await async_client.get(
        f"/api/v2/comments/{cid}",
        headers=curator_headers,
    )
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_include_deleted_returns_full_body(
    async_client, curator_headers, published_record
):
    comment = await _seed_comment(
        async_client, curator_headers, published_record.id, body="visible"
    )
    cid = comment["id"]

    await async_client.delete(
        f"/api/v2/comments/{cid}",
        headers=curator_headers,
    )

    detail = await async_client.get(
        f"/api/v2/comments/{cid}",
        params={"include": "deleted"},
        headers=curator_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["body_markdown"] == "visible"
    assert detail.json()["deleted_at"] is not None
