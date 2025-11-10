"""Tests for cursor-based pagination.

Tests the cursor pagination implementation added in Phase 2 of issue #62.
"""
import base64
import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.phenopackets.models import Phenopacket


@pytest.mark.asyncio
async def test_cursor_pagination_first_page(async_client: AsyncClient, db_session):
    """Test requesting first page with cursor pagination (no cursor provided)."""
    # When no cursor is provided, it should use offset pagination
    response = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[size]": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should use offset pagination (PageMeta, not CursorPageMeta)
    assert "meta" in data
    assert "page" in data["meta"]
    assert "currentPage" in data["meta"]["page"]  # Offset pagination field
    assert data["meta"]["page"]["pageSize"] == 5


@pytest.mark.asyncio
async def test_cursor_pagination_with_page_after(async_client: AsyncClient, db_session):
    """Test cursor pagination with page[after] parameter."""
    # First, get some real phenopackets from the database
    query = select(Phenopacket).order_by(Phenopacket.created_at.desc()).limit(3)
    result = await db_session.execute(query)
    phenopackets = result.scalars().all()

    if len(phenopackets) < 2:
        pytest.skip("Need at least 2 phenopackets in database")

    # Create cursor for first phenopacket
    first = phenopackets[0]
    cursor_data = {
        "id": str(first.id),
        "created_at": first.created_at.isoformat(),
    }
    cursor_json = json.dumps(cursor_data, separators=(",", ":"))
    cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()

    # Request page AFTER this cursor
    response = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[after]": cursor,
            "page[size]": 2,
        },
    )

    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()

    # Should use cursor pagination (CursorPageMeta)
    assert "meta" in data
    assert "page" in data["meta"]
    assert "pageSize" in data["meta"]["page"]  # Cursor pagination field
    assert "hasNextPage" in data["meta"]["page"]  # Cursor pagination field
    assert "hasPreviousPage" in data["meta"]["page"]  # Cursor pagination field

    # Should have data
    assert "data" in data
    assert isinstance(data["data"], list)

    # Should have cursors in metadata
    assert "startCursor" in data["meta"]["page"]
    assert "endCursor" in data["meta"]["page"]


@pytest.mark.asyncio
async def test_cursor_pagination_stable_results(async_client: AsyncClient, db_session):
    """Test that cursor pagination provides stable results."""
    # Get first page without cursor (offset pagination)
    response1 = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[size]": 10,
        },
    )
    assert response1.status_code == 200

    # Get at least 3 phenopackets to test with
    query = select(Phenopacket).order_by(Phenopacket.created_at.desc()).limit(10)
    result = await db_session.execute(query)
    all_pps = result.scalars().all()

    if len(all_pps) < 5:
        pytest.skip("Need at least 5 phenopackets for this test")

    # Create cursor from 3rd phenopacket
    third_pp = all_pps[2]
    cursor_data = {
        "id": str(third_pp.id),
        "created_at": third_pp.created_at.isoformat(),
    }
    cursor = base64.urlsafe_b64encode(
        json.dumps(cursor_data, separators=(",", ":")).encode()
    ).decode()

    # Request page after this cursor
    response2 = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[after]": cursor,
            "page[size]": 2,
        },
    )
    assert response2.status_code == 200, f"Response: {response2.text}"

    data2 = response2.json()
    assert len(data2["data"]) <= 2

    # The returned records should be AFTER the cursor
    # (4th and 5th phenopackets in our query order)
    if len(all_pps) > 3:
        # Verify the first returned record is different from the cursor record
        first_returned_id = data2["data"][0]["id"]
        assert first_returned_id != third_pp.phenopacket["id"]


@pytest.mark.asyncio
async def test_cursor_encode_decode_functions():
    """Test cursor encoding and decoding functions."""
    from app.phenopackets.routers.crud import decode_cursor, encode_cursor

    # Test data
    test_id = uuid.uuid4()
    test_created_at = datetime.now(timezone.utc).isoformat()

    cursor_data = {
        "id": test_id,
        "created_at": test_created_at,
    }

    # Encode
    cursor = encode_cursor(cursor_data)
    assert isinstance(cursor, str)
    assert len(cursor) > 0

    # Decode
    decoded = decode_cursor(cursor)
    assert isinstance(decoded, dict)
    assert "id" in decoded
    assert "created_at" in decoded

    # ID should be converted back to UUID
    assert isinstance(decoded["id"], uuid.UUID)
    assert decoded["id"] == test_id

    # created_at should be converted to datetime
    assert isinstance(decoded["created_at"], datetime)


@pytest.mark.asyncio
async def test_cursor_pagination_invalid_cursor(async_client: AsyncClient):
    """Test that invalid cursors return proper error."""
    response = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[after]": "invalid-cursor-data",
            "page[size]": 10,
        },
    )

    # Should return 400 Bad Request
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "cursor" in data["detail"].lower()


@pytest.mark.asyncio
async def test_cursor_pagination_with_filters(async_client: AsyncClient, db_session):
    """Test cursor pagination combined with filters."""
    # Get phenopackets with a specific sex
    query = (
        select(Phenopacket)
        .where(Phenopacket.subject_sex == "MALE")
        .order_by(Phenopacket.created_at.desc())
        .limit(3)
    )
    result = await db_session.execute(query)
    male_pps = result.scalars().all()

    if len(male_pps) < 2:
        pytest.skip("Need at least 2 MALE phenopackets")

    # Create cursor for first MALE phenopacket
    first = male_pps[0]
    cursor_data = {
        "id": str(first.id),
        "created_at": first.created_at.isoformat(),
    }
    cursor = base64.urlsafe_b64encode(
        json.dumps(cursor_data, separators=(",", ":")).encode()
    ).decode()

    # Request next page with filter
    response = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[after]": cursor,
            "page[size]": 2,
            "filter[sex]": "MALE",
        },
    )

    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()

    # All returned records should be MALE
    for pp_data in data["data"]:
        if "subject" in pp_data and "sex" in pp_data["subject"]:
            assert pp_data["subject"]["sex"] == "MALE"


@pytest.mark.asyncio
async def test_cursor_pagination_navigation_links(async_client: AsyncClient, db_session):
    """Test that cursor pagination generates proper navigation links."""
    # Get some phenopackets
    query = select(Phenopacket).order_by(Phenopacket.created_at.desc()).limit(5)
    result = await db_session.execute(query)
    pps = result.scalars().all()

    if len(pps) < 3:
        pytest.skip("Need at least 3 phenopackets")

    # Create cursor
    cursor_data = {
        "id": str(pps[0].id),
        "created_at": pps[0].created_at.isoformat(),
    }
    cursor = base64.urlsafe_b64encode(
        json.dumps(cursor_data, separators=(",", ":")).encode()
    ).decode()

    # Request with cursor
    response = await async_client.get(
        "/api/v2/phenopackets/",
        params={
            "page[after]": cursor,
            "page[size]": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have links
    assert "links" in data
    assert "self" in data["links"]
    assert "first" in data["links"]

    # Links should contain cursor parameters
    if data["meta"]["page"]["hasNextPage"]:
        assert "next" in data["links"]
        assert data["links"]["next"] is not None
        assert "page[after]" in data["links"]["next"] or "page%5Bafter%5D" in data["links"]["next"]

    if data["meta"]["page"]["hasPreviousPage"]:
        assert "prev" in data["links"]
        assert data["links"]["prev"] is not None
