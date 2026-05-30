"""Service functions for the local publication cache.

IMPORTANT: This service serves the LOCAL publication cache ONLY.
It NEVER calls ``/publications/{pmid}/metadata`` (that endpoint triggers a live
PubMed fetch + DB write and is denied by the allowlist).  Use only:
- ``GET /publications/``   – paginated list
- ``GET /phenopackets/by-publication/{pmid}``  – reverse discovery lookup
"""

from __future__ import annotations

from typing import Any

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.config import Settings
from hnf1b_mcp.contract._generated_paths import (
    PHENOPACKETS_BY_PUBLICATION_BY_PMID,
    PUBLICATIONS,
)
from hnf1b_mcp.services.citation import build_citation
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.shaping import apply_budget


def _strip_pmid_prefix(raw: str) -> str:
    """Return the bare numeric part of a PMID string.

    Args:
        raw: A PMID string, possibly prefixed with ``"PMID:"``.

    Returns:
        The bare PMID without a leading ``"PMID:"`` prefix.
    """
    # Strip only a LEADING prefix (the documented intent); ``replace`` would
    # corrupt any value that legitimately contained the substring elsewhere.
    return raw.removeprefix("PMID:")


def _shape_publication(
    item: dict[str, Any], response_mode: str = "compact"
) -> dict[str, Any]:
    """Convert a FLAT publication item into an output dict.

    The API returns flat items (no JSON:API ``attributes`` nesting).
    Fields like ``pmid``, ``title``, ``authors``, etc. are top-level keys.

    Token efficiency: ``recommended_citation`` already embeds the journal, year,
    and PMID verbatim, so in ``minimal``/``compact`` modes the separate
    ``journal``/``year``/``date_confidence`` fields (≈30-40% redundant tokens
    when scanning a listing) are dropped. ``standard``/``full`` retain them for
    callers that want to filter/sort on the structured fields.

    Args:
        item: A single flat item from the ``data`` list returned by
            ``GET /publications/``.
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``.

    Returns:
        A flat dict with ``pmid``, ``recommended_citation``,
        ``phenopacket_count``, ``uri`` (always), plus ``journal``/``year``/
        ``date_confidence`` in ``standard``/``full``.
    """
    # Items are FLAT — read fields directly from the top-level dict.
    pmid: str = str(item.get("pmid") or "")

    # Build a record for the citation helper.
    pub_record: dict[str, Any] = {
        "pmid": pmid,
        "title": item.get("title"),
        "authors": item.get("authors"),
        "journal": item.get("journal"),
        "year": item.get("year"),
        "doi": item.get("doi"),
    }
    citation_info = build_citation(pub_record)

    bare_pmid = _strip_pmid_prefix(pmid)
    uri = f"hnf1b://publication/PMID:{bare_pmid}"

    shaped: dict[str, Any] = {
        "pmid": pmid,
        "recommended_citation": citation_info["recommended_citation"],
        "phenopacket_count": item.get("phenopacket_count"),
        "uri": uri,
    }
    # Full-text coverage flags are tiny and high-signal — they tell an agent
    # whether hnf1b_get_publication_passages can retrieve body text for this
    # publication — so they ride along in every mode.
    coverage = item.get("coverage")
    if coverage is not None:
        shaped["coverage"] = coverage
        shaped["has_full_text"] = coverage == "full_text"
    if response_mode in ("standard", "full"):
        shaped["date_confidence"] = citation_info["date_confidence"]
        shaped["journal"] = item.get("journal")
        shaped["year"] = item.get("year")
        # The abstract is large (~1.5 KB); include it only in the verbose tiers
        # where the caller has opted into richer-but-fewer records.
        abstract = item.get("abstract")
        if abstract:
            shaped["abstract"] = abstract
    return shaped


#: Sort fields the backend publications list endpoint honors (``-`` prefix =
#: descending). The backend default is ``-phenopacket_count`` (most-cited
#: first), which we surface explicitly so the ordering is never undocumented.
PUBLICATION_SORT_FIELDS: tuple[str, ...] = (
    "phenopacket_count",
    "year",
    "pmid",
    "title",
    "journal",
    "first_added",
)
DEFAULT_PUBLICATION_SORT = "-phenopacket_count"


async def list_publications(
    client: ApiClient,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 25,
    sort: str | None = None,
    response_mode: str = "compact",
) -> dict[str, Any]:
    """Return a page of publications from the local DB cache.

    Args:
        client: An :class:`~hnf1b_mcp.client.api_client.ApiClient` instance.
        q: Optional free-text search query forwarded as the ``q`` parameter.
        filters: Optional dict of filter parameters (keys become
            ``filter[key]`` query params).  Recognised keys include
            ``year``, ``year_gte``, ``year_lte``, ``has_doi``.
        page: 1-based page number (default 1).
        page_size: Number of items per page; clamped to 1000 (default 25).
        sort: Optional sort expression (e.g. ``-phenopacket_count``, ``year``).
            When ``None`` the backend default ``-phenopacket_count`` applies and
            is echoed in the response so the ordering is explicit.
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``;
            controls per-record citation-field trimming.

    Returns:
        A plain dict with keys ``publications`` (list of shaped items),
        ``total`` (from JSON:API meta), ``page``, ``page_size``, and
        ``applied_sort`` (the ordering actually in effect).
    """
    effective_size = min(page_size, 1000)
    # Validate the sort field client-side so a typo returns an actionable
    # invalid_input error instead of an opaque upstream 422 / a silent default.
    if sort is not None:
        bare_field = sort[1:] if sort.startswith("-") else sort
        if bare_field not in PUBLICATION_SORT_FIELDS:
            raise McpToolError(
                "invalid_input",
                f"sort field {bare_field!r} is not sortable; "
                f"choose one of {list(PUBLICATION_SORT_FIELDS)} "
                "(optionally '-'-prefixed for descending)",
                argument="sort",
                choices=list(PUBLICATION_SORT_FIELDS),
            )
    applied_sort = sort or DEFAULT_PUBLICATION_SORT

    params: dict[str, Any] = {
        "page[number]": page,
        "page[size]": effective_size,
        "sort": applied_sort,
    }
    if q is not None:
        params["q"] = q
    if filters:
        for key, value in filters.items():
            params[f"filter[{key}]"] = value

    body: dict[str, Any] = await client.get(PUBLICATIONS, params=params)

    data: list[dict[str, Any]] = body.get("data") or []
    meta: dict[str, Any] = body.get("meta") or {}
    # Real API: meta.page is a nested dict with totalRecords/currentPage/pageSize.
    # Older/stub responses may have flat meta.total / meta.page (int) / meta.page_size.
    _raw_page_meta = meta.get("page")
    page_meta: dict[str, Any] = (
        _raw_page_meta if isinstance(_raw_page_meta, dict) else {}
    )

    publications = [_shape_publication(item, response_mode) for item in data]

    total: int = int(
        page_meta.get("totalRecords") or meta.get("total") or len(publications)
    )
    _page_int = _raw_page_meta if isinstance(_raw_page_meta, int) else None
    current_page: int = int(
        page_meta.get("currentPage") or _page_int or meta.get("page") or page
    )
    current_size: int = int(
        page_meta.get("pageSize") or meta.get("page_size") or effective_size
    )

    result: dict[str, Any] = {
        "publications": publications,
        "total": total,
        "page": current_page,
        "page_size": current_size,
        "applied_sort": applied_sort,
    }

    # Enforce the response_mode char budget on the publications list. A full page
    # (up to 1000) — and especially standard/full pages carrying abstracts —
    # otherwise dwarfs the mode budget (minimal returned ~46 KB vs the 4 KB cap).
    # ``total`` stays the true server count; only the returned slice is trimmed,
    # with a machine-readable truncation signal.
    budget = Settings().mode_char_budgets.get(response_mode, 12000)
    result, dropped = apply_budget(result, budget, ["publications"])
    if dropped:
        result["_dropped"] = dropped
    return result


async def build_pmid_citation_map(client: ApiClient) -> dict[str, dict[str, Any]]:
    """Return a ``bare_pmid -> {recommended_citation, date_confidence, …}`` map.

    Fetches the local publication cache once (cached by the API client's TTL) so
    embedded publication references inside individual records can be enriched to
    the SAME verified citation/date_confidence that ``hnf1b_get_publications``
    reports — eliminating the inconsistency where an inline ref showed
    ``unverified`` while the list showed ``verified``.

    Args:
        client: An :class:`~hnf1b_mcp.client.api_client.ApiClient` instance.

    Returns:
        Mapping of bare PMID (digits) to enrichment fields.
    """
    body: dict[str, Any] = await client.get(
        PUBLICATIONS,
        params={
            "page[number]": 1,
            "page[size]": 1000,
            "sort": DEFAULT_PUBLICATION_SORT,
        },
    )
    out: dict[str, dict[str, Any]] = {}
    for item in body.get("data") or []:
        pmid = str(item.get("pmid") or "")
        bare = _strip_pmid_prefix(pmid)
        if not bare:
            continue
        citation_info = build_citation(
            {
                "pmid": pmid,
                "title": item.get("title"),
                "authors": item.get("authors"),
                "journal": item.get("journal"),
                "year": item.get("year"),
                "doi": item.get("doi"),
            }
        )
        out[bare] = {
            "recommended_citation": citation_info["recommended_citation"],
            "date_confidence": citation_info["date_confidence"],
            "journal": item.get("journal"),
            "year": item.get("year"),
        }
    return out


async def get_publication_citing_individuals(
    client: ApiClient,
    pmid: str,
) -> dict[str, Any]:
    """Return phenopacket IDs that cite a given publication (discovery only).

    Uses the reverse-lookup endpoint ``/phenopackets/by-publication/{pmid}``
    to discover which carrier records reference the publication.
    This is a discovery-only call; it NEVER hits the metadata endpoint.

    Args:
        client: An :class:`~hnf1b_mcp.client.api_client.ApiClient` instance.
        pmid: The bare PMID (digits only) or ``"PMID:NNN"`` prefixed string.

    Returns:
        A plain dict with keys ``pmid`` (the input value),
        ``citing_individuals`` (list of ``phenopacket_id`` strings),
        and ``total`` (length of that list).
    """
    bare = _strip_pmid_prefix(pmid)
    path = PHENOPACKETS_BY_PUBLICATION_BY_PMID.format(pmid=bare)

    # The endpoint returns a BARE JSON LIST, not a JSON:API envelope.
    # Shape: [{"phenopacket_id": "...", "phenopacket": {...}}, ...]
    raw = await client.get(path)

    # Normalise: the endpoint returns a bare list; client.get returns Any.
    items: list[dict[str, Any]]
    if isinstance(raw, list):
        items = raw
    else:
        # Fallback: treat as envelope with a "data" key (defensive)
        envelope: dict[str, Any] = raw
        items = envelope.get("data") or []

    # Extract phenopacket_id directly from the flat list items.
    citing: list[str] = []
    for item in items:
        pid: str = str(item.get("phenopacket_id") or "")
        if pid:
            citing.append(pid)

    return {
        "pmid": pmid,
        "citing_individuals": citing,
        "total": len(citing),
    }
