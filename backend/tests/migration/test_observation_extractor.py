"""Source-row extraction preserves typed evidence without reviewer emails."""

from migration.phenopackets.observation_extractor import extract_observation
from migration.phenopackets.source_column_map import SOURCE_COLUMNS


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
        row, row_number=7, source_system="local_fixture", dataset_key="hnf1b-registry",
        manifest_sha256="sha256:fixture", row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Source reviewer 1")},
    )
    ckd = next(item for item in observation.phenotypes if item.column == "RenalInsufficancy")
    solitary = next(item for item in observation.phenotypes if item.column == "SolitaryKidney")
    assert ckd.findings[0].term.id == "HP:0003774"
    assert [modifier.id for modifier in solitary.findings[0].modifiers] == ["HP:0012833", "HP:0012835"]
