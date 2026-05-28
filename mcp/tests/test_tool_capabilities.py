"""Tests for the hnf1b_get_capabilities tool registration and behavior."""
import pytest
from fastmcp import FastMCP

from hnf1b_mcp.tools.capabilities import register


@pytest.mark.asyncio
async def test_registers_with_readonly_hint():
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_capabilities")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_returns_capabilities_payload():
    mcp = FastMCP("test")
    register(mcp, None)
    r = await mcp.call_tool("hnf1b_get_capabilities", {})
    sc = r.structured_content
    assert sc["data_class"] == "operational_metadata"
    assert "meta" in sc
    assert len(sc["tools"]) >= 10
