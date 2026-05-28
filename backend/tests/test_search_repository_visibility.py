"""Visibility tests for ``PhenopacketSearchRepository`` (Wave A Task A3).

The repository's public (``is_curator=False``) branch must source JSONB content
from the head-published revision (``phenopacket_revisions.content_jsonb``), never
the working copy ``phenopackets.phenopacket`` — which may hold an unpublished
clone-to-draft edit mid-edit.

The repository is wrapped by ``PhenopacketSearchService``; it is not currently
mounted on a public HTTP route, so we exercise it directly against the test
session (the same code path the service uses, with ``is_curator`` defaulting to
the public branch).
"""

from __future__ import annotations

import json

import pytest

from app.search.repositories import PhenopacketSearchRepository


@pytest.mark.asyncio
async def test_repository_search_returns_head_published(
    db_session, clone_in_progress_record
):
    """Public repository search must return head-published content, not working copy."""
    repo = PhenopacketSearchRepository(db_session)
    rows = await repo.search(is_curator=False, limit=100)

    serialized = json.dumps(rows, default=str)
    assert "_secret_working_copy" not in serialized
    assert "LEAKED-DRAFT-SUBJECT" not in serialized

    # The record is still visible (just with old published content).
    pid = clone_in_progress_record["record"].phenopacket_id
    ids = {row["phenopacket_id"] for row in rows}
    assert pid in ids


@pytest.mark.asyncio
async def test_repository_count_includes_clone_in_progress(
    db_session, clone_in_progress_record
):
    """A published-but-mid-edit record is still counted by the public branch."""
    repo = PhenopacketSearchRepository(db_session)
    count = await repo.count(is_curator=False)
    assert count >= 1


@pytest.mark.asyncio
async def test_repository_search_text_query_uses_head_content(
    db_session, clone_in_progress_record
):
    """Full-text/ILIKE query must not match on the leaked working-copy marker."""
    repo = PhenopacketSearchRepository(db_session)
    rows = await repo.search(
        query="_secret_working_copy", is_curator=False, limit=100
    )
    serialized = json.dumps(rows, default=str)
    assert "_secret_working_copy" not in serialized
    assert "LEAKED-DRAFT-SUBJECT" not in serialized
