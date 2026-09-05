"""Public publication and sitemap reads stay pinned to the published head."""

from datetime import datetime, timezone
from urllib.parse import quote

import pytest

from app.phenopackets.models import Phenopacket, PhenopacketRevision


def _content(record_id: str, *, pmid: str, variant_id: str) -> dict:
    return {
        "id": record_id,
        "subject": {"id": f"subject-{record_id}", "sex": "UNKNOWN_SEX"},
        "interpretations": [
            {
                "id": f"interpretation-{record_id}",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": f"subject-{record_id}",
                            "variantInterpretation": {
                                "variationDescriptor": {"id": variant_id}
                            },
                        }
                    ]
                },
            }
        ],
        "metaData": {
            "created": "2020-01-01T00:00:00Z",
            "createdBy": "public-head-regression",
            "phenopacketSchemaVersion": "2.0",
            "resources": [],
            "externalReferences": [{"id": f"PMID:{pmid}"}],
        },
    }


@pytest.mark.asyncio
async def test_publication_list_and_sitemaps_use_only_divergent_published_head(
    async_client,
    db_session,
    admin_user,
):
    """A replacement candidate cannot leak identifiers or its update time."""
    record_id = "public-head-publication-sitemap"
    public_pmid = "99100001"
    private_pmid = "99100002"
    public_variant = "public-variant:99100001"
    private_variant = "private-variant:99100002"
    public_content = _content(
        record_id,
        pmid=public_pmid,
        variant_id=public_variant,
    )
    private_working_copy = _content(
        record_id,
        pmid=private_pmid,
        variant_id=private_variant,
    )

    record = Phenopacket(
        phenopacket_id=record_id,
        phenopacket=private_working_copy,
        subject_id=f"subject-{record_id}",
        subject_sex="UNKNOWN_SEX",
        created_by_id=admin_user.id,
        state="draft",
        revision=2,
    )
    db_session.add(record)
    await db_session.flush()
    published_at = datetime(2020, 1, 2, 12, tzinfo=timezone.utc)
    head = PhenopacketRevision(
        record_id=record.id,
        revision_number=1,
        state="published",
        content_jsonb=public_content,
        change_reason="Initial public head",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
        created_at=published_at,
    )
    db_session.add(head)
    await db_session.flush()
    record.state = "published"
    record.head_published_revision_id = head.id
    record.updated_at = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
    await db_session.commit()

    publications = await async_client.get("/api/v2/publications/?page[size]=100")
    assert publications.status_code == 200
    pmids = {item["pmid"] for item in publications.json()["data"]}
    assert public_pmid in pmids
    assert private_pmid not in pmids

    variants = await async_client.get("/api/v2/seo/sitemap-variants.xml")
    assert variants.status_code == 200
    assert quote(public_variant, safe="") in variants.text
    assert quote(private_variant, safe="") not in variants.text
    assert "<lastmod>2020-01-02</lastmod>" in variants.text
    assert "<lastmod>2026-08-30</lastmod>" not in variants.text

    publication_sitemap = await async_client.get("/api/v2/seo/sitemap-publications.xml")
    assert publication_sitemap.status_code == 200
    assert f"/publications/{public_pmid}" in publication_sitemap.text
    assert f"/publications/{private_pmid}" not in publication_sitemap.text
    assert "<lastmod>2020-01-02</lastmod>" in publication_sitemap.text
    assert "<lastmod>2026-08-30</lastmod>" not in publication_sitemap.text

    phenopackets = await async_client.get("/api/v2/seo/sitemap-phenopackets.xml")
    assert phenopackets.status_code == 200
    assert f"/phenopackets/{record_id}" in phenopackets.text
    assert "<lastmod>2020-01-02</lastmod>" in phenopackets.text
    assert "<lastmod>2026-08-30</lastmod>" not in phenopackets.text
