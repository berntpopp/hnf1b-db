import json
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


@pytest.fixture
async def sample_phenopackets_for_search(db_session: AsyncSession):
    """Create sample phenopackets for enhanced search testing."""
    sanitizer = PhenopacketSanitizer()
    phenopackets_data = []

    # Phenopacket 1: Kidney disease, MALE, HNF1B gene, PMID:123
    pp1_data = {
        "id": "search_pp_001",
        "subject": {"id": "patient_001", "sex": "MALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000077", "label": "Abnormality of the kidney"}},
            {"type": {"id": "HP:0000112", "label": "Kidney disease"}},
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
                                "variationDescriptor": {"geneContext": {"symbol": "GCK"}}
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

    # Phenopacket 3: Kidney disease, FEMALE, no gene, no PMID
    pp3_data = {
        "id": "search_pp_003",
        "subject": {"id": "patient_003", "sex": "FEMALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000077", "label": "Abnormality of the kidney"}},
            {"type": {"id": "HP:0000112", "label": "Kidney disease"}},
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

    # Cleanup
    for pp in phenopackets_data:
        await db_session.delete(pp)
    await db_session.commit()


@pytest.mark.asyncio
async def test_search_full_text_query(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test full-text search with a query string."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=kidney", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 2  # pp1 and pp3 should match
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
    """Test search with sex filter."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?sex=MALE", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1  # pp1 should match
    assert any(pp["id"] == "search_pp_001" for pp in data)
    assert all(pp["attributes"]["subject"]["sex"] == "MALE" for pp in data)


@pytest.mark.asyncio
async def test_search_gene_filter(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with gene symbol filter."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?gene=HNF1B", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1  # pp1 should match
    assert any(pp["id"] == "search_pp_001" for pp in data)
    assert all("HNF1B" in json.dumps(pp["attributes"]) for pp in data)


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
    """Test search with a combination of filters."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=kidney&sex=FEMALE", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1  # pp3 should match
    assert any(pp["id"] == "search_pp_003" for pp in data)
    assert all(pp["attributes"]["subject"]["sex"] == "FEMALE" for pp in data)
    assert all("Kidney disease" in json.dumps(pp["attributes"]) for pp in data)


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
    """Test search endpoint pagination."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=kidney&limit=1", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    meta = response.json()["meta"]
    assert len(data) == 1
    assert meta["total"] >= 2  # pp1 and pp3 match "kidney"

    response_page2 = await async_client.get(
        "/api/v2/phenopackets/search?q=kidney&limit=1&skip=1", headers=auth_headers
    )
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()["data"]
    assert len(data_page2) == 1
    assert data[0]["id"] != data_page2[0]["id"]  # Should be different phenopackets


@pytest.mark.asyncio
async def test_search_rank_by_relevance_false(
    async_client: AsyncClient, sample_phenopackets_for_search, auth_headers
):
    """Test search with rank_by_relevance=false."""
    response = await async_client.get(
        "/api/v2/phenopackets/search?q=kidney&rank_by_relevance=false&limit=100",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 2

    # When rank_by_relevance is false, it should sort by created_at DESC
    # pp3 (created 1 day ago) should be before pp1 (created 10 days ago)
    pp_ids = [pp["id"] for pp in data if pp["id"] in ["search_pp_001", "search_pp_003"]]
    assert pp_ids[0] == "search_pp_003"
    assert pp_ids[1] == "search_pp_001"
