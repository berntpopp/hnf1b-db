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
async def test_delete_without_revision_still_works(
    async_client: AsyncClient, admin_headers: dict
):
    """Backwards compat: clients that omit `revision` are not broken.

    Revision is optional; if not provided, the delete proceeds without
    a check. This preserves existing client behavior until the frontend
    is updated.
    """
    create_payload = _valid_payload("delete-revision-optional")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-optional",
        json={"change_reason": "no revision"},
        headers=admin_headers,
    )
    assert response.status_code == 200
