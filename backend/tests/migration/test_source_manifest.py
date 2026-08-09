"""Unit tests for the closed, content-addressed source manifest contract."""

import hashlib

import pytest

from migration.source_manifest import (
    EXPECTED_HEADERS,
    REQUIRED_SHEETS,
    SourceManifestError,
    SourceManifestPayload,
    build_source_manifest,
)


def _csv(headers: list[str], row: list[str] | None = None) -> bytes:
    values = row or ["value"] * len(headers)
    return (",".join(headers) + "\n" + ",".join(values) + "\n").encode()


def test_manifest_requires_all_named_sheets_before_returning_any_data():
    """A partial source set is not a valid import input."""
    with pytest.raises(SourceManifestError, match="missing required sheets"):
        build_source_manifest(
            source_system="fixture",
            dataset_key="hnf1b-registry",
            sheets={"Individuals": _csv(["individual_id"])},
        )


def test_manifest_rejects_unknown_and_duplicate_individual_headers():
    """Source columns must be complete and owned exactly once."""
    required_headers = [
        "individual_id",
        "report_id",
        "IndividualIdentifier",
        "Publication",
        "PublicationType",
        "DupCheck",
        "Problematic",
        "Cohort",
        "Sex",
        "FamilyHistory",
        "AgeOnset",
        "AgeReported",
        "VariantType",
        "VariantReported",
        "ID",
        "hg19_INFO",
        "hg19",
        "hg38_INFO",
        "hg38",
        "Varsome",
        "DetecionMethod",
        "Segregation",
        "verdict_classification",
        "criteria_classification",
        "comment_classification",
        "system_classification",
        "date_classification",
        "RenalInsufficancy",
        "Hyperechogenicity",
        "RenalCysts",
        "MulticysticDysplasticKidney",
        "KidneyBiopsy",
        "RenalHypoplasia",
        "SolitaryKidney",
        "UrinaryTractMalformation",
        "GenitalTractAbnormality",
        "AntenatalRenalAbnormalities",
        "Hypomagnesemia",
        "Hypokalemia",
        "Hyperuricemia",
        "Gout",
        "MODY",
        "PancreaticHypoplasia",
        "ExocrinePancreaticInsufficiency",
        "Hyperparathyroidism",
        "NeurodevelopmentalDisorder",
        "MentalDisease",
        "Seizures",
        "BrainAbnormality",
        "PrematureBirth",
        "CongenitalCardiacAnomalies",
        "EyeAbnormality",
        "ShortStature",
        "MusculoskeletalFeatures",
        "DysmorphicFeatures",
        "ElevatedHepaticTransaminase",
        "AbnormalLiverPhysiology",
        "Comment",
        "ReviewBy",
        "ReviewDate",
    ]
    source = {
        "Individuals": _csv(required_headers + ["unexpected"]),
        "Phenotypes": _csv(["phenotype_category", "phenotype_id", "phenotype_name", "phenotype_description"]),
        "Phenotype_modifier": _csv(["modifier", "modifier_id"]),
        "Publications": _csv(["publication_id", "publication_alias", "PMID", "DOI"]),
    }

    with pytest.raises(SourceManifestError, match="unknown headers"):
        build_source_manifest(
            source_system="fixture", dataset_key="hnf1b-registry", sheets=source
        )

    source["Individuals"] = _csv(required_headers + ["RenalCysts"])
    with pytest.raises(SourceManifestError, match="duplicate headers"):
        build_source_manifest(
            source_system="fixture", dataset_key="hnf1b-registry", sheets=source
        )


def test_manifest_hashes_all_raw_sheets_and_never_returns_partial_data():
    """The declared snapshot hash commits the complete immutable source input."""
    sheets = {
        "Individuals": _csv(["individual_id"]),
        "Phenotypes": _csv(["phenotype_category", "phenotype_id", "phenotype_name", "phenotype_description"]),
        "Phenotype_modifier": _csv(["modifier", "modifier_id"]),
        "Publications": _csv(["publication_id", "publication_alias", "PMID", "DOI"]),
    }
    manifest = build_source_manifest(
        source_system="fixture",
        dataset_key="hnf1b-registry",
        sheets=sheets,
        header_validation=False,
    )

    assert set(manifest.sheets) == REQUIRED_SHEETS
    assert (
        manifest.sha256
        == hashlib.sha256(
            b"".join(
                name.encode() + b"\0" + sheets[name] for name in sorted(REQUIRED_SHEETS)
            )
        ).hexdigest()
    )


def test_manifest_payload_preserves_only_structural_metadata_and_row_counts():
    sheets = {
        "Individuals": _csv(list(EXPECTED_HEADERS["Individuals"]), ["source-subject"] * 60),
        "Phenotypes": _csv(list(EXPECTED_HEADERS["Phenotypes"])),
        "Phenotype_modifier": _csv(["modifier", "modifier_id"], ["Left", "HP:1"]),
        "Publications": _csv(list(EXPECTED_HEADERS["Publications"])),
    }
    manifest = build_source_manifest(
        source_system="fixture",
        dataset_key="hnf1b-registry",
        sheets=sheets,
        header_validation=False,
    )

    payload = SourceManifestPayload.from_manifest(manifest).to_storage()

    assert payload["sha256"] == manifest.sha256
    assert payload["sheets"]["Individuals"]["row_count"] == 1
    assert "source-subject" not in repr(payload)


def test_manifest_payload_rejects_non_sha256_digest():
    with pytest.raises(SourceManifestError, match="SHA-256"):
        SourceManifestPayload(
            source_system="fixture",
            dataset_key="hnf1b-registry",
            sha256="not-a-digest",
            sheets={},
        )


def test_manifest_payload_rechecks_exact_sheet_contract_before_persistence():
    manifest = build_source_manifest(
        source_system="fixture",
        dataset_key="hnf1b-registry",
        header_validation=False,
        sheets={
            "Individuals": _csv(["unexpected"]),
            "Phenotypes": _csv(["phenotype_category"]),
            "Phenotype_modifier": _csv(["modifier"]),
            "Publications": _csv(["publication_id"]),
        },
    )

    with pytest.raises(SourceManifestError, match="required headers"):
        SourceManifestPayload.from_manifest(manifest)
