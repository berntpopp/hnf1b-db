"""POST /phenopackets/{id}/transitions response shape.

Verifies that the transitions endpoint response body carries
``effective_state`` alongside ``state`` after the manual dict
augmentation was removed (refactor Task 8).  The builder now
populates all state fields via ``include_state=True`` (spec §4.2.4–6).
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_post_transition_response_includes_effective_state(
    async_client,
    curator_headers,
    draft_record,
):
    """Response body carries effective_state alongside state after a transition.

    Uses the ``draft_record`` fixture (state='draft', no head_published_revision_id)
    so that ``draft → in_review`` advances both ``pp.state`` and the
    ``editing_revision.state``.  Either path gives ``effective_state == 'in_review'``.
    """
    resp = await async_client.post(
        f"/api/v2/phenopackets/{draft_record.phenopacket_id}/transitions",
        json={"to_state": "in_review", "reason": "ready for review", "revision": 1},
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()

    pp = body["phenopacket"]
    # Core state fields populated by build_phenopacket_response(include_state=True)
    assert pp["state"] == "in_review"
    assert "head_published_revision_id" in pp
    assert "editing_revision_id" in pp
    assert "draft_owner_id" in pp

    # effective_state is the key addition from Task 7 / spec §4.2.4
    assert "effective_state" in pp
    assert pp["effective_state"] == "in_review"
