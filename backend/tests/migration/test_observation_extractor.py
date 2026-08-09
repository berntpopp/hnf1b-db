"""Source-row extraction preserves typed evidence without reviewer emails."""

import pytest

from app.phenopackets.curation.models import AssessmentStatus
from migration.phenopackets.laterality import (
    ModifierVocabularyError,
    modifier_vocabulary_from_rows,
)
from migration.phenopackets.observation_extractor import (
    ObservationExtractionError,
    extract_observation,
)
from migration.phenopackets.publication_mapping import (
    PublicationMappingError,
    publication_mapping_from_rows,
)
from migration.phenopackets.source_column_map import SOURCE_COLUMNS


def _modifier_vocabulary():
    return modifier_vocabulary_from_rows(
        [
            {"modifier": "Bilateral", "modifier_id": "HP:0012832"},
            {"modifier": "Unilateral", "modifier_id": "HP:0012833"},
            {"modifier": "Left", "modifier_id": "HP:0012835"},
            {"modifier": "Right", "modifier_id": "HP:0012834"},
        ],
        version_sha256="a" * 64,
    )


def _row() -> dict[str, str]:
    row = {entry.header: "NR" for entry in SOURCE_COLUMNS}
    row.update(
        {
            "individual_id": "317",
            "report_id": "RPT-001",
            "IndividualIdentifier": "Family A / II-2",
            "Publication": "PMID:123456",
            "PublicationType": "case report",
            "DupCheck": "no",
            "Problematic": "no",
            "Cohort": "fetus",
            "Sex": "female",
            "FamilyHistory": "unknown",
            "AgeOnset": "28w",
            "AgeReported": "12 years",
            "VariantType": "SNV",
            "VariantReported": "c.1A>G",
            "ID": "source-variant-1",
            "hg19_INFO": "source hg19 info",
            "hg19": "chr17:g.1A>G",
            "hg38_INFO": "source hg38 info",
            "hg38": "chr17:g.2A>G",
            "Varsome": "source varsome",
            "DetecionMethod": "sequencing",
            "Segregation": "de novo",
            "verdict_classification": "pathogenic",
            "criteria_classification": "PS2",
            "comment_classification": "reviewed classification",
            "system_classification": "ACMG",
            "date_classification": "2026-08-09",
            "RenalCysts": "unilateral left",
            "Comment": "deidentified source comment",
            "ReviewBy": "reviewer@example.test",
            "ReviewDate": "2026-08-09",
        }
    )
    return row


def test_extractor_builds_one_lossless_typed_observation_with_thirty_assessments():
    observation = extract_observation(
        _row(),
        row_number=7,
        source_system="local_fixture",
        dataset_key="hnf1b-registry",
        manifest_sha256="sha256:fixture",
        row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Source reviewer 1")},
        modifier_vocabulary=_modifier_vocabulary(),
    )

    assert observation.identifiers.report_id == "RPT-001"
    assert observation.ages.onset.value.kind == "gestationalAge"
    assert len(observation.phenotypes) == 30
    renal_cysts = next(
        item for item in observation.phenotypes if item.column == "RenalCysts"
    )
    assert [item.id for item in renal_cysts.findings[0].modifiers] == [
        "HP:0012833",
        "HP:0012835",
    ]
    serialized = observation.model_dump_json()
    assert "reviewer@example.test" not in serialized
    assert "source hg19 info" in serialized


def test_extractor_preserves_categorical_definition_and_solitary_kidney_laterality():
    row = _row()
    row["RenalInsufficancy"] = "Stage 5 chronic kidney disease"
    row["SolitaryKidney"] = "unilateral left"
    observation = extract_observation(
        row,
        row_number=7,
        source_system="local_fixture",
        dataset_key="hnf1b-registry",
        manifest_sha256="sha256:fixture",
        row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Source reviewer 1")},
        modifier_vocabulary=_modifier_vocabulary(),
    )
    ckd = next(
        item for item in observation.phenotypes if item.column == "RenalInsufficancy"
    )
    solitary = next(
        item for item in observation.phenotypes if item.column == "SolitaryKidney"
    )
    assert ckd.findings[0].term.id == "HP:0003774"
    assert [modifier.id for modifier in solitary.findings[0].modifiers] == [
        "HP:0012833",
        "HP:0012835",
    ]


def test_extractor_refuses_laterality_without_versioned_source_modifiers():
    with pytest.raises(ObservationExtractionError) as error:
        extract_observation(
            _row(),
            row_number=7,
            source_system="local_fixture",
            dataset_key="hnf1b-registry",
            manifest_sha256="sha256:fixture",
            row_hmac_key=b"test-only-key",
            reviewer_mapping={
                "reviewer@example.test": ("reviewer-1", "Source reviewer 1")
            },
        )

    assert isinstance(error.value.__cause__, ModifierVocabularyError)


def test_modifier_vocabulary_rejects_non_hpo_modifier_identifiers():
    rows = [
        {"modifier": "Bilateral", "modifier_id": "not-an-hpo-id"},
        {"modifier": "Unilateral", "modifier_id": "HP:0012833"},
        {"modifier": "Left", "modifier_id": "HP:0012835"},
        {"modifier": "Right", "modifier_id": "HP:0012834"},
    ]

    with pytest.raises(ModifierVocabularyError, match="invalid source modifier"):
        modifier_vocabulary_from_rows(rows, version_sha256="a" * 64)


def test_modifier_vocabulary_rejects_swapped_known_hpo_terms():
    rows = [
        {"modifier": "Bilateral", "modifier_id": "HP:0012833"},
        {"modifier": "Unilateral", "modifier_id": "HP:0012832"},
        {"modifier": "Left", "modifier_id": "HP:0012835"},
        {"modifier": "Right", "modifier_id": "HP:0012834"},
    ]

    with pytest.raises(ModifierVocabularyError, match="does not match"):
        modifier_vocabulary_from_rows(rows, version_sha256="a" * 64)


def test_kidney_biopsy_no_is_explicitly_not_assessed_not_two_negative_findings():
    row = _row()
    row["KidneyBiopsy"] = "no"

    observation = extract_observation(
        row,
        row_number=7,
        source_system="local_fixture",
        dataset_key="hnf1b-registry",
        manifest_sha256="sha256:fixture",
        row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Source reviewer 1")},
        modifier_vocabulary=_modifier_vocabulary(),
    )

    biopsy = next(
        item for item in observation.phenotypes if item.column == "KidneyBiopsy"
    )
    assert biopsy.assessment_status is AssessmentStatus.NOT_ASSESSED
    assert biopsy.findings == ()


def test_extractor_normalizes_publication_alias_to_lossless_pmid_and_doi():
    row = _row()
    row["Publication"] = "family-study"
    publications = publication_mapping_from_rows(
        [
            {
                "publication_id": "study-2026",
                "publication_alias": "family-study",
                "PMID": "PMID:123456",
                "DOI": "DOI:10.1000/Family.Study",
            }
        ]
    )

    observation = extract_observation(
        row,
        row_number=7,
        source_system="local_fixture",
        dataset_key="hnf1b-registry",
        manifest_sha256="sha256:fixture",
        row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Source reviewer 1")},
        modifier_vocabulary=_modifier_vocabulary(),
        publication_mapping=publications,
    )

    assert observation.publication.source_key.value == "family-study"
    assert observation.publication.pmid == "123456"
    assert observation.publication.doi == "10.1000/family.study"


def test_extractor_refuses_an_unknown_publication_alias():
    row = _row()
    row["Publication"] = "unmapped-study"

    with pytest.raises(ObservationExtractionError, match="publication alias"):
        extract_observation(
            row,
            row_number=7,
            source_system="local_fixture",
            dataset_key="hnf1b-registry",
            manifest_sha256="sha256:fixture",
            row_hmac_key=b"test-only-key",
            reviewer_mapping={
                "reviewer@example.test": ("reviewer-1", "Source reviewer 1")
            },
            modifier_vocabulary=_modifier_vocabulary(),
            publication_mapping=publication_mapping_from_rows([]),
        )


def test_publication_mapping_refuses_ambiguous_aliases():
    with pytest.raises(PublicationMappingError, match="ambiguous publication alias"):
        publication_mapping_from_rows(
            [
                {
                    "publication_id": "study-one",
                    "publication_alias": "shared",
                    "PMID": "123456",
                    "DOI": "10.1000/one",
                },
                {
                    "publication_id": "study-two",
                    "publication_alias": "shared",
                    "PMID": "123457",
                    "DOI": "10.1000/two",
                },
            ]
        )


@pytest.mark.parametrize(
    "value",
    ["bilateral left", "unilateral left right", "left unilateral", "unilateral-left"],
)
def test_extractor_rejects_noncanonical_or_conflicting_laterality(value):
    row = _row()
    row["RenalCysts"] = value

    with pytest.raises(ObservationExtractionError, match="laterality"):
        extract_observation(
            row,
            row_number=7,
            source_system="local_fixture",
            dataset_key="hnf1b-registry",
            manifest_sha256="sha256:fixture",
            row_hmac_key=b"test-only-key",
            reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Reviewer 1")},
            modifier_vocabulary=_modifier_vocabulary(),
        )


@pytest.mark.parametrize(
    "reviewer",
    [("", "Reviewer 1"), ("reviewer-1", ""), ("reviewer@example.test", "Reviewer 1")],
)
def test_extractor_rejects_nonpseudonymous_reviewer_mapping_values(reviewer):
    with pytest.raises(ObservationExtractionError, match="pseudonymous"):
        extract_observation(
            _row(),
            row_number=7,
            source_system="local_fixture",
            dataset_key="hnf1b-registry",
            manifest_sha256="sha256:fixture",
            row_hmac_key=b"test-only-key",
            reviewer_mapping={"reviewer@example.test": reviewer},
            modifier_vocabulary=_modifier_vocabulary(),
        )
