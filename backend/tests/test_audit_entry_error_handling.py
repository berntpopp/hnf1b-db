"""Wave 5b: audit.create_audit_entry error path maps cleanly to 500, not AssertionError.

Wave 5a exit follow-up #3: audit.py has `assert audit_row is not None`
that fires an AssertionError if the RETURNING round-trip fails. Python's
assert is not caught by PhenopacketService's (IntegrityError,
SQLAlchemyError) except chain, so the raw AssertionError propagates to
the client as a 500 with stack trace.

This test monkeypatches the second `db.execute` call in create_audit_entry
to return a Mock whose fetchone() returns None. Before the fix, this
raises AssertionError. After the fix, it raises ValueError which the
service maps to ServiceDatabaseError -> 500 with a clean detail message.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.audit import create_audit_entry


@pytest.mark.asyncio
async def test_create_audit_entry_raises_value_error_when_fetchone_none():
    """When the post-INSERT SELECT returns None, raise ValueError not AssertionError."""
    mock_session = MagicMock(spec=AsyncSession)

    # First execute call (the INSERT) returns an object whose scalar_one
    # returns a UUID. Second execute call (the SELECT) returns an object
    # whose fetchone returns None -- this is the edge case.
    first_result = MagicMock()
    first_result.scalar_one.return_value = "00000000-0000-0000-0000-000000000000"

    second_result = MagicMock()
    second_result.fetchone.return_value = None

    execute_mock = AsyncMock(side_effect=[first_result, second_result])
    mock_session.execute = execute_mock

    with pytest.raises(ValueError, match="audit entry"):
        await create_audit_entry(
            db=mock_session,
            phenopacket_id="test-err-001",
            action="CREATE",
            old_value=None,
            new_value={"id": "test-err-001"},
            changed_by_id=1,
            change_reason="test",
        )
