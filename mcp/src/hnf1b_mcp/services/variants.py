"""Variant service: browse all-variants and fetch authoritative variant records."""

from __future__ import annotations

from typing import Any, Literal

from ..client.api_client import ApiClient
from ..config import Settings
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
from .shaping import apply_budget

# ---------------------------------------------------------------------------
# Valid enum values — sourced from the generated API contract (DRY Layer 2).
# ---------------------------------------------------------------------------

_VALID_CLASSIFICATION = frozenset(VARIANT_CLASSIFICATION_VALUES)
_VALID_CONSEQUENCE = frozenset(MOLECULAR_CONSEQUENCE_VALUES)
_VALID_VARIANT_TYPE = frozenset(VARIANT_TYPE_VALUES)
_VALID_DOMAIN = frozenset(PROTEIN_DOMAIN_VALUES)

_MAX_PAGE_SIZE = 500
_GENE_SYMBOL = "HNF1B"

# Number of carrier IDs returned by default (include_carriers=False) for any
# response whose full carrier set exceeds this. A heavily-carried variant (the
# recurrent 17q12 deletion carries ~379 individuals ≈ 7.5 KB of bare IDs) would
# otherwise dump the ENTIRE list in compact/standard with no opt-out, blowing
# the token budget the rest of the server respects. The caller recovers the
# full set via include_carriers=True or hnf1b_find_individuals_by_phenotype.
_CARRIER_SAMPLE_SIZE = 10
_CARRIERS_NOTE = (
    "Showing the first {sample} of {total} carrier ids. To get all carriers,"
    " re-call hnf1b_get_variant with include_carriers=true, or use"
    " hnf1b_find_individuals_by_phenotype for the matched cohort with phenotype"
    " detail."
)


def _summarize_carriers(
    carriers: list[str], total: int, *, sample_size: int = _CARRIER_SAMPLE_SIZE
) -> tuple[list[str], dict[str, Any]]:
    """Down-sample a carrier-id list to a bounded sample with a meta signal.

    The reusable carrier-shaping pattern: when *carriers* exceeds *sample_size*,
    return only the first *sample_size* ids plus a machine-readable meta block
    (``carriers_total`` / ``carriers_returned`` / ``carriers_truncated`` /
    ``carriers_note``) that tells the agent the omission happened and exactly how
    to recover the full set. When the list already fits, it is returned whole
    with an empty signal so the caller never emits a spurious truncation flag.

    Args:
        carriers: The full list of carrier ids (or whatever subset was fetched).
        total: The authoritative total carrier count (== ``carrier_count``);
            used for the ``carriers_total`` signal and the note, which may exceed
            ``len(carriers)`` if the upstream fetch itself was bounded.
        sample_size: Maximum number of ids to keep (default
            :data:`_CARRIER_SAMPLE_SIZE`).

    Returns:
        ``(sampled, signal)`` — *sampled* is the (possibly shortened) id list and
        *signal* is the meta dict to merge (empty when no truncation occurred).
    """
    if len(carriers) <= sample_size:
        return carriers, {}
    sampled = carriers[:sample_size]
    return sampled, {
        "carriers_total": total,
        "carriers_returned": len(sampled),
        "carriers_truncated": True,
        "carriers_note": _CARRIERS_NOTE.format(sample=len(sampled), total=total),
    }

# Self-documenting basis for the ``carrier_count`` field, mirroring the
# statistics tool's ``unit`` + ``unit_note`` pattern. carrier_count is the
# backend ``phenopacket_count`` == COUNT(DISTINCT phenopacket_id), i.e. the
# number of DISTINCT CARRIER INDIVIDUALS for a variant — NOT a count of
# reports/observations and NOT a count of distinct publications. Defined once
# here and reused by both variant tools (in their response meta) and the
# capabilities descriptor, so the documented semantics can never drift between
# them and an evaluator never has to guess what "most common variant" means.
CARRIER_COUNT_BASIS = "distinct_carrier_individuals"
CARRIER_COUNT_NOTE = (
    "carrier_count counts DISTINCT carrier individuals (phenopackets) for the"
    " variant — NOT reports/observations and NOT distinct publications. Sorting"
    " by carrier_count therefore ranks variants by how many individuals carry"
    " them."
)

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

# Self-describing sort vocabulary for the search_variants tool. Each canonical
# field above appears in BOTH directions: bare = ascending, ``-``-prefixed =
# descending. A typed Literal makes the tool's sort param exactly as
# self-describing as its enum filters, so an agent never has to guess
# ``-carrier_count`` and confirm it worked only by reading meta.applied_sort.
#
# mypy requires Literal members to be spelled out (it cannot derive them from
# VARIANT_SORT_FIELDS at type-check time), so the two are kept in lockstep by a
# drift-guard test (test_variants.py::test_variant_sort_enum_matches_sort_fields)
# that fails fast if either is edited without the other. This is an MCP-local
# type, NOT part of the generated backend contract.
VariantSort = Literal[
    "carrier_count",
    "-carrier_count",
    "classification",
    "-classification",
    "structural_type",
    "-structural_type",
    "variant_id",
    "-variant_id",
    "simple_id",
    "-simple_id",
    "transcript",
    "-transcript",
    "protein",
    "-protein",
    "hg38",
    "-hg38",
]

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


# Scalar field policy for the single-variant detail payload (get_variant), by
# response mode. Mirrors get_individual's _INDIVIDUAL_FIELDS_BY_MODE and the
# sibling search_variants._ROW_FIELDS_BY_MODE in this file so the documented
# response_mode knob actually trims the field set — without it a low-carrier
# variant (already under the smallest char budget) returned an identical payload
# for minimal/compact/standard/full because only the carriers LIST was
# budget-trimmed.
#
# Design (honoring the established get_variant contract — see test_variants.py /
# test_tool_variants.py): ``_DETAIL_ALWAYS`` are the identity + summary keys plus
# the chainable ``carriers`` list, kept in EVERY mode so the documented
# carriers -> hnf1b_get_individuals workflow and the carriers char-budget trim
# (which operates on the carriers list in any mode) keep working. The tiers form
# a STRICT ladder so the knob can never silently re-collapse:
#   * minimal  = identity + interpretation (classification/consequence) only;
#   * compact  = + gene_symbol + structural_type;
#   * standard = + the genomic-coordinate block (hg38/transcript/protein);
#   * full     = keep-all (() == keep every field), which additionally surfaces
#                the provenance prose (data_provenance + note).
# This yields minimal(8) ⊊ compact(10) ⊊ standard(13) ⊊ full(15), matching the
# get_individual and search_variants ladders.
_DETAIL_ALWAYS = (
    "variant_id",
    "simple_id",
    "label",
    "uri",
    "carrier_count",
    "carriers",
)
_DETAIL_FIELDS_BY_MODE: dict[str, tuple[str, ...]] = {
    "minimal": _DETAIL_ALWAYS + ("classification", "consequence"),
    "compact": _DETAIL_ALWAYS
    + ("classification", "consequence", "gene_symbol", "structural_type"),
    "standard": _DETAIL_ALWAYS
    + (
        "classification",
        "consequence",
        "gene_symbol",
        "structural_type",
        "hg38",
        "transcript",
        "protein",
    ),
    "full": (),  # () == keep every field (adds data_provenance + note)
}


def _project_variant_detail(result: dict[str, Any], mode: str) -> dict[str, Any]:
    """Trim the detail dict to the field set allowed for ``mode`` (full keeps all).

    Args:
        result: The fully-built single-variant detail dict (output of
            :func:`get_variant` before budgeting).
        mode: One of ``minimal``, ``compact``, ``standard``, ``full``.

    Returns:
        A new dict containing only the keys permitted in *mode*; ``full`` (or an
        unknown mode) returns the dict unchanged.
    """
    allowed = _DETAIL_FIELDS_BY_MODE.get(mode, ())
    if not allowed:
        return result
    keep = set(allowed) | set(_DETAIL_ALWAYS)
    return {k: v for k, v in result.items() if k in keep}


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
        sort: Optional MCP-friendly sort expression (a key of
            :data:`VARIANT_SORT_FIELDS`, optionally ``-``-prefixed for
            descending). Translated to the backend ORDER BY token and echoed
            back in the public vocabulary as ``applied_sort``; a field the
            backend cannot sort on is reported in ``ignored_params`` rather than
            silently dropped (see :data:`VariantSort` for the typed tool-facing
            enum).
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
    # Always state what carrier_count counts (distinct carrier individuals), so
    # an agent sorting by carrier_count never has to guess whether "common" means
    # distinct individuals, reports, or publications. Flat in meta (not per-row)
    # to keep token cost constant. Mirrors the statistics tool's unit/unit_note.
    extra_meta: dict[str, Any] = {
        "carrier_count_basis": CARRIER_COUNT_BASIS,
        "carrier_count_note": CARRIER_COUNT_NOTE,
    }
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

    # extra_meta always carries the carrier_count basis, so it is never empty.
    result["_meta"] = extra_meta

    return result


async def get_variant(
    client: ApiClient,
    variant_id: str,
    *,
    response_mode: str = "compact",
    include_carriers: bool = False,
) -> dict[str, Any]:
    """Fetch the FULL authoritative record for a single variant.

    Enriches the variant by (1) paging through the all-variants aggregate
    endpoint and matching the row whose ``variant_id`` equals *variant_id*
    (the upstream ``query`` param does not match variant_id reliably and the
    dataset is small ~200 rows), and (2) merging the carrier phenopacket IDs
    from ``/phenopackets/by-variant/{id}``.

    Carrier token discipline (applies in EVERY response mode):

    * ``include_carriers=False`` (default) — the ``carriers`` list is
      SUMMARIZED to the first :data:`_CARRIER_SAMPLE_SIZE` ids. A heavily-carried
      variant (e.g. the recurrent 17q12 deletion carries ~379 individuals) would
      otherwise dump the entire id list (~7.5 KB) with no opt-out. The full
      ``carrier_count`` is always kept, and when the full set exceeds the sample
      the response meta carries ``carriers_total`` (== carrier_count),
      ``carriers_returned``, ``carriers_truncated: true``, and a ``carriers_note``
      telling the caller how to recover the rest (``include_carriers=true`` or
      ``hnf1b_find_individuals_by_phenotype``).
    * ``include_carriers=True`` — the FULL carriers list is returned, still
      bounded by the response mode's char budget; if it must be trimmed to fit,
      ``carriers_truncated`` + a ``dropped_summary`` are emitted (mode-independent).

    Narrower modes additionally trim the SCALAR field set per the per-mode policy
    (full keeps every field, including ``data_provenance`` + ``note``).
    ``carrier_count`` (the true total) is always preserved unchanged.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        variant_id: The canonical variant identifier (e.g.
            ``"var:HNF1B:17:36459258-37832869:DEL"``) or the friendly
            ``simple_id`` (e.g. ``"Var6"``).
        response_mode: One of ``minimal``/``compact``/``standard``/``full``;
            controls the scalar field set and the carrier char budget.
        include_carriers: When ``False`` (default) the ``carriers`` list is
            summarized to a small sample (see above) in every mode; when ``True``
            the full list is returned, budget-bounded with a truncation signal.

    Returns:
        A dict with the full variant record: ``variant_id``, ``simple_id``,
        ``label``, ``gene_symbol``, ``classification``, ``consequence``,
        ``structural_type``, ``hg38``, ``transcript``, ``protein``,
        ``carrier_count``, ``carriers`` (phenopacket ID list — a bounded sample
        unless ``include_carriers=True``), ``uri``, ``data_provenance``, and
        ``note``.

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

    # Resolve the canonical id from the matched aggregate row BEFORE the
    # by-variant fetch. The caller may have passed the friendly simple_id (e.g.
    # "Var1"), but /phenopackets/by-variant/{id} only honors the canonical
    # variant_id — interpolating the raw caller value there returns 200 [] for a
    # simple_id, leaving carriers empty while carrier_count falls back to the
    # aggregate count (a silent disagreement that breaks the documented
    # carriers -> hnf1b_get_individuals workflow).
    shaped = _shape_variant(match)
    raw_carriers: list[dict[str, Any]] = await client.get(
        PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID.format(variant_id=shaped["variant_id"])
    )
    carriers: list[str] = [
        record["phenopacket_id"]
        for record in (raw_carriers or [])
        if "phenopacket_id" in record
    ]

    # carrier_count from the live by-variant call is authoritative when present;
    # fall back to the aggregate phenopacket_count.
    carrier_count = len(carriers) if carriers else shaped.get("carrier_count") or 0

    result: dict[str, Any] = {
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

    # Project the SCALAR field set to the requested mode first. Narrower modes
    # graduate the scalar coordinate fields and drop the provenance prose
    # (data_provenance + note); the identity/summary keys AND the chainable
    # ``carriers`` list (all in _DETAIL_ALWAYS) are retained in EVERY mode. This
    # is what makes a low-carrier variant — already under the smallest budget —
    # return a genuinely smaller payload for narrower modes. Without it the
    # budget step below (which only trims the carriers LIST) left minimal ==
    # standard == full for most variants.
    result = _project_variant_detail(result, response_mode)

    # Always document what carrier_count counts (distinct carrier individuals),
    # flat in meta (not per-row), mirroring search_variants and the statistics
    # tool's unit/unit_note — so "carrier_count" is never read as a count of
    # reports or publications. Carrier truncation signals are merged in below.
    extra_meta: dict[str, Any] = {
        "carrier_count_basis": CARRIER_COUNT_BASIS,
        "carrier_count_note": CARRIER_COUNT_NOTE,
    }

    # Carrier token discipline — mode-INDEPENDENT (no minimal-only special case).
    # carrier_count (the true total) is preserved in every branch; only the
    # ``carriers`` LIST is bounded.
    if not include_carriers:
        # DEFAULT: summarize to a bounded sample regardless of mode. A
        # heavily-carried variant (~379 ids ≈ 7.5 KB) otherwise dumped the entire
        # list in compact/standard with no opt-out, blowing the token budget the
        # rest of the server respects. The full set is recoverable via
        # include_carriers=True or hnf1b_find_individuals_by_phenotype (named in
        # the carriers_note). Reuses _summarize_carriers — the shared
        # sample/signal helper get_publications.citing_individuals will adopt next.
        result["carriers"], carrier_signal = _summarize_carriers(
            result["carriers"], carrier_count
        )
        extra_meta.update(carrier_signal)
    else:
        # include_carriers=True: return the FULL list, but still bounded by the
        # response mode's char budget so an enormous carrier set can never blow
        # the budget. ``carriers`` is always present (it is in _DETAIL_ALWAYS, so
        # it survives the projection above in every mode), so this genuinely trims
        # the LIST. ``carrier_count`` stays accurate; the truncation signal +
        # dropped_summary fire in ANY mode when a trim happens.
        budget = Settings().mode_char_budgets.get(response_mode, 12000)
        result, dropped = apply_budget(result, budget, ["carriers"])
        if dropped:
            result["_dropped"] = dropped
            extra_meta["carriers_truncated"] = True
            extra_meta["carriers_total"] = carrier_count
            extra_meta["carriers_returned"] = len(result["carriers"])

    result["_meta"] = extra_meta
    return result
