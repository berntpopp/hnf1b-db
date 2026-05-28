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
    """Convert a JSON:API publication item into a flat output dict.

    Args:
        item: A single JSON:API ``data`` element with ``id`` and ``attributes``.

    Returns:
        A flat dict with ``pmid``, ``recommended_citation``,
        ``date_confidence``, ``journal``, ``year``, ``phenopacket_count``,
        and ``uri``.
    """
    attrs: dict[str, Any] = item.get("attributes") or {}
    # Prefer attributes.pmid; fall back to the top-level id.
    pmid: str = str(attrs.get("pmid") or item.get("id") or "")

    # Build a merged record for the citation helper.
    pub_record: dict[str, Any] = {
        "pmid": pmid,
        "title": attrs.get("title"),
        "authors": attrs.get("authors"),
        "journal": attrs.get("journal"),
        "year": attrs.get("year"),
        "doi": attrs.get("doi"),
    }
    citation_info = build_citation(pub_record)

    bare_pmid = _strip_pmid_prefix(pmid)
    uri = f"hnf1b://publication/PMID:{bare_pmid}"

    return {
        "pmid": pmid,
        "recommended_citation": citation_info["recommended_citation"],
        "date_confidence": citation_info["date_confidence"],
        "journal": attrs.get("journal"),
        "year": attrs.get("year"),
        "phenopacket_count": attrs.get("phenopacket_count"),
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

    publications = [_shape_publication(item) for item in data]

    return {
        "publications": publications,
        "total": meta.get("total", len(publications)),
        "page": meta.get("page", page),
        "page_size": meta.get("page_size", effective_size),
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

    body: dict[str, Any] = await client.get(path)

    data: list[dict[str, Any]] = body.get("data") or []

    # Extract phenopacket_id from attributes, falling back to the item id.
    citing: list[str] = []
    for item in data:
        attrs: dict[str, Any] = item.get("attributes") or {}
        pid: str = str(attrs.get("phenopacket_id") or item.get("id") or "")
        if pid:
            citing.append(pid)

    return {
        "pmid": pmid,
        "citing_individuals": citing,
        "total": len(citing),
    }
