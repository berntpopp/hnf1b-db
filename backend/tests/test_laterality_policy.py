"""Per-term laterality policy (spec §4.4)."""

import pytest
from sqlalchemy import text

BILATERAL, UNILATERAL, LEFT, RIGHT = (
    "HP:0012832",
    "HP:0012833",
    "HP:0012835",
    "HP:0012834",
)
FULL = {BILATERAL, UNILATERAL, LEFT, RIGHT}

FULL_LATERALITY_TERMS = [
    "HP:0000107",  # Renal cyst
    "HP:0000003",  # Multicystic kidney dysplasia
    "HP:0000089",  # Renal hypoplasia
    "HP:0033132",  # Renal cortical hyperechogenicity
    "HP:0000079",  # Abnormality of the urinary system
]


@pytest.mark.parametrize("hpo_id", FULL_LATERALITY_TERMS)
@pytest.mark.asyncio
async def test_full_laterality_terms(db_session, hpo_id):
    result = await db_session.execute(
        text("SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = :id"),
        {"id": hpo_id},
    )
    row = result.first()
    assert row is not None, f"{hpo_id} missing from hpo_terms_lookup"
    assert set(row[0]) == FULL


@pytest.mark.asyncio
async def test_unilateral_renal_agenesis_rejects_bilateral_only(db_session):
    """HP:0000122 already asserts unilaterality, so Bilateral contradicts the term.

    Unilateral is redundant here but NOT rejected: 20 source rows record
    'unilateral unspecified' on this term, and dropping them would leave those
    features with no modifier at all — indistinguishable from 'laterality never
    stated', the defect of docs/ontology-defect-report-2026-07-30.md §3.
    """
    result = await db_session.execute(
        text(
            "SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = 'HP:0000122'"
        )
    )
    modifiers = set(result.scalar_one())
    assert modifiers == {UNILATERAL, LEFT, RIGHT}
    assert BILATERAL not in modifiers


@pytest.mark.asyncio
async def test_other_terms_admit_no_modifiers(db_session):
    result = await db_session.execute(
        text(
            "SELECT allowed_modifiers FROM hpo_terms_lookup WHERE hpo_id = 'HP:0004904'"
        )
    )
    assert result.scalar_one() == []


@pytest.mark.asyncio
async def test_endpoint_lists_only_terms_with_modifiers(async_client):
    response = await async_client.get("/api/v2/ontology/laterality-policy")
    assert response.status_code == 200
    policy = {
        item["hpo_id"]: set(item["allowed_modifiers"])
        for item in response.json()["data"]
    }

    assert policy["HP:0000107"] == FULL
    assert policy["HP:0000122"] == {UNILATERAL, LEFT, RIGHT}
    assert "HP:0004904" not in policy, "terms admitting no modifiers are omitted"
