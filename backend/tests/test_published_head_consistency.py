"""Public reads resolve the immutable head, never a mutable working copy."""

import pytest

from app.phenopackets.repositories.visibility import resolve_public_content


@pytest.mark.asyncio
async def test_public_resolution_uses_head_even_without_an_active_draft(
    db_session, published_record
):
    """No working-copy fast path can expose an out-of-band mutable value."""
    published_record.phenopacket = {"id": published_record.phenopacket_id, "leak": True}
    await db_session.flush()

    public = await resolve_public_content(db_session, published_record)

    assert public == {"id": published_record.phenopacket_id}
    assert public != published_record.phenopacket
