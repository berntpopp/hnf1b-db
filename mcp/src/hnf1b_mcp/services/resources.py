"""Static resource loader for packaged Markdown documentation."""

from __future__ import annotations

import importlib.resources

from hnf1b_mcp.services.errors import McpToolError

RESOURCE_URIS: dict[str, str] = {
    "hnf1b://schema/overview": "schema_overview.md",
    "hnf1b://schema/tool-guide": "tool_guide.md",
}


def load_resource(uri: str) -> str:
    """Load a packaged Markdown resource by its URI.

    Args:
        uri: One of the well-known ``hnf1b://`` resource URIs defined in
            :data:`RESOURCE_URIS`.

    Returns:
        The UTF-8 text content of the corresponding Markdown file.

    Raises:
        McpToolError: With code ``not_found`` when *uri* is not in
            :data:`RESOURCE_URIS`.
    """
    if uri not in RESOURCE_URIS:
        raise McpToolError(
            "not_found",
            f"Unknown resource URI: {uri!r}. Available URIs: {sorted(RESOURCE_URIS)}",
        )
    filename = RESOURCE_URIS[uri]
    resource_pkg = importlib.resources.files("hnf1b_mcp.resources")
    return resource_pkg.joinpath(filename).read_text(encoding="utf-8")
