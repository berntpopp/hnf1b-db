"""HTTP-level integration tests for the transitions and revisions endpoints.

Wave 7 D.1 Task 10.

Endpoints tested:
- POST /api/v2/phenopackets/{id}/transitions
- GET  /api/v2/phenopackets/{id}/revisions
- GET  /api/v2/phenopackets/{id}/revisions/{revision_id}

All tests use a real DB (no mocks).  Fixtures are defined in
``conftest.py`` (async_client, curator_user, admin_user, viewer_user,
curator_headers, admin_headers, viewer_headers, draft_record,
published_record).
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pp_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}"


def _transitions_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}/transitions"


def _revisions_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}/revisions"


def _revision_detail_url(phenopacket_id: str, revision_id: int) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}/revisions/{revision_id}"


# ---------------------------------------------------------------------------
# POST /transitions — end-to-end lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_endpoint_end_to_end(
    async_client,
    db_session,
    curator_user,
    admin_user,
    curator_headers,
    admin_headers,
    draft_record,
):
    """Curator submits → admin approves → admin publishes; verifies state
    progression and head_published_revision_id set after publish.
    """
    pid = draft_record.phenopacket_id
    rev = draft_record.revision  # 1

    # Step 1: curator submits draft → in_review
    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "ready for review", "revision": rev},
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phenopacket"]["state"] == "in_review"
    rev = data["phenopacket"]["revision"]

    # Step 2: admin approves in_review → approved
    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "approved", "reason": "looks good", "revision": rev},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phenopacket"]["state"] == "approved"
    rev = data["phenopacket"]["revision"]

    # Step 3: admin publishes approved → published
    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "published", "reason": "go live", "revision": rev},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phenopacket"]["state"] == "published"
    assert data["phenopacket"]["head_published_revision_id"] is not None
    assert data["revision"]["to_state"] == "published"
    assert data["revision"]["is_head_published"] is True


@pytest.mark.asyncio
async def test_transition_forbidden_role_returns_403(
    async_client, draft_record, curator_user, curator_headers
):
    """Curator trying an admin-only transition gets 403 with forbidden_role code."""
    pid = draft_record.phenopacket_id

    # First get to in_review
    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "submit", "revision": 1},
        headers=curator_headers,
    )
    assert resp.status_code == 200

    # Now curator tries to approve (admin-only)
    resp = await async_client.post(
        _transitions_url(pid),
        json={
            "to_state": "approved",
            "reason": "self-approve",
            "revision": resp.json()["phenopacket"]["revision"],
        },
        headers=curator_headers,
    )
    assert resp.status_code == 403
    body = resp.json()
    # The error envelope wraps detail: body["detail"]["code"]
    assert body["detail"]["code"] == "forbidden_role"


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(
    async_client, draft_record, admin_headers
):
    """Admin trying draft → published directly gets 409 invalid_transition."""
    pid = draft_record.phenopacket_id

    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "published", "reason": "skip steps", "revision": 1},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "invalid_transition"


@pytest.mark.asyncio
async def test_transition_revision_mismatch_returns_409(
    async_client, draft_record, curator_headers
):
    """Stale revision in transition body returns 409 revision_mismatch."""
    pid = draft_record.phenopacket_id

    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "submit", "revision": 999},
        headers=curator_headers,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "revision_mismatch"


# ---------------------------------------------------------------------------
# GET /revisions — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revisions_list_curator_only(
    async_client,
    draft_record,
    curator_user,
    admin_user,
    curator_headers,
    admin_headers,
    viewer_headers,
):
    """Curator and admin get 200; viewer gets 404."""
    pid = draft_record.phenopacket_id

    # Create a revision first (submit → in_review)
    r = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "go", "revision": 1},
        headers=curator_headers,
    )
    assert r.status_code == 200

    # curator: 200
    resp = await async_client.get(_revisions_url(pid), headers=curator_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert body["meta"]["total"] >= 1

    # admin: 200
    resp = await async_client.get(_revisions_url(pid), headers=admin_headers)
    assert resp.status_code == 200

    # viewer: 404 (spec §7.2: non-curator gets 404)
    resp = await async_client.get(_revisions_url(pid), headers=viewer_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revisions_list_omits_content(
    async_client, draft_record, curator_headers
):
    """GET /revisions list does NOT include content_jsonb in each item."""
    pid = draft_record.phenopacket_id

    # Create at least one revision
    await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "go", "revision": 1},
        headers=curator_headers,
    )

    resp = await async_client.get(_revisions_url(pid), headers=curator_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    for item in data:
        assert "content_jsonb" not in item or item["content_jsonb"] is None


# ---------------------------------------------------------------------------
# GET /revisions/{revision_id} — detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revision_detail_includes_content(
    async_client, draft_record, curator_headers
):
    """GET /{revision_id} returns content_jsonb populated."""
    pid = draft_record.phenopacket_id

    # Create a revision
    tr = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "submit", "revision": 1},
        headers=curator_headers,
    )
    assert tr.status_code == 200
    revision_id = tr.json()["revision"]["id"]

    resp = await async_client.get(
        _revision_detail_url(pid, revision_id), headers=curator_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == revision_id
    assert body["content_jsonb"] is not None
    assert isinstance(body["content_jsonb"], dict)
