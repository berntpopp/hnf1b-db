"""``POST /api/v2/variants/validate`` endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.phenopackets.validator import PhenopacketValidator

from .helpers import detect_notation_type
from .schemas import VariantValidationRequest, VariantValidationResponse

router = APIRouter(tags=["variant-validation"])
validator = PhenopacketValidator()


@router.post(
    "/validate",
    response_model=VariantValidationResponse,
    summary="Validate variant notation",
    description="""
Validate variant notation and provide suggestions for corrections.

This endpoint validates variant formats and optionally queries Ensembl VEP
for additional validation.

**Supported Formats:**
- HGVS coding: `NM_000458.4:c.544+1G>A`
- HGVS protein: `NP_000449.3:p.Arg182Trp`
- HGVS genomic: `NC_000017.11:g.36459258A>G`
- VCF: `17-36459258-A-G` or `chr17-36459258-A-G`
- CNV: `17:36459258-37832869:DEL`

**Features:**
1. Format validation (HGVS, VCF, CNV)
2. VEP validation for HGVS notations
3. Helpful suggestions for invalid formats
4. Standardized format conversion when possible
    """,
    response_description="Validation result with suggestions and standardized formats",
    responses={
        200: {
            "description": "Successful validation",
            "content": {
                "application/json": {
                    "examples": {
                        "valid_hgvs": {
                            "summary": "Valid HGVS notation",
                            "value": {
                                "is_valid": True,
                                "notation": "NM_000458.4:c.544+1G>A",
                                "notation_type": "hgvs.c",
                                "errors": [],
                                "suggestions": [],
                                "vep_annotation": {
                                    "most_severe_consequence": "splice_donor_variant",
                                    "gene_symbol": "HNF1B",
                                },
                                "standardized_formats": {
                                    "hgvs_c": "NM_000458.4:c.544+1G>A",
                                    "hgvs_g": "NC_000017.11:g.36459258A>G",
                                },
                            },
                        },
                        "invalid_notation": {
                            "summary": "Invalid notation with suggestions",
                            "value": {
                                "is_valid": False,
                                "notation": "NM_000458.4c.544+1G>A",
                                "notation_type": "unknown",
                                "errors": ["Could not recognize variant format"],
                                "suggestions": [
                                    "Missing ':' after transcript ID",
                                    "Did you mean: NM_000458.4:c.544+1G>A?",
                                ],
                                "vep_annotation": None,
                                "standardized_formats": None,
                            },
                        },
                    }
                }
            },
        }
    },
)
async def validate_variant(request: VariantValidationRequest):
    """Validate variant notation and provide suggestions."""
    notation = request.notation.strip()

    # Try VEP validation first for HGVS notations
    if ":" in notation and any(x in notation for x in ["c.", "p.", "g."]):
        is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
            notation
        )

        if is_valid and vep_data:
            standardized = {
                "hgvs_c": vep_data.get("hgvsc"),
                "hgvs_p": vep_data.get("hgvsp"),
                "hgvs_g": vep_data.get("hgvsg"),
                "consequence": vep_data.get("most_severe_consequence"),
                "gene": vep_data.get("gene_symbol", "HNF1B"),
                "transcript": vep_data.get("transcript_id"),
            }

            return VariantValidationResponse(
                is_valid=True,
                notation=notation,
                notation_type=request.notation_type or detect_notation_type(notation),
                errors=[],
                suggestions=[],
                vep_annotation=vep_data,
                standardized_formats=standardized,
            )

    # Fallback to regex validation
    errors: list[str] = []
    suggestions = validator._get_notation_suggestions(notation)

    notation_type = request.notation_type or detect_notation_type(notation)
    is_valid = False

    if notation_type == "hgvs.c":
        is_valid = validator._validate_hgvs_c(notation)
        if not is_valid:
            errors.append(f"Invalid HGVS c. notation: {notation}")
    elif notation_type == "hgvs.p":
        is_valid = validator._validate_hgvs_p(notation)
        if not is_valid:
            errors.append(f"Invalid HGVS p. notation: {notation}")
    elif notation_type == "hgvs.g":
        is_valid = validator._validate_hgvs_g(notation)
        if not is_valid:
            errors.append(f"Invalid HGVS g. notation: {notation}")
    elif notation_type == "vcf":
        is_valid = validator._validate_vcf(notation)
        if not is_valid:
            errors.append(f"Invalid VCF format: {notation}")
    elif notation_type == "cnv":
        is_valid = validator._is_ga4gh_cnv_notation(notation)
        if not is_valid:
            errors.append(f"Invalid CNV notation: {notation}")
            suggestions.append("Use format: 17:start-end:DEL or 17:start-end:DUP")
    else:
        is_valid = validator._fallback_validation(notation)
        if not is_valid:
            errors.append(f"Could not recognize variant format: {notation}")

    return VariantValidationResponse(
        is_valid=is_valid,
        notation=notation,
        notation_type=notation_type,
        errors=errors,
        suggestions=suggestions,
        vep_annotation=None,
        standardized_formats=None,
    )
