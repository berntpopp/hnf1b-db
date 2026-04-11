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
        """
        conditions = ["deleted_at IS NULL"]
        params: dict[str, Any] = {}

        if query:
            conditions.append(
                "search_vector @@ plainto_tsquery('english', :query)"
            )
            params["query"] = query

        if hpo_id:
            conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])

        if gene:
            conditions.append("phenopacket->'interpretations' @> :gene_filter")
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
            pmid_cond = "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            conditions.append(pmid_cond)
            params["pmid_filter"] = json.dumps([{"id": pmid_val}])

        where_clause = " AND ".join(conditions)

        # Sex facets (exclude sex filter for this facet).
        sex_conditions = [c for c in conditions if "subject_sex" not in c]
        if sex:
            sex_conditions.append("subject_sex = :sex")
            params["sex"] = sex
        sex_where = " AND ".join(sex_conditions) if sex_conditions else "TRUE"

        sex_sql = text(f"""
            SELECT subject_sex AS value, COUNT(*) AS count
            FROM phenopackets
            WHERE {sex_where.replace("subject_sex = :sex", "TRUE")}
            GROUP BY subject_sex
            ORDER BY count DESC
        """)
        sex_params = {k: v for k, v in params.items() if k != "sex"}
        sex_result = await self.db.execute(sex_sql, sex_params)
        sex_facets = [
            {"value": r.value, "label": r.value or "Unknown", "count": r.count}
            for r in sex_result.fetchall()
        ]

        # Has variants facet.
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
            WHERE {where_clause}
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
            WHERE p.deleted_at IS NULL
            AND {acmg_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        pathogenicity_result = await self.db.execute(pathogenicity_sql, {})
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
            WHERE p.deleted_at IS NULL
            AND {gene_symbol_path} IS NOT NULL
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
        """)
        genes_result = await self.db.execute(genes_sql, {})
        genes_facets = [
            {"value": r.value, "label": r.value, "count": r.count}
            for r in genes_result.fetchall()
        ]

        # Top phenotypes facet.
        phenotypes_sql = text("""
            SELECT
                pf.value->'type'->>'id' AS hpo_id,
                pf.value->'type'->>'label' AS label,
                COUNT(DISTINCT p.id) AS count
            FROM phenopackets p
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(p.phenopacket->'phenotypicFeatures', '[]'::jsonb)) AS pf
            WHERE p.deleted_at IS NULL
            AND pf.value->'type'->>'id' IS NOT NULL
            GROUP BY hpo_id, label
            ORDER BY count DESC
            LIMIT 20
        """)
        phenotypes_result = await self.db.execute(phenotypes_sql, {})
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
