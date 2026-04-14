"""Comments router smoke test. Full permissions matrix lands in Task 32."""
import pytest


@pytest.mark.asyncio
async def test_post_comment_201(
    async_client, curator_headers, published_record
):
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
