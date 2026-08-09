"""Public behaviour of the strict source-observation profile contract."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.phenopackets.curation.models import (
    AssessmentStatus,
    CurationCorrection,
    CurationStatus,
    Hnf1bCurationProfile,
    ObservedValue,
    PhenotypeAssessment,
    ReportObservation,
    SourceManifestRef,
    SourceStatus,
    SubjectObservation,
)

OBSERVATION_ID = "7ae87ce5-3b8f-5a22-927c-0d8f5a9c71c1"


def report() -> ReportObservation:
    return ReportObservation(
        observation_id=OBSERVATION_ID,
        origin="manual",
        source=SourceManifestRef(
            provider="fixture",
            dataset_id="hnf1b-registry",
            sheet="Individuals",
            row_number=7,
            row_hmac_sha256="hmac-sha256:abc",
            manifest_sha256="sha256:manifest",
        ),
        identifiers=SubjectObservation(
            individual_id="317",
            source_subject_id="source-317",
            report_id="RPT-001",
        ),
    )


def test_scalar_and_phenotype_status_axes_are_not_interchangeable():
    """A workflow state cannot silently stand in for clinical source meaning."""
    scalar = ObservedValue[str](
        raw="not reported", source_status=SourceStatus.NOT_REPORTED, value=None
    )
    assert scalar.source_status is SourceStatus.NOT_REPORTED

    untouched = PhenotypeAssessment(
        assessment_id="assessment-1",
        column="RenalCysts",
        raw_value="",
        curation_status=CurationStatus.UNCURATED,
        assessment_status=None,
    )
    assert untouched.assessment_status is None

    curated = untouched.model_copy(
        update={
            "curation_status": CurationStatus.CURATED,
            "assessment_status": AssessmentStatus.NOT_REPORTED,
        }
    )
    assert curated.assessment_status is AssessmentStatus.NOT_REPORTED

    with pytest.raises(ValidationError):
        PhenotypeAssessment(
            assessment_id="assessment-2",
            column="RenalCysts",
            raw_value="yes",
            curation_status=CurationStatus.UNCURATED,
            assessment_status=AssessmentStatus.PRESENT,
        )
    with pytest.raises(ValidationError):
        PhenotypeAssessment(
            assessment_id="assessment-3",
            column="RenalCysts",
            raw_value="yes",
            curation_status=CurationStatus.CURATED,
            assessment_status=None,
        )


def test_corrections_preserve_raw_preimage_and_are_append_only_profile_entries():
    """Corrected interpretation cannot overwrite source evidence in-place."""
    correction = CurationCorrection(
        correction_id="correction-1",
        json_pointer="/observationsById/7ae87ce5-3b8f-5a22-927c-0d8f5a9c71c1/case/sex",
        preimage={"raw": "f"},
        postimage={"value": "FEMALE"},
        source_manifest_sha256="sha256:manifest",
        reason="Source legend clarifies abbreviation.",
        actor_id=12,
        created_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    profile = Hnf1bCurationProfile(
        source_subject_id="source-317",
        observations_by_id={OBSERVATION_ID: report()},
        corrections_by_id={correction.correction_id: correction},
    )
    assert profile.corrections_by_id["correction-1"].preimage == {"raw": "f"}
    with pytest.raises(ValidationError):
        ObservedValue[str](raw="f", source_status="stated", value="FEMALE", extra="no")


def test_profile_requires_observation_map_key_and_source_subject_binding_to_match():
    """A report cannot move between subjects or be duplicated under another key."""
    with pytest.raises(ValidationError):
        Hnf1bCurationProfile(
            source_subject_id="source-317",
            observations_by_id={"other": report()},
        )
    with pytest.raises(ValidationError):
        Hnf1bCurationProfile(
            source_subject_id="another-source-subject",
            observations_by_id={OBSERVATION_ID: report()},
        )


def test_profile_serialization_agrees_with_json_schema_and_rejects_unknown_fields():
    """Legacy JSON validation receives the same closed new-profile shape as Pydantic."""
    from app.phenopackets.validation.schema_validator import SchemaValidator

    profile = Hnf1bCurationProfile(
        source_subject_id="source-317", observations_by_id={OBSERVATION_ID: report()}
    )
    document = {
        "id": "phenopacket-317",
        "subject": {"id": "317"},
        "metaData": {
            "created": "2026-08-09T00:00:00Z",
            "createdBy": "test",
            "resources": [],
        },
        "hnf1bCuration": profile.model_dump(by_alias=True, mode="json"),
    }
    assert SchemaValidator().validate(document) == []
    document["hnf1bCuration"]["observationsById"][OBSERVATION_ID]["unexpected"] = True
    assert SchemaValidator().validate(document)
