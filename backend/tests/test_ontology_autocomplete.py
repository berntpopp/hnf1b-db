import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Synthetic identifier namespace for this fixture's sample rows.
#
# These must NEVER be real HPO identifiers. A previous version of this
# fixture inserted fake rows under HP:0000001-HP:0000010, which collided
# with real reference data — most notably HP:0000003, the genuine
# "Multicystic kidney dysplasia" term, which carries a laterality policy
# (see test_laterality_policy.py) and is referenced by 274 stored
# phenotypic features. The fixture's cleanup then ran a `LIKE
# 'HP:000000%'` delete that removed the real HP:0000003 row but missed
# HP:0000010 (which the fixture also inserted), silently and cumulatively
# corrupting the test database across runs. HP:999xxxx is outside the real
# HPO id space and is deleted by exact id match below, so this fixture can
# never again touch genuine reference rows.
SYNTHETIC_HPO_IDS = [
    "HP:9990001",
    "HP:9990002",
    "HP:9990003",
    "HP:9990004",
    "HP:9990005",
    "HP:9990006",
    "HP:9990007",
    "HP:9990008",
    "HP:9990009",
    "HP:9990010",
]


@pytest.fixture
async def populate_hpo_terms(db_session: AsyncSession):
    """Populate hpo_terms_lookup table with sample data."""
    # Pre-cleanup: Remove any leftover test data (exact ids only — see
    # SYNTHETIC_HPO_IDS comment for why this must never be a LIKE pattern).
    try:
        await db_session.execute(
            text("DELETE FROM hpo_terms_lookup WHERE hpo_id = ANY(:ids)"),
            {"ids": SYNTHETIC_HPO_IDS},
        )
        await db_session.commit()
    except Exception:
        await db_session.rollback()

    # Ensure fresh session state
    await db_session.rollback()

    hpo_terms_data = [
        (SYNTHETIC_HPO_IDS[0], "Abnormality of the kidney", 100),
        (SYNTHETIC_HPO_IDS[1], "Renal cyst", 50),
        (SYNTHETIC_HPO_IDS[2], "Kidney disease", 120),
        (SYNTHETIC_HPO_IDS[3], "Abnormal kidney morphology", 80),
        (SYNTHETIC_HPO_IDS[4], "Diabetes mellitus", 200),
        (SYNTHETIC_HPO_IDS[5], "Diabetic nephropathy", 70),
        (SYNTHETIC_HPO_IDS[6], "Hypomagnesemia", 150),
        (SYNTHETIC_HPO_IDS[7], "Magnesium deficiency", 60),
        (SYNTHETIC_HPO_IDS[8], "Renal tubular acidosis", 40),
        (SYNTHETIC_HPO_IDS[9], "Tubular dysfunction", 30),
    ]

    for hpo_id, label, count in hpo_terms_data:
        await db_session.execute(
            text(
                """
                INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count)
                VALUES (:hpo_id, :label, :count)
                ON CONFLICT (hpo_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    phenopacket_count = EXCLUDED.phenopacket_count
                """
            ),
            {"hpo_id": hpo_id, "label": label, "count": count},
        )
    await db_session.commit()

    yield

    # Cleanup: delete precisely the ids inserted above (exact match, no LIKE
    # pattern — see SYNTHETIC_HPO_IDS comment).
    try:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM hpo_terms_lookup WHERE hpo_id = ANY(:ids)"),
            {"ids": SYNTHETIC_HPO_IDS},
        )
        await db_session.commit()
    except Exception:
        try:
            await db_session.rollback()
        except Exception:
            # Ignore exceptions during rollback in cleanup; session may already be closed or in an invalid state.
            pass


@pytest.mark.asyncio
async def test_hpo_autocomplete_basic(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test basic HPO autocomplete functionality."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=kidney", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    assert any("Kidney disease" in term["label"] for term in data)
    assert any("Abnormality of the kidney" in term["label"] for term in data)


@pytest.mark.asyncio
async def test_hpo_autocomplete_fuzzy_matching(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test HPO autocomplete with fuzzy matching (typo)."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=kidny", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    assert any("Kidney disease" in term["label"] for term in data)


@pytest.mark.asyncio
async def test_hpo_autocomplete_limit(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test HPO autocomplete limit parameter."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=renal&limit=2", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2


@pytest.mark.asyncio
async def test_hpo_autocomplete_min_length(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test HPO autocomplete with query string less than min_length."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=k", headers=auth_headers
    )
    assert response.status_code == 422  # Unprocessable Entity due to validation error


@pytest.mark.asyncio
async def test_hpo_autocomplete_no_results(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test HPO autocomplete with a query that yields no results."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=nonexistentterm", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 0


@pytest.mark.asyncio
async def test_hpo_autocomplete_ranking(
    async_client: AsyncClient, populate_hpo_terms, auth_headers
):
    """Test HPO autocomplete results are ranked by similarity first, then count."""
    response = await async_client.get(
        "/api/v2/ontology/hpo/autocomplete?q=magnesium", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 1

    # Expect Magnesium deficiency to rank higher than Hypomagnesemia because
    # it has higher similarity (exact substring match) even though Hypomagnesemia
    # has more phenopackets (150 vs 60). Similarity is prioritized over count.
    hypomagnesemia_index = -1
    magnesium_deficiency_index = -1

    for i, term in enumerate(data):
        if "Hypomagnesemia" in term["label"]:
            hypomagnesemia_index = i
        if "Magnesium deficiency" in term["label"]:
            magnesium_deficiency_index = i

    assert hypomagnesemia_index != -1
    assert magnesium_deficiency_index != -1
    assert magnesium_deficiency_index < hypomagnesemia_index, (
        "Magnesium deficiency should rank higher due to better similarity match"
    )


@pytest.mark.asyncio
async def test_populate_hpo_terms_does_not_destroy_real_reference_data(
    db_session: AsyncSession, populate_hpo_terms
):
    """Regression test for the fixture corrupting shared reference data.

    HP:0000003 ("Multicystic kidney dysplasia") is real reference data that
    carries a laterality policy (see test_laterality_policy.py) and is used
    by hundreds of stored phenotypic features. A previous version of
    ``populate_hpo_terms`` inserted fake rows under real HPO ids (including
    this one) and then deleted them with an imprecise ``LIKE`` pattern,
    which destroyed this row as a side effect of every autocomplete test
    run. This test asserts the row survives the fixture — both while the
    fixture's synthetic rows are present (``yield``-time, checked here) and
    ensures the fixture is exercised at all so its cleanup runs too.
    """
    result = await db_session.execute(
        text(
            "SELECT label, allowed_modifiers FROM hpo_terms_lookup "
            "WHERE hpo_id = 'HP:0000003'"
        )
    )
    row = result.first()
    assert row is not None, (
        "HP:0000003 missing from hpo_terms_lookup — the autocomplete fixture "
        "destroyed real reference data"
    )
    label, allowed_modifiers = row
    assert label == "Multicystic kidney dysplasia"
    assert len(allowed_modifiers) > 0, (
        "HP:0000003.allowed_modifiers must remain non-empty (laterality policy)"
    )
