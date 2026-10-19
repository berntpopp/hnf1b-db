"""Tests for pagination utilities.

Tests the cursor encode/decode functions (used by search endpoint) and
verifies CRUD endpoint uses offset pagination.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.utils.pagination import decode_cursor, encode_cursor


@pytest.mark.asyncio
async def test_crud_endpoint_uses_offset_pagination(
    async_client: AsyncClient, db_session
):
    """Test that CRUD endpoint uses offset pagination (not cursor)."""
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
    assert "totalPages" in data["meta"]["page"]  # Offset pagination field
    assert "totalRecords" in data["meta"]["page"]  # Offset pagination field
    assert data["meta"]["page"]["pageSize"] == 5


@pytest.mark.asyncio
async def test_cursor_encode_decode_functions():
    """Test cursor encoding and decoding functions.

    These utilities are still used by the search endpoint for cursor pagination.
    """
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
async def test_cursor_decode_invalid_primitives():
    """Test that non-dict JSON cursors raise HTTPException 400 instead of 500 [BUG-01]."""
    # 'MTIz' decodes to 123 (JSON int)
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor("MTIz")
    assert exc_info.value.status_code == 400

    # 'ImFiYyI=' decodes to "abc" (JSON string)
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor("ImFiYyI=")
    assert exc_info.value.status_code == 400

    # 'WzEsIDIsIDNd' decodes to [1, 2, 3] (JSON array)
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor("WzEsIDIsIDNd")
    assert exc_info.value.status_code == 400

