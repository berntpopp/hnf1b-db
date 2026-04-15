"""After clone-to-draft, subsequent PUTs route to _inplace_save (not 409)."""

import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_second_put_after_clone_is_inplace(
    db_session, published_record, curator_user
):
    """Second PUT on a clone-cycle record routes to inplace-save, not 409."""
    svc = PhenopacketStateService(db_session)
    pp = published_record

    # First PUT — clone to draft
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "first-edit"}},
        change_reason="first edit",
        expected_revision=pp.revision,
        actor=curator_user,
    )
    assert pp.editing_revision_id is not None
    first_editing_id = pp.editing_revision_id

    # Second PUT — must inplace-save, not raise EditInProgress
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "second-edit"}},
        change_reason="iterating",
        expected_revision=pp.revision,
        actor=curator_user,
    )
    # editing_revision_id unchanged (inplace-save doesn't create new row)
    assert pp.editing_revision_id == first_editing_id
    assert pp.phenopacket["subject"]["id"] == "second-edit"
    # pp.state still 'published' (I8)
    assert pp.state == "published"
