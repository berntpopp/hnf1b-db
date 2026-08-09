"""Behavioural tests for the source-ledger to GA4GH projection."""

from app.phenopackets.curation.models import (
    AssessmentStatus,
    CurationStatus,
    PhenotypeAssessment,
    PhenotypeFinding,
    ReportObservation,
    SourceManifestRef,
    SubjectObservation,
)
from app.phenopackets.curation.projection import project_individual


def observation(observation_id, status, modifiers=(), sex=None):
    return ReportObservation(
        observation_id=observation_id,
        origin="manual",
        source=SourceManifestRef(
            provider="fixture",
            dataset_id="registry",
            sheet="Individuals",
            manifest_sha256="sha256:m",
        ),
        identifiers=SubjectObservation(
            individual_id="317",
            source_subject_id="source-317",
            report_id=observation_id,
            sex=sex,
        ),
        phenotypes=(
            PhenotypeAssessment(
                assessment_id=f"assessment-{observation_id}",
                column="RenalCysts",
                raw_value="yes",
                curation_status=CurationStatus.CURATED,
                assessment_status=status,
                findings=(
                    PhenotypeFinding(
                        definition_id="renal-cyst",
                        term={"id": "HP:0000107", "label": "Renal cyst"},
                        modifiers=modifiers,
                    ),
                )
                if status in {AssessmentStatus.PRESENT, AssessmentStatus.EXCLUDED}
                else (),
            ),
        ),
    )


def test_present_and_excluded_are_a_blocking_conflict_not_a_first_row_winner():
    """Scientific disagreement cannot be resolved by report ordering."""
    result = project_individual(
        [
            observation("report-a", AssessmentStatus.PRESENT),
            observation("report-b", AssessmentStatus.EXCLUDED),
        ],
        [],
        algorithm_version="1.0",
    )

    assert {conflict.conflict_key for conflict in result.blocking_conflicts} == {
        "phenotype:HP:0000107:polarity"
    }
    assert result.phenopacket["phenotypicFeatures"] == []


def test_silent_and_not_applicable_assessments_remain_ledger_only():
    """NR/NA must never manufacture a GA4GH present or excluded feature."""
    result = project_individual(
        [
            observation("report-a", AssessmentStatus.NOT_REPORTED),
            observation("report-b", AssessmentStatus.NOT_APPLICABLE),
        ],
        [],
        algorithm_version="1.0",
    )

    assert result.phenopacket["phenotypicFeatures"] == []
    assert result.blocking_conflicts == ()


def test_conflicting_compound_laterality_blocks_and_projects_no_arbitrary_modifier_set():
    """Left and right cannot be promoted to an invented bilateral assertion."""
    left = (
        {"id": "HP:0012833", "label": "Unilateral"},
        {"id": "HP:0012835", "label": "Left"},
    )
    right = (
        {"id": "HP:0012833", "label": "Unilateral"},
        {"id": "HP:0012834", "label": "Right"},
    )
    result = project_individual(
        [
            observation("report-a", AssessmentStatus.PRESENT, left),
            observation("report-b", AssessmentStatus.PRESENT, right),
        ],
        [],
        algorithm_version="1.0",
    )

    assert result.phenopacket["phenotypicFeatures"] == [
        {"type": {"id": "HP:0000107", "label": "Renal cyst"}, "excluded": False}
    ]
    assert {conflict.conflict_key for conflict in result.blocking_conflicts} == {
        "phenotype:HP:0000107:modifiers"
    }


def test_stated_sex_disagreement_blocks_projection_instead_of_selecting_a_report():
    """Only one stated sex may project without an explicit curator resolution."""
    female = observation(
        "report-a",
        AssessmentStatus.NOT_REPORTED,
        sex={"raw": "F", "sourceStatus": "stated", "value": "FEMALE"},
    )
    male = observation(
        "report-b",
        AssessmentStatus.NOT_REPORTED,
        sex={"raw": "M", "sourceStatus": "stated", "value": "MALE"},
    )

    result = project_individual([female, male], [], algorithm_version="1.0")
    assert "sex" not in result.phenopacket["subject"]
    assert {conflict.conflict_key for conflict in result.blocking_conflicts} == {
        "subject:sex"
    }
