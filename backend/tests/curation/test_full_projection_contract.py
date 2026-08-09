"""Regression coverage for lossless typed source facts in GA4GH projection."""

from google.protobuf.json_format import ParseDict
from phenopackets import Phenopacket

from app.phenopackets.curation.models import (
    AssessmentStatus,
    ClassificationObservation,
    CurationStatus,
    DiseaseObservation,
    EvidenceObservation,
    ObservedValue,
    PhenotypeAssessment,
    PhenotypeFinding,
    PublicationObservation,
    ReportObservation,
    SourceManifestRef,
    SubjectObservation,
    TemporalObservation,
    VariantObservation,
)
from app.phenopackets.curation.projection import project_individual


def test_projection_emits_typed_disease_variant_classification_references_evidence_and_onset():
    """Typed source facts must not disappear into empty GA4GH stubs."""
    report = ReportObservation(
        observation_id="manual-full-contract",
        origin="manual",
        source=SourceManifestRef(
            provider="manual", dataset_id="d", sheet="s", manifest_sha256="sha256:m"
        ),
        identifiers=SubjectObservation(
            individual_id="317", source_subject_id="s-317", report_id="r-1"
        ),
        publication=PublicationObservation(pmid="12345", doi="10.1/example"),
        ages=TemporalObservation(
            onset=ObservedValue(
                raw="prenatal",
                source_status="stated",
                value={
                    "kind": "ontologyClass",
                    "term": {"id": "HP:0030674", "label": "Antenatal onset"},
                },
            )
        ),
        diseases=(DiseaseObservation(term={"id": "MONDO:0007669", "label": "RCAD"}),),
        variant=VariantObservation(
            normalized={
                "id": "ga4gh:VA.abc",
                "variation": {"text": {"definition": "validated source expression"}},
            },
        ),
        classification=ClassificationObservation(
            verdict=ObservedValue(raw="5", source_status="stated", value="PATHOGENIC"),
            contribution=ObservedValue(
                raw="causative", source_status="stated", value="CAUSATIVE"
            ),
        ),
        phenotypes=(
            PhenotypeAssessment(
                assessment_id="a",
                column="RenalCysts",
                raw_value="yes",
                curation_status=CurationStatus.CURATED,
                assessment_status=AssessmentStatus.PRESENT,
                findings=(
                    PhenotypeFinding(
                        definition_id="renal-cyst",
                        term={"id": "HP:0000107", "label": "Renal cyst"},
                    ),
                ),
                evidence=(
                    EvidenceObservation(
                        reference="PMID:12345",
                        evidence_code={"id": "ECO:0000000", "label": "evidence"},
                    ),
                ),
                onset=ObservedValue(
                    raw="prenatal",
                    source_status="stated",
                    value={
                        "kind": "ontologyClass",
                        "term": {"id": "HP:0030674", "label": "Antenatal onset"},
                    },
                ),
            ),
        ),
    )
    result = project_individual([report], [], algorithm_version="1.0")
    assert result.phenopacket["diseases"][0]["term"]["id"] == "MONDO:0007669"
    genomic = result.phenopacket["interpretations"][0]["diagnosis"][
        "genomicInterpretations"
    ][0]
    assert genomic["subjectOrBiosampleId"] == "317"
    assert genomic["interpretationStatus"] == "CAUSATIVE"
    assert (
        genomic["variantInterpretation"]["acmgPathogenicityClassification"]
        == "PATHOGENIC"
    )
    assert result.phenopacket["metaData"]["externalReferences"]
    assert (
        result.phenopacket["phenotypicFeatures"][0]["onset"]["ontologyClass"]["id"]
        == "HP:0030674"
    )
    assert (
        result.phenopacket["phenotypicFeatures"][0]["evidence"][0]["reference"]["id"]
        == "PMID:12345"
    )
    parsed = ParseDict(result.phenopacket, Phenopacket())
    assert (
        parsed.interpretations[0]
        .diagnosis.genomic_interpretations[0]
        .subject_or_biosample_id
        == "317"
    )


def test_vrs_descriptor_identity_must_be_exact_when_reports_are_grouped():
    """A claimed VRS ID cannot group two non-identical variation payloads."""

    def report(identifier: str, expression: str) -> ReportObservation:
        return ReportObservation(
            observation_id=identifier,
            origin="manual",
            source=SourceManifestRef(
                provider="manual", dataset_id="d", sheet="s", manifest_sha256="sha256:m"
            ),
            identifiers=SubjectObservation(
                individual_id="317", source_subject_id="s-317", report_id=identifier
            ),
            variant=VariantObservation(
                normalized={
                    "id": "ga4gh:VA.abc",
                    "variation": {"text": {"definition": expression}},
                }
            ),
        )

    first = report("manual-first", "first expression")
    malformed = report("manual-second", "different expression")
    import pytest

    with pytest.raises(ValueError, match="VRS descriptor id"):
        project_individual([first, malformed], [], algorithm_version="1.0")


def test_resolving_acmg_leaves_independent_contribution_conflict_blocking():
    """ACMG selection cannot silently choose the causal contribution status."""
    from datetime import datetime, timezone

    from app.phenopackets.curation.models import ProjectionResolution

    def report(identifier: str, verdict: str, contribution: str) -> ReportObservation:
        return ReportObservation(
            observation_id=identifier,
            origin="manual",
            source=SourceManifestRef(
                provider="manual", dataset_id="d", sheet="s", manifest_sha256="sha256:m"
            ),
            identifiers=SubjectObservation(
                individual_id="317", source_subject_id="s", report_id=identifier
            ),
            variant=VariantObservation(
                normalized={
                    "id": "ga4gh:VA.same",
                    "variation": {"text": {"definition": "same"}},
                }
            ),
            classification=ClassificationObservation(
                verdict=ObservedValue(
                    raw=verdict, source_status="stated", value=verdict
                ),
                contribution=ObservedValue(
                    raw=contribution, source_status="stated", value=contribution
                ),
            ),
        )

    reports = [
        report("one", "PATHOGENIC", "CAUSATIVE"),
        report("two", "BENIGN", "CANDIDATE"),
    ]
    initial = project_individual(reports, [], algorithm_version="1.0")
    acmg = next(
        conflict
        for conflict in initial.blocking_conflicts
        if conflict.conflict_key.endswith(":acmg")
    )
    resolution = ProjectionResolution(
        resolution_id="resolve-acmg",
        conflict_key=acmg.conflict_key,
        candidate_set_digest=acmg.candidate_set_digest,
        strategy="select_observations",
        selected_observation_ids=("one",),
        reason="source review",
        resolved_by_user_id=1,
        resolved_at=datetime.now(timezone.utc),
    )
    resolved = project_individual(reports, [resolution], algorithm_version="1.0")
    assert resolved.phenopacket["interpretations"] == []
    assert [item.conflict_key for item in resolved.blocking_conflicts] == [
        "variant:ga4gh:VA.same:contribution"
    ]
