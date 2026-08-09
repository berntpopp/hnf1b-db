"""Schema declaration for the seven Phase 3 curation console fields (plan Task 1).

Extends the hnf1bCuration block added by the previous phase
(see tests/test_hnf1b_curation_schema.py) with:
publicationType, classificationSystem, classificationDate, classificationComment,
caseComment, problematic, duplicateCheck.
"""

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


def test_accepts_the_seven_new_fields(validator):
    errors = validator.validate(
        with_curation(
            publicationType="case_report",
            classificationSystem="acmg",
            classificationDate="2026-07-30",
            classificationComment="Meets PS3+PM2 per ClinGen HNF1B specifications.",
            caseComment="Index case, mother unaffected.",
            problematic="Age at report unclear from source text.",
            duplicateCheck="Checked against PMID:12345678, not a duplicate.",
        )
    )
    assert errors == []


def test_accepts_the_seven_new_fields_alongside_the_existing_ones(validator):
    """New fields coexist with the Phase 2 fields inside the same block."""
    errors = validator.validate(
        with_curation(
            cohort="fetus",
            familyHistory="positive",
            detectionMethod="mlpa",
            curatedBy="Bernt Popp",
            curatedAt="2026-07-30T14:02:11Z",
            publicationType="case_series",
            classificationSystem="clingen_cnv",
            classificationDate="2026-07-30",
            classificationComment="",
            caseComment="",
            problematic="",
            duplicateCheck="",
        )
    )
    assert errors == []


def test_accepts_a_block_missing_all_seven_new_fields(validator):
    """Absence means 'not yet curated'; the new fields must stay optional."""
    assert validator.validate(with_curation(cohort="born")) == []


def test_accepts_a_phenopacket_with_no_curation_block(validator):
    """All 923 legacy records have no block; none may become invalid."""
    assert validator.validate(MINIMAL) == []


def test_rejects_a_typo_inside_the_block_with_new_fields_present():
    """additionalProperties:false must still catch a typo'd key.

    This is the property the previous phase bought: a bag-of-notes field would
    have defeated it. Prove it still holds now that seven more typed fields
    exist alongside the free-typing-prone ones.
    """
    validator = SchemaValidator()
    errors = validator.validate(
        with_curation(
            publicationType="case_report",
            calssificationSystem="acmg",  # typo: should be classificationSystem
        )
    )
    assert errors, "additionalProperties:false must apply inside the block"


@pytest.mark.parametrize(
    "field",
    [
        "publicationType",
        "classificationSystem",
        "classificationDate",
        "classificationComment",
        "caseComment",
        "problematic",
        "duplicateCheck",
    ],
)
def test_rejects_a_non_string_value_for_each_new_field(validator, field):
    errors = validator.validate(with_curation(**{field: 42}))
    assert errors, f"{field} must be typed as a string"


def test_does_not_accept_a_free_form_notes_bag(validator):
    """Rejected design per spec §4: one 'notes' object with arbitrary keys would
    defeat additionalProperties:false. Prove the schema has no such escape hatch.
    """
    errors = validator.validate(
        with_curation(notes={"anything": "goes", "here": "too"})
    )
    assert errors
