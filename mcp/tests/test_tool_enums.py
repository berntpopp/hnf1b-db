"""B7: schema-visible Literal enums for response_mode / mode / rerank / genome_build.

Two guarantees:
  1. Each tool-facing Literal stays in lockstep with the runtime tuple it
     mirrors (drift guards), so adding a value in one place fails loudly until
     the other is updated.
  2. The Literals actually surface as ``enum`` in the generated JSON input
     schema for every tool that takes them — the whole point of B7 (a client/
     agent can see the allowed values instead of an opaque ``string``).
"""

from typing import get_args

import pytest
from fastmcp import FastMCP

from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.publication_passages import (
    API_MODES,
    RERANK_MODES,
    PassageMode,
    RerankMode,
)
from hnf1b_mcp.services.reference import GENOME_BUILDS, GenomeBuild, get_gene_context
from hnf1b_mcp.services.shaping import MODES, ResponseMode
from hnf1b_mcp.tools import register_all

# ---------------------------------------------------------------------------
# Drift guards: Literal members must equal the runtime-validated tuple.
# ---------------------------------------------------------------------------


def test_response_mode_literal_matches_modes():
    assert set(get_args(ResponseMode)) == set(MODES)


def test_passage_mode_literal_matches_api_modes():
    assert set(get_args(PassageMode)) == set(API_MODES)


def test_rerank_mode_literal_matches_rerank_modes():
    assert set(get_args(RerankMode)) == set(RERANK_MODES)


def test_genome_build_literal_matches_builds():
    assert set(get_args(GenomeBuild)) == set(GENOME_BUILDS)


# ---------------------------------------------------------------------------
# Schema introspection: the enums are visible in the JSON input schema.
# ---------------------------------------------------------------------------


def _enum_values(schema: dict) -> set[str] | None:
    """Extract the enum value set from a param schema (direct or under anyOf)."""
    if "enum" in schema:
        return set(schema["enum"])
    for branch in schema.get("anyOf", []):
        if "enum" in branch:
            return set(branch["enum"])
    return None


async def _tool_params() -> dict[str, dict]:
    mcp = FastMCP("enum-test")
    register_all(mcp, client=None)
    tools = await mcp.list_tools()
    return {t.name: (getattr(t, "parameters", None) or {}) for t in tools}


@pytest.mark.asyncio
async def test_response_mode_is_enum_on_every_tool_that_takes_it():
    params = await _tool_params()
    seen = 0
    for name, schema in params.items():
        props = schema.get("properties", {})
        if "response_mode" in props:
            seen += 1
            assert _enum_values(props["response_mode"]) == set(MODES), name
    # All but get_capabilities expose response_mode; guard against a silent drop.
    assert seen >= 10


@pytest.mark.asyncio
async def test_passages_mode_rerank_are_enums():
    params = await _tool_params()
    props = params["hnf1b_get_publication_passages"]["properties"]
    assert _enum_values(props["mode"]) == set(API_MODES)
    assert _enum_values(props["rerank"]) == set(RERANK_MODES)


@pytest.mark.asyncio
async def test_genome_build_is_enum_on_gene_context():
    params = await _tool_params()
    props = params["hnf1b_get_gene_context"]["properties"]
    assert _enum_values(props["genome_build"]) == set(GENOME_BUILDS)


# ---------------------------------------------------------------------------
# genome_build was the one true silent passthrough — now it rejects typos.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_genome_build_rejects_unknown_value():
    # Validation precedes any HTTP call, so a client is never needed.
    with pytest.raises(McpToolError) as excinfo:
        await get_gene_context(client=None, genome_build="hg38")  # type: ignore[arg-type]
    err = excinfo.value
    assert err.code == "invalid_input"
    assert err.details.get("argument") == "genome_build"
    assert "GRCh38" in err.details.get("choices", [])
