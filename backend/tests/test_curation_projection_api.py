"""Projection preview and conflict-resolution API behavior."""

from __future__ import annotations

from copy import deepcopy

from app.phenopackets.curation.projection import project_individual
from app.phenopackets.models import Phenopacket
from tests.test_curation_observation_api import _curation_document


def _assessment(observation_id: str, status: str) -> dict:
    return {
        "assessmentId": f"assessment-{observation_id}",
        "column": "RenalCysts",
        "rawValue": "yes",
        "curationStatus": "CURATED",
        "assessmentStatus": status,
        "findings": [
            {
                "definitionId": "renal-cyst",
                "term": {"id": "HP:0000107", "label": "Renal cyst"},
            }
        ],
    }


async def _insert_conflicting_record(db_session) -> Phenopacket:
    document = _curation_document()
    first = document["hnf1bCuration"]["observationsById"]["report-1"]
    first["phenotypes"] = [_assessment("report-1", "PRESENT")]
    second = deepcopy(first)
    second["observationId"] = "report-2"
    second["identifiers"]["reportId"] = "RPT-2"
    second["phenotypes"] = [_assessment("report-2", "EXCLUDED")]
    document["hnf1bCuration"]["observationsById"]["report-2"] = second
    record = Phenopacket(
        phenopacket_id="curation-projection-317",
        version="2.0",
        revision=1,
        state="draft",
        phenopacket=document,
        subject_id="317",
    )
    db_session.add(record)
    await db_session.commit()
    return record


async def test_preview_does_not_write_and_returns_projected_candidate(
    async_client, db_session, admin_headers
):
    """Preview is a pure request: it projects the report replacement only."""
    record = await _insert_conflicting_record(db_session)
    observation = deepcopy(
        record.phenopacket["hnf1bCuration"]["observationsById"]["report-2"]
    )
    observation["phenotypes"] = [_assessment("report-2", "PRESENT")]

    response = await async_client.post(
        "/api/v2/phenopackets/curation-projection-317/curation/preview",
        json={"observation": observation},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1
    assert response.json()["projection"]["phenopacket"]["phenotypicFeatures"]

    unchanged = await async_client.get(
        "/api/v2/phenopackets/curation-projection-317/curation", headers=admin_headers
    )
    assert unchanged.json()["revision"] == 1
    assert unchanged.json()["projection"]["issues"]


async def test_resolution_appends_only_for_current_conflict_digest(
    async_client, db_session, admin_headers
):
    """A stale conflict is rejected; a current one is persisted as a new entry."""
    record = await _insert_conflicting_record(db_session)
    ledger = await async_client.get(
        "/api/v2/phenopackets/curation-projection-317/curation", headers=admin_headers
    )
    assert ledger.status_code == 200, ledger.text
    issue = ledger.json()["projection"]["issues"][0]
    stale = await async_client.post(
        "/api/v2/phenopackets/curation-projection-317/curation/resolutions",
        json={
            "conflictKey": issue["conflictKey"],
            "candidateSetDigest": "sha256:stale",
            "strategy": "select_observations",
            "selectedObservationIds": ["report-1"],
            "reason": "Use the directly observed positive report.",
            "revision": 1,
        },
        headers=admin_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_conflict"

    # The endpoint exposes a human-readable issue, while the curation model
    # itself keeps the precise candidate digest used for writes.
    profile = record.phenopacket["hnf1bCuration"]
    from app.phenopackets.curation.models import Hnf1bCurationProfile

    typed = Hnf1bCurationProfile.model_validate(profile)
    conflict = project_individual(
        list(typed.observations_by_id.values()), [], algorithm_version="1.0"
    ).blocking_conflicts[0]
    response = await async_client.post(
        "/api/v2/phenopackets/curation-projection-317/curation/resolutions",
        json={
            "conflictKey": conflict.conflict_key,
            "candidateSetDigest": conflict.candidate_set_digest,
            "strategy": "select_observations",
            "selectedObservationIds": ["report-1"],
            "reason": "Use the directly observed positive report.",
            "revision": 1,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert len(response.json()["resolutions"]) == 1
    assert response.json()["projection"]["issues"] == []
