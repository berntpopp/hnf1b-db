"""Regression coverage for PR-422 Lane A review findings."""

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ontology.conformance import load_correction_ledger
from app.phenopackets.curation.definitions import _build_registry
from app.phenopackets.curation.hashing import observation_digest
from app.phenopackets.curation.identifiers import (
    assessment_id_for,
    observation_id_for,
    row_hmac_sha256,
)
from app.phenopackets.curation.models import (
    AssessmentStatus,
    CurationCorrection,
    CurationStatus,
    Hnf1bCurationProfile,
    ObservedValue,
    ReportObservation,
    SourceManifestRef,
    SubjectObservation,
)
from app.phenopackets.curation.projection import project_individual


def _report(report_id="RPT-1", row_number=1, manifest="sha256:one"):
    observation_id = observation_id_for("fixture", "registry", report_id)
    return ReportObservation(
        observation_id=observation_id,
        origin="manual",
        source=SourceManifestRef(
            provider="fixture",
            dataset_id="registry",
            sheet="Individuals",
            row_number=row_number,
            row_hmac_sha256=row_hmac_sha256(b"row", b"key"),
            manifest_sha256=manifest,
        ),
        identifiers=SubjectObservation(
            individual_id="317", source_subject_id="source-317", report_id=report_id
        ),
    )


def test_raw_imported_value_is_frozen_and_correction_null_serializes_through_schema():
    """Raw source evidence cannot be assigned over, including through correction nulls."""
    value = ObservedValue[str](raw="28w", source_status="stated", value="P28W")
    with pytest.raises(ValidationError):
        value.raw = "29w"

    correction = CurationCorrection(
        correction_id="correction-1",
        json_pointer="/projection/outputDigest",
        preimage=None,
        postimage="digest",
        source_manifest_sha256="sha256:one",
        reason="Parsed source unit.",
        actor_id=1,
        created_at="2026-08-09T00:00:00Z",
        supersedes_correction_id=None,
    )
    profile = Hnf1bCurationProfile(
        source_subject_id="source-317",
        observations_by_id={_report().observation_id: _report()},
        corrections_by_id={"correction-1": correction},
    )
    from app.phenopackets.validation.schema_validator import SchemaValidator

    document = {
        "id": "phenopacket-317",
        "subject": {"id": "317"},
        "metaData": {
            "created": "2026-08-09T00:00:00Z",
            "createdBy": "t",
            "resources": [],
        },
        "hnf1bCuration": profile.model_dump(by_alias=True, mode="json"),
    }
    assert SchemaValidator().validate(document) == []


def test_imported_report_requires_exactly_the_30_known_assessments_and_canonical_ids():
    """A shortened or invented phenotype matrix cannot silently pass import validation."""
    base = _report("RPT-import").model_dump()
    base["origin"] = "imported"
    with pytest.raises(ValidationError):
        ReportObservation.model_validate(base)


def test_imported_report_rejects_missing_required_source_sections_and_row_hmac():
    """A source import cannot serialize a syntactically valid partial ledger."""
    base = _report("RPT-import").model_dump()
    base["origin"] = "imported"
    base["phenotypes"] = []
    base["source"]["row_hmac_sha256"] = None
    with pytest.raises(ValidationError, match="rowHmacSha256"):
        ReportObservation.model_validate(base)


def test_schema_is_valid_runs_the_closed_curation_model_not_only_json_schema():
    """Production boolean validation must reject an imported partial source ledger."""
    from app.phenopackets.validation.schema_validator import SchemaValidator

    base = _report("RPT-import").model_dump(by_alias=True)
    base["origin"] = "imported"
    document = {
        "id": "packet",
        "subject": {"id": "317"},
        "metaData": {
            "created": "2026-08-09T00:00:00Z",
            "createdBy": "t",
            "resources": [],
        },
        "hnf1bCuration": {
            "schemaVersion": "2.0",
            "definitionsVersion": "hnf1b-phenotypes/1",
            "sourceSubjectId": "source-317",
            "observationsById": {base["observationId"]: base},
        },
    }
    assert not SchemaValidator().is_valid(document)


def test_observed_source_values_are_deeply_immutable():
    """Typed source values cannot retain a mutable dict below a frozen cell."""
    from app.phenopackets.curation.models import TemporalValue

    value = ObservedValue(
        raw="28 weeks",
        source_status="stated",
        value=TemporalValue(kind="age", iso8601_duration="P28W"),
    )
    with pytest.raises(ValidationError):
        value.value.iso8601_duration = "P29W"


def test_nonpositive_source_status_cannot_create_a_present_finding():
    """NA/NR source cells stay non-clinical even when a curator supplies a finding."""
    from app.phenopackets.curation.models import PhenotypeAssessment

    with pytest.raises(ValidationError, match="cannot contain findings"):
        PhenotypeAssessment(
            assessment_id="a",
            column="RenalCysts",
            raw_value="NR",
            curation_status=CurationStatus.CURATED,
            assessment_status=AssessmentStatus.NOT_REPORTED,
            findings=(
                {
                    "definitionId": "renal-cyst",
                    "term": {"id": "HP:0000107", "label": "Renal cyst"},
                },
            ),
        )


def test_laterality_is_rejected_for_a_non_lateralized_source_question():
    """Modifiers are constrained by the source definition, not arbitrary HPO terms."""
    from app.phenopackets.curation.models import PhenotypeAssessment

    with pytest.raises(ValidationError, match="does not allow laterality"):
        PhenotypeAssessment(
            assessment_id="a",
            column="Hypomagnesemia",
            raw_value="yes",
            curation_status=CurationStatus.CURATED,
            assessment_status=AssessmentStatus.PRESENT,
            findings=(
                {
                    "definitionId": "hypomagnesemia",
                    "term": {"id": "HP:0002917", "label": "Hypomagnesemia"},
                    "modifiers": ({"id": "HP:0012832", "label": "Bilateral"},),
                },
            ),
        )


def test_identity_helpers_are_unambiguous_and_models_enforce_uuid_and_hmac_formats():
    """Delimiter collisions and arbitrary identity/fingerprint strings are rejected."""
    assert observation_id_for("a:b", "c", "d") != observation_id_for("a", "b:c", "d")
    UUID(observation_id_for("fixture", "registry", "RPT-1"))
    assert assessment_id_for("abc", "a:b", "c", "d") != assessment_id_for(
        "abc", "a", "b:c", "d"
    )
    with pytest.raises(ValidationError):
        SourceManifestRef(
            provider="x",
            dataset_id="d",
            sheet="s",
            manifest_sha256="sha256:x",
            row_hmac_sha256="plain",
        )
    with pytest.raises(ValidationError):
        SourceManifestRef(
            provider="x",
            dataset_id="d",
            sheet="s",
            manifest_sha256="sha256:x",
            row_hmac_sha256="hmac-sha256:abc",
        )


def test_profile_rejects_duplicate_observation_identity_and_projector_rejects_duplicate_input():
    """Both JSON map and in-memory projection boundaries reject duplicate observations."""
    report = _report()
    with pytest.raises(ValidationError):
        Hnf1bCurationProfile(
            source_subject_id="source-317",
            observations_by_id={report.observation_id: report},
            corrections_by_id={},
            resolutions_by_id={},
            duplicate_observations=[report],
        )
    with pytest.raises(ValueError, match="duplicate observationId"):
        project_individual([report, report], [], algorithm_version="1.0")


def test_digest_ignores_snapshot_provenance_but_not_clinical_content():
    """A new manifest/import row cannot alter projection semantics by itself."""
    assert observation_digest(
        [_report(row_number=1, manifest="sha256:one")]
    ) == observation_digest([_report(row_number=999, manifest="sha256:two")])


def test_definition_registry_does_not_assign_definition_ids_by_csv_position():
    """An ontology CSV reorder must not change the stable clinical definition IDs."""
    import csv
    from pathlib import Path

    path = Path(__file__).parents[2] / "app/ontology/data/curation_vocabulary.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    original, _ = _build_registry(rows)
    reordered, _ = _build_registry(list(reversed(rows)))
    assert {item.term_id: item.definition_id for item in original} == {
        item.term_id: item.definition_id for item in reordered
    }


def test_ledger_rejects_blank_negative_and_nonnumeric_count_data(tmp_path):
    """Correction accounting is validated before reports can cite it."""
    source = Path(__file__).parents[2] / "app/ontology/data/ontology_corrections.csv"
    bad = tmp_path / "ledger.csv"
    content = source.read_text(encoding="utf-8")
    bad.write_text(content.replace(",460,", ",-1,"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_correction_ledger(bad)
    bad.write_text(content.replace(",460,", ",not-a-number,"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_correction_ledger(bad)


def test_active_correction_chain_applies_a_to_b_to_c_in_order():
    """Supersession preserves the full historical transform, not only its tail."""
    from app.phenopackets.curation.adapters import _apply_active_corrections

    block = {
        "value": "A",
        "correctionsById": {
            "one": {"jsonPointer": "/value", "preimage": "A", "postimage": "B"},
            "two": {
                "jsonPointer": "/value",
                "preimage": "B",
                "postimage": "C",
                "supersedesCorrectionId": "one",
            },
        },
    }
    assert _apply_active_corrections(block)["value"] == "C"
    assert block["value"] == "A"


def test_malformed_scalar_correction_pointer_has_structured_error_code():
    """Bad pointer traversal does not leak a KeyError/TypeError from projection."""
    from app.phenopackets.curation.adapters import (
        CurationProjectionError,
        _apply_active_corrections,
    )

    with pytest.raises(CurationProjectionError) as error:
        _apply_active_corrections(
            {
                "value": "A",
                "correctionsById": {
                    "bad": {
                        "jsonPointer": "/value/x",
                        "preimage": "A",
                        "postimage": "B",
                    }
                },
            }
        )
    assert error.value.code == "invalid_correction"
