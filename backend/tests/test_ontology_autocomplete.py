import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def populate_hpo_terms(db_session: AsyncSession):
    """Populate hpo_terms_lookup table with sample data."""
    # Pre-cleanup: Remove any leftover test data
    try:
        await db_session.execute(
            text("DELETE FROM hpo_terms_lookup WHERE hpo_id LIKE 'HP:000000%'")
        )
        await db_session.commit()
    except Exception:
        await db_session.rollback()

    # Ensure fresh session state
    await db_session.rollback()

    hpo_terms_data = [
        ("HP:0000001", "Abnormality of the kidney", 100),
        ("HP:0000002", "Renal cyst", 50),
        ("HP:0000003", "Kidney disease", 120),
        ("HP:0000004", "Abnormal kidney morphology", 80),
        ("HP:0000005", "Diabetes mellitus", 200),
        ("HP:0000006", "Diabetic nephropathy", 70),
        ("HP:0000007", "Hypomagnesemia", 150),
        ("HP:0000008", "Magnesium deficiency", 60),
        ("HP:0000009", "Renal tubular acidosis", 40),
        ("HP:0000010", "Tubular dysfunction", 30),
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

    # Cleanup
    try:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM hpo_terms_lookup WHERE hpo_id LIKE 'HP:000000%'")
        )
        await db_session.commit()
    except Exception:
        try:
            await db_session.rollback()
        except Exception:
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
