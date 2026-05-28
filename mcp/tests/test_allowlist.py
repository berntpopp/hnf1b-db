import pytest

from hnf1b_mcp.client.allowlist import assert_allowed, is_allowed, is_discovery_only


def test_known_allowed():
    assert is_allowed("/phenopackets/HNF1B-001")
    assert is_allowed("/phenopackets/batch")
    assert is_allowed("/phenopackets/aggregate/summary")
    assert is_allowed("/reference/genes/HNF1B")
    assert is_allowed("/publications/")
    assert is_allowed("/ontology/hpo/autocomplete")

def test_global_search_allowed_after_mv_fix():
    # /search/global and /search/autocomplete are SAFE once the global_search_index
    # MV is fixed (Task A4): state-gated + head-content sourced. They are exposed,
    # NOT excluded. hnf1b_search consumes /search/global.
    assert is_allowed("/search/global")
    assert is_allowed("/search/autocomplete")
    assert is_discovery_only("/search/global")          # IDs/labels only

def test_excluded_side_effecting():
    assert not is_allowed("/publications/PMID:1/metadata")   # PubMed fetch+store
    assert not is_allowed("/admin/sync")
    assert not is_allowed("/auth/login")

def test_assert_raises():
    with pytest.raises(PermissionError):
        assert_allowed("/admin/sync")
