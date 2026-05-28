"""Reference-data service: gene context from /reference/genes/{symbol}."""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract._generated_paths import (
    REFERENCE_GENES_BY_SYMBOL,
    REFERENCE_GENES_BY_SYMBOL_DOMAINS,
    REFERENCE_GENES_BY_SYMBOL_TRANSCRIPTS,
)


async def get_gene_context(
    client: ApiClient,
    gene_symbol: str = "HNF1B",
    genome_build: str = "GRCh38",
    include_transcripts: bool = True,
    include_domains: bool = True,
) -> dict[str, Any]:
    """Fetch gene context from the HNF1B-db reference API.

    Args:
        client: The shared :class:`ApiClient` instance.
        gene_symbol: HGNC gene symbol to look up.  Defaults to ``"HNF1B"``.
        genome_build: Genome assembly to request (e.g. ``"GRCh38"``).
        include_transcripts: When *True*, fetch and include the transcripts
            list from ``/reference/genes/{gene_symbol}/transcripts``.
        include_domains: When *True*, fetch and include the protein-domain
            list from ``/reference/genes/{gene_symbol}/domains``.

    Returns:
        A plain dict with the following keys:

        - ``gene`` – the full GeneDetailSchema dict.
        - ``transcripts`` – list of transcript dicts (only when
          *include_transcripts* is ``True``).
        - ``domains`` – list of protein-domain dicts (only when
          *include_domains* is ``True``).
        - ``uri`` – a stable ``hnf1b://gene/{gene_symbol}`` identifier.
    """
    params: dict[str, Any] = {"genome_build": genome_build}

    gene: dict[str, Any] = await client.get(
        REFERENCE_GENES_BY_SYMBOL.format(symbol=gene_symbol), params=params
    )

    result: dict[str, Any] = {
        "gene": gene,
        "uri": f"hnf1b://gene/{gene_symbol}",
    }

    if include_transcripts:
        transcripts: list[Any] = await client.get(
            REFERENCE_GENES_BY_SYMBOL_TRANSCRIPTS.format(symbol=gene_symbol),
            params=params,
        )
        result["transcripts"] = transcripts

    if include_domains:
        domains_response: dict[str, Any] = await client.get(
            REFERENCE_GENES_BY_SYMBOL_DOMAINS.format(symbol=gene_symbol),
            params=params,
        )
        result["domains"] = domains_response.get("domains", [])

    return result
