"""``POST /api/v2/variants/recode`` and ``/recode/batch`` endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.phenopackets.validator import PhenopacketValidator

from .schemas import BatchRecodeRequest, BatchRecodeResponse

router = APIRouter(tags=["variant-validation"])
validator = PhenopacketValidator()


@router.post(
    "/recode",
    summary="Recode variant between formats",
    description="""
Convert variant between different notation formats.

This endpoint uses Ensembl VEP's variant_recoder API to convert between:
- **HGVS notations** (coding, protein, genomic)
- **VCF format** (chromosome-position-ref-alt)
- **SPDI notation** (sequence position deletion insertion)
- **Variant IDs** (rsIDs, ClinVar IDs)

**Common Workflows:**
- `rsID → HGVS`: Literature reference to clinical notation
- `HGVS → VCF`: Clinical notation to database query format
- `VCF → HGVS`: Sequencing data to clinical report format

**Input Formats:**
- HGVS: `NM_000458.4:c.544G>A`, `NC_000017.11:g.36459258A>G`
- VCF: `17-36459258-A-G` or `chr17-36459258-A-G`
- rsID: `rs56116432`

**Performance:**
- Cached responses: ~10ms
- First call: ~600ms (VEP API)
- Rate limit: 15 requests/second
    """,
    response_description="All available variant representations",
    responses={
        200: {
            "description": "Successful recoding",
            "content": {
                "application/json": {
                    "example": {
                        "input": "rs56116432",
                        "hgvsg": ["NC_000017.11:g.36459258A>G"],
                        "hgvsc": [
                            "ENST00000366667.8:c.544+1G>A",
                            "NM_000458.4:c.544+1G>A",
                        ],
                        "hgvsp": [],
                        "spdi": {
                            "seq_id": "NC_000017.11",
                            "position": 36459257,
                            "deleted_sequence": "A",
                            "inserted_sequence": "G",
                        },
                        "vcf_string": "17:36459258-36459258:A:G",
                        "id": ["rs56116432"],
                        "full_response": {"input": "rs56116432"},
                    }
                }
            },
        },
        400: {
            "description": "Recoding failed (invalid format or variant not found)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Variant recoding failed. Supported formats: "
                            "HGVS (NM_000458.4:c.544G>A), VCF (17-36459258-A-G), "
                            "rsID (rs56116432)"
                        )
                    }
                }
            },
        },
    },
)
async def recode_variant(
    variant: str = Query(
        ...,
        description="Variant in any supported format",
        examples=["rs56116432"],
    ),
) -> Dict[str, Any]:
    """Recode variant to all possible representations."""
    recoded = await validator.variant_validator.recode_variant_with_vep(variant)

    if not recoded:
        raise HTTPException(
            status_code=400,
            detail=(
                "Variant recoding failed. Supported formats: "
                "HGVS (NM_000458.4:c.544G>A), VCF (17-36459258-A-G), rsID (rs56116432)"
            ),
        )

    return {
        "input": variant,
        "hgvsg": recoded.get("hgvsg", []),
        "hgvsc": recoded.get("hgvsc", []),
        "hgvsp": recoded.get("hgvsp", []),
        "spdi": recoded.get("spdi", {}),
        "vcf_string": recoded.get("vcf_string"),
        "id": recoded.get("id", []),
        "full_response": recoded,
    }


@router.post(
    "/recode/batch",
    response_model=BatchRecodeResponse,
    summary="Batch recode variants",
    description="""
Recode multiple variants in batch to all possible representations.

This endpoint efficiently processes up to 200 variants per batch using the
Ensembl Variant Recoder POST API.

**Input Formats:**
- HGVS: `NM_000458.4:c.544G>A`, `NC_000017.11:g.36459258A>G`
- rsID: `rs56116432`
- SPDI: `NC_000017.11:36459257:A:G`

**Output Includes:**
- hgvsg: Genomic HGVS notations
- hgvsc: Coding HGVS notations
- hgvsp: Protein HGVS notations
- spdi: SPDI notation
- vcf_string: VCF format representation
- id: Variant IDs (rsIDs)

**Performance:**
- Batch size: Up to 200 variants per request
- Cached responses: ~10ms per variant
- First call: ~500ms per batch
    """,
    response_description="Batch recoding results",
    responses={
        200: {
            "description": "Successful batch recoding",
            "content": {
                "application/json": {
                    "example": {
                        "results": {
                            "rs56116432": {
                                "input": "rs56116432",
                                "hgvsg": ["NC_000017.11:g.36459258A>G"],
                                "hgvsc": ["NM_000458.4:c.544+1G>A"],
                                "vcf_string": "17-36459258-A-G",
                            },
                            "invalid_variant": None,
                        },
                        "success_count": 1,
                        "failed_count": 1,
                    }
                }
            },
        },
    },
)
async def batch_recode_variants(request: BatchRecodeRequest) -> BatchRecodeResponse:
    """Recode multiple variants in one VEP round-trip."""
    if len(request.variants) > 200:
        raise HTTPException(
            status_code=400,
            detail="Maximum 200 variants per batch request",
        )

    results = await validator.variant_validator.recode_variants_batch(
        request.variants,
        include_vcf=request.include_vcf,
    )

    success_count = sum(1 for r in results.values() if r is not None)
    failed_count = len(results) - success_count

    return BatchRecodeResponse(
        results=results,
        success_count=success_count,
        failed_count=failed_count,
    )
