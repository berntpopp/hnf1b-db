"""Permissions matrix enforcement (D.2 §5.2).

Four roles × representative CRUD actions. Viewers are blocked everywhere.
Curators can author/edit their own; admins can delete anyone's, not edit.
"""
import pytest


async def _post_comment(client, headers, record_id, body="hello"):
    return await client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(record_id),
            "body_markdown": body,
            "mention_user_ids": [],
        },
        headers=headers,
    )


@pytest.mark.asyncio
async def test_create_viewer_forbidden(async_client, viewer_headers, published_record):
    resp = await _post_comment(async_client, viewer_headers, published_record.id)
    # viewer role should be denied — 403 from require_curator guard
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_curator_201(async_client, curator_headers, published_record):
    resp = await _post_comment(async_client, curator_headers, published_record.id)
    assert resp.status_code == 201, resp.json()


@pytest.mark.asyncio
async def test_create_admin_201(async_client, admin_headers, published_record):
    resp = await _post_comment(async_client, admin_headers, published_record.id)
    assert resp.status_code == 201, resp.json()


@pytest.mark.asyncio
async def test_list_viewer_forbidden(async_client, viewer_headers, published_record):
    resp = await async_client.get(
        "/api/v2/comments",
        params={
            "filter[record_type]": "phenopacket",
            "filter[record_id]": str(published_record.id),
        },
        headers=viewer_headers,
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_patch_admin_not_author_forbidden(
    async_client, curator_headers, admin_headers, published_record
):
    # curator creates
    created = await _post_comment(async_client, curator_headers, published_record.id, body="orig")
    assert created.status_code == 201
    cid = created.json()["id"]
    # admin tries to edit another user's comment — matrix forbids admin body edits
    resp = await async_client.patch(
        f"/api/v2/comments/{cid}",
        json={"body_markdown": "haxx", "mention_user_ids": []},
        headers=admin_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_author_succeeds(
    async_client, curator_headers, published_record
):
    created = await _post_comment(async_client, curator_headers, published_record.id, body="orig")
    cid = created.json()["id"]
    resp = await async_client.patch(
        f"/api/v2/comments/{cid}",
        json={"body_markdown": "revised", "mention_user_ids": []},
        headers=curator_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["body_markdown"] == "revised"


@pytest.mark.asyncio
async def test_delete_admin_can_delete_others(
    async_client, curator_headers, admin_headers, published_record
):
    created = await _post_comment(async_client, curator_headers, published_record.id)
    cid = created.json()["id"]
    resp = await async_client.delete(
        f"/api/v2/comments/{cid}",
        headers=admin_headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_resolve_curator_can_resolve_own(
    async_client, curator_headers, published_record
):
    created = await _post_comment(async_client, curator_headers, published_record.id)
    cid = created.json()["id"]
    resp = await async_client.post(
        f"/api/v2/comments/{cid}/resolve",
        headers=curator_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_edits_viewer_forbidden(
    async_client, curator_headers, viewer_headers, published_record
):
    created = await _post_comment(async_client, curator_headers, published_record.id)
    cid = created.json()["id"]
    resp = await async_client.get(
        f"/api/v2/comments/{cid}/edits",
        headers=viewer_headers,
    )
    assert resp.status_code in (401, 403)
