"""Wave 5b: variant_query_builder raw-SQL CTEs must honour soft-delete.

Wave 5a exit follow-up #2: two CTEs in variant_query_builder.py query
``phenopackets p`` directly and bypass the global soft-delete filter,
leaking variant counts from soft-deleted rows through
``/api/v2/phenopackets/aggregate/all-variants``.

This test creates a phenopacket with a variant, fetches the all-variants
aggregation, soft-deletes the phenopacket, fetches again, and asserts
the variant is gone.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_soft_deleted_phenopacket_hidden_from_all_variants(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Soft-deleting a phenopacket removes it from /aggregate/all-variants."""
    # Create a phenopacket with an interpretations.variationDescriptor block
    # that the variant_query_builder CTEs will pick up.
    create_payload = {
        "phenopacket": {
            "id": "wave5b-softdel-variant-001",
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "interpretations": [
                {
                    "id": "interp-1",
                    "progressStatus": "SOLVED",
                    "diagnosis": {
                        "disease": {"id": "MONDO:0000001", "label": "test"},
                        "genomicInterpretations": [
                            {
                                "subjectOrBiosampleId": "s",
                                "interpretationStatus": "PATHOGENIC",
                                "variantInterpretation": {
                                    "acmgPathogenicityClassification": ("PATHOGENIC"),
                                    "variationDescriptor": {
                                        "id": "wave5b-softdel-var-001",
                                        "label": "test variant",
                                        "geneContext": {
                                            "valueId": "HGNC:11621",
                                            "symbol": "HNF1B",
                                        },
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.c",
                                                "value": "c.100A>G",
                                            },
                                        ],
                                        "vcfRecord": {
                                            "chrom": "17",
                                            "pos": "36000000",
                                            "ref": "A",
                                            "alt": "G",
                                        },
                                    },
                                },
                            }
                        ],
                    },
                }
            ],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pytest",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-01-01",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        }
    }
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    # Capture baseline: the new variant should appear under query lookup.
    before = await async_client.get(
        "/api/v2/phenopackets/aggregate/all-variants",
        params={"query": "wave5b-softdel-var-001"},
        headers=admin_headers,
    )
    assert before.status_code == 200, before.text
    before_ids = {v.get("variant_id") for v in (before.json().get("data") or [])}
    assert "wave5b-softdel-var-001" in before_ids, (
        "setup: variant should appear before soft-delete"
    )

    # Soft delete the phenopacket.
    del_resp = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/wave5b-softdel-variant-001",
        json={"change_reason": "wave5b soft-delete leak test"},
        headers=admin_headers,
    )
    assert del_resp.status_code == 200, del_resp.text

    # After delete, the variant must no longer appear.
    after = await async_client.get(
        "/api/v2/phenopackets/aggregate/all-variants",
        params={"query": "wave5b-softdel-var-001"},
        headers=admin_headers,
    )
    assert after.status_code == 200, after.text
    after_ids = {v.get("variant_id") for v in (after.json().get("data") or [])}
    assert "wave5b-softdel-var-001" not in after_ids, (
        "Soft-deleted phenopacket's variant is still leaking through "
        "/aggregate/all-variants - variant_query_builder CTEs need "
        "AND p.deleted_at IS NULL"
    )
