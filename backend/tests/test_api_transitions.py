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
    candidate = data["revision"]
    assert candidate["actor_role"] == "curator"
    assert candidate["actor_role_at_decision_recorded"] is True
    assert candidate["decision_metadata"] is None
    assert candidate["content_sha256"].startswith("sha256:")
    assert candidate["ledger_version"] == 2
    rev = data["phenopacket"]["revision"]

    # Step 2: admin approves in_review → approved
    resp = await async_client.post(
        _transitions_url(pid),
        json={
            "to_state": "approved",
            "reason": "looks good",
            "revision": rev,
            "candidate_revision_id": candidate["id"],
            "candidate_content_sha256": candidate["content_sha256"],
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": True,
            },
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phenopacket"]["state"] == "approved"
    approved = data["revision"]
    rev = data["phenopacket"]["revision"]

    # Step 3: admin publishes approved → published
    resp = await async_client.post(
        _transitions_url(pid),
        json={
            "to_state": "published",
            "reason": "go live",
            "revision": rev,
            "approved_revision_id": approved["id"],
            "approved_content_sha256": approved["content_sha256"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phenopacket"]["state"] == "published"
    assert data["phenopacket"]["head_published_revision_id"] is not None
    assert data["revision"]["to_state"] == "published"
    assert data["revision"]["is_head_published"] is True


@pytest.mark.asyncio
async def test_transition_self_review_returns_specific_403(
    async_client, draft_record, curator_user, curator_headers
):
    """A submitting curator receives the specific independence blocker code."""
    pid = draft_record.phenopacket_id

    # First get to in_review
    resp = await async_client.post(
        _transitions_url(pid),
        json={"to_state": "in_review", "reason": "submit", "revision": 1},
        headers=curator_headers,
    )
    assert resp.status_code == 200
    candidate = resp.json()["revision"]

    # Now curator tries to approve (admin-only)
    resp = await async_client.post(
        _transitions_url(pid),
        json={
            "to_state": "approved",
            "reason": "self-approve",
            "revision": resp.json()["phenopacket"]["revision"],
            "candidate_revision_id": candidate["id"],
            "candidate_content_sha256": candidate["content_sha256"],
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": True,
            },
        },
        headers=curator_headers,
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "self_review_forbidden"


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(
    async_client, draft_record, admin_headers
):
    """Admin trying draft → published directly gets 409 invalid_transition."""
    pid = draft_record.phenopacket_id

    resp = await async_client.post(
        _transitions_url(pid),
        json={
            "to_state": "published",
            "reason": "skip steps",
            "revision": 1,
            "approved_revision_id": 999,
            "approved_content_sha256": "sha256:" + "0" * 64,
        },
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"to_state": "approved"},
        {
            "to_state": "approved",
            "candidate_revision_id": 1,
            "candidate_content_sha256": "sha256:" + "1" * 64,
        },
        {
            "to_state": "approved",
            "candidate_revision_id": 1,
            "candidate_content_sha256": "sha256:" + "1" * 64,
            "attestation": {
                "independent_review": False,
                "no_unmanaged_conflict": True,
            },
        },
        {
            "to_state": "approved",
            "candidate_revision_id": 1,
            "candidate_content_sha256": "sha256:" + "1" * 64,
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": False,
            },
        },
        {
            "to_state": "approved",
            "candidate_revision_id": 1,
            "candidate_content_sha256": "sha256:" + "1" * 64,
            "approved_revision_id": 2,
            "approved_content_sha256": "sha256:" + "2" * 64,
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": True,
            },
        },
        {"to_state": "published"},
        {
            "to_state": "published",
            "approved_revision_id": 2,
            "approved_content_sha256": "sha256:" + "2" * 64,
            "candidate_revision_id": 1,
        },
        {
            "to_state": "in_review",
            "candidate_revision_id": 1,
            "candidate_content_sha256": "sha256:" + "1" * 64,
        },
    ],
)
async def test_transition_conditional_fields_are_discriminated_with_422(
    async_client,
    draft_record,
    admin_headers,
    payload,
):
    """Missing, false, or irrelevant exact-review fields are malformed input."""
    response = await async_client.post(
        _transitions_url(draft_record.phenopacket_id),
        json={"reason": "invalid conditional body", "revision": 1, **payload},
        headers=admin_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_stale_well_formed_candidate_digest_returns_stable_409(
    async_client,
    draft_record,
    curator_headers,
    admin_headers,
):
    """A syntactically valid but stale exact candidate is a workflow conflict."""
    submitted = await async_client.post(
        _transitions_url(draft_record.phenopacket_id),
        json={"to_state": "in_review", "reason": "submit", "revision": 1},
        headers=curator_headers,
    )
    assert submitted.status_code == 200, submitted.text
    candidate = submitted.json()["revision"]

    response = await async_client.post(
        _transitions_url(draft_record.phenopacket_id),
        json={
            "to_state": "approved",
            "reason": "stale exact candidate",
            "revision": submitted.json()["phenopacket"]["revision"],
            "candidate_revision_id": candidate["id"],
            "candidate_content_sha256": "sha256:" + "0" * 64,
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": True,
            },
        },
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "review_revision_mismatch"


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


@pytest.mark.asyncio
async def test_revision_detail_labels_legacy_role_snapshot_as_unrecorded(
    async_client,
    published_record,
    admin_headers,
):
    """A current actor relationship never masquerades as historic role evidence."""
    legacy_revision_id = published_record.head_published_revision_id
    assert legacy_revision_id is not None

    response = await async_client.get(
        _revision_detail_url(published_record.phenopacket_id, legacy_revision_id),
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["actor_username"] is not None
    assert body["actor_role"] is None
    assert body["actor_role_at_decision_recorded"] is False
    assert body["decision_metadata"] is None
    assert body["content_sha256"] is None
    assert body["ledger_version"] is None


@pytest.mark.asyncio
async def test_independence_policy_error_preserves_specific_403_code(
    async_client,
    db_session,
    draft_record,
    admin_user,
    admin_headers,
):
    """An independence denial is not collapsed into generic forbidden_role."""
    draft_record.draft_owner_id = admin_user.id
    draft_record.created_by_id = admin_user.id
    await db_session.commit()

    submitted = await async_client.post(
        _transitions_url(draft_record.phenopacket_id),
        json={"to_state": "in_review", "reason": "self submit", "revision": 1},
        headers=admin_headers,
    )
    assert submitted.status_code == 200, submitted.text
    candidate = submitted.json()["revision"]

    response = await async_client.post(
        _transitions_url(draft_record.phenopacket_id),
        json={
            "to_state": "approved",
            "reason": "self approve",
            "revision": submitted.json()["phenopacket"]["revision"],
            "candidate_revision_id": candidate["id"],
            "candidate_content_sha256": candidate["content_sha256"],
            "attestation": {
                "independent_review": True,
                "no_unmanaged_conflict": True,
            },
        },
        headers=admin_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "self_review_forbidden"
