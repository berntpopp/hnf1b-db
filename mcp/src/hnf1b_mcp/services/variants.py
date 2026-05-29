"""Variant service: browse all-variants and fetch authoritative variant records."""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract import (
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
)
from ..contract._generated_paths import (
    PHENOPACKETS_AGGREGATE_ALL_VARIANTS,
    PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID,
)
from .errors import McpToolError

# ---------------------------------------------------------------------------
# Valid enum values — sourced from the generated API contract (DRY Layer 2).
# ---------------------------------------------------------------------------

_VALID_CLASSIFICATION = frozenset(VARIANT_CLASSIFICATION_VALUES)
_VALID_CONSEQUENCE = frozenset(MOLECULAR_CONSEQUENCE_VALUES)
_VALID_VARIANT_TYPE = frozenset(VARIANT_TYPE_VALUES)
_VALID_DOMAIN = frozenset(PROTEIN_DOMAIN_VALUES)

_MAX_PAGE_SIZE = 500
_GENE_SYMBOL = "HNF1B"

# Translate MCP-friendly sort keys (the field names this server returns in each
# row) to the backend all-variants sort tokens it actually honors. Keys the
# backend does not support (e.g. ``label``, ``consequence``) are reported as
# ignored in meta rather than silently dropped — an unknown sort key otherwise
# falls back to the default order, looking like a no-op.
# Canonical, agent-facing sortable fields for variant search: the MCP-friendly
# name -> the backend ORDER BY token it maps to. This is the single source of
# truth; capabilities advertises exactly these keys (see capabilities.py) so the
# documented sort vocabulary can never drift from what the tool actually honors.
VARIANT_SORT_FIELDS: dict[str, str] = {
    "carrier_count": "individualCount",
    "classification": "classificationVerdict",
    "structural_type": "variant_type",
    "variant_id": "variant_id",
    "simple_id": "simple_id",
    "transcript": "transcript",
    "protein": "protein",
    "hg38": "hg38",
}

# The accepted translation set is the canonical fields plus the raw backend
# tokens accepted verbatim (defensive: a caller that read a backend token
# elsewhere still gets a correct sort). Built from VARIANT_SORT_FIELDS so the two
# stay in lockstep.
_SORT_FIELD_TRANSLATION: dict[str, str] = {
    **VARIANT_SORT_FIELDS,
    "individualCount": "individualCount",
    "classificationVerdict": "classificationVerdict",
    "variant_type": "variant_type",
}

# Reverse map: backend ORDER BY token -> canonical public field. Used to echo
# ``applied_sort`` in the CALLER's vocabulary (e.g. ``-carrier_count``), never
# the internal column name (``-individualCount``). An echo field exists to
# confirm what the server did, so it must speak the public token the caller used.
_BACKEND_TO_PUBLIC: dict[str, str] = {
    backend: public for public, backend in VARIANT_SORT_FIELDS.items()
}


def _translate_sort(sort: str | None) -> tuple[str | None, list[str]]:
    """Map an MCP-friendly sort expression to the backend token.

    Args:
        sort: A sort expression, optionally ``-``-prefixed for descending
            (e.g. ``-carrier_count``), or ``None``.

    Returns:
        ``(backend_sort, ignored_params)`` — *backend_sort* is the translated
        expression to forward (or ``None`` when the field is not sortable
        server-side), and *ignored_params* is ``["sort"]`` when the requested
        sort could not be honored, else ``[]``.
    """
    if not sort:
        return None, []
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    backend_field = _SORT_FIELD_TRANSLATION.get(field)
    if backend_field is None:
        return None, ["sort"]
    return (f"-{backend_field}" if descending else backend_field), []


def _public_sort(sort: str | None) -> str | None:
    """Return the canonical *public* form of a honored sort, else ``None``.

    Normalizes both public keys and accepted backend-token aliases to the public
    vocabulary (e.g. ``-carrier_count`` and ``-individualCount`` both echo back as
    ``-carrier_count``). ``None`` when the field is not sortable server-side.

    Args:
        sort: A sort expression, optionally ``-``-prefixed for descending.

    Returns:
        The public canonical sort token, or ``None`` when not honored.
    """
    if not sort:
        return None
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    backend_field = _SORT_FIELD_TRANSLATION.get(field)
    if backend_field is None:
        return None
    public = _BACKEND_TO_PUBLIC.get(backend_field, field)
    return f"-{public}" if descending else public


# Per-mode field policies (Anthropic: smallest high-signal payload).  Fields not
# listed for a mode are dropped from each row.  ``gene_symbol`` is always hoisted
# to the response header when invariant, and ``uri`` is dropped in
# minimal/compact as it is a deterministic function of ``variant_id``.
_ROW_FIELDS_BY_MODE: dict[str, tuple[str, ...]] = {
    "minimal": (
        "simple_id",
        "variant_id",
        "label",
        "classification",
        "consequence",
        "carrier_count",
    ),
    "compact": (
        "simple_id",
        "variant_id",
        "label",
        "classification",
        "consequence",
        "carrier_count",
        "structural_type",
    ),
    "standard": (
        "simple_id",
        "variant_id",
        "label",
        "structural_type",
        "classification",
        "consequence",
        "hg38",
        "transcript",
        "protein",
        "carrier_count",
        "uri",
    ),
    "full": (
        "simple_id",
        "variant_id",
        "label",
        "gene_symbol",
        "structural_type",
        "classification",
        "consequence",
        "hg38",
        "transcript",
        "protein",
        "carrier_count",
        "uri",
    ),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_enum(value: str | None, valid: frozenset[str], argument: str) -> None:
    """Raise McpToolError(invalid_input) when *value* is not in *valid*.

    Args:
        value: The caller-supplied string to check, or None to skip.
        valid: The set of accepted values.
        argument: The argument name to embed in the error for easy diagnosis.

    Raises:
        McpToolError: When *value* is not None and not in *valid*.
    """
    if value is not None and value not in valid:
        raise McpToolError(
            "invalid_input",
            f"Invalid value '{value}' for argument '{argument}'."
            f" Accepted values: {sorted(valid)!r}",
            argument=argument,
            choices=sorted(valid),
        )


def _shape_variant(item: dict[str, Any]) -> dict[str, Any]:
    """Map a raw JSON:API data item to the canonical full variant shape.

    Args:
        item: A raw variant object from the all-variants aggregate endpoint.

    Returns:
        A shaped variant dict with the canonical field names (all fields).
    """
    variant_id: str = item.get("variant_id", "") or ""
    return {
        "simple_id": item.get("simple_id"),
        "variant_id": variant_id,
        "label": item.get("label"),
        "gene_symbol": item.get("gene_symbol"),
        "structural_type": item.get("structural_type"),
        "classification": item.get("pathogenicity"),
        "consequence": item.get("molecular_consequence"),
        "hg38": item.get("hg38"),
        "transcript": item.get("transcript"),
        "protein": item.get("protein"),
        "carrier_count": item.get("phenopacket_count"),
        "uri": f"hnf1b://variant/{variant_id}",
    }


def _project_row(row: dict[str, Any], mode: str) -> dict[str, Any]:
    """Project a fully-shaped variant row down to the fields allowed by *mode*.

    Args:
        row: A fully-shaped variant dict (output of :func:`_shape_variant`).
        mode: One of ``minimal``, ``compact``, ``standard``, ``full``.

    Returns:
        A new dict containing only the fields permitted in *mode*.
    """
    allowed = _ROW_FIELDS_BY_MODE.get(mode, _ROW_FIELDS_BY_MODE["compact"])
    return {key: row[key] for key in allowed if key in row}


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def search_variants(
    client: ApiClient,
    *,
    query: str | None = None,
    variant_type: str | None = None,
    classification: str | None = None,
    gene: str | None = None,
    consequence: str | None = None,
    domain: str | None = None,
    page: int = 1,
    page_size: int = 25,
    sort: str | None = None,
    response_mode: str = "compact",
) -> dict[str, Any]:
    """Browse the all-variants aggregate endpoint with optional filters.

    Validates the *classification*, *consequence*, and *domain* enums before
    issuing the request.  Returns a plain dict (no meta/data_class wrapper).

    Token efficiency: in ``minimal``/``compact`` modes the invariant
    ``gene_symbol`` is hoisted to a single top-level ``gene_symbol_all`` header
    and dropped from each row; the deterministic per-row ``uri`` is also dropped
    in those modes.  ``standard``/``full`` retain all fields.

    Consequence filtering is applied server-side (pre-pagination) by the
    all-variants endpoint, which returns an honest filtered ``totalRecords``;
    this function forwards the filter and trusts the server's data and totals.
    When *consequence* is set, ``filtered_count`` (== ``total``) is included.

    When any filter is active, the result's ``_meta`` carries a machine-readable
    ``applied_filters`` dict (the exact predicates honored) and
    ``filter_mode == "server"`` so a caller can programmatically confirm the
    filter was applied server-side against the honest cross-page total — without
    parsing prose. These fields surface in the wrapped ``meta`` block.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        query: Free-text search query forwarded to the API.
        variant_type: Free-form variant type filter (e.g. "SNV", "DEL").
        classification: Pathogenicity classification filter.  Must be one of
            ``PATHOGENIC``, ``LIKELY_PATHOGENIC``, ``UNCERTAIN_SIGNIFICANCE``,
            ``LIKELY_BENIGN``, or ``BENIGN``.
        gene: Gene symbol or ID filter (free-form).
        consequence: Molecular consequence filter.  Must be one of the
            ``MolecularConsequence`` values (e.g. ``Frameshift``, ``Nonsense``,
            ``Missense``, ``Splice Donor``).
        domain: Protein domain filter.  Must be one of ``"Dimerization Domain"``,
            ``"POU-Specific Domain"``, ``"POU Homeodomain"``, or
            ``"Transactivation Domain"``.
        page: 1-based page number (default 1).
        page_size: Number of results per page (default 25, capped at 500).
        sort: Optional sort expression forwarded as-is to the API.
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``
            (default ``compact``).  Controls the per-row field set.

    Returns:
        A dict with keys ``variants``, ``total``, ``total_pages``, ``has_more``,
        ``page``, ``page_size`` (and, when *consequence* is set, a
        ``filtered_count`` equal to the server-side filtered ``total``).
        When ``gene_symbol`` is invariant across rows it is hoisted to
        ``gene_symbol_all`` in ``minimal``/``compact`` modes.

    Raises:
        McpToolError: ``invalid_input`` if any enum arg is outside its allowed
            set; ``not_found`` / ``temporarily_unavailable`` propagated from
            :class:`ApiClient`.
    """
    _validate_enum(classification, _VALID_CLASSIFICATION, "classification")
    _validate_enum(consequence, _VALID_CONSEQUENCE, "consequence")
    _validate_enum(domain, _VALID_DOMAIN, "domain")

    # The all-variants endpoint applies the molecular-consequence filter
    # server-side (pre-pagination) and returns an honest meta.page.totalRecords,
    # so we forward every filter and trust the server's data + totals — no
    # client-side post-filtering or pagination shimming.
    effective_page_size = min(page_size, _MAX_PAGE_SIZE)
    params: dict[str, Any] = {
        "page[number]": page,
        "page[size]": effective_page_size,
    }
    if query is not None:
        params["query"] = query
    if variant_type is not None:
        params["variant_type"] = variant_type
    if classification is not None:
        params["classification"] = classification
    if gene is not None:
        params["gene"] = gene
    if consequence is not None:
        params["consequence"] = consequence
    if domain is not None:
        params["domain"] = domain
    backend_sort, ignored_sort = _translate_sort(sort)
    if backend_sort is not None:
        params["sort"] = backend_sort

    raw: dict[str, Any] = await client.get(
        PHENOPACKETS_AGGREGATE_ALL_VARIANTS, params=params
    )

    data: list[dict[str, Any]] = raw.get("data") or []
    meta: dict[str, Any] = raw.get("meta") or {}
    page_meta: dict[str, Any] = meta.get("page") or {}

    # Authoritative total: the API returns it at meta.page.totalRecords (already
    # filtered server-side). Fall back to legacy locations, then to len(data) so
    # total is NEVER 0 when rows are present.
    total: int = (
        page_meta.get("totalRecords")
        or meta.get("total")
        or meta.get("pagination", {}).get("total")
        or 0
    )
    total_pages: int = page_meta.get("totalPages") or 0
    current_page: int = page_meta.get("currentPage") or page

    if total == 0 and data:
        total = len(data)

    shaped_full = [_shape_variant(item) for item in data]
    if total_pages == 0 and total and effective_page_size:
        total_pages = -(-total // effective_page_size)  # ceil division
    has_more = current_page < total_pages if total_pages else False
    result: dict[str, Any] = {
        "variants": [_project_row(row, response_mode) for row in shaped_full],
        "total": total,
        "total_pages": total_pages,
        "page": current_page,
        "page_size": effective_page_size,
        "has_more": has_more,
    }
    if consequence is not None:
        # The server filtered by consequence; total is the full filtered count.
        result["filtered_count"] = total

    # Hoist the invariant gene_symbol to a single header in compact/minimal.
    if response_mode in ("minimal", "compact"):
        symbols = {row.get("gene_symbol") for row in shaped_full}
        if symbols and symbols <= {_GENE_SYMBOL}:
            result["gene_symbol_all"] = _GENE_SYMBOL

    # Make the server's filtering and sorting machine-readable so an agent never
    # has to parse prose to learn what was applied. Every filter listed below is
    # a real server-side query predicate evaluated against an honest
    # meta.page.totalRecords (the consequence filter is applied pre-pagination by
    # the all-variants endpoint), so filter_mode is "server": pagination totals
    # and has_more stay trustworthy across pages. These two keys are emitted only
    # when at least one filter is active — an unfiltered browse needs neither.
    extra_meta: dict[str, Any] = {}
    applied_filters: dict[str, Any] = {}
    if query is not None:
        applied_filters["query"] = query
    if variant_type is not None:
        applied_filters["variant_type"] = variant_type
    if classification is not None:
        applied_filters["classification"] = classification
    if gene is not None:
        applied_filters["gene"] = gene
    if consequence is not None:
        applied_filters["consequence"] = consequence
    if domain is not None:
        applied_filters["domain"] = domain
    if applied_filters:
        extra_meta["applied_filters"] = applied_filters
        extra_meta["filter_mode"] = "server"

    # Echo the sort actually applied in the CALLER's public vocabulary (never the
    # internal column name) and name any parameter that was requested but could
    # not be honored. An LLM cannot self-correct on a silently-dropped argument,
    # and a leaked internal token (``-individualCount``) erodes trust in the one
    # field whose job is to confirm what the server did.
    if sort is not None:
        extra_meta["applied_sort"] = _public_sort(sort)
        extra_meta["ignored_params"] = ignored_sort
        if ignored_sort:
            extra_meta["sort_note"] = (
                f"sort={sort!r} is not sortable server-side; default order"
                " (carrier_count desc, then variant_id asc) was used. Sortable"
                f" fields: {sorted(VARIANT_SORT_FIELDS)}"
            )

    if extra_meta:
        result["_meta"] = extra_meta

    return result


async def get_variant(client: ApiClient, variant_id: str) -> dict[str, Any]:
    """Fetch the FULL authoritative record for a single variant.

    Enriches the variant by (1) paging through the all-variants aggregate
    endpoint and matching the row whose ``variant_id`` equals *variant_id*
    (the upstream ``query`` param does not match variant_id reliably and the
    dataset is small ~200 rows), and (2) merging the carrier phenopacket IDs
    from ``/phenopackets/by-variant/{id}``.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        variant_id: The exact variant identifier (e.g.
            ``"var:HNF1B:17:36459258-37832869:DEL"``).

    Returns:
        A dict with the full variant record: ``variant_id``, ``simple_id``,
        ``label``, ``gene_symbol``, ``classification``, ``consequence``,
        ``structural_type``, ``hg38``, ``transcript``, ``protein``,
        ``carrier_count``, ``carriers`` (phenopacket ID list), ``uri``,
        ``data_provenance``, and ``note``.

    Raises:
        McpToolError: ``not_found`` if no variant matches *variant_id*;
            ``temporarily_unavailable`` on upstream errors.
    """
    listing: dict[str, Any] = await client.get(
        PHENOPACKETS_AGGREGATE_ALL_VARIANTS,
        params={"page[number]": 1, "page[size]": _MAX_PAGE_SIZE},
    )
    rows: list[dict[str, Any]] = listing.get("data") or []
    # Accept either the canonical variant_id (GA4GH VRS / CNV descriptor) or the
    # friendly simple_id (e.g. "Var6") shown in list payloads.
    match: dict[str, Any] | None = next(
        (
            item
            for item in rows
            if item.get("variant_id") == variant_id
            or str(item.get("simple_id")) == variant_id
        ),
        None,
    )
    if match is None:
        raise McpToolError(
            "not_found",
            f"variant '{variant_id}' not found",
            field="variant_id",
        )

    raw_carriers: list[dict[str, Any]] = await client.get(
        PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID.format(variant_id=variant_id)
    )
    carriers: list[str] = [
        record["phenopacket_id"]
        for record in (raw_carriers or [])
        if "phenopacket_id" in record
    ]

    shaped = _shape_variant(match)
    # carrier_count from the live by-variant call is authoritative when present;
    # fall back to the aggregate phenopacket_count.
    carrier_count = len(carriers) if carriers else shaped.get("carrier_count") or 0

    return {
        "variant_id": shaped["variant_id"],
        "simple_id": shaped.get("simple_id"),
        "label": shaped.get("label"),
        "gene_symbol": shaped.get("gene_symbol"),
        "classification": shaped.get("classification"),
        "consequence": shaped.get("consequence"),
        "structural_type": shaped.get("structural_type"),
        "hg38": shaped.get("hg38"),
        "transcript": shaped.get("transcript"),
        "protein": shaped.get("protein"),
        "carrier_count": carrier_count,
        "carriers": carriers,
        "uri": shaped["uri"],
        "data_provenance": "curated HNF1B-db variant record",
        "note": (
            "Call hnf1b_get_individuals with the `carriers` ids for"
            " authoritative per-carrier phenotype detail."
        ),
    }
