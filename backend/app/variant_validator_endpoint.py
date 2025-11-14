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
        example="NM_000458.4:c.544+1G>A",
    )
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
        example="rs56116432",
    )
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


@router.get(
    "/suggest/{partial_notation}",
    summary="Get variant notation suggestions",
    description="""
Get autocomplete suggestions for partial variant notation.

This endpoint provides:
- Common HNF1B variant examples matching the partial input
- Format hints when no matches are found
- Helpful examples for different notation types

**Use Cases:**
- Frontend autocomplete during variant entry
- Format validation hints
- Learning correct notation formats

**Returns up to 10 suggestions** including:
- Matching HNF1B variants from common database
- Format templates (e.g., "Format: NM_000458.4:c.123A>G")
    """,
    response_description="List of notation suggestions",
    responses={
        200: {
            "description": "Suggestions returned",
            "content": {
                "application/json": {
                    "examples": {
                        "matching_variants": {
                            "summary": "Partial input matches variants",
                            "value": {
                                "query": "NM_000458",
                                "suggestions": [
                                    "NM_000458.4:c.544+1G>A",
                                    "NM_000458.4:c.544G>T",
                                    "NM_000458.4:c.1234A>T",
                                ],
                            },
                        },
                        "format_hints": {
                            "summary": "No matches, return format hints",
                            "value": {
                                "query": "c.123",
                                "suggestions": ["Format: NM_000458.4:c.123A>G"],
                            },
                        },
                    }
                }
            },
        }
    },
)
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
