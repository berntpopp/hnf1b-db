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
    assert parsed.interpretations[0].diagnosis.genomic_interpretations[0].subject_or_biosample_id == "317"
