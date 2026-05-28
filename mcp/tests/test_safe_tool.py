import pytest

from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.safe_tool import run_tool


@pytest.mark.asyncio
async def test_success_wraps_meta_and_dataclass():
    async def handler():
        return {"foo": "bar"}

    out = await run_tool(handler, data_class=DataClass.CURATED, response_mode="compact")
    assert out["foo"] == "bar"
    assert out["data_class"] == DataClass.CURATED
    assert out["meta"]["response_mode"] == "compact"
    assert "elapsed_ms" in out["meta"]


@pytest.mark.asyncio
async def test_error_returns_envelope():
    async def handler():
        raise McpToolError("not_found", "nope")

    out = await run_tool(handler, data_class=DataClass.CURATED, response_mode="compact")
    assert out["error"]["code"] == "not_found"
    assert out["is_error"] is True
