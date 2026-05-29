"""Service functions for retrieving and shaping individual phenopacket records."""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..config import Settings
from ..contract._generated_paths import (
    PHENOPACKETS,
    PHENOPACKETS_BATCH,
    PHENOPACKETS_BY_PHENOPACKET_ID,
)
from . import publications as publications_service
from .citation import build_citation
from .errors import McpToolError
from .shaping import apply_budget

# Per-mode field policy for a shaped individual record. ``full`` keeps every
# field (identity projection); the narrower modes drop the largest sections so
# response_mode is a real lever, not a no-op. ``publication_refs`` is retained
# whenever publications would be (dedupe_publications hoists them).
_INDIVIDUAL_FIELDS_BY_MODE: dict[str, tuple[str, ...]] = {
    "minimal": ("phenopacket_id", "subject", "uri"),
    "compact": (
        "phenopacket_id",
        "subject",
        "diseases",
        "phenotypic_features",
        "feature_counts",
        "variants",
        "publication_refs",
        "uri",
    ),
    "standard": (
        "phenopacket_id",
        "subject",
        "diseases",
        "phenotypic_features",
        "excluded_features",
        "feature_counts",
        "variants",
        "publications",
        "publication_refs",
        "uri",
    ),
}

# Fields always kept so a projected record stays chainable/identifiable.
_ALWAYS_KEEP = ("phenopacket_id", "uri")


def _project_individual(record: dict[str, Any], mode: str) -> dict[str, Any]:
    """Project a shaped individual down to the fields allowed by *mode*.

    ``full`` returns the record unchanged; ``minimal``/``compact``/``standard``
    keep only their allow-listed keys so smaller modes return genuinely smaller
    payloads.

    Args:
        record: A shaped individual dict (output of :func:`_shape_individual`).
        mode: One of ``minimal``, ``compact``, ``standard``, ``full``.

    Returns:
        The projected record (a new dict for the narrower modes).
    """
    allowed = _INDIVIDUAL_FIELDS_BY_MODE.get(mode)
    if allowed is None:  # full (or unknown) → identity
        return record
    return {key: value for key, value in record.items() if key in allowed}


def _select_fields(
    record: dict[str, Any], fields: list[str] | None
) -> dict[str, Any]:
    """Keep only caller-requested top-level *fields* (plus id/uri for chaining).

    Explicit field projection — the highest-leverage token control for
    slicing tasks (e.g. ``fields=["variants"]`` to enumerate variant ids
    without pulling phenotypes/measurements). Applied on top of the mode
    projection. ``None`` is a no-op.

    Args:
        record: A shaped (and mode-projected) individual dict.
        fields: Requested top-level field names, or ``None`` for all.

    Returns:
        The field-projected record.
    """
    if not fields:
        return record
    keep = set(fields) | set(_ALWAYS_KEEP)
    return {key: value for key, value in record.items() if key in keep}


def _extract_variants(phenopacket: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk interpretations and extract a compact variant list.

    Args:
        phenopacket: The phenopacket JSONB dict.

    Returns:
        A list of compact variant dicts with id, hgvs, classification, gene.
    """
    variants: list[dict[str, Any]] = []
    for interp in phenopacket.get("interpretations", []):
        diagnosis = interp.get("diagnosis", {})
        for gi in diagnosis.get("genomicInterpretations", []):
            vi = gi.get("variantInterpretation", {})
            vd = vi.get("variationDescriptor", {})
            if not vd:
                continue
            # Derive HGVS from expressions
            hgvs = ""
            for expr in vd.get("expressions", []):
                if "hgvs" in expr.get("syntax", ""):
                    hgvs = expr.get("value", "")
                    break
            # Derive gene symbol
            gene_ctx = vd.get("geneContext", {})
            gene = gene_ctx.get("symbol", gene_ctx.get("geneId", ""))
            # Classification from interpretationStatus
            classification = gi.get("interpretationStatus", "")
            variants.append(
                {
                    "id": vd.get("id", ""),
                    "hgvs": hgvs,
                    "classification": classification,
                    "gene": gene,
                }
            )
    return variants


def _extract_publications(phenopacket: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract publications from metaData.externalReferences (PMIDs only).

    Args:
        phenopacket: The phenopacket JSONB dict.

    Returns:
        A list of publication dicts each with pmid, recommended_citation,
        and date_confidence. Non-PMID references are skipped.
    """
    pubs: list[dict[str, Any]] = []
    meta = phenopacket.get("metaData", {})
    for ref in meta.get("externalReferences", []):
        ref_id: str = ref.get("id", "")
        if not ref_id.startswith("PMID:"):
            continue
        pmid = ref_id.removeprefix("PMID:")
        citation_info = build_citation({"pmid": pmid})
        pubs.append(
            {
                "pmid": pmid,
                **citation_info,
            }
        )
    return pubs


def _shape_individual(
    record: dict[str, Any],
    include_phenotypes: bool = True,
    include_variants: bool = True,
    include_measurements: bool = True,
    include_publications: bool = True,
) -> dict[str, Any]:
    """Shape a raw phenopacket API record into a compact individual dict.

    Args:
        record: Raw API record from /phenopackets/{id}.
        include_phenotypes: Whether to include phenotypic_features.
        include_variants: Whether to include variants.
        include_measurements: Whether to include measurements.
        include_publications: Whether to include publications.

    Returns:
        A compact individual dict.
    """
    pp_id: str = record.get("phenopacket_id", record.get("id", ""))
    phenopacket: dict[str, Any] = record.get("phenopacket", {})

    out: dict[str, Any] = {
        "phenopacket_id": pp_id,
        "subject": phenopacket.get("subject", {}),
        "diseases": phenopacket.get("diseases", []),
        "uri": f"hnf1b://individual/{pp_id}",
    }

    if include_phenotypes:
        raw_features = phenopacket.get("phenotypicFeatures", [])
        observed: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for feat in raw_features:
            entry = {
                "id": feat.get("type", {}).get("id", ""),
                "label": feat.get("type", {}).get("label", ""),
            }
            if feat.get("excluded", False):
                excluded.append(entry)
            else:
                observed.append(entry)
        # Split observed vs excluded (confirmed-negative) features so a caller
        # pays for the bulky excluded set only when it wants it.
        # ``phenotypic_features`` is the observed set; ``excluded_features`` are
        # the excluded:true terms; ``feature_counts`` lets a caller gauge size.
        out["phenotypic_features"] = observed
        out["excluded_features"] = excluded
        out["feature_counts"] = {
            "observed": len(observed),
            "excluded": len(excluded),
        }

    if include_measurements:
        out["measurements"] = phenopacket.get("measurements", [])

    if include_variants:
        out["variants"] = _extract_variants(phenopacket)

    if include_publications:
        out["publications"] = _extract_publications(phenopacket)

    return out


async def get_individual(
    client: ApiClient,
    phenopacket_id: str,
    include_phenotypes: bool = True,
    include_variants: bool = True,
    include_measurements: bool = True,
    include_publications: bool = True,
    response_mode: str = "compact",
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch and shape a single individual record by phenopacket_id.

    Fetches from ``/phenopackets/{phenopacket_id}`` and returns a compact
    record. Raises McpToolError (not_found) if the record does not exist.

    Args:
        client: Authenticated ApiClient instance.
        phenopacket_id: The phenopacket identifier to look up.
        include_phenotypes: Include phenotypic_features in the output.
        include_variants: Include variants in the output.
        include_measurements: Include measurements in the output.
        include_publications: Include publications in the output.
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``;
            controls how much of the shaped record is returned (full = all).
        fields: Optional explicit top-level field allow-list (e.g.
            ``["variants"]``); applied on top of the mode. ``phenopacket_id``
            and ``uri`` are always retained.

    Returns:
        A plain dict with shaped individual data, projected to *response_mode*
        and *fields*.
    """
    record: dict[str, Any] = await client.get(
        PHENOPACKETS_BY_PHENOPACKET_ID.format(phenopacket_id=phenopacket_id)
    )
    shaped = _shape_individual(
        record,
        include_phenotypes=include_phenotypes,
        include_variants=include_variants,
        include_measurements=include_measurements,
        include_publications=include_publications,
    )
    shaped = _project_individual(shaped, response_mode)
    # Harmonize embedded publication provenance with hnf1b_get_publications so an
    # inline PMID never shows "unverified" while the publications tool shows it
    # verified. Only runs when publications survive the projection (standard/
    # full), and is best-effort — a publications-cache hiccup must not fail the
    # individual fetch.
    if shaped.get("publications"):
        try:
            citation_map = await publications_service.build_pmid_citation_map(client)
        except McpToolError:
            citation_map = {}
        for pub in shaped["publications"]:
            enrichment = citation_map.get(pub.get("pmid", ""))
            if enrichment:
                pub.update(enrichment)
    return _select_fields(shaped, fields)


async def get_individuals(
    client: ApiClient,
    ids: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    page_size: int = 25,
    expand: bool = False,
    dedupe_publications: bool = False,
    response_mode: str = "compact",
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve a list of individuals, either by IDs (batch) or filtered list.

    When ``ids`` is provided the batch endpoint is used. Otherwise the
    discovery list endpoint is queried and each individual is optionally
    fetched in full when ``expand=True``.

    Args:
        client: Authenticated ApiClient instance.
        ids: Optional list of phenopacket IDs for batch retrieval.
        filters: Optional filter dict; keys become ``filter[key]`` params.
        page_size: Number of results per page (discovery endpoint only).
        expand: If True and using discovery, fetch each record in full.
        dedupe_publications: Hoist unique publications to a top-level list
            and replace per-record publications with publication_refs.
        response_mode: One of ``minimal``, ``compact``, ``standard``, ``full``;
            projects each returned record to a progressively smaller field set
            AND enforces the mode's char budget (the list is trimmed to fit,
            with a ``_dropped`` truncation signal — so a "minimal" batch is
            genuinely minimal, not full records).
        fields: Optional explicit top-level field allow-list applied to every
            record (e.g. ``["variants"]`` to enumerate variant ids cheaply).

    Returns:
        A plain dict with keys: individuals, total, page_size (plus
        ``requested``/``not_found`` for batch ``ids`` requests, and
        ``publications`` when dedupe_publications=True).
    """
    individuals: list[dict[str, Any]] = []
    total = 0
    not_found: list[str] = []

    if ids is not None:
        # Batch endpoint: GET /phenopackets/batch?phenopacket_ids=a,b,c
        # Response is a BARE LIST: [{phenopacket_id, phenopacket}, ...]
        params: dict[str, Any] = {"phenopacket_ids": ",".join(ids)}
        batch_resp: Any = await client.get(PHENOPACKETS_BATCH, params=params)
        batch_list: list[dict[str, Any]] = (
            batch_resp
            if isinstance(batch_resp, list)
            else batch_resp.get("results", [])
        )
        for item in batch_list:
            # Each batch item has phenopacket_id and phenopacket keys
            pp_id: str = item.get("phenopacket_id", item.get("id", ""))
            if not pp_id:
                continue
            phenopacket_content: dict[str, Any] = item.get("phenopacket", item)
            # Build a normalised record that _shape_individual understands
            record: dict[str, Any] = {
                "phenopacket_id": pp_id,
                "phenopacket": phenopacket_content,
            }
            individuals.append(_shape_individual(record))
        total = len(individuals)
        # Surface which requested IDs the batch endpoint did not return, so a
        # caller can distinguish "does not exist" from a silently-dropped id.
        returned_ids = {ind.get("phenopacket_id") for ind in individuals}
        not_found = [i for i in ids if i not in returned_ids]
    else:
        # Discovery list endpoint
        # Response: {data:[ITEM,...], meta:{page:{totalRecords:N}}, links:{}}
        # Each ITEM is a raw phenopacket object with top-level "id".
        params = {"page[size]": page_size}
        if filters:
            for key, val in filters.items():
                params[f"filter[{key}]"] = val
        list_resp: dict[str, Any] = await client.get(PHENOPACKETS, params=params)
        data_items: list[dict[str, Any]] = list_resp.get("data", [])
        meta: dict[str, Any] = list_resp.get("meta", {})
        # Support both meta.page.totalRecords (real API) and legacy meta.total
        page_meta: dict[str, Any] = meta.get("page", {})
        total = int(page_meta.get("totalRecords", meta.get("total", len(data_items))))

        for item in data_items:
            # Real API: item["id"] is the phenopacket id.
            # Defensive: also support legacy {attributes:{phenopacket_id:...}}.
            if "id" in item and not item.get("attributes"):
                # Real API shape: id is at the top level
                item_pp_id: str = item.get("id", item.get("phenopacket_id", ""))
            else:
                # Legacy/attributes shape
                attrs: dict[str, Any] = item.get("attributes", item)
                item_pp_id = attrs.get("phenopacket_id", attrs.get("id", ""))

            if not item_pp_id:
                continue

            if expand:
                full_record: dict[str, Any] = await client.get(
                    PHENOPACKETS_BY_PHENOPACKET_ID.format(phenopacket_id=item_pp_id)
                )
                individuals.append(_shape_individual(full_record))
            else:
                # Minimal stub without full phenopacket data
                individuals.append(
                    {
                        "phenopacket_id": item_pp_id,
                        "uri": f"hnf1b://individual/{item_pp_id}",
                    }
                )

    if dedupe_publications:
        seen: dict[str, dict[str, Any]] = {}
        for ind in individuals:
            for pub in ind.get("publications", []):
                pmid: str = pub.get("pmid", "")
                if pmid and pmid not in seen:
                    seen[pmid] = pub
            # Replace publications with refs
            if "publications" in ind:
                ind["publication_refs"] = [
                    pub.get("pmid", "") for pub in ind.pop("publications")
                ]
    shaped_individuals = [
        _select_fields(_project_individual(i, response_mode), fields)
        for i in individuals
    ]
    if dedupe_publications:
        result: dict[str, Any] = {
            "individuals": shaped_individuals,
            "total": total,
            "page_size": page_size,
            "publications": list(seen.values()),
        }
    else:
        result = {
            "individuals": shaped_individuals,
            "total": total,
            "page_size": page_size,
        }

    # Batch (ids) requests echo coverage so a caller never has to diff the
    # request against the response to learn which ids were missing.
    if ids is not None:
        result["requested"] = len(ids)
        result["not_found"] = not_found

    # Enforce the advertised char budget on the (potentially large) batch: trim
    # the individuals list to the mode ceiling rather than overflowing it.
    max_chars = Settings().mode_char_budgets.get(response_mode, 12000)
    result, dropped = apply_budget(result, max_chars, ["individuals"])
    if dropped is not None:
        result["_dropped"] = dropped

    return result
