"""Wave 5a: global soft-delete filter for Phenopacket.

Before this change, every router method that queried Phenopacket had
to remember to add `.where(Phenopacket.deleted_at.is_(None))`. A router
that forgot would leak deleted rows. The SQLAlchemy do_orm_execute
event listener now adds this filter transparently; an escape hatch
via execution_options(include_deleted=True) lets the audit/history
endpoints still see deleted rows.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket


def _valid_payload(phenopacket_id: str, subject_id: str = "s", sex: str = "MALE"):
    """Build a minimal-but-valid phenopacket create payload."""
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
async def test_global_filter_hides_deleted_from_list(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Plain SELECT Phenopacket omits a soft-deleted row even without explicit filter."""
    # Create
    create_resp = await async_client.post(
        "/api/v2/phenopackets/",
        json=_valid_payload("soft-delete-001"),
        headers=admin_headers,
    )
    assert create_resp.status_code == 200, create_resp.text

    # Soft delete
    delete_resp = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/soft-delete-001",
        json={"change_reason": "test"},
        headers=admin_headers,
    )
    assert delete_resp.status_code == 200, delete_resp.text

    # Any plain SELECT Phenopacket should NOT return the deleted row
    stmt = select(Phenopacket).where(Phenopacket.phenopacket_id == "soft-delete-001")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_include_deleted_escape_hatch_still_works(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """execution_options(include_deleted=True) bypasses the global filter."""
    create_resp = await async_client.post(
        "/api/v2/phenopackets/",
        json=_valid_payload("soft-delete-002"),
        headers=admin_headers,
    )
    assert create_resp.status_code == 200, create_resp.text

    delete_resp = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/soft-delete-002",
        json={"change_reason": "test"},
        headers=admin_headers,
    )
    assert delete_resp.status_code == 200, delete_resp.text

    # Query WITH the escape hatch
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id == "soft-delete-002")
        .execution_options(include_deleted=True)
    )
    result = await db_session.execute(stmt)
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.deleted_at is not None
