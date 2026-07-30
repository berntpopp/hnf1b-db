"""hnf1bCuration inherits the revision machinery (spec §2.7, §4.1).

Living in the JSONB rather than a side table is the design's central claim.
These tests are what make it true rather than merely asserted.
"""

import pytest
from sqlalchemy import select

from app.phenopackets.models import PhenopacketRevision

_RESOURCES = [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}]


def _meta():
    return {
        "created": "2026-07-30T00:00:00Z",
        "createdBy": "test",
        "resources": _RESOURCES,
    }


def _content(phenopacket_id, **overrides):
    return {
        "id": phenopacket_id,
        "subject": {"id": phenopacket_id, "sex": "FEMALE"},
        "metaData": _meta(),
        **overrides,
    }


@pytest.mark.asyncio
async def test_update_round_trips_curation(async_client, curator_headers, draft_record):
    """PUT then GET returns what was written."""
    pid = draft_record.phenopacket_id
    curation = {"cohort": "fetus", "detectionMethod": "mlpa"}

    put_resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration=curation),
            "revision": draft_record.revision,
            "change_reason": "add curation",
        },
        headers=curator_headers,
    )
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["phenopacket"]["hnf1bCuration"] == curation

    get_resp = await async_client.get(
        f"/api/v2/phenopackets/{pid}", headers=curator_headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["phenopacket"]["hnf1bCuration"] == curation


@pytest.mark.asyncio
async def test_absence_and_not_reported_are_distinguishable(
    async_client, curator_headers, draft_record
):
    """NULL/absent means 'not yet curated'; not_reported means 'source is silent'.

    Phase 3's completeness indicator and any later QC queue depend on telling
    these apart through the API, not just in storage.
    """
    pid = draft_record.phenopacket_id

    # No hnf1bCuration key at all: never curated.
    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid),
            "revision": draft_record.revision,
            "change_reason": "not yet curated",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    assert "hnf1bCuration" not in resp.json()["phenopacket"]
    revision = resp.json()["revision"]

    # familyHistory explicitly recorded as "not_reported": the source was
    # consulted and said nothing, which is a different fact than "nobody
    # has looked yet".
    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(
                pid, hnf1bCuration={"familyHistory": "not_reported"}
            ),
            "revision": revision,
            "change_reason": "source is silent on family history",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text

    get_resp = await async_client.get(
        f"/api/v2/phenopackets/{pid}", headers=curator_headers
    )
    assert (
        get_resp.json()["phenopacket"]["hnf1bCuration"]["familyHistory"]
        == "not_reported"
    )


@pytest.mark.asyncio
async def test_editing_curation_produces_a_revision_containing_the_change(
    db_session, async_client, curator_headers, draft_record
):
    """phenopacket_revisions.content_jsonb must carry the curation edit."""
    pid = draft_record.phenopacket_id
    revision = draft_record.revision

    # A bare in-place save on a never-transitioned draft has no revision row
    # to update (state_service._inplace_save only touches an existing
    # editing_revision_id). Drive one transition cycle so such a row exists.
    resp = await async_client.post(
        f"/api/v2/phenopackets/{pid}/transitions",
        json={"to_state": "in_review", "reason": "submit", "revision": revision},
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    revision = resp.json()["phenopacket"]["revision"]

    resp = await async_client.post(
        f"/api/v2/phenopackets/{pid}/transitions",
        json={"to_state": "draft", "reason": "withdraw", "revision": revision},
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    revision = resp.json()["phenopacket"]["revision"]
    editing_revision_id = resp.json()["phenopacket"]["editing_revision_id"]
    assert editing_revision_id is not None

    curation = {"cohort": "born"}
    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration=curation),
            "revision": revision,
            "change_reason": "curate",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text

    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.id == editing_revision_id)
    )
    stored = result.scalar_one()
    assert stored.content_jsonb["hnf1bCuration"] == curation


@pytest.mark.asyncio
async def test_curation_edit_does_not_alter_the_published_head(
    db_session, async_client, curator_headers, published_record
):
    """Editing the working copy must leave head_published_revision untouched."""
    pid = published_record.phenopacket_id
    head_id = published_record.head_published_revision_id

    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration={"cohort": "fetus"}),
            "revision": published_record.revision,
            "change_reason": "curate a published record",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Clone-to-draft (§6.1): state stays published, head pointer unchanged (I1).
    assert body["state"] == "published"
    assert body["head_published_revision_id"] == head_id

    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.id == head_id)
    )
    head_rev = result.scalar_one()
    assert "hnf1bCuration" not in head_rev.content_jsonb


@pytest.mark.asyncio
async def test_public_read_during_an_edit_shows_published_curation(
    async_client, db_session, clone_in_progress_record
):
    """visibility.py:80 dereferences the published head; curation follows it."""
    record = clone_in_progress_record["record"]

    # Give the published head a curation value the in-progress working copy
    # does not have, so the assertion below cannot pass by accident.
    result = await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.id == record.head_published_revision_id
        )
    )
    head_rev = result.scalar_one()
    head_content = dict(head_rev.content_jsonb)
    head_content["hnf1bCuration"] = {"cohort": "born"}
    head_rev.content_jsonb = head_content
    await db_session.commit()

    assert "hnf1bCuration" not in record.phenopacket

    response = await async_client.get(f"/api/v2/phenopackets/{record.phenopacket_id}")
    assert response.status_code == 200
    body = response.json()["phenopacket"]
    assert body["hnf1bCuration"] == {"cohort": "born"}
    # The leak markers from the in-progress working copy must not appear.
    assert body.get("subject", {}).get("id") != "LEAKED-DRAFT-SUBJECT"
    assert "_secret_working_copy" not in body


@pytest.mark.asyncio
async def test_concurrent_curation_edit_returns_409(
    async_client, curator_headers, another_curator, draft_record
):
    """Two curators, one stale revision -> optimistic lock rejects the second.

    Inherited from Phenopacket.revision at no cost, which a side table would
    have had to reimplement. The revision check in
    PhenopacketStateService._lock_and_check runs before the ownership check,
    so a second, non-owning curator hitting a stale revision still surfaces
    as revision_mismatch, not forbidden_not_owner.
    """
    pid = draft_record.phenopacket_id
    stale_revision = draft_record.revision

    first = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration={"cohort": "born"}),
            "revision": stale_revision,
            "change_reason": "first curator's edit",
        },
        headers=curator_headers,
    )
    assert first.status_code == 200, first.text

    login = await async_client.post(
        "/api/v2/auth/login",
        json={"username": another_curator.username, "password": "CuratorPass123!"},
    )
    assert login.status_code == 200, login.text
    another_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    second = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration={"cohort": "fetus"}),
            "revision": stale_revision,
            "change_reason": "second curator's edit, stale revision",
        },
        headers=another_headers,
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "revision_mismatch"


@pytest.mark.asyncio
async def test_a_record_with_zero_interpretations_accepts_curation(
    async_client, curator_headers, draft_record
):
    """59 corpus records have no interpretations at all.

    This is why case-level facts are not on variantInterpretation.
    """
    pid = draft_record.phenopacket_id
    curation = {"cohort": "born"}

    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration=curation),
            "revision": draft_record.revision,
            "change_reason": "curate a record with zero interpretations",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["phenopacket"]
    assert "interpretations" not in body
    assert body["hnf1bCuration"] == curation


@pytest.mark.asyncio
async def test_rollback_restores_prior_curation(
    db_session, async_client, curator_headers, published_record
):
    """Reverting to an earlier revision reverts curation with it.

    There is no dedicated "rollback" endpoint — that is the point. The
    JSONB/revision-log design means a curator can restore a prior state
    using nothing but the existing GET .../revisions/{id} + PUT primitives.
    """
    pid = published_record.phenopacket_id
    head_id = published_record.head_published_revision_id

    # Seed the published head with curation A directly (bypassing REST, the
    # same way the published_record fixture itself is built) so there is a
    # genuine prior revision to roll back to.
    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.id == head_id)
    )
    head_rev = result.scalar_one()
    content_a = _content(pid, hnf1bCuration={"cohort": "born"})
    head_rev.content_jsonb = content_a
    published_record.phenopacket = content_a
    await db_session.commit()
    await db_session.refresh(published_record)

    # Curator changes the working copy to curation B (clone-to-draft).
    content_b = _content(pid, hnf1bCuration={"cohort": "fetus"})
    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": content_b,
            "revision": published_record.revision,
            "change_reason": "change curation",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    working_revision = resp.json()["revision"]

    get_resp = await async_client.get(
        f"/api/v2/phenopackets/{pid}", headers=curator_headers
    )
    assert get_resp.json()["phenopacket"]["hnf1bCuration"] == {"cohort": "fetus"}

    # Roll back: fetch the prior (published) revision's content and PUT it
    # back as the new working copy.
    revision_detail = await async_client.get(
        f"/api/v2/phenopackets/{pid}/revisions/{head_id}", headers=curator_headers
    )
    assert revision_detail.status_code == 200
    prior_content = revision_detail.json()["content_jsonb"]
    assert prior_content["hnf1bCuration"] == {"cohort": "born"}

    rollback_resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": prior_content,
            "revision": working_revision,
            "change_reason": "rollback to prior curation",
        },
        headers=curator_headers,
    )
    assert rollback_resp.status_code == 200, rollback_resp.text
    assert rollback_resp.json()["phenopacket"]["hnf1bCuration"] == {"cohort": "born"}
