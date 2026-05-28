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
from hnf1b_mcp.contract._generated_paths import (
    PHENOPACKETS_BY_PUBLICATION_BY_PMID,
    PUBLICATIONS,
)
from hnf1b_mcp.services.citation import build_citation


def _strip_pmid_prefix(raw: str) -> str:
    """Return the bare numeric part of a PMID string.

    Args:
        raw: A PMID string, possibly prefixed with ``"PMID:"``.

    Returns:
        The bare PMID without the ``"PMID:"`` prefix.
    """
    return raw.replace("PMID:", "")


def _shape_publication(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a FLAT publication item into an output dict.

    The API returns flat items (no JSON:API ``attributes`` nesting).
    Fields like ``pmid``, ``title``, ``authors``, etc. are top-level keys.

    Args:
        item: A single flat item from the ``data`` list returned by
            ``GET /publications/``.

    Returns:
        A flat dict with ``pmid``, ``recommended_citation``,
        ``date_confidence``, ``journal``, ``year``, ``phenopacket_count``,
        and ``uri``.
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

    return {
        "pmid": pmid,
        "recommended_citation": citation_info["recommended_citation"],
        "date_confidence": citation_info["date_confidence"],
        "journal": item.get("journal"),
        "year": item.get("year"),
        "phenopacket_count": item.get("phenopacket_count"),
        "uri": uri,
    }


async def list_publications(
    client: ApiClient,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 25,
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

    Returns:
        A plain dict with keys ``publications`` (list of shaped items),
        ``total`` (from JSON:API meta), ``page``, and ``page_size``.
    """
    effective_size = min(page_size, 1000)

    params: dict[str, Any] = {
        "page[number]": page,
        "page[size]": effective_size,
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

    publications = [_shape_publication(item) for item in data]

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

    return {
        "publications": publications,
        "total": total,
        "page": current_page,
        "page_size": current_size,
    }


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
