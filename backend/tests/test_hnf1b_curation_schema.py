"""Schema declaration for the hnf1bCuration block (spec §4.1)."""

import pytest

from app.phenopackets.validation.schema_validator import SchemaValidator

MINIMAL = {
    "id": "phenopacket-940",
    "subject": {"id": "940", "sex": "FEMALE"},
    "metaData": {
        "created": "2026-07-30T00:00:00Z",
        "createdBy": "test",
        "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
    },
}


@pytest.fixture
def validator():
    return SchemaValidator()


def with_curation(**block):
    return {**MINIMAL, "hnf1bCuration": block}


def test_accepts_a_full_curation_block(validator):
    errors = validator.validate(
        with_curation(
            cohort="fetus",
            familyHistory="positive",
            detectionMethod="mlpa",
            curatedBy="Bernt Popp",
            curatedAt="2026-07-30T14:02:11Z",
        )
    )
    assert errors == []


def test_accepts_a_partial_block(validator):
    """Absence means 'not yet curated' and must stay expressible."""
    assert validator.validate(with_curation(cohort="born")) == []


def test_accepts_a_phenopacket_with_no_curation_block(validator):
    """All 923 legacy records have no block; none may become invalid."""
    assert validator.validate(MINIMAL) == []


def test_rejects_an_unknown_key_inside_the_block(validator):
    errors = validator.validate(with_curation(cohort="born", cohorrt="fetus"))
    assert errors, "additionalProperties:false must apply inside the block"


def test_rejects_a_non_string_field(validator):
    assert validator.validate(with_curation(cohort=42))


def test_top_level_stays_permissive(validator):
    """Tightening the top level is conformance work; legacy shapes must pass."""
    assert validator.validate({**MINIMAL, "someLegacyKey": {"a": 1}}) == []


def _with_molecule_context(value):
    return {
        **MINIMAL,
        "interpretations": [
            {
                "id": "interpretation-001",
                "progressStatus": "IN_PROGRESS",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": "940",
                            "interpretationStatus": "UNKNOWN",
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "id": "var:x",
                                    "moleculeContext": value,
                                }
                            },
                        }
                    ]
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "value", ["genomic", "transcript", "protein", "unspecified_molecule_context"]
)
def test_accepts_every_ga4gh_molecule_context(validator, value):
    assert validator.validate(_with_molecule_context(value)) == []


def test_rejects_a_vep_consequence_as_molecule_context(validator):
    """The B1 defect: the writer put 'missense_variant' in an enum field."""
    assert validator.validate(_with_molecule_context("missense_variant"))
