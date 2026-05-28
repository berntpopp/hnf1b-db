"""Variant service: browse all-variants and fetch carrier IDs by variant."""
from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from .errors import McpToolError

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

_VALID_CLASSIFICATION = frozenset(
    {
        "PATHOGENIC",
        "LIKELY_PATHOGENIC",
        "UNCERTAIN_SIGNIFICANCE",
        "LIKELY_BENIGN",
        "BENIGN",
    }
)

_VALID_CONSEQUENCE = frozenset({"lof", "missense", "splicing", "inframe", "other"})

_VALID_DOMAIN = frozenset(
    {
        "Dimerization Domain",
        "POU-Specific Domain",
        "POU Homeodomain",
        "Transactivation Domain",
    }
)

_MAX_PAGE_SIZE = 500


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
    """Map a raw JSON:API data item to the canonical variant shape.

    Args:
        item: A raw variant object from the all-variants aggregate endpoint.

    Returns:
        A shaped variant dict with the canonical field names.
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
) -> dict[str, Any]:
    """Browse the all-variants aggregate endpoint with optional filters.

    Validates the *classification*, *consequence*, and *domain* enums before
    issuing the request.  Returns a plain dict (no meta/data_class wrapper).

    Args:
        client: Authenticated :class:`ApiClient` instance.
        query: Free-text search query forwarded to the API.
        variant_type: Free-form variant type filter (e.g. "SNV", "DEL").
        classification: Pathogenicity classification filter.  Must be one of
            ``PATHOGENIC``, ``LIKELY_PATHOGENIC``, ``UNCERTAIN_SIGNIFICANCE``,
            ``LIKELY_BENIGN``, or ``BENIGN``.
        gene: Gene symbol or ID filter (free-form).
        consequence: Molecular consequence filter.  Must be one of ``lof``,
            ``missense``, ``splicing``, ``inframe``, or ``other``.
        domain: Protein domain filter.  Must be one of ``"Dimerization Domain"``,
            ``"POU-Specific Domain"``, ``"POU Homeodomain"``, or
            ``"Transactivation Domain"``.
        page: 1-based page number (default 1).
        page_size: Number of results per page (default 25, capped at 500).
        sort: Optional sort expression forwarded as-is to the API.

    Returns:
        A dict with keys ``variants``, ``total``, ``page``, ``page_size``.
        Each entry in ``variants`` has the canonical shape defined by
        :func:`_shape_variant`.

    Raises:
        McpToolError: ``invalid_input`` if any enum arg is outside its allowed
            set; ``not_found`` / ``temporarily_unavailable`` propagated from
            :class:`ApiClient`.
    """
    _validate_enum(classification, _VALID_CLASSIFICATION, "classification")
    _validate_enum(consequence, _VALID_CONSEQUENCE, "consequence")
    _validate_enum(domain, _VALID_DOMAIN, "domain")

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
    if sort is not None:
        params["sort"] = sort

    raw: dict[str, Any] = await client.get(
        "/phenopackets/aggregate/all-variants", params=params
    )

    data: list[dict[str, Any]] = raw.get("data") or []
    meta: dict[str, Any] = raw.get("meta") or {}
    total: int = (
        meta.get("total")
        or meta.get("pagination", {}).get("total")
        or 0
    )

    return {
        "variants": [_shape_variant(item) for item in data],
        "total": total,
        "page": page,
        "page_size": effective_page_size,
    }


async def get_variant(client: ApiClient, variant_id: str) -> dict[str, Any]:
    """Fetch carrier phenopacket IDs for a specific variant.

    This is a discovery endpoint: only ``phenopacket_id`` values are extracted
    from the response.  For authoritative carrier detail, callers should pass
    the returned IDs to ``hnf1b_get_individuals``.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        variant_id: The variant identifier (e.g. ``"HNF1B:c.494G>A"``).

    Returns:
        A dict with keys ``variant_id``, ``carriers`` (list of
        phenopacket ID strings), ``carrier_count``, ``uri``, and ``note``.

    Raises:
        McpToolError: ``not_found`` if the variant does not exist;
            ``temporarily_unavailable`` on upstream errors.
    """
    raw: list[dict[str, Any]] = await client.get(
        f"/phenopackets/by-variant/{variant_id}"
    )

    carriers: list[str] = [
        record["phenopacket_id"]
        for record in (raw or [])
        if "phenopacket_id" in record
    ]

    return {
        "variant_id": variant_id,
        "carriers": carriers,
        "carrier_count": len(carriers),
        "uri": f"hnf1b://variant/{variant_id}",
        "note": (
            "Call hnf1b_get_individuals with these ids for authoritative"
            " carrier detail."
        ),
    }
