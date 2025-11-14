"""Variant validation and suggestion endpoint."""

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.phenopackets.validator import PhenopacketValidator

router = APIRouter(prefix="/api/v2/variants", tags=["variant-validation"])
validator = PhenopacketValidator()


class VariantValidationRequest(BaseModel):
    """Request model for variant validation."""

    notation: str
    notation_type: Optional[str] = None  # hgvs.c, hgvs.p, vcf, cnv, and others


class VariantValidationResponse(BaseModel):
    """Response model for variant validation."""

    is_valid: bool
    notation: str
    notation_type: Optional[str]
    errors: List[str]
    suggestions: List[str]
    vep_annotation: Optional[Dict] = None
    standardized_formats: Optional[Dict] = None


@router.post("/validate", response_model=VariantValidationResponse)
async def validate_variant(request: VariantValidationRequest):
    """Validate variant notation and provide suggestions.

    This endpoint:
    1. Validates variant format (HGVS, VCF, CNV, and others)
    2. Queries VEP for additional validation and annotation
    3. Provides helpful suggestions for invalid formats
    4. Returns standardized formats when possible
    """
    notation = request.notation.strip()

    # Try VEP validation first for HGVS notations
    if ":" in notation and any(x in notation for x in ["c.", "p.", "g."]):
        is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
            notation
        )

        if is_valid and vep_data:
            # Extract standardized formats from VEP response
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
                notation_type=request.notation_type or _detect_notation_type(notation),
                errors=[],
                suggestions=[],
                vep_annotation=vep_data,
                standardized_formats=standardized,
            )

    # Fallback to regex validation
    errors = []
    suggestions = validator._get_notation_suggestions(notation)

    # Check various formats
    notation_type = request.notation_type or _detect_notation_type(notation)
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
        # Try all validators
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


@router.post("/annotate")
async def annotate_variant(
    variant: str = Query(..., description="Variant in VCF or HGVS format")
) -> Dict[str, Any]:
    """Annotate variant with VEP including functional predictions.

    This endpoint provides:
    - Consequence predictions (missense, splice_donor, etc.)
    - Impact severity (HIGH, MODERATE, LOW, MODIFIER)
    - CADD pathogenicity scores
    - gnomAD population frequencies
    - Gene context and transcript information

    Args:
        variant: Variant in VCF (17-36459258-A-G) or
            HGVS (NM_000458.4:c.544+1G>A) format

    Returns:
        Dictionary with annotation data

    Raises:
        HTTPException: If annotation fails
    """
    # Get VEP annotation
    annotation = await validator.variant_validator.annotate_variant_with_vep(
        variant
    )

    if not annotation:
        raise HTTPException(
            status_code=400,
            detail=(
                "Variant annotation failed. Check format: "
                "VCF (17-36459258-A-G) or HGVS (NM_000458.4:c.544+1G>A)"
            ),
        )

    # Extract key information
    primary_consequence = None
    cadd_score = None
    gnomad_af = None

    # Get primary transcript consequence (MANE select preferred)
    transcript_consequences = annotation.get("transcript_consequences", [])
    for tc in transcript_consequences:
        if tc.get("mane_select"):
            primary_consequence = tc
            break

    if not primary_consequence and transcript_consequences:
        # Fallback to canonical
        for tc in transcript_consequences:
            if tc.get("canonical"):
                primary_consequence = tc
                break

    if not primary_consequence and transcript_consequences:
        # Fallback to first transcript
        primary_consequence = transcript_consequences[0]

    # Extract CADD score
    if primary_consequence:
        cadd_score = primary_consequence.get("cadd_phred")

    # Extract gnomAD frequency
    colocated_variants = annotation.get("colocated_variants", [])
    if colocated_variants:
        gnomad_af = colocated_variants[0].get("gnomad_af")

    # Build response
    return {
        "input": variant,
        "assembly": annotation.get("assembly_name", "GRCh38"),
        "chromosome": annotation.get("seq_region_name"),
        "position": annotation.get("start"),
        "allele_string": annotation.get("allele_string"),
        "most_severe_consequence": annotation.get("most_severe_consequence"),
        "impact": (
            primary_consequence.get("impact") if primary_consequence else None
        ),
        "gene_symbol": (
            primary_consequence.get("gene_symbol")
            if primary_consequence
            else None
        ),
        "gene_id": (
            primary_consequence.get("gene_id") if primary_consequence else None
        ),
        "transcript_id": (
            primary_consequence.get("transcript_id")
            if primary_consequence
            else None
        ),
        "hgvsc": (
            primary_consequence.get("hgvsc") if primary_consequence else None
        ),
        "hgvsp": (
            primary_consequence.get("hgvsp") if primary_consequence else None
        ),
        "cadd_score": cadd_score,
        "gnomad_af": gnomad_af,
        "full_annotation": annotation,  # Include full response for advanced users
    }


@router.post("/recode")
async def recode_variant(
    variant: str = Query(..., description="Variant in any supported format")
) -> Dict[str, Any]:
    """Recode variant to all possible representations (HGVS, VCF, SPDI, rsID).

    This endpoint converts between different variant notations:
    - HGVS c./p./g. notations (coding, protein, genomic)
    - VCF format (chr-pos-ref-alt)
    - SPDI notation (genomic coordinates)
    - Variant IDs (rsIDs, ClinVar IDs)

    Useful for:
    - Converting user input c. notation to VCF for database queries
    - Getting all equivalent representations for a variant
    - Standardizing variant nomenclature

    Args:
        variant: Variant in any format (e.g., "NM_000458.4:c.544G>A",
            "17-36459258-A-G", "rs56116432")

    Returns:
        Dictionary with all available variant representations

    Example Response:
        {
            "input": "NM_000458.4:c.544G>A",
            "hgvsg": ["NC_000017.11:g.36459258A>G"],
            "hgvsc": ["NM_000458.4:c.544G>A"],
            "hgvsp": ["NP_000449.3:p.Gly182Ser"],
            "spdi": {...},
            "vcf_string": "17:36459258-36459258:A:G",
            "id": ["rs56116432"]
        }
    """
    # Get variant recoding
    recoded = await validator.variant_validator.recode_variant_with_vep(variant)

    if not recoded:
        raise HTTPException(
            status_code=400,
            detail=(
                "Variant recoding failed. Supported formats: "
                "HGVS (NM_000458.4:c.544G>A), VCF (17-36459258-A-G), rsID (rs56116432)"
            ),
        )

    # Build clean response
    return {
        "input": variant,
        "hgvsg": recoded.get("hgvsg", []),
        "hgvsc": recoded.get("hgvsc", []),
        "hgvsp": recoded.get("hgvsp", []),
        "spdi": recoded.get("spdi", {}),
        "vcf_string": recoded.get("vcf_string"),
        "id": recoded.get("id", []),
        "full_response": recoded,  # Include complete VEP response
    }


@router.get("/suggest/{partial_notation}")
async def suggest_notation(partial_notation: str):
    """Get autocomplete suggestions for partial variant notation.

    Useful for frontend autocomplete as user types.
    """
    # Common HNF1B variants for autocomplete
    common_variants = [
        "NM_000458.4:c.544+1G>A",
        "NM_000458.4:c.544G>T",
        "NM_000458.4:c.1234A>T",
        "NM_000458.4:c.721C>T",
        "17:36459258-37832869:DEL",
        "17:36459258-37832869:DUP",
        "chr17:g.36459258A>G",
    ]

    # Filter based on partial input
    suggestions = []
    partial_lower = partial_notation.lower()

    for variant in common_variants:
        if partial_lower in variant.lower():
            suggestions.append(variant)

    # Add format hints
    if len(suggestions) == 0:
        if "c." in partial_lower:
            suggestions.append("Format: NM_000458.4:c.123A>G")
        elif "p." in partial_lower:
            suggestions.append("Format: NP_000449.3:p.Arg181*")
        elif "del" in partial_lower:
            suggestions.append("Format: 17:start-end:DEL")
        elif "dup" in partial_lower:
            suggestions.append("Format: 17:start-end:DUP")

    return {
        "query": partial_notation,
        "suggestions": suggestions[:10],  # Limit to 10 suggestions
    }


def _detect_notation_type(notation: str) -> str:
    """Detect the type of variant notation."""
    if ":c." in notation:
        return "hgvs.c"
    elif ":p." in notation:
        return "hgvs.p"
    elif ":g." in notation:
        return "hgvs.g"
    elif re.match(r"^(chr)?[\dXY]+-\d+-[ATCG]+-[ATCG]+", notation):
        return "vcf"
    elif re.match(r"^[\dXY]+:\d+-\d+:(DEL|DUP|INS|INV)", notation):
        return "cnv"
    else:
        return "unknown"
