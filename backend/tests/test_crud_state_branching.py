"""HTTP-level integration tests for PUT clone-to-draft branching and
role-based list/detail visibility.

Wave 7 D.1 Task 11.

Tests:
- PUT on published record → clone-to-draft (editing_revision_id set)
- Anonymous GET during clone returns OLD head content (I1 at HTTP level)
- Curator GET during clone returns NEW working copy
- Anonymous list hides non-published records
- Curator list includes all states
- Non-curator GET detail: state field is null in response

All tests use a real DB (no mocks).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.phenopackets.models import PhenopacketRevision

# Minimal valid GA4GH Phenopackets v2 content that passes schema validation.
# The sanitizer strips empty lists, so resources must be non-empty.
_VALID_PP_BASE = {
    "id": "wave7-published-1",
    "subject": {"id": "wave7-published-1", "sex": "UNKNOWN_SEX"},
    "metaData": {
        "created": "2026-04-13T00:00:00Z",
        "createdBy": "test",
        "phenopacketSchemaVersion": "2.0",
        "resources": [
            {
                "id": "hp",
                "name": "HPO",
                "namespacePrefix": "HP",
                "url": "http://purl.obolibrary.org/obo/hp.owl",
                "version": "2024-01-01",
                "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
            }
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pp_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}"


def _list_url() -> str:
    return "/api/v2/phenopackets/"


def _transitions_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}/transitions"


# ---------------------------------------------------------------------------
# PUT on published → clone-to-draft
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_on_published_creates_clone(
    async_client,
    db_session,
    published_record,
    curator_headers,
    curator_user,
):
    """Curator PUTs on a published record → state stays 'published',
    editing_revision_id is set, and a new revision row with to_state='draft'
    is written.
    """
    pid = published_record.phenopacket_id
    original_rev = published_record.revision
    original_head = published_record.head_published_revision_id

    new_content = dict(_VALID_PP_BASE)
    new_content["notes"] = "curator_change"

    resp = await async_client.put(
        _pp_url(pid),
        json={
            "phenopacket": new_content,
            "revision": original_rev,
            "change_reason": "curator fix",
        },
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # State stays 'published'
    assert data["state"] == "published"
    # editing_revision_id is now set (clone in progress)
    assert data["editing_revision_id"] is not None
    # head_published_revision_id unchanged (I1)
    assert data["head_published_revision_id"] == original_head

    # A new revision row with to_state='draft' exists
    await db_session.refresh(published_record)
    rows = (
        await db_session.execute(
            select(PhenopacketRevision)
            .where(PhenopacketRevision.record_id == published_record.id)
            .order_by(PhenopacketRevision.revision_number)
        )
    ).scalars().all()
    assert len(rows) == 2  # initial published + new draft row
    draft_row = rows[-1]
    assert draft_row.to_state == "draft"
    assert draft_row.is_head_published is False


# ---------------------------------------------------------------------------
# Anonymous GET during clone returns OLD head content (I1 at HTTP level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_get_returns_old_head_during_clone(
    async_client,
    db_session,
    published_record,
    curator_headers,
):
    """After clone-to-draft, anonymous GET returns OLD head content, not the
    curator's working copy (invariant I1 at the HTTP level).
    """
    # The original head content is taken from the head_published_revision_id row;
    # any subsequent PUT creates a draft clone but must NOT change that pointer.
    pid = published_record.phenopacket_id
    original_rev = published_record.revision

    from sqlalchemy import select as sa_select

    from app.phenopackets.models import PhenopacketRevision as PR

    head_row = (
        await db_session.execute(
            sa_select(PR).where(PR.id == published_record.head_published_revision_id)
        )
    ).scalar_one()
    original_head_content = dict(head_row.content_jsonb)

    # New content: valid GA4GH shape with an extra field
    new_content = dict(_VALID_PP_BASE)
    new_content["notes"] = "should_not_be_public"

    # Clone-to-draft via PUT
    r = await async_client.put(
        _pp_url(pid),
        json={
            "phenopacket": new_content,
            "revision": original_rev,
            "change_reason": "fix",
        },
        headers=curator_headers,
    )
    assert r.status_code == 200, r.text

    # Anonymous GET (no auth header)
    resp = await async_client.get(_pp_url(pid))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Should see original head content, not curator's working copy
    assert body["phenopacket"] == original_head_content
    assert "notes" not in body["phenopacket"]
    # state must be None (not exposed to non-curators)
    assert body.get("state") is None


# ---------------------------------------------------------------------------
# Curator GET during clone returns NEW working copy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_curator_get_returns_working_copy_during_clone(
    async_client,
    published_record,
    curator_headers,
):
    """After clone-to-draft, curator GET returns the NEW working copy."""
    pid = published_record.phenopacket_id
    original_rev = published_record.revision

    new_content = dict(_VALID_PP_BASE)
    new_content["curator_field"] = "new_value"

    r = await async_client.put(
        _pp_url(pid),
        json={
            "phenopacket": new_content,
            "revision": original_rev,
            "change_reason": "update",
        },
        headers=curator_headers,
    )
    assert r.status_code == 200, r.text

    # Curator GET
    resp = await async_client.get(_pp_url(pid), headers=curator_headers)
    assert resp.status_code == 200
    body = resp.json()

    # Curator sees working copy
    assert body["phenopacket"]["curator_field"] == "new_value"
    # Curator sees state — record remains 'published' while draft clone is active
    assert body["state"] == "published"


# ---------------------------------------------------------------------------
# List visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_list_hides_non_published(
    async_client,
    draft_record,
    published_record,
):
    """Anonymous list returns only published records — draft hidden."""
    resp = await async_client.get(_list_url())
    assert resp.status_code == 200
    body = resp.json()

    # published_record should appear (its phenopacket["id"])
    assert any(
        published_record.phenopacket.get("id") == item.get("id")
        for item in body.get("data", [])
    )
    # draft_record should NOT appear
    assert all(
        draft_record.phenopacket.get("id") != item.get("id")
        for item in body.get("data", [])
    )


@pytest.mark.asyncio
async def test_curator_list_includes_non_published(
    async_client,
    draft_record,
    published_record,
    curator_headers,
):
    """Curator list includes draft records alongside published ones."""
    resp = await async_client.get(_list_url(), headers=curator_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert any(
        published_record.phenopacket.get("id") == item.get("id")
        for item in body.get("data", [])
    )
    assert any(
        draft_record.phenopacket.get("id") == item.get("id")
        for item in body.get("data", [])
    )


# ---------------------------------------------------------------------------
# Non-curator state field is null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_curator_state_field_is_null(
    async_client,
    published_record,
    viewer_headers,
):
    """Non-curator GET detail returns state=None (not exposed per spec §7.2)."""
    pid = published_record.phenopacket_id

    resp = await async_client.get(_pp_url(pid), headers=viewer_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body.get("state") is None


# ---------------------------------------------------------------------------
# /batch endpoint visibility (Important #3 — draft-leak fix)
# ---------------------------------------------------------------------------

def _batch_url(ids: list[str]) -> str:
    return f"/api/v2/phenopackets/batch?phenopacket_ids={','.join(ids)}"


@pytest.mark.asyncio
async def test_batch_hides_drafts_from_anonymous(
    async_client,
    draft_record,
    published_record,
):
    """Anonymous callers receive only published records from /batch.

    A draft phenopacket_id included in the request must be silently omitted
    from the response — it must not be leaked to unauthenticated callers.
    """
    ids = [draft_record.phenopacket_id, published_record.phenopacket_id]
    resp = await async_client.get(_batch_url(ids))
    assert resp.status_code == 200
    body = resp.json()

    returned_ids = {item["phenopacket_id"] for item in body}
    assert published_record.phenopacket_id in returned_ids
    assert draft_record.phenopacket_id not in returned_ids


@pytest.mark.asyncio
async def test_batch_returns_all_for_curator(
    async_client,
    draft_record,
    published_record,
    curator_headers,
):
    """Curator callers receive both draft and published records from /batch."""
    ids = [draft_record.phenopacket_id, published_record.phenopacket_id]
    resp = await async_client.get(_batch_url(ids), headers=curator_headers)
    assert resp.status_code == 200
    body = resp.json()

    returned_ids = {item["phenopacket_id"] for item in body}
    assert published_record.phenopacket_id in returned_ids
    assert draft_record.phenopacket_id in returned_ids
