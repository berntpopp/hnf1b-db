"""Tests for pagination utilities.

Tests the cursor encode/decode functions (used by search endpoint) and
verifies CRUD endpoint uses offset pagination.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pagination_offset_crud_endpoint_returns_page_metadata(
    fixture_async_client: AsyncClient, fixture_db_session
):
    """Test that CRUD endpoint uses offset pagination with page metadata."""
    response = await fixture_async_client.get(
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
    assert "totalPages" in data["meta"]["page"]  # Offset pagination field
    assert "totalRecords" in data["meta"]["page"]  # Offset pagination field
    assert data["meta"]["page"]["pageSize"] == 5


@pytest.mark.asyncio
async def test_pagination_cursor_encode_decode_preserves_data():
    """Test cursor encoding and decoding preserves ID and timestamp data.

    These utilities are still used by the search endpoint for cursor pagination.
    """
    from app.utils.pagination import decode_cursor, encode_cursor

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
