"""Unified discovery search service — returns typed IDs only.

Content is fetched later via the typed get_* tools.
"""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract._generated_paths import SEARCH_GLOBAL
from .errors import McpToolError

# Recognised entity types understood by this service.
_VALID_TYPES = frozenset({"individual", "variant", "publication", "gene"})

# Default types returned when the caller does not specify.
_DEFAULT_TYPES = ("individual", "variant", "publication")

# Map from MCP-friendly type name → the backend ``type`` token used by the
# global-search materialized view. The MV stores capitalized tokens
# (``Phenopacket``/``Variant``/``Publication``/``Gene``) and filters with an
# exact equality match, so a lowercase token would silently match zero rows.
_TYPE_TOKEN: dict[str, str] = {
    "individual": "Phenopacket",
    "variant": "Variant",
    "publication": "Publication",
    "gene": "Gene",
}

_GUIDANCE = (
    "Each hit carries a 'resolve_with' object naming the exact tool and"
    " argument to fetch authoritative content for that id — call it verbatim"
    " (the chain is never severed)."
)


def _derive_uri(item_id: str) -> tuple[str, str, dict[str, str] | None]:
    """Derive (normalised_type, uri, resolve_with) from a prefixed result id.

    The third element is an explicit handoff descriptor naming the tool and
    argument a caller should use to fetch authoritative content for the hit,
    eliminating any ambiguity about which id form the detail tool accepts.

    Args:
        item_id: The prefixed result id, e.g. ``pp_001``,
            ``var_ga4gh:VA.xxx``, ``pub_12345678``, or ``gene_HNF1B``.

    Returns:
        A tuple of ``(normalised_type, uri, resolve_with)`` where
        *resolve_with* is ``{"tool", "argument", "value"}`` or ``None`` for an
        unknown id form.
    """
    if item_id.startswith("pp_"):
        rest = item_id[len("pp_") :]
        return (
            "individual",
            f"hnf1b://individual/{rest}",
            {
                "tool": "hnf1b_get_individual",
                "argument": "phenopacket_id",
                "value": rest,
            },
        )
    if item_id.startswith("var_"):
        rest = item_id[len("var_") :]
        # ``rest`` is the resolvable GA4GH VRS / CNV descriptor id that
        # hnf1b_get_variant accepts directly.
        return (
            "variant",
            f"hnf1b://variant/{rest}",
            {"tool": "hnf1b_get_variant", "argument": "variant_id", "value": rest},
        )
    if item_id.startswith("pub_"):
        rest = item_id[len("pub_") :]
        # ``rest`` may already carry the ``PMID:`` prefix (e.g. ``pub_PMID:123``);
        # normalise to a single canonical ``PMID:`` so the URI is not doubled.
        bare = rest[len("PMID:") :] if rest.startswith("PMID:") else rest
        return (
            "publication",
            f"hnf1b://publication/PMID:{bare}",
            {
                "tool": "hnf1b_get_publications",
                "argument": "citing_pmid",
                "value": bare,
            },
        )
    if item_id.startswith("gene_"):
        rest = item_id[len("gene_") :]
        return (
            "gene",
            f"hnf1b://gene/{rest}",
            {
                "tool": "hnf1b_get_gene_context",
                "argument": "gene_symbol",
                "value": rest,
            },
        )
    # Unknown prefix — best-effort passthrough; type is unknown.
    return "unknown", f"hnf1b://unknown/{item_id}", None


def _extract_results(raw: Any) -> list[dict[str, Any]]:
    """Normalise the API response to a flat list of result dicts.

    Handles both ``{"results": [...]}`` and JSON:API ``{"data": [...]}``
    envelopes.

    Args:
        raw: The deserialized JSON body returned by the API.

    Returns:
        A list of raw result item dicts.
    """
    if isinstance(raw, dict):
        if "results" in raw:
            items = raw["results"]
        elif "data" in raw:
            items = raw["data"]
        else:
            items = []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    return list(items) if items else []


async def search(
    client: ApiClient,
    query: str,
    types: tuple[str, ...] = _DEFAULT_TYPES,
    limit: int = 10,
    response_mode: str = "compact",  # noqa: ARG001 — reserved for future shaping
) -> dict[str, Any]:
    """Unified discovery search — returns typed IDs for downstream resolution.

    Calls ``GET /search/global`` and maps each result to a minimal hit record
    containing only the entity type, prefixed id, label, and a ``hnf1b://``
    URI.  Content is intentionally not included; callers should resolve
    individual hits via ``hnf1b_get_individual``, ``hnf1b_get_variant``, etc.

    Args:
        client: Authenticated :class:`~hnf1b_mcp.client.api_client.ApiClient`.
        query: Free-text search string (must be non-empty).
        types: Tuple of entity type names to include in the result set.
            Allowed values: ``individual``, ``variant``, ``publication``,
            ``gene``.  Defaults to ``(individual, variant, publication)``.
        limit: Maximum number of results requested from the backend
            (``page_size``).  Must be ≥ 1.
        response_mode: Reserved for future response-shaping; currently unused.

    Returns:
        A plain dict with keys:

        - ``query``: The original query string.
        - ``hits``: List of ``{type, id, label, uri}`` dicts; each hit also
          carries a numeric ``score`` (relevance, 0–1, higher = better) when
          the backend supplied one.
        - ``counts``: ``{type: count}`` for each type present in *hits*.
        - ``guidance``: Short string directing callers to typed get_* tools.

    Raises:
        McpToolError: On invalid input (``invalid_input``) or upstream errors.
    """
    # --- Input validation ---------------------------------------------------
    if not query or not query.strip():
        raise McpToolError(
            "invalid_input",
            "query must be a non-empty string",
            argument="query",
        )

    if limit < 1:
        raise McpToolError(
            "invalid_input",
            "limit must be ≥ 1",
            argument="limit",
        )

    bad = sorted(set(types) - _VALID_TYPES)
    if bad:
        raise McpToolError(
            "invalid_input",
            f"unknown type(s): {bad}. Must be one of {sorted(_VALID_TYPES)}",
            argument="types",
        )

    # --- Build request params -----------------------------------------------
    params: dict[str, Any] = {
        "q": query.strip(),
        "page_size": limit,
    }

    # When the caller requests exactly one type, pass it to the backend to
    # reduce the result set at the source.  Multi-type filtering is done
    # client-side after one broad call.
    if len(types) == 1:
        params["type"] = _TYPE_TOKEN[types[0]]

    # --- Call the API -------------------------------------------------------
    raw = await client.get(SEARCH_GLOBAL, params=params)

    # --- Normalise and filter results ---------------------------------------
    items = _extract_results(raw)
    requested = frozenset(types)

    hits: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for item in items:
        item_id: str = str(item.get("id") or "")
        if not item_id:
            continue

        norm_type, uri, resolve_with = _derive_uri(item_id)

        # Filter to requested types only.
        if norm_type not in requested:
            continue

        label: str = str(item.get("label") or item_id)
        hit: dict[str, Any] = {
            "type": norm_type,
            "id": item_id,
            "label": label,
            "uri": uri,
        }
        # Forward the backend's numeric relevance score (ts_rank / trigram
        # similarity, 0–1, higher = better) verbatim so a client can rank
        # strong vs. weak matches. Guarded so a missing score never crashes
        # and never fabricates a misleading value.
        if "score" in item:
            hit["score"] = item["score"]
        if resolve_with is not None:
            hit["resolve_with"] = resolve_with
        hits.append(hit)
        counts[norm_type] = counts.get(norm_type, 0) + 1

    result: dict[str, Any] = {
        "query": query.strip(),
        "hits": hits,
        "counts": counts,
        "guidance": _GUIDANCE,
    }

    # When a query matched ONLY publications while individuals/variants were also
    # requested, a free-text phenotype phrase likely matched publication text but
    # not the cohort. Nudge toward the HPO-precise path so the agent does not
    # mistake "publications only" for "no individuals have this phenotype".
    if (
        hits
        and set(counts) <= {"publication"}
        and ({"individual", "variant"} & set(types))
    ):
        result["phenotype_hint"] = (
            "Only publications matched. If this is a phenotype query, resolve it"
            " to HPO IDs via hnf1b_resolve_terms(text=..., vocabulary='hpo'),"
            " then call hnf1b_find_individuals_by_phenotype(hpo_ids=[...])."
        )

    return result
