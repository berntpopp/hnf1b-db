import pytest
from fastmcp import FastMCP

from hnf1b_mcp.tools import register_all


@pytest.mark.asyncio
async def test_all_tools_registered():
    mcp = FastMCP("test")
    register_all(mcp, client=None)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "hnf1b_get_capabilities",
        "hnf1b_search",
        "hnf1b_get_individual",
        "hnf1b_get_individuals",
        "hnf1b_find_individuals_by_phenotype",
        "hnf1b_search_variants",
        "hnf1b_get_variant",
        "hnf1b_get_gene_context",
        "hnf1b_get_publications",
        "hnf1b_get_statistics",
        "hnf1b_resolve_terms",
    }
    assert expected <= names
    for t in tools:
        assert t.annotations.readOnlyHint is True
