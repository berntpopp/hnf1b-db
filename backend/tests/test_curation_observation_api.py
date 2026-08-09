"""Public HTTP contract for source-observation curation."""

from __future__ import annotations

from app.phenopackets.models import Phenopacket


def _curation_document() -> dict:
    """Return a minimal manual ledger that projects to a valid packet."""
    observation_id = "report-1"
    return {
        "id": "phenopacket-317",
        "subject": {"id": "317"},
        "phenotypicFeatures": [],
        "diseases": [],
        "interpretations": [],
        "metaData": {"created": "2026-08-09T00:00:00Z", "createdBy": "test"},
        "hnf1bCuration": {
            "schemaVersion": "2.0",
            "sourceSubjectId": "source-317",
            "observationsById": {
                observation_id: {
                    "observationId": observation_id,
                    "origin": "manual",
                    "source": {
                        "provider": "fixture",
                        "datasetId": "registry",
                        "sheet": "Individuals",
                        "manifestSha256": "sha256:fixture",
                    },
                    "identifiers": {
                        "individualId": "317",
                        "sourceSubjectId": "source-317",
                        "reportId": "RPT-1",
                    },
                    "case": {
                        "cohort": {
                            "raw": "born",
                            "sourceStatus": "stated",
                            "value": "born",
                        }
                    },
                }
            },
            "correctionsById": {},
            "resolutionsById": {},
            "projection": {"algorithmVersion": "1.0"},
        },
    }


async def _insert_curation_record(db_session) -> Phenopacket:
    record = Phenopacket(
        phenopacket_id="curation-api-317",
        version="2.0",
        revision=1,
        state="draft",
        phenopacket=_curation_document(),
        subject_id="317",
        created_by_id=None,
        updated_by_id=None,
    )
    db_session.add(record)
    await db_session.commit()
    return record


async def test_curator_gets_source_ledger_and_revision_etag(
    async_client, db_session, admin_headers
):
    """The ledger is curator-only and carries a usable optimistic ETag."""
    await _insert_curation_record(db_session)

    response = await async_client.get(
        "/api/v2/phenopackets/curation-api-317/curation", headers=admin_headers
    )

    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    body = response.json()
    assert body["revision"] == 1
    assert body["observations"][0]["observationId"] == "report-1"
    assert body["projection"]["phenopacket"]["subject"]["id"] == "317"


async def test_correction_requires_a_precondition_and_server_stamps_audit_fields(
    async_client, db_session, admin_headers, admin_user
):
    """Corrections append immutable server-owned audit data, never client values."""
    await _insert_curation_record(db_session)
    body = {
        "jsonPointer": "/observationsById/report-1/case/cohort/value",
        "preimage": "born",
        "postimage": "fetus",
        "reason": "The source cohort token was normalized incorrectly.",
    }

    missing = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/corrections",
        json=body,
        headers=admin_headers,
    )
    assert missing.status_code == 428

    response = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/corrections",
        json={**body, "revision": 1},
        headers=admin_headers,
    )

    assert response.status_code == 200
    correction = response.json()["corrections"][0]
    assert correction["actorId"] == admin_user.id
    assert correction["createdAt"]
    assert correction["sourceManifestSha256"] == "sha256:fixture"
    assert correction["preimage"] == "born"


async def test_report_patch_reprojects_and_preserves_unknown_legacy_root_keys(
    async_client, db_session, admin_headers
):
    """An observation save cannot erase unrelated legacy GA4GH extension data."""
    record = await _insert_curation_record(db_session)
    record.phenopacket["legacyExtension"] = {"preserve": True}
    await db_session.commit()
    observation = _curation_document()["hnf1bCuration"]["observationsById"]["report-1"]
    observation["case"]["cohort"]["value"] = "fetus"

    response = await async_client.patch(
        "/api/v2/phenopackets/curation-api-317/reports/report-1",
        json={
            "observation": observation,
            "revision": 1,
            "changeReason": "Corrected report-level cohort normalization.",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    await db_session.refresh(record)
    assert record.phenopacket["legacyExtension"] == {"preserve": True}
    assert (
        record.phenopacket["hnf1bCuration"]["observationsById"]["report-1"]["case"][
            "cohort"
        ]["value"]
        == "fetus"
    )


async def test_report_patch_returns_path_addressable_profile_errors(
    async_client, db_session, admin_headers
):
    """Cross-report identity violations never leak as a 500 database error."""
    await _insert_curation_record(db_session)
    observation = _curation_document()["hnf1bCuration"]["observationsById"]["report-1"]
    observation["identifiers"]["sourceSubjectId"] = "other-source-subject"

    response = await async_client.patch(
        "/api/v2/phenopackets/curation-api-317/reports/report-1",
        json={
            "observation": observation,
            "revision": 1,
            "changeReason": "Demonstrate validation response shape.",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    error = response.json()["detail"]
    assert error["code"] == "invalid_profile"
    assert error["errors"][0]["path"]
