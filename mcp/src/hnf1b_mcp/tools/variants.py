"""MCP tools: hnf1b_search_variants and hnf1b_get_variant."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.contract import (
    MolecularConsequence,
    ProteinDomain,
    VariantClassification,
)
from hnf1b_mcp.services import variants as variants_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import ResponseMode, resolve_mode
from hnf1b_mcp.services.variants import VariantSort


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the variants tools on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_search_variants",
        annotations={
            "title": "Search HNF1B Variants",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_search_variants(
        query: str | None = None,
        variant_type: str | None = None,
        classification: VariantClassification | None = None,
        gene: str | None = None,
        consequence: MolecularConsequence | None = None,
        domain: ProteinDomain | None = None,
        page: int = 1,
        page_size: int = 25,
        sort: VariantSort | None = None,
        response_mode: ResponseMode | None = None,
    ) -> dict[str, Any]:
        """Browse HNF1B variant records with optional filters.

        Returns a paginated list of HNF1B-db variants shaped with canonical
        fields (``variant_id``, ``label``, ``classification``, ``consequence``,
        ``hg38``, ``carrier_count``, ``uri``, etc.).  Filter by pathogenicity
        classification, molecular consequence, protein domain, gene, or a
        free-text query.

        Args:
            query: Free-text search string forwarded to the API.
            variant_type: Free-form variant type filter (e.g. ``"SNV"``,
                ``"DEL"``).
            classification: Pathogenicity classification filter.  Must be one
                of ``PATHOGENIC``, ``LIKELY_PATHOGENIC``,
                ``UNCERTAIN_SIGNIFICANCE``, ``LIKELY_BENIGN``, or ``BENIGN``.
            gene: Gene symbol or identifier filter (free-form).
            consequence: Molecular consequence filter.  Must be one of the
                ``MolecularConsequence`` values (e.g. ``Frameshift``,
                ``Nonsense``, ``Missense``, ``Splice Donor``).
            domain: Protein domain filter.  Must be one of
                ``"Dimerization Domain"``, ``"POU-Specific Domain"``,
                ``"POU Homeodomain"``, or ``"Transactivation Domain"``.
            page: 1-based page number (default 1).
            page_size: Number of results per page (default 25, capped at 500).
            sort: Sort the result set by one of the sortable fields:
                ``carrier_count``, ``classification``, ``structural_type``,
                ``variant_id``, ``simple_id``, ``transcript``, ``protein``, or
                ``hg38``.  A leading ``-`` means descending (e.g.
                ``-carrier_count`` lists the most common variants first); no
                prefix means ascending.  The honored sort is echoed back in
                ``meta.applied_sort`` using this same public vocabulary.
                ``carrier_count`` counts DISTINCT carrier individuals
                (phenopackets) for the variant — NOT reports/observations or
                distinct publications (see ``meta.carrier_count_basis``).
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to
                ``compact``.

        Returns:
            A dict with keys ``variants``, ``total``, ``total_pages``,
            ``has_more``, ``page``, ``page_size``, ``data_class``, and
            ``meta``.  In ``minimal``/``compact`` the invariant gene symbol is
            hoisted to ``gene_symbol_all`` and dropped from each row, while the
            friendly ``simple_id`` is retained alongside ``variant_id``.  When a
            ``consequence`` filter is supplied it is applied server-side and a
            ``filtered_count`` (== ``total``) is included.
        """
        mode = resolve_mode(response_mode)
        return await run_tool(
            lambda: variants_service.search_variants(
                client,  # type: ignore[arg-type]
                query=query,
                variant_type=variant_type,
                classification=classification,
                gene=gene,
                consequence=consequence,
                domain=domain,
                page=page,
                page_size=page_size,
                sort=sort,
                response_mode=mode,
            ),
            data_class=DataClass.CURATED,
            response_mode=mode,
        )

    @mcp.tool(
        name="hnf1b_get_variant",
        annotations={
            "title": "Get HNF1B Variant",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_variant(
        variant_id: str,
        response_mode: ResponseMode | None = None,
        include_carriers: bool = False,
    ) -> dict[str, Any]:
        """Fetch the full authoritative record for a single HNF1B variant.

        Returns the complete curated variant record — ``classification``
        (pathogenicity), molecular ``consequence``, ``label``, ``hg38``,
        ``transcript``, ``protein``, ``structural_type``, ``gene_symbol`` and
        ``carrier_count`` — together with a ``carriers`` list of phenopacket IDs.
        Pass those ``carriers`` IDs to ``hnf1b_get_individuals`` for per-carrier
        phenotype detail. ``carrier_count`` counts DISTINCT carrier individuals
        (phenopackets) for the variant — NOT reports/observations or distinct
        publications (see ``meta.carrier_count_basis``).

        Carriers are SUMMARIZED by default to bound token cost: a heavily-carried
        variant can have hundreds of carrier IDs. By default (and in EVERY
        response mode) at most 10 carrier IDs are returned; ``carrier_count``
        stays the true total, and when the full set is larger the ``meta`` block
        carries ``carriers_total``, ``carriers_returned``, ``carriers_truncated``,
        and a ``carriers_note`` naming how to get the rest. Set
        ``include_carriers=True`` to return the full list (still bounded by the
        response-mode char budget, with the same truncation signal if it must be
        trimmed). For the matched cohort WITH phenotype detail, use
        ``hnf1b_find_individuals_by_phenotype`` instead.

        Args:
            variant_id: The variant identifier as returned by
                ``hnf1b_search_variants`` — either the canonical id (GA4GH VRS
                ``"ga4gh:VA.…"`` or CNV ``"var:HNF1B:17:…:DEL"``) or the
                friendly ``simple_id`` (e.g. ``"Var6"``).
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to
                ``compact``.
            include_carriers: When ``False`` (default) the ``carriers`` list is
                summarized to at most 10 IDs (in every mode) with a
                ``carriers_truncated`` meta signal; when ``True`` the full
                carriers list is returned, bounded by the response-mode char
                budget.

        Returns:
            A dict with keys ``variant_id``, ``simple_id``, ``label``,
            ``gene_symbol``, ``classification``, ``consequence``,
            ``structural_type``, ``hg38``, ``transcript``, ``protein``,
            ``carrier_count``, ``carriers``, ``uri``, ``data_provenance``,
            ``note``, ``data_class``, and ``meta``.
        """
        mode = resolve_mode(response_mode)
        return await run_tool(
            lambda: variants_service.get_variant(
                client,  # type: ignore[arg-type]
                variant_id,
                response_mode=mode,
                include_carriers=include_carriers,
            ),
            data_class=DataClass.CURATED,
            response_mode=mode,
        )
