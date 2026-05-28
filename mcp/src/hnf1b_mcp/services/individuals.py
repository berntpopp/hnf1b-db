"""Service functions for retrieving and shaping individual phenopacket records."""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract._generated_paths import (
    PHENOPACKETS,
    PHENOPACKETS_BATCH,
    PHENOPACKETS_BY_PHENOPACKET_ID,
)
from .citation import build_citation


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
        out["phenotypic_features"] = [
            {
                "id": feat.get("type", {}).get("id", ""),
                "label": feat.get("type", {}).get("label", ""),
                "excluded": feat.get("excluded", False),
            }
            for feat in raw_features
        ]

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

    Returns:
        A plain dict with shaped individual data.
    """
    record: dict[str, Any] = await client.get(
        PHENOPACKETS_BY_PHENOPACKET_ID.format(phenopacket_id=phenopacket_id)
    )
    return _shape_individual(
        record,
        include_phenotypes=include_phenotypes,
        include_variants=include_variants,
        include_measurements=include_measurements,
        include_publications=include_publications,
    )


async def get_individuals(
    client: ApiClient,
    ids: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    page_size: int = 25,
    expand: bool = False,
    dedupe_publications: bool = False,
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

    Returns:
        A plain dict with keys: individuals, total, page_size (and
        optionally publications when dedupe_publications=True).
    """
    individuals: list[dict[str, Any]] = []
    total = 0

    if ids is not None:
        # Batch endpoint: GET /phenopackets/batch?phenopacket_ids=a,b,c
        params: dict[str, Any] = {"phenopacket_ids": ",".join(ids)}
        batch_resp: dict[str, Any] = await client.get(PHENOPACKETS_BATCH, params=params)
        records: list[dict[str, Any]] = batch_resp.get("results", [])
        for record in records:
            individuals.append(_shape_individual(record))
        total = len(individuals)
    else:
        # Discovery list endpoint
        params = {"page[size]": page_size}
        if filters:
            for key, val in filters.items():
                params[f"filter[{key}]"] = val
        list_resp: dict[str, Any] = await client.get(PHENOPACKETS, params=params)
        data_items: list[dict[str, Any]] = list_resp.get("data", [])
        meta: dict[str, Any] = list_resp.get("meta", {})
        total = int(meta.get("total", len(data_items)))

        for item in data_items:
            attrs: dict[str, Any] = item.get("attributes", item)
            pp_id: str = attrs.get("phenopacket_id", "")
            if expand and pp_id:
                full_record: dict[str, Any] = await client.get(
                    PHENOPACKETS_BY_PHENOPACKET_ID.format(phenopacket_id=pp_id)
                )
                individuals.append(_shape_individual(full_record))
            else:
                # Minimal stub without full phenopacket data
                individuals.append(
                    {
                        "phenopacket_id": pp_id,
                        "uri": f"hnf1b://individual/{pp_id}",
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
        return {
            "individuals": individuals,
            "total": total,
            "page_size": page_size,
            "publications": list(seen.values()),
        }

    return {
        "individuals": individuals,
        "total": total,
        "page_size": page_size,
    }
