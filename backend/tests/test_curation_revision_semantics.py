"""hnf1bCuration inherits the revision machinery (spec §2.7, §4.1).

Living in the JSONB rather than a side table is the design's central claim.
These tests are what make it true rather than merely asserted.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.phenopackets.models import PhenopacketRevision

_RESOURCES = [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}]


def _assert_recent_server_curated_at(curation: dict) -> None:
    """``curatedAt`` must be a server-stamped, recent ISO-8601 UTC timestamp.

    Proves the value came from the server clock
    (``app/phenopackets/services/phenopacket_service.py::stamp_curated_at``),
    not from whatever the request body happened to contain.
    """
    assert "curatedAt" in curation
    stamped = datetime.fromisoformat(curation["curatedAt"])
    assert stamped.tzinfo is not None and stamped.utcoffset() == timedelta(0), (
        "curatedAt must be timezone-aware UTC"
    )
    assert abs(datetime.now(timezone.utc) - stamped) < timedelta(minutes=5)


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
    put_curation = put_resp.json()["phenopacket"]["hnf1bCuration"]
    assert {k: v for k, v in put_curation.items() if k != "curatedAt"} == curation
    _assert_recent_server_curated_at(put_curation)

    get_resp = await async_client.get(
        f"/api/v2/phenopackets/{pid}", headers=curator_headers
    )
    assert get_resp.status_code == 200
    get_curation = get_resp.json()["phenopacket"]["hnf1bCuration"]
    assert {k: v for k, v in get_curation.items() if k != "curatedAt"} == curation
    # The GET is a pure read of what PUT persisted -- the stamp must not
    # move between the write and a subsequent read.
    assert get_curation["curatedAt"] == put_curation["curatedAt"]


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

    # Drive one transition cycle so the draft has an active editing revision.
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

    # Saves are append-only: the active editing pointer advances to a fresh
    # snapshot and the withdrawn revision remains immutable audit history.
    updated_editing_revision_id = resp.json()["editing_revision_id"]
    assert updated_editing_revision_id != editing_revision_id
    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.id == editing_revision_id)
    )
    assert "hnf1bCuration" not in result.scalar_one().content_jsonb
    result = await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.id == updated_editing_revision_id
        )
    )
    stored = result.scalar_one()
    stored_curation = stored.content_jsonb["hnf1bCuration"]
    assert {k: v for k, v in stored_curation.items() if k != "curatedAt"} == curation
    _assert_recent_server_curated_at(stored_curation)


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

    assert "hnf1bCuration" not in record.phenopacket

    response = await async_client.get(f"/api/v2/phenopackets/{record.phenopacket_id}")
    assert response.status_code == 200
    body = response.json()["phenopacket"]
    # Public representations redact local curation data even when it is
    # present in the immutable head snapshot.
    assert "hnf1bCuration" not in body
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
    body_curation = body["hnf1bCuration"]
    assert {k: v for k, v in body_curation.items() if k != "curatedAt"} == curation
    _assert_recent_server_curated_at(body_curation)


@pytest.mark.asyncio
async def test_curated_by_is_left_untouched_by_the_server_stamp(
    async_client, curator_headers, draft_record
):
    """``stamp_curated_at`` only ever writes ``curatedAt``.

    Its docstring claims it "never touches curatedBy or any other field --
    those are out of scope for this task" (Phase 3 plan Task 9 §c). Prove
    it: a curator-supplied ``curatedBy`` must round-trip through the live
    write path unchanged while ``curatedAt`` is independently server-
    stamped alongside it.
    """
    pid = draft_record.phenopacket_id
    curation = {"cohort": "fetus", "curatedBy": "Bernt Popp"}

    resp = await async_client.put(
        f"/api/v2/phenopackets/{pid}",
        json={
            "phenopacket": _content(pid, hnf1bCuration=curation),
            "revision": draft_record.revision,
            "change_reason": "curate with an explicit curatedBy",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    stored = resp.json()["phenopacket"]["hnf1bCuration"]
    assert stored["curatedBy"] == "Bernt Popp"
    assert stored["cohort"] == "fetus"
    _assert_recent_server_curated_at(stored)


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

    # Append a published snapshot with curation A, then atomically point the
    # record at it. Revision rows cannot be rewritten after insertion.
    content_a = _content(pid, hnf1bCuration={"cohort": "born"})
    seeded_head = PhenopacketRevision(
        record_id=published_record.id,
        revision_number=published_record.revision + 1,
        state="published",
        content_jsonb=content_a,
        change_reason="seed immutable prior curation",
        actor_id=published_record.created_by_id,
        from_state="published",
        to_state="published",
    )
    db_session.add(seeded_head)
    await db_session.flush()
    published_record.head_published_revision_id = seeded_head.id
    published_record.phenopacket = content_a
    published_record.revision += 1
    await db_session.commit()
    await db_session.refresh(published_record)
    head_id = seeded_head.id

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
    working_curation = get_resp.json()["phenopacket"]["hnf1bCuration"]
    assert {k: v for k, v in working_curation.items() if k != "curatedAt"} == {
        "cohort": "fetus"
    }
    _assert_recent_server_curated_at(working_curation)

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
    rollback_curation = rollback_resp.json()["phenopacket"]["hnf1bCuration"]
    assert {k: v for k, v in rollback_curation.items() if k != "curatedAt"} == {
        "cohort": "born"
    }
    _assert_recent_server_curated_at(rollback_curation)
