"""Tests that the FK-ified audit actor columns round-trip correctly.

After the Wave 5a FK-ify migration, ``phenopackets.created_by_id``,
``.updated_by_id``, ``.deleted_by_id``, and
``phenopacket_audit.changed_by_id`` are nullable BigInt FKs to
``users.id``. This test module verifies:

1. A newly inserted ``_system_migration_`` placeholder user exists
   with ``is_active=False`` and ``is_fixture_user=False``. (The test
   inserts it itself because the autouse conftest fixture truncates
   the ``users`` table between tests — we can't rely on the migration
   seed surviving.)
2. A new phenopacket created through the HTTP API has ``created_by_id``
   set to the authenticated user's id, and the response layer
   renders the username string under the ``created_by`` key.
3. An audit row written during a PUT update has ``changed_by_id``
   populated and resolves back to the actor's username via JOIN.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.models.user import User


def _build_phenopacket_payload(phenopacket_id: str, subject_id: str) -> dict:
    """Return a minimal valid phenopacket body for the HTTP POST / PUT.

    Mirrors the ``_build_phenopacket`` helper in
    ``test_phenopacket_service.py`` — the validator requires a
    ``metaData`` block with ``created`` / ``createdBy`` and at least one
    ``resources`` entry.
    """
    return {
        "id": phenopacket_id,
        "subject": {"id": subject_id, "sex": "MALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
        "metaData": {
            "created": "2026-04-11T00:00:00Z",
            "createdBy": "pytest",
            "phenopacketSchemaVersion": "2.0",
            "resources": [
                {
                    "id": "hp",
                    "name": "Human Phenotype Ontology",
                    "namespacePrefix": "HP",
                    "url": "http://purl.obolibrary.org/obo/hp.owl",
                    "version": "2024-01-01",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_system_migration_placeholder_user_can_exist(
    db_session: AsyncSession,
) -> None:
    """Insert + read the ``_system_migration_`` placeholder user.

    The migration seeds this user on upgrade, but the conftest truncates
    the ``users`` table before each test, so we re-insert here and
    verify the row shape the FK column points at. The important
    invariants are ``is_active=False`` and ``is_fixture_user=False`` —
    operators must never accidentally log in as the placeholder.
    """
    placeholder = User(
        username="_system_migration_",
        email="system-migration@hnf1b-db.local",
        hashed_password=get_password_hash("placeholder-not-loginable"),
        full_name="System Migration Placeholder",
        role="viewer",
        is_active=False,
        is_verified=False,
        is_fixture_user=False,
    )
    db_session.add(placeholder)
    await db_session.commit()
    await db_session.refresh(placeholder)

    result = await db_session.execute(
        text(
            "SELECT id, is_active, is_fixture_user "
            "FROM users WHERE username = '_system_migration_'"
        )
    )
    row = result.fetchone()
    assert row is not None, "placeholder user not found after insert"
    assert row.is_active is False, "placeholder user must be inactive"
    assert row.is_fixture_user is False, "placeholder is not a fixture user"


@pytest.mark.asyncio
async def test_new_phenopacket_has_fk_created_by_id(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    """POST /phenopackets stores ``created_by_id`` = authenticated user.id.

    Verifies both that the underlying column is a BigInt FK and that
    the HTTP response layer still renders the username string under
    ``created_by`` so the API contract is preserved.
    """
    payload = {
        "phenopacket": _build_phenopacket_payload("test-fk-audit-001", "subject-fk-001")
    }
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Response still serialises created_by as a username string (via
    # the eager-loaded FK relationship), not as an integer id.
    assert isinstance(body.get("created_by"), str)
    assert body["created_by"] == admin_user.username

    # Underlying storage is a BigInt FK pointing at the admin user.
    result = await db_session.execute(
        text("SELECT created_by_id FROM phenopackets WHERE phenopacket_id = :pid"),
        {"pid": "test-fk-audit-001"},
    )
    row = result.fetchone()
    assert row is not None
    assert row.created_by_id == admin_user.id


@pytest.mark.asyncio
async def test_audit_row_has_fk_changed_by_id(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    """PUT /phenopackets/{id} writes an audit row with ``changed_by_id``.

    Also verifies the row resolves back to the actor's username via a
    standard JOIN — the shape the new audit query reads.
    """
    # First create a phenopacket
    create_payload = {
        "phenopacket": _build_phenopacket_payload("test-fk-audit-002", "subject-fk-002")
    }
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    # Then update it
    update_payload = {
        "phenopacket": _build_phenopacket_payload(
            "test-fk-audit-002", "subject-fk-002-updated"
        ),
        "revision": 1,
        "change_reason": "test-fk-audit update",
    }
    update_resp = await async_client.put(
        "/api/v2/phenopackets/test-fk-audit-002",
        json=update_payload,
        headers=admin_headers,
    )
    assert update_resp.status_code == 200, update_resp.text

    # Verify the audit row has changed_by_id set and joins back to
    # the admin user's username.
    result = await db_session.execute(
        text(
            """
            SELECT a.changed_by_id, u.username
            FROM phenopacket_audit a
            JOIN users u ON u.id = a.changed_by_id
            WHERE a.phenopacket_id = :pid
            ORDER BY a.changed_at DESC
            LIMIT 1
            """
        ),
        {"pid": "test-fk-audit-002"},
    )
    row = result.fetchone()
    assert row is not None, "audit row not written"
    assert row.changed_by_id == admin_user.id
    assert row.username == admin_user.username
