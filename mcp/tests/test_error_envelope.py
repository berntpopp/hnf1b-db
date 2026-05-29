"""Tests for ErrorEnvelopeMiddleware: raw pydantic errors → clean envelope."""

from __future__ import annotations

import json

import pytest
from fastmcp import FastMCP

from hnf1b_mcp.server import ErrorEnvelopeMiddleware
from hnf1b_mcp.tools.variants import register as register_variants


def _build() -> FastMCP:
    mcp = FastMCP("test")
    mcp.add_middleware(ErrorEnvelopeMiddleware())
    register_variants(mcp, None)
    return mcp


def _envelope(result) -> dict:
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_bad_enum_value_returns_clean_envelope() -> None:
    """A lowercase classification (bad Literal) yields invalid_input + allowed."""
    mcp = _build()
    result = await mcp.call_tool(
        "hnf1b_search_variants", {"classification": "pathogenic"}
    )
    env = _envelope(result)
    assert env["is_error"] is True
    assert env["schema_version"] == "1.0"
    err = env["error"]
    assert err["code"] == "invalid_input"
    assert err["field"] == "classification"
    assert "PATHOGENIC" in err["allowed"]
    assert "hint" in err
    # No raw FastMCP/pydantic shape leaks through.
    assert "literal_error" not in err["message"]


@pytest.mark.asyncio
async def test_unexpected_keyword_returns_clean_envelope() -> None:
    """An unknown parameter name yields invalid_input naming the bad param."""
    mcp = _build()
    result = await mcp.call_tool(
        "hnf1b_search_variants", {"molecular_consequence": "Missense"}
    )
    env = _envelope(result)
    assert env["is_error"] is True
    err = env["error"]
    assert err["code"] == "invalid_input"
    assert err["field"] == "molecular_consequence"
    assert "molecular_consequence" in err["message"]
    assert "capabilities" in err["hint"]
