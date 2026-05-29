"""MCP tools exposed by the HNF1B-db server."""

from __future__ import annotations

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools import (
    capabilities,
    compare,
    individuals,
    publication_passages,
    publications,
    reference,
    search,
    statistics,
    terms,
    variants,
)

_MODULES = (
    capabilities,
    search,
    individuals,
    variants,
    reference,
    publications,
    publication_passages,
    statistics,
    terms,
    compare,
)


def register_all(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register every HNF1B tool module on the given FastMCP instance.

    Imports each of the eight tool modules and invokes its ``register``
    function. Tolerates ``client=None`` (tools that need the client guard
    against this themselves).

    Args:
        mcp: The FastMCP application instance to register tools on.
        client: The API client, or ``None`` (e.g. during introspection).
    """
    for module in _MODULES:
        module.register(mcp, client)
