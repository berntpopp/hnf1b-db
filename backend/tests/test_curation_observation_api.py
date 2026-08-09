"""Public HTTP contract for source-observation curation."""

from __future__ import annotations

from copy import deepcopy

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
    assert missing.json()["detail"]["code"] == "precondition_required"
    assert missing.json()["detail"]["errors"]

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
    assert (
        correction["correctionId"]
        in response.json()["observations"][0]["case"]["cohort"]["correctionIds"]
    )


async def test_report_patch_cannot_overwrite_correction_owned_value(
    async_client, db_session, admin_headers
):
    """A report replacement cannot bypass the append-only correction ledger."""
    await _insert_curation_record(db_session)
    corrected = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/corrections",
        json={
            "jsonPointer": "/observationsById/report-1/case/cohort/value",
            "preimage": "born",
            "postimage": "fetus",
            "reason": "Correct source normalization.",
            "revision": 1,
        },
        headers=admin_headers,
    )
    assert corrected.status_code == 200, corrected.text
    observation = corrected.json()["observations"][0]
    observation["case"]["cohort"]["value"] = "neonate"

    response = await async_client.patch(
        "/api/v2/phenopackets/curation-api-317/reports/report-1",
        json={
            "observation": observation,
            "revision": 2,
            "changeReason": "Attempt to overwrite corrected value.",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "immutable_source"


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


async def test_report_patch_returns_path_addressable_immutable_source_errors(
    async_client, db_session, admin_headers
):
    """Source identity changes never leak as a 500 database error."""
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
    assert error["code"] == "immutable_source"
    assert error["errors"][0]["path"]


async def test_report_patch_cannot_change_nested_raw_or_provenance(
    async_client, db_session, admin_headers
):
    """Source evidence is immutable below the report root as well."""
    record = await _insert_curation_record(db_session)
    report = record.phenopacket["hnf1bCuration"]["observationsById"]["report-1"]
    report["phenotypes"] = [
        {
            "assessmentId": "assessment-report-1",
            "column": "RenalCysts",
            "rawValue": "yes",
            "curationStatus": "UNCURATED",
            "assessmentStatus": None,
        }
    ]
    await db_session.commit()

    changed = _curation_document()["hnf1bCuration"]["observationsById"]["report-1"]
    changed.update(report)
    changed["source"] = {**report["source"], "sheet": "Other sheet"}
    changed["phenotypes"] = [{**report["phenotypes"][0], "rawValue": "no"}]
    response = await async_client.patch(
        "/api/v2/phenopackets/curation-api-317/reports/report-1",
        json={
            "observation": changed,
            "revision": 1,
            "changeReason": "Attempt to alter imported evidence.",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "immutable_source"


async def test_legacy_put_is_blocked_for_observation_backed_packets(
    async_client, db_session, admin_headers
):
    """Whole-ledger replacement must use the append/report curation API."""
    record = await _insert_curation_record(db_session)

    response = await async_client.put(
        "/api/v2/phenopackets/curation-api-317",
        json={
            "phenopacket": record.phenopacket,
            "revision": 1,
            "change_reason": "Attempt wholesale source ledger replacement.",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "curation_api_required"


async def test_get_projection_uses_active_correction_values(
    async_client, db_session, admin_headers
):
    """A correction is an overlay for GET/preview, not merely audit metadata."""
    record = await _insert_curation_record(db_session)
    report = record.phenopacket["hnf1bCuration"]["observationsById"]["report-1"]
    report["identifiers"]["sex"] = {
        "raw": "M",
        "sourceStatus": "stated",
        "value": "MALE",
    }
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/corrections",
        json={
            "jsonPointer": "/observationsById/report-1/identifiers/sex/value",
            "preimage": "MALE",
            "postimage": "FEMALE",
            "reason": "Correct source normalization.",
            "revision": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["projection"]["phenopacket"]["subject"]["sex"] == "FEMALE"
    get_response = await async_client.get(
        "/api/v2/phenopackets/curation-api-317/curation", headers=admin_headers
    )
    assert (
        get_response.json()["projection"]["phenopacket"]["subject"]["sex"] == "FEMALE"
    )


async def test_correction_validates_its_active_postimage_against_domains(
    async_client, db_session, admin_headers
):
    """A correction cannot bypass controlled vocabulary validation."""
    record = await _insert_curation_record(db_session)
    report = record.phenopacket["hnf1bCuration"]["observationsById"]["report-1"]
    report["classification"] = {
        "system": {"raw": "ACMG", "sourceStatus": "stated", "value": "ACMG"}
    }
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/corrections",
        json={
            "jsonPointer": "/observationsById/report-1/classification/system/value",
            "preimage": "ACMG",
            "postimage": "not-a-classification-system",
            "reason": "Exercise controlled-vocabulary validation.",
            "revision": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_domain"


async def test_curation_request_validation_uses_structured_422_errors(
    async_client, db_session, admin_headers
):
    """Pydantic request failures share the ledger API's error contract."""
    await _insert_curation_record(db_session)

    response = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/resolutions",
        json={
            "conflictKey": "subject:sex",
            "candidateSetDigest": "sha256:fixture",
            "strategy": "not-a-strategy",
            "reason": "Exercise route request validation.",
            "revision": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_request"
    assert detail["errors"][0]["path"]


async def test_resolution_resolved_value_is_typed_at_request_boundary(
    async_client, db_session, admin_headers
):
    """Conflict-specific resolved values fail as structured request errors."""
    await _insert_curation_record(db_session)

    response = await async_client.post(
        "/api/v2/phenopackets/curation-api-317/curation/resolutions",
        json={
            "conflictKey": "subject:sex",
            "candidateSetDigest": "sha256:fixture",
            "strategy": "resolved_value",
            "resolvedValue": "not-a-ga4gh-sex",
            "reason": "Exercise typed resolved values.",
            "revision": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_request"


async def test_correction_requires_explicit_predecessor_for_same_value(
    async_client, db_session, admin_headers
):
    """Sequential corrections have a deterministic explicit predecessor chain."""
    await _insert_curation_record(db_session)
    url = "/api/v2/phenopackets/curation-api-317/curation/corrections"
    first = await async_client.post(
        url,
        json={
            "jsonPointer": "/observationsById/report-1/case/cohort/value",
            "preimage": "born",
            "postimage": "fetus",
            "reason": "First correction.",
            "revision": 1,
        },
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text
    correction_id = first.json()["corrections"][0]["correctionId"]

    missing_predecessor = await async_client.post(
        url,
        json={
            "jsonPointer": "/observationsById/report-1/case/cohort/value",
            "preimage": "fetus",
            "postimage": "neonate",
            "reason": "Missing explicit predecessor.",
            "revision": 2,
        },
        headers=admin_headers,
    )
    assert missing_predecessor.status_code == 422
    assert (
        missing_predecessor.json()["detail"]["code"]
        == "correction_predecessor_required"
    )

    chained = await async_client.post(
        url,
        json={
            "jsonPointer": "/observationsById/report-1/case/cohort/value",
            "preimage": "fetus",
            "postimage": "neonate",
            "reason": "Explicitly supersede the first correction.",
            "supersedesCorrectionId": correction_id,
            "revision": 2,
        },
        headers=admin_headers,
    )
    assert chained.status_code == 200, chained.text
    assert len(chained.json()["corrections"]) == 2


async def test_preview_runs_domain_and_parser_validation_without_writing(
    async_client, db_session, admin_headers
):
    """Preview executes the report write validation pipeline without a revision."""
    record = await _insert_curation_record(db_session)
    report = record.phenopacket["hnf1bCuration"]["observationsById"]["report-1"]
    report["classification"] = {
        "system": {"raw": "ACMG", "sourceStatus": "stated", "value": "ACMG"}
    }
    report["identifiers"]["sex"] = {
        "raw": "M",
        "sourceStatus": "stated",
        "value": "MALE",
    }
    await db_session.commit()
    url = "/api/v2/phenopackets/curation-api-317/curation/preview"

    invalid_domain = deepcopy(report)
    invalid_domain["classification"]["system"]["value"] = "not-a-system"
    domain_response = await async_client.post(
        url, json={"observation": invalid_domain}, headers=admin_headers
    )
    assert domain_response.status_code == 422, domain_response.text
    assert domain_response.json()["detail"]["code"] == "invalid_domain"

    # A pre-existing malformed normalized value can occur in legacy source
    # truth. Preview must still take the canonical parser path before it
    # returns an otherwise plausible projection.
    report["identifiers"]["sex"]["value"] = "not-a-ga4gh-sex"
    await db_session.commit()
    invalid_parser = deepcopy(report)
    parser_response = await async_client.post(
        url, json={"observation": invalid_parser}, headers=admin_headers
    )
    assert parser_response.status_code == 422, parser_response.text
    assert parser_response.json()["detail"]["code"] == "parser_error"
    await db_session.refresh(record)
    assert record.revision == 1
