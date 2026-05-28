"""Tool module: hnf1b_get_capabilities — server discovery and metadata."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.capabilities import get_capabilities
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool


def register(mcp: FastMCP, client: ApiClient | None) -> None:  # noqa: ARG001
    """Register the hnf1b_get_capabilities tool on the given FastMCP instance.

    Args:
        mcp: The FastMCP application instance to register the tool on.
        client: The API client (unused for this tool; may be ``None``).
    """

    @mcp.tool(
        name="hnf1b_get_capabilities",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_get_capabilities() -> dict[str, Any]:
        """Return server capabilities, tool inventory, and operational metadata.

        Discover what the HNF1B MCP server can do: canonical workflows, the
        full tool inventory with per-tool summaries, supported payload modes
        with character budgets, pagination limits, citation contract, error
        codes, data-class taxonomy, v1 exclusions, and safety notices.

        Call this tool first when starting a new session to orient yourself
        before using any other HNF1B tool.  No arguments are required and no
        API call is made — the response is assembled from server-local data.

        Returns:
            A dict with keys ``canonical_workflows``, ``tools``,
            ``payload_modes``, ``limits``, ``citation_contract``,
            ``error_codes``, ``data_classes``, ``exclusions``, ``safety``,
            ``data_class``, and ``meta``.
        """

        async def handler() -> dict[str, Any]:
            return get_capabilities()

        return await run_tool(
            handler, data_class=DataClass.OPERATIONAL, response_mode="compact"
        )
