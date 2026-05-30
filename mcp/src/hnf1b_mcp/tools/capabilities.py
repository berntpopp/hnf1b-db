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
        annotations={
            "title": "HNF1B: Capabilities & Tool Inventory",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_capabilities() -> dict[str, Any]:
        """Return server capabilities, tool inventory, and operational metadata.

        Discover what the HNF1B MCP server can do: canonical workflows, the
        full tool inventory with per-tool summaries, supported payload modes
        with character budgets, pagination limits, citation contract, error
        codes, data-class taxonomy, v1 exclusions, and safety notices.

        Calling this is RECOMMENDED for orientation in a new/cold session but
        is OPTIONAL: tools with enum-constrained filters advertise them in
        `filterable_fields`, so many valid calls can be built without a cold
        capabilities load. A
        warm client should compare the returned `capabilities_version` content
        hash and skip re-fetching this descriptor when it is unchanged. It can
        also compare `tool_guide_version` before re-reading the tool-guide
        resource and inspect `descriptor_chars` (echoed as
        `meta.descriptor_chars`) for the current serialized descriptor size. No
        arguments are required and no API call is made — the response is
        assembled from server-local data.

        Returns:
            A dict with keys ``canonical_workflows``, ``tools``,
            ``filterable_fields`` (per-tool valid filter params + their allowed
            enum values — read this to construct valid calls), ``payload_modes``,
            ``limits``, ``identifiers`` (the canonical id form per record type),
            ``pagination_semantics``, ``citation_contract``, ``error_codes``,
            ``data_classes``, ``exclusions``, ``safety``, ``resources``,
            ``tool_guide_version``, ``capabilities_version`` (a content hash a
            warm client can compare to skip re-fetching), ``descriptor_chars``,
            ``data_class``, and ``meta``.
        """

        async def handler() -> dict[str, Any]:
            descriptor = get_capabilities()
            descriptor["_meta"] = {"descriptor_chars": descriptor["descriptor_chars"]}
            return descriptor

        return await run_tool(
            handler, data_class=DataClass.OPERATIONAL, response_mode="compact"
        )
