#!/usr/bin/env python3
"""Manual test script for cursor pagination.

This script tests cursor pagination by:
1. Querying the database to get real UUIDs
2. Creating a cursor with real data
3. Testing page[after] pagination
"""
import asyncio
import base64
import json
import sys
from datetime import datetime

from app.database import async_session_maker
from app.phenopackets.models import Phenopacket
from sqlalchemy import select


async def test_cursor_pagination():
    """Test cursor pagination with real database data."""
    async with async_session_maker() as db:
        # Get first 3 phenopackets to test pagination
        query = select(Phenopacket).order_by(Phenopacket.created_at.desc()).limit(3)
        result = await db.execute(query)
        phenopackets = result.scalars().all()

        if not phenopackets:
            print("❌ No phenopackets found in database")
            return False

        print(f"✅ Found {len(phenopackets)} phenopackets")
        print()

        # Display first phenopacket details
        first = phenopackets[0]
        print("First phenopacket:")
        print(f"  Database ID (UUID): {first.id}")
        print(f"  Phenopacket ID: {first.phenopacket_id}")
        print(f"  Created at: {first.created_at}")
        print()

        # Create cursor for first phenopacket
        cursor_data = {
            "id": str(first.id),
            "created_at": first.created_at.isoformat(),
        }
        cursor_json = json.dumps(cursor_data, separators=(",", ":"))
        cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()

        print("Generated cursor:")
        print(f"  Data: {cursor_data}")
        print(f"  Encoded: {cursor}")
        print()

        # Generate curl command
        print("Test cursor pagination with:")
        print(f'  curl "http://localhost:8000/api/v2/phenopackets/?page%5Bafter%5D={cursor}&page%5Bsize%5D=2"')
        print()

        if len(phenopackets) >= 2:
            second = phenopackets[1]
            print("Expected result:")
            print(f"  Should return records AFTER created_at={first.created_at}")
            print(f"  Next record should be: {second.phenopacket_id} (created_at={second.created_at})")

        return True


if __name__ == "__main__":
    success = asyncio.run(test_cursor_pagination())
    sys.exit(0 if success else 1)
