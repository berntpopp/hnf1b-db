"""HTTP-level tests for visibility filter routing — Wave 7 D.1 Tasks 12–13.

Every endpoint that reads from ``phenopackets`` must:
  - For anonymous callers: return only ``state='published'`` rows with
    ``deleted_at IS NULL`` and ``head_published_revision_id IS NOT NULL``
    (public_filter invariants I3 + I7).
  - For curators: obey ``curator_filter`` (draft + published, no deleted
    unless explicitly requested, no archived by default).

TDD: these tests are written **before** the implementation is complete;
the first run should show FAILUREs on files that still use only
``deleted_at IS NULL`` without the full public-state check.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Shared inline helper — creates a draft + a published phenopacket in the
# current db_session without depending on cross-session fixtures.
# ---------------------------------------------------------------------------


async def _insert_draft_and_published(db_session, curator_user, admin_user):
    """Insert one draft + one published record and return (draft, published)."""
    from app.phenopackets.models import Phenopacket, PhenopacketRevision

    draft = Phenopacket(
        phenopacket_id="vis-draft-search-1",
        phenopacket={"id": "vis-draft-search-1"},
        state="draft",
        revision=1,
        draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    published = Phenopacket(
        phenopacket_id="vis-published-search-1",
        phenopacket={"id": "vis-published-search-1"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
        subject_sex="UNKNOWN_SEX",
    )
    db_session.add(draft)
    db_session.add(published)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=published.id,
        revision_number=1,
        state="published",
        content_jsonb=published.phenopacket,
        change_reason="init",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()
    published.head_published_revision_id = rev.id
    await db_session.commit()
    return draft, published


# ---------------------------------------------------------------------------
# Task 12: Search endpoint — anonymous caller must NOT see drafts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_excludes_drafts_from_anonymous(
    async_client,
    db_session,
    curator_user,
    admin_user,
):
    """Anonymous GET /phenopackets/search must not return draft records."""
    draft, published = await _insert_draft_and_published(
        db_session, curator_user, admin_user
    )

    r = await async_client.get("/api/v2/phenopackets/search")
    assert r.status_code == 200

    ids_in_response = {item.get("id") for item in r.json().get("data", [])}
    assert draft.phenopacket_id not in ids_in_response, (
        f"Draft {draft.phenopacket_id!r} must not appear in anonymous search results"
    )
    assert published.phenopacket_id in ids_in_response


@pytest.mark.asyncio
async def test_search_includes_drafts_for_curator(
    async_client,
    curator_headers,
    db_session,
    curator_user,
    admin_user,
):
    """Curator GET /phenopackets/search should include draft records."""
    draft, published = await _insert_draft_and_published(
        db_session, curator_user, admin_user
    )

    r = await async_client.get("/api/v2/phenopackets/search", headers=curator_headers)
    assert r.status_code == 200

    ids_in_response = {item.get("id") for item in r.json().get("data", [])}
    assert draft.phenopacket_id in ids_in_response, (
        f"Draft {draft.phenopacket_id!r} must appear in curator search results"
    )
    assert published.phenopacket_id in ids_in_response


@pytest.mark.asyncio
async def test_search_facets_excludes_drafts_from_anonymous(
    async_client,
    db_session,
    curator_user,
    admin_user,
):
    """Anonymous GET /phenopackets/search/facets must not count draft records."""
    draft, _ = await _insert_draft_and_published(db_session, curator_user, admin_user)

    r = await async_client.get("/api/v2/phenopackets/search/facets")
    assert r.status_code == 200
    assert draft.phenopacket_id not in r.text


# ---------------------------------------------------------------------------
# Task 12: Comparisons endpoint — anonymous caller must NOT see drafts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comparisons_excludes_drafts_from_anonymous(
    async_client,
    db_session,
    curator_user,
    admin_user,
):
    """Anonymous access to comparisons variant-types must not return draft data."""
    draft, _ = await _insert_draft_and_published(db_session, curator_user, admin_user)

    r = await async_client.get(
        "/api/v2/phenopackets/compare/variant-types",
        params={"variant_type1": "frameshift", "variant_type2": "missense"},
    )
    assert r.status_code == 200
    assert draft.phenopacket_id not in r.text


# ---------------------------------------------------------------------------
# Task 13: Aggregation endpoints — anonymous callers must NOT see drafts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v2/phenopackets/aggregate/summary",
        "/api/v2/phenopackets/aggregate/by-feature",
        "/api/v2/phenopackets/aggregate/sex-distribution",
        "/api/v2/phenopackets/aggregate/by-disease",
        "/api/v2/phenopackets/aggregate/publication-types",
    ],
)
async def test_aggregations_exclude_drafts_from_anonymous(
    async_client,
    endpoint,
    db_session,
    curator_user,
    admin_user,
):
    """All aggregation endpoints must not include draft data in their output."""
    draft, _ = await _insert_draft_and_published(db_session, curator_user, admin_user)

    r = await async_client.get(endpoint)
    assert r.status_code == 200
    assert draft.phenopacket_id not in r.text, (
        f"Draft {draft.phenopacket_id!r} leaked into {endpoint}"
    )


# ---------------------------------------------------------------------------
# Task 13: crud_related by-variant — anonymous must NOT see drafts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_by_variant_excludes_drafts_from_anonymous(
    async_client,
    db_session,
    curator_user,
):
    """Anonymous GET /phenopackets/by-variant/{id} must not return draft records."""
    from app.phenopackets.models import Phenopacket

    variant_id = "vis-test-variant-unique-xyz-123"
    pp = Phenopacket(
        phenopacket_id="vis-draft-variant-1",
        phenopacket={
            "id": "vis-draft-variant-1",
            "subject": {"id": "subj-vis-draft-var"},
            "phenotypicFeatures": [],
            "interpretations": [
                {
                    "id": "interp-1",
                    "progressStatus": "SOLVED",
                    "diagnosis": {
                        "disease": {"id": "OMIM:189500"},
                        "genomicInterpretations": [
                            {
                                "subjectOrBiosampleId": "subj-vis-draft-var",
                                "interpretationStatus": "PATHOGENIC",
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": variant_id,
                                        "geneContext": {
                                            "valueId": "HGNC:11367",
                                            "symbol": "HNF1B",
                                        },
                                    }
                                },
                            }
                        ],
                    },
                }
            ],
        },
        state="draft",
        revision=1,
        draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    db_session.add(pp)
    await db_session.commit()

    r = await async_client.get(f"/api/v2/phenopackets/by-variant/{variant_id}")
    assert r.status_code == 200
    assert "vis-draft-variant-1" not in r.text, (
        "Draft 'vis-draft-variant-1' leaked into by-variant response"
    )


@pytest.mark.asyncio
async def test_by_publication_excludes_drafts_from_anonymous(
    async_client,
    db_session,
    curator_user,
):
    """Anonymous GET /phenopackets/by-publication/{pmid} must not return draft records."""
    from app.phenopackets.models import Phenopacket

    draft_pp = Phenopacket(
        phenopacket_id="vis-draft-pub-1",
        phenopacket={
            "id": "vis-draft-pub-1",
            "subject": {"id": "subj-draft-pub"},
            "phenotypicFeatures": [],
            "interpretations": [],
            "metaData": {
                "externalReferences": [
                    {"id": "PMID:99999999", "description": "test pub"}
                ]
            },
        },
        state="draft",
        revision=1,
        draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    db_session.add(draft_pp)
    await db_session.commit()

    r = await async_client.get("/api/v2/phenopackets/by-publication/99999999")
    # Either 404 (no published records for this PMID) or 200 with draft absent
    if r.status_code == 200:
        assert "vis-draft-pub-1" not in r.text, (
            "Draft 'vis-draft-pub-1' leaked into by-publication response"
        )
    else:
        assert r.status_code == 404
