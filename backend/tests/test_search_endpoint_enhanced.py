import json
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


@pytest.fixture(scope="function")
async def sample_phenopackets_for_search(db_session: AsyncSession):
    """Create sample phenopackets for enhanced search testing."""
    from sqlalchemy import delete

    sanitizer = PhenopacketSanitizer()

    # Pre-cleanup: Remove any leftover test data from failed previous runs
    try:
        await db_session.execute(
            delete(Phenopacket).where(Phenopacket.phenopacket_id.like("search_pp_%"))
        )
        await db_session.commit()
    except Exception:
        await db_session.rollback()

    # Ensure fresh session state
    await db_session.rollback()

    phenopackets_data = []

    # Phenopacket 1: UNIQUE test phenotype, MALE, HNF1B gene, PMID:123
    # Use UNIQUE search terms to avoid conflicts with 864 real phenopackets
    pp1_data = {
        "id": "search_pp_001",
        "subject": {"id": "patient_001", "sex": "MALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000077", "label": "ZZTEST_UNIQUE_RENAL_ABNORMALITY"}},
            {"type": {"id": "HP:0000112", "label": "ZZTEST_UNIQUE_NEPHROPATHY"}},
        ],
        "interpretations": [
            {
                "id": "interp_001",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "geneContext": {"symbol": "HNF1B"}
                                }
                            }
                        }
                    ]
                },
            }
        ],
        "metaData": {
            "created": (datetime.now() - timedelta(days=10)).isoformat() + "Z",
            "phenopacketSchemaVersion": "2.0.0",
            "externalReferences": [{"id": "PMID:123", "reference": "pubmed.gov/123"}],
        },
    }
    pp1_sanitized = sanitizer.sanitize_phenopacket(pp1_data)
    pp1 = Phenopacket(
        phenopacket_id=pp1_sanitized["id"],
        phenopacket=pp1_sanitized,
        subject_id=pp1_sanitized["subject"]["id"],
        subject_sex=pp1_sanitized["subject"].get("sex", "UNKNOWN_SEX"),
        created_by="test_user",
        created_at=datetime.now() - timedelta(days=10),
    )
    db_session.add(pp1)
    phenopackets_data.append(pp1)

    # Phenopacket 2: Diabetes, FEMALE, GCK gene, PMID:456
    pp2_data = {
        "id": "search_pp_002",
        "subject": {"id": "patient_002", "sex": "FEMALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000118", "label": "Diabetes mellitus"}},
            {"type": {"id": "HP:0000119", "label": "Hyperglycemia"}},
        ],
        "interpretations": [
            {
                "id": "interp_002",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "geneContext": {"symbol": "GCK"}
                                }
                            }
                        }
                    ]
                },
            }
        ],
        "metaData": {
            "created": (datetime.now() - timedelta(days=5)).isoformat() + "Z",
            "phenopacketSchemaVersion": "2.0.0",
            "externalReferences": [{"id": "PMID:456", "reference": "pubmed.gov/456"}],
        },
    }
    pp2_sanitized = sanitizer.sanitize_phenopacket(pp2_data)
    pp2 = Phenopacket(
        phenopacket_id=pp2_sanitized["id"],
        phenopacket=pp2_sanitized,
        subject_id=pp2_sanitized["subject"]["id"],
        subject_sex=pp2_sanitized["subject"].get("sex", "UNKNOWN_SEX"),
        created_by="test_user",
        created_at=datetime.now() - timedelta(days=5),
    )
    db_session.add(pp2)
    phenopackets_data.append(pp2)

    # Phenopacket 3: UNIQUE test phenotype, FEMALE, no gene, no PMID
    pp3_data = {
        "id": "search_pp_003",
        "subject": {"id": "patient_003", "sex": "FEMALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000077", "label": "ZZTEST_UNIQUE_RENAL_ABNORMALITY"}},
            {"type": {"id": "HP:0000112", "label": "ZZTEST_UNIQUE_NEPHROPATHY"}},
        ],
        "metaData": {
            "created": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
            "phenopacketSchemaVersion": "2.0.0",
        },
    }
    pp3_sanitized = sanitizer.sanitize_phenopacket(pp3_data)
    pp3 = Phenopacket(
        phenopacket_id=pp3_sanitized["id"],
        phenopacket=pp3_sanitized,
        subject_id=pp3_sanitized["subject"]["id"],
        subject_sex=pp3_sanitized["subject"].get("sex", "UNKNOWN_SEX"),
        created_by="test_user",
        created_at=datetime.now() - timedelta(days=1),
    )
    db_session.add(pp3)
    phenopackets_data.append(pp3)

    await db_session.commit()

    yield phenopackets_data

    # Cleanup: Use delete query instead of iterating over objects
    try:
        await db_session.rollback()  # Clear any pending transactions
        await db_session.execute(
            delete(Phenopacket).where(Phenopacket.phenopacket_id.like("search_pp_%"))
        )
        await db_session.commit()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")
        try:
            await db_session.rollback()
        except Exception:
            # Ignore errors during rollback in cleanup to avoid cascading failures in test teardown.
            pass


@pytest.mark.asyncio
async def test_search_full_text_query(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test full-text search with a query string.

    Uses unique search term (ZZTEST) to avoid conflicts with real data.
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=ZZTEST_UNIQUE_RENAL", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2  # Exactly pp1 and pp3 should match
    assert any(pp["id"] == "search_pp_001" for pp in data)
    assert any(pp["id"] == "search_pp_003" for pp in data)
    assert all(pp["meta"]["search_rank"] is not None for pp in data)


@pytest.mark.asyncio
async def test_search_hpo_filter(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with HPO ID filter."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?hpo_id=HP:0000118", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1  # pp2 should match
    assert any(pp["id"] == "search_pp_002" for pp in data)
    assert all("Diabetes mellitus" in json.dumps(pp["attributes"]) for pp in data)


@pytest.mark.asyncio
async def test_search_sex_filter(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with sex filter.

    Verifies that the sex filter correctly filters results to only include
    phenopackets with the specified sex.
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?sex=MALE&limit=100", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1, "Expected at least one result with sex=MALE"

    # Verify ALL results have the correct sex
    for pp in data:
        assert pp["attributes"]["subject"]["sex"] == "MALE", (
            f"Expected all results to have sex=MALE, found: {pp['attributes']['subject'].get('sex')}"
        )


@pytest.mark.asyncio
async def test_search_gene_filter(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with gene symbol filter.

    Verifies that the gene filter correctly filters results to only include
    phenopackets with variants in the specified gene.
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?gene=HNF1B&limit=100", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1, "Expected at least one result with gene=HNF1B"

    # Verify ALL results contain the HNF1B gene in their variant data
    for pp in data:
        pp_json = json.dumps(pp["attributes"])
        assert "HNF1B" in pp_json, (
            f"Expected all results to contain HNF1B gene, phenopacket {pp['id']} does not"
        )


@pytest.mark.asyncio
async def test_search_pmid_filter(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with PMID filter."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?pmid=123", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1  # pp1 should match
    assert any(pp["id"] == "search_pp_001" for pp in data)
    assert all("PMID:123" in json.dumps(pp["attributes"]) for pp in data)


@pytest.mark.asyncio
async def test_search_combined_filters(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with a combination of filters.

    Uses unique search term to avoid conflicts with real data.
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=ZZTEST_UNIQUE_RENAL&sex=FEMALE",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1  # Exactly pp3 should match
    assert any(pp["id"] == "search_pp_003" for pp in data)
    assert all(pp["attributes"]["subject"]["sex"] == "FEMALE" for pp in data)
    assert all("ZZTEST_UNIQUE" in json.dumps(pp["attributes"]) for pp in data)


@pytest.mark.asyncio
async def test_search_no_results(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with a query that yields no results."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=nonexistentphenotype", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 0


@pytest.mark.asyncio
async def test_search_pagination(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search endpoint pagination.

    Uses unique search term to ensure deterministic results.
    Search uses cursor-based pagination (no total count for efficiency).
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=ZZTEST_UNIQUE_RENAL&page[size]=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    meta = response.json()["meta"]
    assert len(data) == 1
    # Cursor pagination uses page.hasNextPage instead of total count
    assert meta["page"]["hasNextPage"] is True

    # Get second page using cursor from first page
    end_cursor = meta["page"]["endCursor"]
    response_page2 = await async_client.get(
        f"/api/v2/phenopackets/search?q=ZZTEST_UNIQUE_RENAL&page[size]=1&page[after]={end_cursor}",
        headers=auth_headers,
    )
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()["data"]
    assert len(data_page2) == 1
    assert data[0]["id"] != data_page2[0]["id"]  # Should be different phenopackets


@pytest.mark.asyncio
async def test_search_rank_by_relevance_false(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with rank_by_relevance=false.

    This test verifies that the rank_by_relevance parameter works correctly
    by ensuring results are returned (sorted by created_at DESC instead of
    relevance score when false). Uses unique search term for deterministic results.
    """
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=ZZTEST_UNIQUE_RENAL&rank_by_relevance=false&limit=100",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2  # Exactly 2 test phenopackets match unique term

    # Verify both test phenopackets are in the results
    test_pp_ids = [
        pp["id"] for pp in data if pp["id"] in ["search_pp_001", "search_pp_003"]
    ]
    assert len(test_pp_ids) == 2, (
        f"Expected to find both test phenopackets, found: {test_pp_ids}"
    )

    # Verify they both contain unique test term
    test_pps = [pp for pp in data if pp["id"] in ["search_pp_001", "search_pp_003"]]
    for pp in test_pps:
        assert "zztest_unique" in json.dumps(pp["attributes"]).lower()
