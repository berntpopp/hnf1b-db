import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.search.services import GlobalSearchService

@pytest.mark.asyncio
async def test_global_search_integration(db_session: AsyncSession):
    # 1. Setup Data
    # Insert a dummy gene
    await db_session.execute(text("""
        INSERT INTO genes (id, symbol, name, chromosome, start, "end", strand, genome_id, source)
        VALUES (gen_random_uuid(), 'TESTGENE', 'Test Gene for Search', '1', 100, 200, '+', gen_random_uuid(), 'Manual')
    """))
    
    # Insert a dummy publication
    await db_session.execute(text("""
        INSERT INTO publication_metadata (pmid, title, authors, journal, year)
        VALUES ('PMID:99999', 'Clinical features of TESTGENE mutations', '[]'::jsonb, 'Genetics Med', 2024)
    """))
    
    # Insert a dummy phenopacket (requires jsonb)
    await db_session.execute(text("""
        INSERT INTO phenopackets (phenopacket_id, phenopacket)
        VALUES ('PP_SEARCH_001', '{"subject": {"id": "SUBJ_001", "sex": "MALE"}}'::jsonb)
    """))

    await db_session.commit()

    # 2. Refresh Materialized View
    await db_session.execute(text("REFRESH MATERIALIZED VIEW global_search_index"))
    await db_session.commit()

    # 3. Test Autocomplete
    results = await GlobalSearchService.autocomplete(db_session, "TEST", limit=10)
    assert len(results) >= 1
    assert any(r.label == 'TESTGENE' for r in results)
    
    # Test Autocomplete for Publication (by Title isn't in autocomplete label logic? 
    # MV label for pub is Title. So yes.)
    results_pub = await GlobalSearchService.autocomplete(db_session, "Clinical", limit=10)
    assert len(results_pub) >= 1
    assert any(r.id == 'PMID:99999' for r in results_pub)

    # 4. Test Global Search
    search_res = await GlobalSearchService.global_search(db_session, "TESTGENE")
    assert search_res["total"] >= 2 # Gene + Publication
    types = search_res["summary"]
    assert types.get("Gene") >= 1
    assert types.get("Publication") >= 1
    
    # Test Filter
    search_res_gene = await GlobalSearchService.global_search(db_session, "TESTGENE", type_filter="Gene")
    assert len(search_res_gene["results"]) == 1
    assert search_res_gene["results"][0].type == "Gene"

    # Cleanup (optional, transaction rollback handles it usually, but MV persists?)
    # MV is separate storage. Data in tables will be rolled back by pytest fixture if properly set up.
    # But Refresh MV commits data to MV.
    # Future tests might see this data in MV if not cleared.
    # Ideally we'd truncate tables and refresh MV at end, or fixture handles it.
