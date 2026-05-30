"""Tests for capabilities and resources services."""

import hashlib
import json
import re
from pathlib import Path

from hnf1b_mcp.contract import (
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
)
from hnf1b_mcp.services.capabilities import get_capabilities
from hnf1b_mcp.services.publications import PUBLICATION_SORT_FIELDS
from hnf1b_mcp.services.resources import RESOURCE_URIS, load_resource
from hnf1b_mcp.services.variants import VARIANT_SORT_FIELDS

TOOL_GUIDE_URI = "hnf1b://schema/tool-guide"


def test_capabilities_version_present_and_deterministic():
    """A content hash is exposed and stable across calls (warm-client skip)."""
    cap = get_capabilities()
    assert cap["capabilities_version"].startswith("sha256:")
    assert cap["capabilities_version"] == get_capabilities()["capabilities_version"]


def test_capabilities_descriptor_chars_is_computed_size():
    cap = get_capabilities()
    descriptor_chars = cap["descriptor_chars"]
    descriptor_without_size = dict(cap)
    descriptor_without_size.pop("descriptor_chars")
    expected = len(json.dumps(descriptor_without_size, sort_keys=True, default=str))
    assert descriptor_chars == expected


def test_tool_guide_version_is_content_hash_and_advertised():
    cap = get_capabilities()
    guide_body = load_resource(TOOL_GUIDE_URI)
    expected = hashlib.sha256(guide_body.encode("utf-8")).hexdigest()[:16]
    expected_version = f"sha256:{expected}"
    assert cap["tool_guide_version"] == expected_version
    assert cap["resources"]["tool_guide"] == {
        "uri": TOOL_GUIDE_URI,
        "version": expected_version,
    }


def test_capabilities_descriptor_size_is_not_hardcoded_in_source():
    source_root = Path(__file__).resolve().parents[1] / "src" / "hnf1b_mcp"
    stale_size = re.compile(r"~(?:9|11)k(?:[- ]?chars?)?", re.IGNORECASE)
    offenders: list[str] = []
    for path in source_root.rglob("*.py"):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if stale_size.search(line):
                rel = path.relative_to(source_root)
                offenders.append(f"{rel}:{line_number}: {line.strip()}")
    assert offenders == []


def test_capabilities_citation_contract_scoped_to_publications():
    """The citation claim is scoped, not the falsified universal 'every response'."""
    contract = get_capabilities()["citation_contract"].lower()
    assert "publication and evidence payloads" in contract
    assert "every response includes a recommended_citation" not in contract


def test_capabilities_shape():
    cap = get_capabilities()
    assert "canonical_workflows" in cap
    assert "tools" in cap and len(cap["tools"]) >= 10
    assert cap["citation_contract"]
    assert cap["pagination_semantics"]
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
        "hnf1b_get_variant",
        "hnf1b_resolve_terms",
        "hnf1b_get_statistics",
        "hnf1b_get_publications",
        "hnf1b_get_publication_passages",
        "hnf1b_get_individuals",
        "hnf1b_find_individuals_by_phenotype",
        "hnf1b_get_gene_context",
    }

    # get_gene_context advertises the exon-gating opt-in so the summarized-by-
    # default behavior (exon_count scalar, no exon array) is discoverable.
    gc = ff["hnf1b_get_gene_context"]
    assert gc["include_exons"]["type"] == "boolean"
    assert gc["include_exons"]["default"] is False
    gc_hint = gc["include_exons"]["hint"].lower()
    assert "exon_count" in gc_hint
    assert "exons" in gc_hint

    # get_variant advertises the carrier-summarization opt-out so the
    # summarized-by-default behavior is discoverable from capabilities.
    gv = ff["hnf1b_get_variant"]
    assert gv["include_carriers"]["type"] == "boolean"
    assert gv["include_carriers"]["default"] is False
    gv_hint = gv["include_carriers"]["hint"].lower()
    assert "carriers_truncated" in gv_hint
    assert "hnf1b_find_individuals_by_phenotype" in gv_hint

    # get_publications advertises the citing_individuals-summarization opt-out so
    # the summarized-by-default reverse-lookup behavior is discoverable too.
    gp = ff["hnf1b_get_publications"]
    assert gp["include_citing_individuals"]["type"] == "boolean"
    assert gp["include_citing_individuals"]["default"] is False
    gp_hint = gp["include_citing_individuals"]["hint"].lower()
    assert "citing_individuals_truncated" in gp_hint
    assert "hnf1b_find_individuals_by_phenotype" in gp_hint

    # The advertised publication sort vocabulary is exactly the canonical
    # sortable fields, sourced from the tool's own map so the advert can never
    # drift from what the tool actually honors (mirrors the search_variants sort
    # lock above).
    assert gp["sort"]["values"] == list(PUBLICATION_SORT_FIELDS)
    assert "descending" in gp["sort"]["hint"].lower()

    # find_individuals_by_phenotype advertises match_mode so the AND/intersection
    # capability is discoverable alongside the default OR/union semantics.
    fp = ff["hnf1b_find_individuals_by_phenotype"]
    assert fp["match_mode"]["values"] == ["any", "all"]
    fp_hint = fp["match_mode"]["hint"].lower()
    assert "union" in fp_hint
    assert "intersection" in fp_hint
    # The capping caveat for the AND path must be surfaced in the advert.
    assert "cap" in fp_hint

    sv = ff["hnf1b_search_variants"]
    # Exactly the real filter/sort params plus the carrier_count field-semantics
    # note — no invented hgvs_c / acmg_class.
    assert set(sv) == {
        "classification",
        "consequence",
        "variant_type",
        "domain",
        "gene",
        "query",
        "sort",
        "carrier_count",
    }
    # sort defaults to most-common-first so "top variant" needs no extra call.
    assert "carrier_count" in sv["sort"]["values"]
    # The advertised sort vocabulary is exactly the canonical sortable fields,
    # so a consuming LLM can self-describe a valid sort without guessing — and
    # the advert can never drift from what the tool actually honors.
    assert sv["sort"]["values"] == list(VARIANT_SORT_FIELDS)
    # The direction syntax must be documented so '-carrier_count' is not a guess.
    assert "descending" in sv["sort"]["hint"].lower()
    assert sv["classification"]["values"] == list(VARIANT_CLASSIFICATION_VALUES)
    assert sv["consequence"]["values"] == list(MOLECULAR_CONSEQUENCE_VALUES)
    assert sv["variant_type"]["values"] == list(VARIANT_TYPE_VALUES)
    assert sv["domain"]["values"] == list(PROTEIN_DOMAIN_VALUES)
    # 'Missense' is the capitalized consequence value, not a variant_type.
    assert "Missense" in sv["consequence"]["values"]
    assert "Missense" not in sv["variant_type"]["values"]

    # carrier_count semantics are discoverable from capabilities, so "most
    # common variant" is never ambiguous: it counts distinct carrier
    # individuals (phenopackets), not reports/observations or publications.
    cc = sv["carrier_count"]
    assert cc["basis"] == "distinct_carrier_individuals"
    cc_hint = cc["hint"].lower()
    assert "individual" in cc_hint or "phenopacket" in cc_hint
    assert "publication" in cc_hint

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
    assert TOOL_GUIDE_URI in RESOURCE_URIS
    assert len(load_resource("hnf1b://schema/overview")) > 100
