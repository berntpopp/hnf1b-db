"""Stable UUIDv5 and HMAC identity behaviour for source observations."""

from app.phenopackets.curation.identifiers import (
    assessment_id_for,
    observation_id_for,
    row_hmac_sha256,
)


def test_observation_identity_depends_only_on_source_dataset_and_canonical_report_id():
    """Row ordering/content revisions must never create another source report identity."""
    first = observation_id_for("google_sheets", "hnf1b-registry", " RPT-001 ")
    second = observation_id_for("google_sheets", "hnf1b-registry", "RPT-001")
    changed_row = observation_id_for("google_sheets", "hnf1b-registry", "RPT-001")

    assert first == second == changed_row
    assert observation_id_for("google_sheets", "hnf1b-registry", "RPT-002") != first


def test_assessment_identity_and_row_fingerprint_are_stable_but_not_plain_hashes():
    """Assessment keys are source-field based; fingerprints use an HMAC namespace."""
    observation_id = observation_id_for("fixture", "dataset", "report")
    assert assessment_id_for(
        observation_id, "phenotype", "RenalCysts", "0"
    ) == assessment_id_for(observation_id, "phenotype", "RenalCysts", "0")
    assert assessment_id_for(
        observation_id, "phenotype", "RenalCysts", "0"
    ) != assessment_id_for(observation_id, "phenotype", "RenalCysts", "1")
    fingerprint = row_hmac_sha256(b"source row", b"test-secret")
    assert fingerprint.startswith("hmac-sha256:")
    assert "source row" not in fingerprint
