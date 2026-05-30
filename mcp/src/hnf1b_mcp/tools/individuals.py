"""MCP tools for retrieving HNF1B-db individual phenopacket records."""

from __future__ import annotations

import re
from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.contract import SexFilter
from hnf1b_mcp.services import individuals as individuals_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode

# Canonical HPO term-ID shape: "HP:" + exactly 7 digits (e.g. HP:0000107).
_HPO_ID_RE = re.compile(r"^HP:\d{7}$")


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register individual phenopacket retrieval and cohort-discovery tools on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_individual",
        annotations={
            "title": "Get HNF1B Individual (phenopacket)",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_individual(
        phenopacket_id: str,
        include_phenotypes: bool = True,
        include_variants: bool = True,
        include_measurements: bool = True,
        include_publications: bool = True,
        response_mode: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve the full phenopacket record for a single individual.

        Fetches by phenopacket_id.

        Fetches authoritative curated data for one HNF1B-db individual from the
        ``/phenopackets/{phenopacket_id}`` endpoint and returns a compact shaped
        record.  Use ``hnf1b_get_individuals`` to retrieve multiple records in a
        single call, or ``hnf1b_find_individuals_by_phenotype`` to discover
        individuals sharing a given HPO phenotype.

        Args:
            phenopacket_id: The phenopacket identifier to look up.
            include_phenotypes: Include the ``phenotypic_features`` list in the
                response.  Defaults to ``True``.
            include_variants: Include the ``variants`` list extracted from
                genomic interpretations.  Defaults to ``True``.
            include_measurements: Include the ``measurements`` list.  Defaults
                to ``True``.
            include_publications: Include the ``publications`` list extracted
                from ``metaData.externalReferences`` (PMID entries only).
                Defaults to ``True``.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.
            fields: Optional explicit top-level field allow-list (e.g.
                ``["variants"]``) for precise token control; applied on top of
                the mode. ``phenopacket_id`` and ``uri`` are always kept.

        Returns:
            A dict with keys ``phenopacket_id``, ``subject``, ``diseases``,
            ``uri``, and conditionally ``phenotypic_features`` (observed),
            ``excluded_features`` (EXCLUDED / confirmed-negative phenotypes —
            clinically meaningful "ruled out" findings, distinct from simply
            unmentioned), ``feature_counts``, ``variants``, ``measurements``,
            ``publications``, plus ``data_class`` and ``meta``.
            ``response_mode`` genuinely trims the field set: ``minimal`` =
            id + subject + uri; ``compact`` adds diseases / observed phenotypes /
            variants / feature_counts AND the ``excluded_features`` list (so a
            negative finding is visible, not just counted); ``standard`` adds
            publications; ``full`` adds measurements and everything else.
            In ``compact``/``standard`` a long ``excluded_features`` list is
            sampled to the first 10 (``feature_counts.excluded`` stays the true
            total; ``meta`` then carries ``excluded_features_total`` /
            ``excluded_features_returned`` / ``excluded_features_truncated`` /
            ``excluded_features_note`` — recover the full list via
            ``response_mode='full'``). ``include_*`` flags are explicit opt-outs
            applied on top of the mode. Embedded publications carry the same
            verified ``recommended_citation`` / ``date_confidence`` as
            ``hnf1b_get_publications``.
        """
        mode = resolve_mode(response_mode)
        return await run_tool(
            lambda: individuals_service.get_individual(
                client,  # type: ignore[arg-type]
                phenopacket_id,
                include_phenotypes=include_phenotypes,
                include_variants=include_variants,
                include_measurements=include_measurements,
                include_publications=include_publications,
                response_mode=mode,
                fields=fields,
            ),
            data_class=DataClass.CURATED,
            response_mode=mode,
        )

    @mcp.tool(
        name="hnf1b_get_individuals",
        annotations={
            "title": "Get/List HNF1B Individuals",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_individuals(
        ids: list[str] | None = None,
        sex: SexFilter | None = None,
        has_variants: bool | None = None,
        page_size: int = 25,
        expand: bool = False,
        dedupe_publications: bool = False,
        response_mode: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a list of HNF1B-db individuals by IDs or with optional filters.

        When ``ids`` is provided the batch endpoint is used for efficient
        multi-record retrieval.  Otherwise the discovery list endpoint is
        queried and each individual is optionally fetched in full when
        ``expand=True``.  Use ``hnf1b_find_individuals_by_phenotype`` to first
        discover individuals sharing a given HPO term before fetching them.

        Args:
            ids: Optional list of phenopacket IDs for batch retrieval.  The
                ``sex`` / ``has_variants`` filters are applied to the batch too
                (and echoed in ``meta.applied_filters``), so a filtered id set is
                never silently returned unfiltered.
            sex: Filter by biological sex — one of ``"MALE"`` or ``"FEMALE"``.
                An invalid value returns an ``invalid_input`` error. Applied in
                both the batch (``ids``) and discovery paths.
            has_variants: Filter to individuals with (``True``) or without
                (``False``) recorded variants.  Applied in both paths.
            page_size: Maximum number of results per page (discovery endpoint
                only).  Defaults to 25.
            expand: When ``True`` and using the discovery endpoint, fetch each
                individual record in full rather than returning minimal stubs.
                Defaults to ``False``.
            dedupe_publications: Hoist unique publications to a top-level
                ``publications`` list and replace per-record publications with
                ``publication_refs`` (PMID strings).  Defaults to ``False``.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.
                The mode's char budget is ENFORCED on the batch: the
                individuals list is trimmed to fit (with a ``meta.truncated``
                signal), so a ``minimal`` batch is genuinely small.
            fields: Optional explicit top-level field allow-list applied to
                every record (e.g. ``["variants"]`` to enumerate variant ids
                without phenotypes/measurements). Highest-leverage token control
                for slicing tasks. ``phenopacket_id``/``uri`` are always kept.

        Returns:
            A dict with keys ``individuals``, ``total``, ``page_size``, and —
            when ``ids`` was supplied — ``requested`` (count) and ``not_found``
            (the requested ids the batch endpoint did not return, so missing
            ids are never silently dropped). Also ``publications`` when
            ``dedupe_publications=True``, plus ``data_class`` and ``meta``.
            ``minimal``/``compact``/``standard`` modes return progressively
            smaller per-record field sets; ``full`` returns every field.
        """
        filters: dict[str, Any] = {}
        if sex is not None:
            filters["sex"] = sex
        if has_variants is not None:
            filters["has_variants"] = has_variants

        mode = resolve_mode(response_mode)
        return await run_tool(
            lambda: individuals_service.get_individuals(
                client,  # type: ignore[arg-type]
                ids=ids,
                filters=filters or None,
                page_size=page_size,
                expand=expand,
                dedupe_publications=dedupe_publications,
                response_mode=mode,
                fields=fields,
            ),
            data_class=DataClass.CURATED,
            response_mode=mode,
        )

    @mcp.tool(
        name="hnf1b_find_individuals_by_phenotype",
        annotations={
            "title": "Find Individuals by HPO Phenotype",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_find_individuals_by_phenotype(
        hpo_ids: list[str],
        page_size: int = 25,
        include_excluded: bool = False,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Cohort discovery: find individuals sharing one or more HPO phenotype terms.

        Queries the ``/phenopackets/search`` discovery endpoint for each
        supplied HPO term ID, collects and deduplicates the matching phenopacket
        IDs while preserving order, then fetches authoritative content for the
        merged cohort via the batch endpoint.  Suitable for building HPO-matched
        cohorts for downstream analysis.

        Args:
            hpo_ids: One or more HPO term IDs (e.g. ``["HP:0000083",
                "HP:0000107"]``).  Match semantics are **OR / union**: an
                individual matches if it carries *any* of the supplied terms.
            page_size: Maximum number of individuals to return in the final
                result page.  Defaults to 25.
            include_excluded: When ``False`` (default) a term matches only when
                it is PRESENT (``excluded=false``); confirmed-absent annotations
                (``excluded=true``) are NOT treated as matches. Set ``True`` to
                also match explicitly-excluded features.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``individuals`` (the first ``page_size`` of the
            matched cohort), ``total`` (the **full** count of matched
            individuals, not the returned page), ``returned`` (page size
            actually returned), ``has_more`` (whether ``total`` exceeds the
            page), ``match_mode`` (``"any"``), ``hpo_ids`` (echoed), plus
            ``page_size``, ``data_class`` and ``meta``. A malformed HPO ID (not
            ``HP:`` + 7 digits) returns an ``invalid_input`` error (with a hint to
            resolve free text via ``hnf1b_resolve_terms``), distinct from a real
            empty cohort which returns ``total: 0``.
        """
        resolved = resolve_mode(response_mode)
        # Cap on cursor pages per HPO term so an honest total cannot trigger an
        # unbounded crawl. 100 ids/page × 50 pages = 5 000 — far above the cohort.
        _PAGE = 100
        _MAX_PAGES = 50

        async def _collect_matches(hpo_id: str) -> tuple[list[str], bool]:
            """Enumerate every published phenopacket_id matching one HPO term.

            Follows the cursor (``page[after]``) until the backend reports no
            next page or the page cap is hit. Returns ``(ids, capped)``.
            """
            ids: list[str] = []
            cursor: str | None = None
            for _ in range(_MAX_PAGES):
                params: dict[str, Any] = {
                    "hpo_id": hpo_id,
                    "page[size]": _PAGE,
                    "include_excluded": include_excluded,
                }
                if cursor:
                    params["page[after]"] = cursor
                resp: dict[str, Any] = await client.get(  # type: ignore[union-attr]
                    "/phenopackets/search", params=params
                )
                for item in resp.get("data", []):
                    item_id: str = item.get("id", "")
                    if item_id:
                        ids.append(item_id)
                page_meta = (resp.get("meta") or {}).get("page") or {}
                if not page_meta.get("hasNextPage"):
                    return ids, False
                cursor = page_meta.get("endCursor")
                if not cursor:
                    return ids, False
            return ids, True  # page cap hit

        async def handler() -> dict[str, Any]:
            # Validate HPO ID shape FIRST so a malformed term (e.g. "renal cyst")
            # returns invalid_input — never total:0, which is indistinguishable
            # from a real empty cohort and would read as a confident wrong answer.
            malformed = [h for h in hpo_ids if not _HPO_ID_RE.match(h)]
            if malformed:
                raise McpToolError(
                    "invalid_input",
                    f"not valid HPO term IDs: {malformed}. Expected 'HP:' + 7"
                    " digits (e.g. 'HP:0000107').",
                    field="hpo_ids",
                    hint=(
                        "resolve free-text phenotypes to HPO IDs first via"
                        " hnf1b_resolve_terms(text=..., vocabulary='hpo')"
                    ),
                )

            seen: dict[str, None] = {}
            capped = False
            # Track per-term hits so a well-formed but unmatched HPO id (e.g.
            # HP:9999999) is reported in unmatched_hpo_ids rather than silently
            # vanishing into an empty cohort indistinguishable from a real match.
            per_term_hit: dict[str, bool] = {}
            for hpo_id in hpo_ids:
                matched, term_capped = await _collect_matches(hpo_id)
                capped = capped or term_capped
                per_term_hit[hpo_id] = per_term_hit.get(hpo_id, False) or bool(matched)
                for item_id in matched:
                    if item_id not in seen:
                        seen[item_id] = None
            merged_ids = list(seen.keys())
            # Deterministic input-order list of well-formed HPO ids that matched
            # zero individuals. Always emitted on both return paths.
            unmatched_hpo_ids = [h for h, hit in per_term_hit.items() if not hit]
            total = len(merged_ids)
            has_more = total > page_size

            if not merged_ids:
                return {
                    "individuals": [],
                    "total": 0,
                    "returned": 0,
                    "page_size": page_size,
                    "has_more": False,
                    "match_mode": "any",
                    "hpo_ids": list(hpo_ids),
                    "unmatched_hpo_ids": unmatched_hpo_ids,
                }

            result = await individuals_service.get_individuals(
                client,  # type: ignore[arg-type]
                ids=merged_ids[:page_size],
                page_size=page_size,
                response_mode=resolved,
            )
            # The batch call reports the size of the returned page; overwrite
            # with the true union count and surface OR (union) match semantics.
            result["returned"] = len(result.get("individuals", []))
            result["total"] = total
            result["has_more"] = has_more
            result["match_mode"] = "any"
            result["hpo_ids"] = list(hpo_ids)
            # HPO-scoped key set explicitly so it is ALWAYS present and never
            # collides with the batch-coverage `not_found` key get_individuals
            # may set for missing phenopacket ids.
            result["unmatched_hpo_ids"] = unmatched_hpo_ids
            if capped:
                result["_meta"] = {
                    "total_is_capped": True,
                    "note": (
                        f"match enumeration stopped at {_MAX_PAGES * _PAGE} per"
                        " HPO term; total is a lower bound"
                    ),
                }
            return result

        return await run_tool(
            handler,
            data_class=DataClass.CURATED,
            response_mode=resolved,
        )
