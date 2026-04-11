"""``POST /api/v2/variants/annotate`` endpoint."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.phenopackets.validator import PhenopacketValidator

router = APIRouter(tags=["variant-validation"])
validator = PhenopacketValidator()


@router.post(
    "/annotate",
    summary="Annotate variant with VEP",
    description="""
Annotate variant using Ensembl Variant Effect Predictor (VEP).

Returns comprehensive variant annotations including:
- **Consequence predictions** (splice_donor_variant, missense_variant, etc.)
- **Impact severity** (HIGH, MODERATE, LOW, MODIFIER)
- **CADD scores** (deleteriousness prediction, >30 = likely pathogenic)
- **gnomAD frequencies** (population allele frequency)
- **Gene and transcript context** (MANE Select preferred)

**Supported Input Formats:**
- HGVS: `NM_000458.4:c.544+1G>A`, `NC_000017.11:g.36459258A>G`
- VCF: `17-36459258-A-G` or `chr17-36459258-A-G`
- rsID: `rs56116432`

**Performance:**
- First call: ~500ms (VEP API call)
- Cached calls: ~10ms (from LRU cache)
- Rate limit: 15 requests/second

**Example Use Cases:**
- Clinical interpretation of patient variants
- Research batch annotation of variant lists
- Phenopacket variant validation
    """,
    response_description="Comprehensive variant annotation",
    responses={
        200: {
            "description": "Successful annotation",
            "content": {
                "application/json": {
                    "example": {
                        "input": "NM_000458.4:c.544+1G>A",
                        "assembly": "GRCh38",
                        "chromosome": "17",
                        "position": 36459258,
                        "allele_string": "A/G",
                        "most_severe_consequence": "splice_donor_variant",
                        "impact": "HIGH",
                        "gene_symbol": "HNF1B",
                        "gene_id": "ENSG00000108753",
                        "transcript_id": "ENST00000366667",
                        "hgvsc": "ENST00000366667.8:c.544+1G>A",
                        "hgvsp": None,
                        "cadd_score": 34.0,
                        "gnomad_af": 0.0001,
                        "full_annotation": {
                            "transcript_consequences": [
                                {
                                    "gene_symbol": "HNF1B",
                                    "consequence_terms": ["splice_donor_variant"],
                                    "impact": "HIGH",
                                    "mane_select": "ENST00000366667.8",
                                }
                            ],
                            "colocated_variants": [
                                {"id": "rs56116432", "gnomad_af": 0.0001}
                            ],
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid variant format or annotation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Variant annotation failed. Check format: "
                            "VCF (17-36459258-A-G) or HGVS (NM_000458.4:c.544+1G>A)"
                        )
                    }
                }
            },
        },
    },
)
async def annotate_variant(
    variant: str = Query(
        ...,
        description="Variant in HGVS, VCF, or rsID format",
        examples=["NM_000458.4:c.544+1G>A"],
    ),
) -> Dict[str, Any]:
    """Annotate variant with VEP including functional predictions."""
    annotation = await validator.variant_validator.annotate_variant_with_vep(variant)

    if not annotation:
        raise HTTPException(
            status_code=400,
            detail=(
                "Variant annotation failed. Check format: "
                "VCF (17-36459258-A-G) or HGVS (NM_000458.4:c.544+1G>A)"
            ),
        )

    primary_consequence = None

    # Get primary transcript consequence (MANE select preferred)
    transcript_consequences = annotation.get("transcript_consequences", [])
    for tc in transcript_consequences:
        if tc.get("mane_select"):
            primary_consequence = tc
            break

    if not primary_consequence and transcript_consequences:
        for tc in transcript_consequences:
            if tc.get("canonical"):
                primary_consequence = tc
                break

    if not primary_consequence and transcript_consequences:
        primary_consequence = transcript_consequences[0]

    cadd_score = primary_consequence.get("cadd_phred") if primary_consequence else None

    colocated_variants = annotation.get("colocated_variants", [])
    gnomad_af = colocated_variants[0].get("gnomad_af") if colocated_variants else None

    return {
        "input": variant,
        "assembly": annotation.get("assembly_name", "GRCh38"),
        "chromosome": annotation.get("seq_region_name"),
        "position": annotation.get("start"),
        "allele_string": annotation.get("allele_string"),
        "most_severe_consequence": annotation.get("most_severe_consequence"),
        "impact": (primary_consequence.get("impact") if primary_consequence else None),
        "gene_symbol": (
            primary_consequence.get("gene_symbol") if primary_consequence else None
        ),
        "gene_id": (
            primary_consequence.get("gene_id") if primary_consequence else None
        ),
        "transcript_id": (
            primary_consequence.get("transcript_id") if primary_consequence else None
        ),
        "hgvsc": (primary_consequence.get("hgvsc") if primary_consequence else None),
        "hgvsp": (primary_consequence.get("hgvsp") if primary_consequence else None),
        "cadd_score": cadd_score,
        "gnomad_af": gnomad_af,
        "full_annotation": annotation,
    }
