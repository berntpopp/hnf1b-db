"""MCP tool: hnf1b_get_gene_context — gene reference data from HNF1B-db."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import reference as reference_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_get_gene_context tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_gene_context",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_get_gene_context(
        gene_symbol: str = "HNF1B",
        genome_build: str = "GRCh38",
        include_transcripts: bool = True,
        include_domains: bool = True,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Return gene reference data including transcripts and protein domains.

        Fetches the canonical gene record for *gene_symbol* from the HNF1B-db
        reference API (``/reference/genes/{gene_symbol}``).  Optionally
        enriches the result with transcript isoforms and annotated protein
        domains from the two sub-endpoints.

        The payload carries a stable ``hnf1b://gene/{gene_symbol}`` URI that
        can be used to anchor citations or cross-tool references.

        Args:
            gene_symbol: HGNC gene symbol to look up.  Defaults to
                ``"HNF1B"``.
            genome_build: Genome assembly to request coordinates for
                (e.g. ``"GRCh38"`` or ``"GRCh37"``).  Defaults to
                ``"GRCh38"``.
            include_transcripts: When *True* (default), include the list of
                transcript isoforms from
                ``/reference/genes/{gene_symbol}/transcripts``.
            include_domains: When *True* (default), include the list of
                annotated protein domains from
                ``/reference/genes/{gene_symbol}/domains``.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``gene``, optionally ``transcripts`` and
            ``domains``, ``uri``, ``data_class``, and ``meta``.
        """
        return await run_tool(
            lambda: reference_service.get_gene_context(
                client,  # type: ignore[arg-type]
                gene_symbol=gene_symbol,
                genome_build=genome_build,
                include_transcripts=include_transcripts,
                include_domains=include_domains,
            ),
            data_class=DataClass.EXTERNAL_REF,
            response_mode=resolve_mode(response_mode),
        )
