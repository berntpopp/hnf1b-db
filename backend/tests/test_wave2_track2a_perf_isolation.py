"""Wave 2 Track 2A regression tests:
- PERF-02 (#521): Partial GIN indexes on phenopacket_revisions, dropped dead/duplicate indexes on phenopackets.
- DATA-04 (#526): Draft edit isolation on phenopackets.phenopacket, MVs join head_published_revision_id.
- PERF-05 (#532): Background MV refresh on transitions and mutations, aggregation endpoints wired to MVs.
- PERF-06 (#542): Missing B-tree FK indexes, RAG embedding B-tree/HNSW indexes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.phenopackets.models import Phenopacket
from app.phenopackets.repositories.visibility import resolve_curator_content
from app.phenopackets.services.state_service import PhenopacketStateService
from app.search.mv_refresh import refresh_global_search_index, schedule_refresh_if_stale


@pytest.mark.asyncio
async def test_track2a_indexes_exist_and_dead_indexes_dropped(db_session):
    """Verify PERF-02 and PERF-06 index additions and drops in PostgreSQL catalog."""
    # 1. Check phenopacket_revisions indexes
    result = await db_session.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'phenopacket_revisions'"
        )
    )
    rev_indexes = {row[0]: row[1] for row in result.fetchall()}

    expected_partial_gins = [
        "idx_phenopacket_revisions_features_gin",
        "idx_phenopacket_revisions_interpretations_gin",
        "idx_phenopacket_revisions_diseases_gin",
        "idx_phenopacket_revisions_external_refs_gin",
    ]
    for idx_name in expected_partial_gins:
        assert idx_name in rev_indexes, f"Missing partial GIN index: {idx_name}"
        assert "WHERE (state = 'published'" in rev_indexes[idx_name]

    expected_rev_fks = [
        "idx_phenopacket_revisions_parent_revision_id",
        "idx_phenopacket_revisions_actor_id",
    ]
    for idx_name in expected_rev_fks:
        assert idx_name in rev_indexes, f"Missing FK index: {idx_name}"

    # 2. Check phenopackets indexes
    result = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'phenopackets'")
    )
    pp_indexes = {row[0] for row in result.fetchall()}

    assert "idx_phenopackets_head_published_revision_id" in pp_indexes
    assert "idx_phenopackets_editing_revision_id" in pp_indexes

    # Dropped duplicate & dead indexes must NOT be present
    dropped_indexes = [
        "idx_phenopacket_diseases",
        "idx_phenopacket_interpretations",
        "idx_phenopackets_external_refs",
        "idx_phenopacket_features",
        "idx_phenopacket_hpo_terms",
        "idx_phenopacket_variant_labels",
        "idx_phenopacket_medical_actions",
    ]
    for idx_name in dropped_indexes:
        assert idx_name not in pp_indexes, f"Index {idx_name} should have been dropped"

    # 3. Check publication_fulltext_embeddings indexes
    result = await db_session.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'publication_fulltext_embeddings'"
        )
    )
    emb_indexes = {row[0]: row[1] for row in result.fetchall()}

    assert "idx_publication_fulltext_embeddings_model_pmid_passage" in emb_indexes
    assert "idx_publication_fulltext_embeddings_hnsw" in emb_indexes
    assert "hnsw" in emb_indexes["idx_publication_fulltext_embeddings_hnsw"].lower()


@pytest.mark.asyncio
async def test_track2a_materialized_views_join_published_revisions(db_session):
    """Verify DATA-04: MVs join phenopacket_revisions at head_published_revision_id."""
    result = await db_session.execute(
        text(
            "SELECT matviewname, definition FROM pg_matviews "
            "WHERE matviewname IN ("
            "'mv_feature_aggregation', 'mv_disease_aggregation', "
            "'mv_sex_distribution', 'mv_summary_statistics')"
        )
    )
    views = {row[0]: row[1] for row in result.fetchall()}

    assert len(views) == 4, f"Expected 4 MVs, found: {list(views.keys())}"
    for view_name, definition in views.items():
        assert "phenopacket_revisions" in definition, (
            f"{view_name} does not join phenopacket_revisions"
        )
        assert "head_published_revision_id" in definition, (
            f"{view_name} does not use head_published_revision_id"
        )
        assert "published" in definition, (
            f"{view_name} does not filter for published state"
        )


@pytest.mark.asyncio
async def test_track2a_draft_edit_isolation(db_session, published_record, curator_user):
    """Verify DATA-04: draft edits on published records do not alter phenopacket column or generated columns."""
    initial_content = dict(published_record.phenopacket)
    initial_features_count = published_record.features_count
    initial_has_variant = published_record.has_variant

    svc = PhenopacketStateService(db_session)

    # Edit with new features and different content
    draft_content = {
        "id": published_record.phenopacket_id,
        "subject": {"id": "isolated-draft-subject", "sex": "MALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000107", "label": "Renal cyst"}},
            {"type": {"id": "HP:0000077", "label": "Abnormality of the kidney"}},
            {"type": {"id": "HP:0000083", "label": "Renal insufficiency"}},
        ],
        "metaData": published_record.phenopacket.get("metaData", {}),
    }

    await svc.edit_record(
        published_record.id,
        new_content=draft_content,
        change_reason="curator draft edit",
        expected_revision=published_record.revision,
        actor=curator_user,
    )
    await db_session.flush()

    # Eagerly load the record as the API endpoints do
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Phenopacket)
        .where(Phenopacket.id == published_record.id)
        .options(selectinload(Phenopacket.editing_revision))
    )
    pp_loaded = (await db_session.execute(stmt)).scalar_one()

    # 1. Public-facing phenopacket column and generated columns are unchanged
    assert pp_loaded.phenopacket == initial_content
    assert pp_loaded.features_count == initial_features_count
    assert pp_loaded.has_variant == initial_has_variant

    # 2. Curator content reflects the draft edit via editing_revision
    curator_content = resolve_curator_content(pp_loaded)
    assert curator_content["subject"]["id"] == "isolated-draft-subject"
    assert len(curator_content.get("phenotypicFeatures", [])) == 3

    # 3. MVs after refresh still only see head_published content
    await refresh_global_search_index(db_session)
    # The draft features should not leak into mv_feature_aggregation
    res = await db_session.execute(
        text("SELECT hpo_id FROM mv_feature_aggregation WHERE hpo_id = 'HP:0000083'")
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_track2a_background_refresh_scheduling(
    db_session, published_record, admin_user
):
    """Verify PERF-05: schedule_refresh_if_stale is dispatched via BackgroundTasks."""
    tasks = []

    class MockBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            tasks.append((func, args, kwargs))

    bg = MockBackgroundTasks()
    svc = PhenopacketStateService(db_session, background_tasks=bg)

    # Archive a published phenopacket
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="test archival",
        expected_revision=published_record.revision,
        actor=admin_user,
    )

    # Verify background task was added
    assert len(tasks) == 1
    func, _, _ = tasks[0]
    assert func == schedule_refresh_if_stale
