"""Pydantic request/response models for the variant validator endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class VariantValidationRequest(BaseModel):
    """Request body for ``POST /api/v2/variants/validate``."""

    notation: str
    notation_type: Optional[str] = None  # hgvs.c, hgvs.p, vcf, cnv, and others


class VariantValidationResponse(BaseModel):
    """Response body for ``POST /api/v2/variants/validate``."""

    is_valid: bool
    notation: str
    notation_type: Optional[str]
    errors: List[str]
    suggestions: List[str]
    vep_annotation: Optional[Dict] = None
    standardized_formats: Optional[Dict] = None


class BatchRecodeRequest(BaseModel):
    """Request body for ``POST /api/v2/variants/recode/batch``."""

    variants: List[str]
    include_vcf: bool = True


class BatchRecodeResponse(BaseModel):
    """Response body for ``POST /api/v2/variants/recode/batch``."""

    results: Dict[str, Optional[Dict[str, Any]]]
    success_count: int
    failed_count: int
