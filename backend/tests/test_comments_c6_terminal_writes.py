"""C6 — soft-deleted comments are terminal for writes (all mutations → 404)."""
import pytest


async def _seed_comment(client, headers, record_id):
    resp = await client.post(
        "/api/v2/comments",
        json={
            "record_type": "phenopacket",
            "record_id": str(record_id),
            "body_markdown": "x",
            "mention_user_ids": [],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path_tpl,body",
    [
        ("PATCH", "/api/v2/comments/{id}", {"body_markdown": "x", "mention_user_ids": []}),
        ("POST", "/api/v2/comments/{id}/resolve", None),
        ("POST", "/api/v2/comments/{id}/unresolve", None),
        ("DELETE", "/api/v2/comments/{id}", None),
    ],
)
async def test_soft_deleted_writes_404(
    async_client, curator_headers, published_record, method, path_tpl, body
):
    comment = await _seed_comment(async_client, curator_headers, published_record.id)
    cid = comment["id"]

    # Soft-delete via curator (author)
    del_resp = await async_client.delete(
        f"/api/v2/comments/{cid}",
        headers=curator_headers,
    )
    assert del_resp.status_code == 204

    url = path_tpl.format(id=cid)
    resp = await async_client.request(
        method, url, json=body, headers=curator_headers
    )
    assert resp.status_code == 404, (
        f"{method} {url} returned {resp.status_code}: {resp.json()}"
    )
