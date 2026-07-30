"""Async domain validation for curation fields (spec §4.5).

Also covers the ontology data-quality plan's Task 7 Step 1 requirement: the
validator calls ``check_label`` (app/ontology/conformance.py) so a wrong HPO
identifier cannot enter through the curation form merely because a modifier
happens to be permitted for it. See ``test_rejects_a_phenotype_whose_label_
does_not_match_its_id`` below.
"""

import pytest

from app.phenopackets.validation.domain import DomainValidator

BILATERAL, UNILATERAL, LEFT = "HP:0012832", "HP:0012833", "HP:0012835"

# Real canonical labels (per app/ontology/data/ontology_snapshot.json) for the
# terms exercised below. check_label now runs on every phenotypicFeature, so a
# placeholder label like "x" would fail A3 and mask the assertion each test is
# actually trying to make — labels must be genuine.
_RENAL_CYST = "Renal cyst"
_UNILATERAL_RENAL_AGENESIS = "Unilateral renal agenesis"
_MODY = "Maturity-onset diabetes of the young"


def packet(**overrides):
    return {
        "id": "phenopacket-940",
        "subject": {"id": "940", "sex": "FEMALE"},
        "metaData": {
            "created": "2026-07-30T00:00:00Z",
            "createdBy": "t",
            "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
        },
        **overrides,
    }


def feature(hpo_id, label, modifiers=None):
    f = {"type": {"id": hpo_id, "label": label}, "excluded": False}
    if modifiers is not None:
        f["modifiers"] = [{"id": m} for m in modifiers]
    return f


@pytest.mark.asyncio
async def test_accepts_valid_curation(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(hnf1bCuration={"cohort": "fetus", "detectionMethod": "mlpa"})
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_unknown_enum_value(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(hnf1bCuration={"detectionMethod": "telepathy"})
    )
    assert len(errors) == 1
    assert "detectionMethod" in errors[0] and "telepathy" in errors[0]
    assert "mlpa" in errors[0], "the message should name the allowed values"


@pytest.mark.asyncio
async def test_rejects_unknown_segregation_origin(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            interpretations=[
                {
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": "var:x",
                                        "extensions": [
                                            {
                                                "name": "segregation",
                                                "value": {"origin": "guessed"},
                                            }
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        )
    )
    assert len(errors) == 1
    assert "segregation" in errors[0]


@pytest.mark.asyncio
async def test_accepts_allowed_laterality(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000107", _RENAL_CYST, [BILATERAL])])
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_bilateral_with_unilateral(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            phenotypicFeatures=[
                feature("HP:0000107", _RENAL_CYST, [BILATERAL, UNILATERAL])
            ]
        )
    )
    assert len(errors) == 1
    assert BILATERAL in errors[0] and UNILATERAL in errors[0]


@pytest.mark.asyncio
async def test_rejects_modifier_outside_the_terms_set(db_session):
    """HP:0000122 already asserts unilaterality, so Bilateral contradicts it."""
    errors = await DomainValidator(db_session).validate(
        packet(
            phenotypicFeatures=[
                feature("HP:0000122", _UNILATERAL_RENAL_AGENESIS, [BILATERAL])
            ]
        )
    )
    assert len(errors) == 1
    assert "HP:0000122" in errors[0]


@pytest.mark.asyncio
async def test_accepts_side_only_modifier_on_that_term(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            phenotypicFeatures=[
                feature("HP:0000122", _UNILATERAL_RENAL_AGENESIS, [LEFT])
            ]
        )
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_modifiers_on_a_term_that_admits_none(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0004904", _MODY, [BILATERAL])])
    )
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_no_curation_and_no_modifiers_is_valid(db_session):
    """Every one of the 923 legacy records must still pass."""
    assert await DomainValidator(db_session).validate(packet()) == []


@pytest.mark.asyncio
async def test_reports_every_problem_not_just_the_first(db_session):
    errors = await DomainValidator(db_session).validate(
        packet(
            hnf1bCuration={"cohort": "nope", "familyHistory": "maybe"},
            phenotypicFeatures=[feature("HP:0004904", _MODY, [BILATERAL])],
        )
    )
    assert len(errors) == 3


def _packet_with_extension_value(value):
    return packet(
        interpretations=[
            {
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "id": "var:x",
                                    "extensions": [
                                        {"name": "segregation", "value": value}
                                    ],
                                }
                            }
                        }
                    ]
                }
            }
        ]
    )


@pytest.mark.parametrize("value", ["de_novo", ["de_novo"], 42, None])
@pytest.mark.asyncio
async def test_malformed_segregation_value_is_a_validation_error_not_a_crash(
    db_session, value
):
    """The schema does not constrain extension values, so anything can arrive.

    An AttributeError here would surface as HTTP 500 instead of the 400 the
    contract promises.
    """
    errors = await DomainValidator(db_session).validate(
        _packet_with_extension_value(value)
    )
    assert errors and "segregation" in errors[0]


@pytest.mark.asyncio
async def test_segregation_extension_without_origin_is_ignored(db_session):
    """An object with no origin states nothing; that is not an error."""
    assert (
        await DomainValidator(db_session).validate(_packet_with_extension_value({}))
        == []
    )


@pytest.mark.parametrize(
    "malformed",
    [
        {"interpretations": "not-a-list"},
        {"interpretations": [{"diagnosis": {"genomicInterpretations": "nope"}}]},
        {"phenotypicFeatures": "not-a-list"},
    ],
)
@pytest.mark.asyncio
async def test_structurally_malformed_documents_do_not_crash(db_session, malformed):
    await DomainValidator(db_session).validate(packet(**malformed))


# ---------------------------------------------------------------------------
# check_label integration (ontology data-quality plan, Task 7 Step 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_a_phenotype_whose_label_does_not_match_its_id(db_session):
    """The modifier-permission check alone would happily accept HP:0033133
    mislabeled 'hyperechogenicity' (the original defect) because it never
    looks at whether a term's own label agrees with its own id.
    ``check_label`` closes that gap for the laterality-bearing terms this
    validator already covers. A valid modifier (Bilateral is permitted for
    HP:0000107) is attached so the only failure is the label mismatch, not
    the modifier-permission check.
    """
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000107", "Seizure", [BILATERAL])])
    )
    assert len(errors) == 1
    assert "HP:0000107" in errors[0]


@pytest.mark.asyncio
async def test_accepts_a_listed_synonym_label(db_session):
    """check_label accepts HPO's listed synonyms, not only the canonical name."""
    errors = await DomainValidator(db_session).validate(
        packet(phenotypicFeatures=[feature("HP:0000107", "Kidney cyst", [UNILATERAL])])
    )
    assert errors == []


@pytest.mark.asyncio
async def test_rejects_a_mislabeled_modifier(db_session):
    """A modifier ontologyClass with a mismatched label is caught too, not
    only the phenotype's own type.
    """
    errors = await DomainValidator(db_session).validate(
        packet(
            phenotypicFeatures=[
                {
                    "type": {"id": "HP:0000107", "label": _RENAL_CYST},
                    "excluded": False,
                    "modifiers": [{"id": BILATERAL, "label": "Not Bilateral"}],
                }
            ]
        )
    )
    assert len(errors) == 1
    assert BILATERAL in errors[0]


@pytest.mark.asyncio
async def test_rest_create_rejects_invalid_curation_with_400(
    async_client, curator_headers
):
    response = await async_client.post(
        "/api/v2/phenopackets/",
        json={"phenopacket": packet(hnf1bCuration={"cohort": "nope"})},
        headers=curator_headers,
    )
    assert response.status_code == 400
    assert "cohort" in str(response.json()["detail"])


@pytest.mark.asyncio
async def test_rest_create_accepts_valid_curation(async_client, curator_headers):
    response = await async_client.post(
        "/api/v2/phenopackets/",
        json={"phenopacket": packet(hnf1bCuration={"cohort": "fetus"})},
        headers=curator_headers,
    )
    assert response.status_code in (200, 201)
