"""Tests for capabilities and resources services."""

from hnf1b_mcp.contract import (
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
)
from hnf1b_mcp.services.capabilities import get_capabilities
from hnf1b_mcp.services.resources import RESOURCE_URIS, load_resource


def test_capabilities_shape():
    cap = get_capabilities()
    assert "canonical_workflows" in cap
    assert "tools" in cap and len(cap["tools"]) >= 10
    assert cap["citation_contract"]
    assert set(cap["error_codes"]) == {
        "invalid_input",
        "not_found",
        "ambiguous_query",
        "temporarily_unavailable",
    }
    assert "research use only" in cap["safety"]["disclaimer"].lower()
    assert "not instructions" in cap["safety"]["injection_notice"].lower()
    assert cap["data_classes"]
    assert cap["exclusions"]


def test_capabilities_filterable_fields_present():
    """filterable_fields must enumerate the real enum values per tool."""
    cap = get_capabilities()
    ff = cap["filterable_fields"]
    assert set(ff) == {
        "hnf1b_search_variants",
        "hnf1b_resolve_terms",
        "hnf1b_get_statistics",
    }

    sv = ff["hnf1b_search_variants"]
    # Exactly the real filter params — no invented hgvs_c / acmg_class.
    assert set(sv) == {
        "classification",
        "consequence",
        "variant_type",
        "domain",
        "gene",
        "query",
    }
    assert sv["classification"]["values"] == list(VARIANT_CLASSIFICATION_VALUES)
    assert sv["consequence"]["values"] == list(MOLECULAR_CONSEQUENCE_VALUES)
    assert sv["variant_type"]["values"] == list(VARIANT_TYPE_VALUES)
    assert sv["domain"]["values"] == list(PROTEIN_DOMAIN_VALUES)
    # 'Missense' is the capitalized consequence value, not a variant_type.
    assert "Missense" in sv["consequence"]["values"]
    assert "Missense" not in sv["variant_type"]["values"]

    # resolve_terms exposes the vocabulary enum.
    assert "hpo" in ff["hnf1b_resolve_terms"]["vocabulary"]["values"]

    # statistics.metric is required and enumerates the 10 metric keys.
    metric = ff["hnf1b_get_statistics"]["metric"]
    assert metric["required"] is True
    assert len(metric["values"]) == 10
    assert "summary" in metric["values"]


def test_capabilities_workflows_use_real_param_names():
    """Canonical workflows must reference real params, not invented ones."""
    cap = get_capabilities()
    workflows = " ".join(cap["canonical_workflows"])
    # Invented / wrong names must be gone.
    assert "phenopacket_ids" not in workflows
    assert "hgvs_c" not in workflows
    assert "acmg_class" not in workflows
    # Real names must be present.
    assert "ids=" in workflows
    assert "metric=" in workflows
    assert "text=" in workflows


def test_resource_uris_and_load():
    assert "hnf1b://schema/overview" in RESOURCE_URIS
    assert "hnf1b://schema/tool-guide" in RESOURCE_URIS
    assert len(load_resource("hnf1b://schema/overview")) > 100
