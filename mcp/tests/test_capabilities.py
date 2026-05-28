"""Tests for capabilities and resources services."""
from hnf1b_mcp.services.capabilities import get_capabilities
from hnf1b_mcp.services.resources import RESOURCE_URIS, load_resource


def test_capabilities_shape():
    cap = get_capabilities()
    assert "canonical_workflows" in cap
    assert "tools" in cap and len(cap["tools"]) >= 10
    assert cap["citation_contract"]
    assert set(cap["error_codes"]) == {"invalid_input","not_found","ambiguous_query","temporarily_unavailable"}
    assert "research use only" in cap["safety"]["disclaimer"].lower()
    assert "not instructions" in cap["safety"]["injection_notice"].lower()
    assert cap["data_classes"]
    assert cap["exclusions"]


def test_resource_uris_and_load():
    assert "hnf1b://schema/overview" in RESOURCE_URIS
    assert "hnf1b://schema/tool-guide" in RESOURCE_URIS
    assert len(load_resource("hnf1b://schema/overview")) > 100
