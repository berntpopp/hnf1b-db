"""Export modes (spec §4.6)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketRevision

CURATION = {"cohort": "fetus", "detectionMethod": "mlpa"}


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


@pytest.fixture
async def curated_phenopacket_id(async_client, curator_headers, db_session):
    payload = {
        "phenopacket": {
            "id": "phenopacket-export-test",
            "subject": {"id": "export-test", "sex": "FEMALE"},
            "metaData": {
                "created": "2026-07-30T00:00:00Z",
                "createdBy": "test",
                "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
            },
            "hnf1bCuration": CURATION,
        }
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=curator_headers
    )
    assert response.status_code in (200, 201)
    phenopacket_id = "phenopacket-export-test"

    # A freshly POSTed record defaults to state='draft' (Wave 7 D.1), which
    # is invisible to anonymous callers — matching the detail GET. Most of
    # these tests care about conformant vs. full shaping, not the draft/
    # published visibility boundary (that is covered separately below), so
    # promote straight to published here rather than driving the full
    # draft -> in_review -> approved -> published review cycle.
    pp = (
        await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
        )
    ).scalar_one()
    rev = PhenopacketRevision(
        record_id=pp.id,
        parent_revision_id=pp.editing_revision_id,
        revision_number=pp.revision + 1,
        state="published",
        content_jsonb=pp.phenopacket,
        change_reason="publish for export test",
        actor_id=pp.created_by_id,
        from_state="draft",
        to_state="published",
        event_type="published",
    )
    db_session.add(rev)
    await db_session.flush()
    pp.state = "published"
    pp.revision += 1
    pp.head_published_revision_id = rev.id
    pp.editing_revision_id = None
    pp.draft_owner_id = None
    await db_session.commit()

    return phenopacket_id


@pytest.mark.asyncio
async def test_full_mode_includes_curation(
    async_client, curator_headers, curated_phenopacket_id
):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=full",
        headers=curator_headers,
    )
    assert response.status_code == 200
    curation = response.json()["hnf1bCuration"]
    # Curator-supplied fields round-trip exactly; curatedAt is added by the
    # server on top of them (it is not part of what the fixture submitted).
    assert {k: v for k, v in curation.items() if k != "curatedAt"} == CURATION
    _assert_recent_server_curated_at(curation)


@pytest.mark.asyncio
async def test_curated_at_cannot_be_forged_by_the_client(async_client, curator_headers):
    """A client-supplied ``curatedAt`` lie must never survive persistence.

    This is the actual reason the field is server-stamped
    (``stamp_curated_at``, spec §3.6): provenance is stamped, not typed, so
    a curator -- or a compromised console -- cannot backdate (or otherwise
    forge) a review timestamp by putting a value in the request body.
    """
    lie = "1999-01-01T00:00:00+00:00"
    payload = {
        "phenopacket": {
            "id": "phenopacket-curated-at-forgery-test",
            "subject": {"id": "forgery-test", "sex": "FEMALE"},
            "metaData": {
                "created": "2026-07-30T00:00:00Z",
                "createdBy": "test",
                "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
            },
            "hnf1bCuration": {"cohort": "fetus", "curatedAt": lie},
        }
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=curator_headers
    )
    assert response.status_code in (200, 201), response.text
    stored_curation = response.json()["phenopacket"]["hnf1bCuration"]
    assert stored_curation["curatedAt"] != lie
    _assert_recent_server_curated_at(stored_curation)


@pytest.mark.asyncio
async def test_conformant_mode_strips_curation(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=conformant"
    )
    assert response.status_code == 200
    assert "hnf1bCuration" not in response.json()


@pytest.mark.asyncio
async def test_conformant_is_the_default(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export"
    )
    assert "hnf1bCuration" not in response.json()


@pytest.mark.asyncio
async def test_the_two_modes_differ_only_by_that_key(
    async_client, curator_headers, curated_phenopacket_id
):
    full = (
        await async_client.get(
            f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=full",
            headers=curator_headers,
        )
    ).json()
    conformant = (
        await async_client.get(
            f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=conformant"
        )
    ).json()

    assert {k: v for k, v in full.items() if k != "hnf1bCuration"} == conformant


@pytest.mark.asyncio
async def test_unknown_mode_is_rejected(async_client, curated_phenopacket_id):
    response = await async_client.get(
        f"/api/v2/phenopackets/{curated_phenopacket_id}/export?mode=pretty"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_record_is_404(async_client):
    response = await async_client.get("/api/v2/phenopackets/does-not-exist/export")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Visibility must mirror the detail GET exactly.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_cannot_export_a_draft(async_client, draft_record):
    response = await async_client.get(
        f"/api/v2/phenopackets/{draft_record.phenopacket_id}/export"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_anonymous_export_of_a_record_being_edited_returns_published_content(
    async_client, clone_in_progress_record
):
    """The working copy has unpublished edits; the export must not show them."""
    record = clone_in_progress_record["record"]
    response = await async_client.get(
        f"/api/v2/phenopackets/{record.phenopacket_id}/export"
    )
    assert response.status_code == 200
    # Assert against the published revision's content, not pp.phenopacket —
    # the working copy carries these leak markers (conftest.py:591-592).
    assert response.json().get("subject", {}).get("id") != "LEAKED-DRAFT-SUBJECT"
    assert "_secret_working_copy" not in response.json()
    assert response.json()["id"] == record.phenopacket_id


@pytest.mark.asyncio
async def test_full_mode_requires_curator(async_client, published_record):
    response = await async_client.get(
        f"/api/v2/phenopackets/{published_record.phenopacket_id}/export?mode=full"
    )
    assert response.status_code in (401, 403)
