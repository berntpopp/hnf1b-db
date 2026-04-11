"""Facet computation service for phenopacket search.

Extracted from the monolithic ``search/services.py`` during Wave 4.
Owns the raw SQL for the five facet categories (sex, hasVariants,
pathogenicity, genes, phenotypes) the search UI renders next to the
results list.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FacetService:
    """Compute search facets.

    Facets show filter options with counts, helping users narrow
    down search results.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def get_facets(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute facet counts based on current filters.

        Returns facets for: ``sex``, ``hasVariants``, ``pathogenicity``,
        ``genes``, ``phenotypes``.

        All five facets apply the active query/hpo/gene/pmid filters.
        The sex filter is additionally applied to ``hasVariants``,
        ``pathogenicity``, ``genes`` and ``phenotypes``, but is
        **deliberately** not applied to the ``sex`` facet itself —
        users need to see counts for the sexes they can switch to,
        not just the one they're currently filtered on.
        """
        # ------------------------------------------------------------------
        # Build the canonical filter condition list + bind params once.
        # Downstream blocks derive two WHERE clauses from this single
        # source: one with the sex predicate (for sex-sensitive facets)
        # and one without (for the sex facet itself).
        # ------------------------------------------------------------------
        base_conditions = ["deleted_at IS NULL"]
        params: dict[str, Any] = {}

        if query:
            base_conditions.append(
                "search_vector @@ plainto_tsquery('english', :query)"
            )
            params["query"] = query

        if hpo_id:
            base_conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])

        if gene:
            base_conditions.append("phenopacket->'interpretations' @> :gene_filter")
            params["gene_filter"] = json.dumps(
                [
                    {
                        "diagnosis": {
                            "genomicInterpretations": [
                                {
                                    "variantInterpretation": {
                                        "variationDescriptor": {
                                            "geneContext": {"symbol": gene}
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            )

        if pmid:
            pmid_val = pmid if pmid.startswith("PMID:") else f"PMID:{pmid}"
            base_conditions.append(
                "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            )
            params["pmid_filter"] = json.dumps([{"id": pmid_val}])

        # ``filtered_where`` includes the sex predicate (when sex is set)
        # and is used by hasVariants/pathogenicity/genes/phenotypes.
        # ``sex_facet_where`` excludes the sex predicate and is used ONLY
        # by the sex facet so it still shows counts for all sexes.
        filtered_conditions = list(base_conditions)
        if sex:
            filtered_conditions.append("subject_sex = :sex")
            params["sex"] = sex
        filtered_where = " AND ".join(filtered_conditions)
        sex_facet_where = " AND ".join(base_conditions)

        # For LATERAL-joined queries the table is aliased as ``p`` so we
        # need a qualified version of the sex predicate.
        filtered_where_p = filtered_where.replace(
            "subject_sex = :sex", "p.subject_sex = :sex"
        )

        # Params to use for queries that don't reference :sex (sex facet).
        params_no_sex = {k: v for k, v in params.items() if k != "sex"}

        sex_sql = text(f"""
            SELECT subject_sex AS value, COUNT(*) AS count
            FROM phenopackets
            WHERE {sex_facet_where}
            GROUP BY subject_sex
            ORDER BY count DESC
        """)
        sex_result = await self.db.execute(sex_sql, params_no_sex)
        sex_facets = [
            {"value": r.value, "label": r.value or "Unknown", "count": r.count}
            for r in sex_result.fetchall()
        ]

        # Has variants facet — now correctly applies the sex filter.
        interp_path = "phenopacket->'interpretations'"
        variants_sql = text(f"""
            SELECT
                CASE
                    WHEN jsonb_array_length(
                        COALESCE({interp_path}, '[]'::jsonb)
                    ) > 0
                    THEN true ELSE false
                END AS value,
                COUNT(*) AS count
            FROM phenopackets
            WHERE {filtered_where}
            GROUP BY value
            ORDER BY value DESC
        """)
        variants_result = await self.db.execute(variants_sql, params)
        variants_facets = [
            {"value": r.value, "label": "Yes" if r.value else "No", "count": r.count}
            for r in variants_result.fetchall()
        ]

        # SQL path fragments for the JSONB queries below.
        acmg_path = (
            "gi.value->'variantInterpretation'->>'acmgPathogenicityClassification'"
        )
        gi_join = (
            "COALESCE(interp.value->'diagnosis'->'genomicInterpretations', '[]'::jsonb)"
        )

        # Pathogenicity facet.
        pathogenicity_sql = text(f"""
            SELECT {acmg_path} AS value, COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'interpretations', '[]'::jsonb)
            ) AS interp
            CROSS JOIN LATERAL jsonb_array_elements({gi_join}) AS gi
            WHERE {filtered_where_p}
            AND {acmg_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        pathogenicity_result = await self.db.execute(pathogenicity_sql, params)
        pathogenicity_facets = [
            {"value": r.value, "label": r.value, "count": r.count}
            for r in pathogenicity_result.fetchall()
        ]

        # Top genes facet.
        gene_symbol_path = (
            "gi.value->'variantInterpretation'"
            "->'variationDescriptor'->'geneContext'->>'symbol'"
        )
        genes_sql = text(f"""
            SELECT {gene_symbol_path} AS value, COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'interpretations', '[]'::jsonb)
            ) AS interp
            CROSS JOIN LATERAL jsonb_array_elements({gi_join}) AS gi
            WHERE {filtered_where_p}
            AND {gene_symbol_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        genes_result = await self.db.execute(genes_sql, params)
        genes_facets = [
            {"value": r.value, "label": r.value, "count": r.count}
            for r in genes_result.fetchall()
        ]

        # Top phenotypes facet.
        phenotypes_sql = text(f"""
            SELECT
                pf.value->'type'->>'id' AS hpo_id,
                pf.value->'type'->>'label' AS label,
                COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'phenotypicFeatures', '[]'::jsonb)) AS pf
            WHERE {filtered_where_p}
            AND pf.value->'type'->>'id' IS NOT NULL
            GROUP BY hpo_id, label
            ORDER BY count DESC
            LIMIT 20
        """)
        phenotypes_result = await self.db.execute(phenotypes_sql, params)
        phenotypes_facets = [
            {"value": r.hpo_id, "label": r.label or r.hpo_id, "count": r.count}
            for r in phenotypes_result.fetchall()
        ]

        return {
            "sex": sex_facets,
            "hasVariants": variants_facets,
            "pathogenicity": pathogenicity_facets,
            "genes": genes_facets,
            "phenotypes": phenotypes_facets,
        }
