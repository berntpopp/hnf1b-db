"""Reference-data service: gene context from /reference/genes/{symbol}."""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..config import Settings
from ..contract._generated_paths import (
    REFERENCE_GENES_BY_SYMBOL,
    REFERENCE_GENES_BY_SYMBOL_DOMAINS,
    REFERENCE_GENES_BY_SYMBOL_TRANSCRIPTS,
)
from .errors import McpToolError
from .shaping import apply_budget

_HARD_CAP = 80_000


async def get_gene_context(
    client: ApiClient,
    gene_symbol: str = "HNF1B",
    genome_build: str = "GRCh38",
    include_transcripts: bool = True,
    include_domains: bool = True,
    response_mode: str = "compact",
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
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``;
            controls the char budget used to trim transcripts/domains.

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

    try:
        gene: dict[str, Any] = await client.get(
            REFERENCE_GENES_BY_SYMBOL.format(symbol=gene_symbol), params=params
        )
    except McpToolError as exc:
        # The shared client raises a generic, value-less not_found on 404. Re-raise
        # the rich form (field + offending symbol) to match get_variant, so callers
        # learn WHICH gene was missing. Any other error propagates unchanged.
        if exc.code == "not_found":
            raise McpToolError(
                "not_found",
                f"gene '{gene_symbol}' not found",
                field="gene_symbol",
            ) from exc
        raise

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

    # Distinguish "no reference data populated" from "this gene genuinely has
    # none". Empty transcripts/domains or null cross-refs almost always mean the
    # backend's reference tables were not seeded for this gene — say so, so the
    # caller does not report "HNF1B has no protein domains".
    gene_obj = result.get("gene") or {}
    missing: list[str] = []
    if include_transcripts and not result.get("transcripts"):
        missing.append("transcripts")
    if include_domains and not result.get("domains"):
        missing.append("domains")
    if not any(gene_obj.get(k) for k in ("hgnc_id", "ncbi_gene_id", "omim_id")):
        missing.append("cross_references")
    if missing:
        result["reference_data_status"] = (
            "Reference enrichment is unavailable for "
            f"{', '.join(missing)} on this backend instance — this reflects an"
            " unseeded reference dataset, not an assertion that none exist."
            " Re-run the HNF1B reference importer or point the server at a"
            " fully-seeded backend."
        )

    # Token-cost control: trim the (potentially long) transcript/domain lists to
    # the response_mode budget rather than returning them unbounded.
    settings = Settings()
    max_chars = min(settings.mode_char_budgets.get(response_mode, 12000), _HARD_CAP)
    result, dropped = apply_budget(result, max_chars, ["transcripts", "domains"])
    if dropped is not None:
        result["_dropped"] = dropped

    return result
