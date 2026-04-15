"""Wave 5a: DELETE must honour the optimistic-locking revision.

Before this fix, soft_delete() blindly set deleted_at/deleted_by
regardless of the client's revision number, so a curator holding a
stale view could delete a record that a co-curator had just updated.

The behavior mirrors UPDATE: if the client's revision doesn't match
the current row revision, return 409 Conflict.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.database import async_session_maker
from app.phenopackets.models import Phenopacket, PhenopacketUpdate
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.phenopacket_service import (
    PhenopacketService,
    ServiceConflict,
)
from app.phenopackets.services.state_service import PhenopacketStateService


def _valid_payload(phenopacket_id: str, subject_id: str = "s", sex: str = "MALE"):
    """Build a minimal-but-valid phenopacket create payload.

    Matches the pattern from test_audit_actor_fk.py — includes resources
    in metaData so the validator accepts it.
    """
    return {
        "phenopacket": {
            "id": phenopacket_id,
            "subject": {"id": subject_id, "sex": sex},
            "phenotypicFeatures": [],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pytest",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-01-01",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        }
    }


@pytest.mark.asyncio
async def test_delete_with_matching_revision_succeeds(
    async_client: AsyncClient, admin_headers: dict
):
    """DELETE with a revision that matches the row's current revision → 200."""
    create_payload = _valid_payload("delete-revision-ok")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-ok",
        json={"change_reason": "test", "revision": 1},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_delete_with_stale_revision_returns_409(
    async_client: AsyncClient, admin_headers: dict
):
    """DELETE with a stale revision after a concurrent UPDATE → 409 Conflict."""
    create_payload = _valid_payload("delete-revision-stale")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    # Simulate concurrent update by another client
    update_payload = {
        **create_payload,
        "revision": 1,
        "change_reason": "concurrent edit",
    }
    update_resp = await async_client.put(
        "/api/v2/phenopackets/delete-revision-stale",
        json=update_payload,
        headers=admin_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    # Current revision is now 2. Client still holds revision 1.

    # Stale delete
    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-stale",
        json={"change_reason": "stale delete", "revision": 1},
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["detail"]["current_revision"] == 2
    assert body["detail"]["expected_revision"] == 1


@pytest.mark.asyncio
async def test_delete_without_revision_returns_422(
    async_client: AsyncClient, admin_headers: dict
):
    """DELETE without a revision is rejected at request validation."""
    create_payload = _valid_payload("delete-revision-required")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-required",
        json={"change_reason": "no revision"},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_delete_fails_when_revision_changes_before_commit(
    db_session,
    admin_user,
):
    """A stale delete loses to a concurrent update even across sessions."""
    create_payload = _valid_payload("delete-revision-race")
    phenopacket = Phenopacket(
        phenopacket_id=create_payload["phenopacket"]["id"],
        phenopacket=create_payload["phenopacket"],
        subject_id=create_payload["phenopacket"]["subject"]["id"],
        subject_sex=create_payload["phenopacket"]["subject"].get("sex", "UNKNOWN_SEX"),
        created_by_id=admin_user.id,
        state="draft",
        revision=1,
    )
    db_session.add(phenopacket)
    await db_session.commit()

    stale_ready = __import__("asyncio").Event()
    update_done = __import__("asyncio").Event()

    async def actor_a_delete() -> None:
        async with async_session_maker() as session:
            service = PhenopacketService(PhenopacketRepository(session))
            loaded = await service.get("delete-revision-race")
            assert loaded is not None
            assert loaded.revision == 1
            stale_ready.set()
            await update_done.wait()

            with pytest.raises(ServiceConflict) as exc_info:
                await service.soft_delete(
                    "delete-revision-race",
                    "stale delete",
                    actor_id=admin_user.id,
                    actor_username=admin_user.username,
                    expected_revision=loaded.revision,
                )

            assert exc_info.value.code == "revision_mismatch"
            assert exc_info.value.detail["current_revision"] == 2
            assert exc_info.value.detail["expected_revision"] == 1

    async def actor_b_update() -> None:
        await stale_ready.wait()
        async with async_session_maker() as session:
            service = PhenopacketService(PhenopacketRepository(session))
            update_payload = PhenopacketUpdate(
                phenopacket={
                    **create_payload["phenopacket"],
                    "phenotypicFeatures": [
                        {
                            "type": {"id": "HP:0000001", "label": "updated"},
                        }
                    ],
                },
                revision=1,
                change_reason="concurrent edit",
            )
            updated = await service.update(
                "delete-revision-race",
                update_payload,
                actor_id=admin_user.id,
            )
            assert updated.revision == 2
        update_done.set()

    await __import__("asyncio").gather(actor_a_delete(), actor_b_update())


@pytest.mark.asyncio
async def test_transition_fails_cleanly_when_delete_wins_after_preread(
    db_session,
    admin_user,
):
    """A state transition that loses to a concurrent delete must not leak KeyError.

    The HTTP transition route currently performs an unlocked pre-read to resolve the
    phenopacket id into the internal UUID before delegating to the state service.
    If another session soft-deletes the row after that pre-read but before
    ``SELECT .. FOR UPDATE`` runs inside ``_lock_and_check()``, the service should
    raise a stable domain error that the router can map to 404 instead of leaking a
    raw ``KeyError`` as a 500.
    """
    phenopacket = Phenopacket(
        phenopacket_id="transition-delete-race",
        phenopacket=_valid_payload("transition-delete-race")["phenopacket"],
        subject_id="s",
        subject_sex="MALE",
        created_by_id=admin_user.id,
        state="draft",
        revision=1,
    )
    db_session.add(phenopacket)
    await db_session.commit()

    preread_complete = __import__("asyncio").Event()
    delete_complete = __import__("asyncio").Event()

    async def actor_a_transition() -> None:
        async with async_session_maker() as session:
            repo = PhenopacketRepository(session)
            loaded = await repo.get_by_id("transition-delete-race")
            assert loaded is not None
            preread_complete.set()
            await delete_complete.wait()

            svc = PhenopacketStateService(session)
            with pytest.raises(PhenopacketStateService.RecordNotFound):
                await svc.transition(
                    loaded.id,
                    to_state="in_review",
                    reason="submit after stale preread",
                    expected_revision=loaded.revision,
                    actor=admin_user,
                )

    async def actor_b_delete() -> None:
        await preread_complete.wait()
        async with async_session_maker() as session:
            service = PhenopacketService(PhenopacketRepository(session))
            result = await service.soft_delete(
                "transition-delete-race",
                "delete wins race",
                actor_id=admin_user.id,
                actor_username=admin_user.username,
                expected_revision=1,
            )
            assert result["deleted_at"] is not None
        delete_complete.set()

    await __import__("asyncio").gather(actor_a_transition(), actor_b_delete())


@pytest.mark.asyncio
async def test_edit_fails_cleanly_when_delete_wins_after_preread(
    db_session,
    admin_user,
):
    """An edit that loses to a concurrent delete must surface a stable not-found error."""
    payload = _valid_payload("edit-delete-race")
    phenopacket = Phenopacket(
        phenopacket_id="edit-delete-race",
        phenopacket=payload["phenopacket"],
        subject_id=payload["phenopacket"]["subject"]["id"],
        subject_sex=payload["phenopacket"]["subject"].get("sex", "UNKNOWN_SEX"),
        created_by_id=admin_user.id,
        state="draft",
        revision=1,
    )
    db_session.add(phenopacket)
    await db_session.commit()

    preread_complete = __import__("asyncio").Event()
    delete_complete = __import__("asyncio").Event()

    async def actor_a_edit() -> None:
        async with async_session_maker() as session:
            repo = PhenopacketRepository(session)
            loaded = await repo.get_by_id("edit-delete-race")
            assert loaded is not None
            preread_complete.set()
            await delete_complete.wait()

            svc = PhenopacketStateService(session)
            with pytest.raises(PhenopacketStateService.RecordNotFound):
                await svc.edit_record(
                    loaded.id,
                    new_content={
                        **payload["phenopacket"],
                        "phenotypicFeatures": [
                            {
                                "type": {"id": "HP:0000001", "label": "updated"},
                            }
                        ],
                    },
                    change_reason="edit after stale preread",
                    expected_revision=loaded.revision,
                    actor=admin_user,
                )

    async def actor_b_delete() -> None:
        await preread_complete.wait()
        async with async_session_maker() as session:
            service = PhenopacketService(PhenopacketRepository(session))
            result = await service.soft_delete(
                "edit-delete-race",
                "delete wins race",
                actor_id=admin_user.id,
                actor_username=admin_user.username,
                expected_revision=1,
            )
            assert result["deleted_at"] is not None
        delete_complete.set()

    await __import__("asyncio").gather(actor_a_edit(), actor_b_delete())
