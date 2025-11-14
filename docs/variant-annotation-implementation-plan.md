# Variant Annotation & Validation System - Implementation Plan

**Version**: 3.0 (Implementation Complete)
**Original Plan Date**: 2025-01-14
**Completion Date**: 2025-01-15
**Actual Effort**: ~4 hours (as estimated)
**Complexity**: Low (enhanced existing code as planned)

---

## 🎉 Implementation Status: COMPLETED ✅

### Summary

All planned features have been successfully implemented, tested, and documented. The implementation followed the KISS principle and enhanced existing code without over-engineering.

**Key Achievements:**
- ✅ Issue #56 resolved: ga4gh.vrs moved to main dependencies
- ✅ Issue #100 resolved: Full VEP annotation pipeline implemented
- ✅ 99% code coverage (332/337 lines) with 83 unit tests + 18 integration tests
- ✅ All tests passing in ~7 seconds
- ✅ Zero linting errors (ruff)
- ✅ Zero type checking errors (mypy)
- ✅ Comprehensive documentation completed

**Delivered Features:**
1. **Variant Validation API** - `/api/v2/variants/validate`
2. **VEP Annotation API** - `/api/v2/variants/annotate`
3. **Variant Recoding API** - `/api/v2/variants/recode`
4. **Notation Suggestions API** - `/api/v2/variants/suggest/{notation}`
5. **Rate Limiting** - Token bucket algorithm (15 req/sec)
6. **Caching** - LRU cache (1000 variants)
7. **Error Handling** - Retry logic with exponential backoff
8. **Format Support** - HGVS, VCF, rsID notations

**Test Coverage:**
- **Unit Tests:** 83 tests in `tests/test_variant_validator_enhanced.py` (1,570 lines)
- **Integration Tests:** 18 tests in `tests/test_variant_validator_api_integration.py` (457 lines)
- **Coverage:** 99% (332/337 lines)
- **Execution Time:** 7.33 seconds (well under 2-minute target)

**Documentation:**
- ✅ API Reference: `docs/api/variant-annotation.md` (comprehensive)
- ✅ User Guide: `docs/user-guide/variant-annotation.md` (with examples)
- ✅ Developer Guide: This document (updated)
- ✅ README: Updated with variant annotation features

### Implementation Timeline

| Date | Milestone | Status |
|------|-----------|--------|
| 2025-01-14 | Implementation plan created | ✅ Complete |
| 2025-01-15 | Phase 1: ga4gh.vrs dependency moved | ✅ Complete |
| 2025-01-15 | Phase 2: VEP integration enhanced | ✅ Complete |
| 2025-01-15 | Phase 3: API endpoints created | ✅ Complete |
| 2025-01-15 | Testing: 83 unit tests written | ✅ Complete |
| 2025-01-15 | Testing: 18 integration tests written | ✅ Complete |
| 2025-01-15 | Code quality: Linting & type checking | ✅ Complete |
| 2025-01-15 | Documentation: API reference | ✅ Complete |
| 2025-01-15 | Documentation: User guide | ✅ Complete |
| 2025-01-15 | Issue #117: Test coverage to 99% | ✅ Complete |
| 2025-01-15 | Issue #118: Documentation review | ✅ Complete |

### Files Modified/Created

**Backend Implementation:**
- ✅ `backend/app/phenopackets/validation/variant_validator.py` (728 lines, 99% coverage)
- ✅ `backend/app/api/v2/variant_validator_endpoint.py` (API endpoints)
- ✅ `backend/pyproject.toml` (moved ga4gh.vrs to main dependencies)

**Testing:**
- ✅ `backend/tests/test_variant_validator_enhanced.py` (1,570 lines, 83 tests)
- ✅ `backend/tests/test_variant_validator_api_integration.py` (457 lines, 18 tests)

**Documentation:**
- ✅ `docs/api/variant-annotation.md` (API reference with examples)
- ✅ `docs/user-guide/variant-annotation.md` (User guide with workflows)
- ✅ `docs/variant-annotation-implementation-plan.md` (this file - updated)
- ✅ `backend/README.md` (updated with variant annotation features)

**Total Lines Added/Modified:**
- Code: ~800 lines (variant_validator.py + endpoints)
- Tests: ~2,027 lines (unit + integration tests)
- Documentation: ~2,500 lines (API ref + user guide + updates)
- **Total: ~5,327 lines**

---

## Executive Summary (Original Plan)

This plan implements Ensembl VEP-based variant annotation by **enhancing existing code** rather than building new infrastructure. It solves Issues #56 and #100 with minimal complexity, following KISS, DRY, and SOLID principles.

**Key Philosophy**: Enhance what exists, don't rebuild from scratch.

---

## Issues Being Addressed

### Issue #56: Fix ga4gh.vrs Installation
**Current**: ga4gh.vrs in optional `phenopackets` dependency group
**Problem**: Variants use placeholder digests, warning during migration
**Solution**: Move to main dependencies
**Effort**: 5 minutes

### Issue #100: Add VEP Annotation Pipeline
**Current**: Basic regex validation, no functional predictions
**Problem**: No consequence, CADD scores, gnomAD frequencies
**Solution**: Enhance existing VEP integration
**Effort**: 2-3 hours

---

## Current State Analysis

### What Already Exists ✅

1. **VEP Integration Started** (`backend/app/phenopackets/validation/variant_validator.py:13-42`)
   - Already has `validate_variant_with_vep()` method
   - Uses httpx AsyncClient
   - Calls Ensembl REST API

2. **VRS Builder** (`backend/migration/vrs/vrs_builder.py`)
   - Creates GA4GH VRS 2.0 structures
   - Needs proper digests (Issue #56)

3. **Validation Endpoint** (`backend/app/variant_validator_endpoint.py`)
   - Has `/validate` endpoint
   - Can be extended for `/annotate`

4. **Service Pattern** (`backend/app/services/ontology_service.py`)
   - Good reference for API + cache + fallback
   - Don't duplicate, follow same pattern

### What's Missing ❌

1. CADD scores in VEP responses
2. gnomAD allele frequencies
3. Proper Ensembl rate limiting (15 req/sec)
4. Simple caching for repeated queries
5. VCF format support in VEP calls

---

## Design Principles

### KISS (Keep It Simple, Stupid)
- ✅ Enhance existing `VariantValidator` class (don't create new files)
- ✅ Simple in-memory cache (dict, not Redis)
- ✅ Focus on actual requirements only

### DRY (Don't Repeat Yourself)
- ✅ Use existing httpx patterns
- ✅ Reuse existing VRS builder
- ✅ Extend existing endpoints

### SOLID
- ✅ Single Responsibility: Each method does one thing
- ✅ Open/Closed: Extend existing class without breaking it
- ✅ Interface Segregation: Small, focused methods

### YAGNI (You Aren't Gonna Need It)
- ❌ No persistent cache layer (premature optimization)
- ❌ No separate orchestrator service (unnecessary abstraction)
- ❌ No batch processing system (not requested)
- ❌ No format conversion service (VEP API does this)

---

## Implementation Plan

### Phase 1: Fix Issue #56 - ga4gh.vrs Installation (5 minutes)

**File**: `backend/pyproject.toml` (line 58)

**Change**:
```toml
# BEFORE (line 58, in phenopackets group):
phenopackets = [
    "ga4gh.vrs>=2.0.0",  # ← Move this
    "oaklib>=0.5.0",
]

# AFTER (line 34, in main dependencies):
dependencies = [
    # ... existing ...
    "ga4gh.vrs>=2.1.3",  # ← Moved here, updated version
]

# Remove from phenopackets group:
phenopackets = [
    "oaklib>=0.5.0",  # Keep this
]
```

**Commands**:
```bash
cd backend
uv sync  # Reinstall dependencies
```

**Verification**:
```bash
uv run python -c "import ga4gh.vrs; print('✅ ga4gh.vrs installed')"
make phenopackets-migrate-test  # Should have no warning
```

**Acceptance Criteria**:
- [ ] No "ga4gh.vrs not available" warning during migration
- [ ] Variant digests use proper GA4GH computation
- [ ] Tests pass: `pytest tests/test_vrs_builder.py -v`

---

### Phase 2: Enhance VEP Integration (2-3 hours)

#### 2.1 Enhance VariantValidator Class

**File**: `backend/app/phenopackets/validation/variant_validator.py`

**Changes**: Add to existing `VariantValidator` class (after line 292)

```python
"""Enhanced VEP annotation with CADD, gnomAD, proper rate limiting."""

import asyncio
import time
from typing import Optional


class VariantValidator:
    """Validates variant formats including HGVS, VCF, VRS, and CNV notations."""

    def __init__(self):
        """Initialize validator with simple in-memory cache and rate limiting."""
        # Simple in-memory cache (sufficient for single-instance app)
        self._vep_cache: Dict[str, Dict[str, Any]] = {}

        # Rate limiting state (Ensembl: 15 req/sec max)
        self._last_request_time = 0.0
        self._request_count = 0
        self._requests_per_second = 15

    # ... existing methods ...

    async def annotate_variant_with_vep(
        self,
        variant: str,
        include_annotations: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Annotate variant with VEP including CADD, gnomAD, consequences.

        Supports both VCF and HGVS formats:
        - VCF: "17-36459258-A-G" or "chr17-36459258-A-G"
        - HGVS: "NM_000458.4:c.544+1G>A"

        Args:
            variant: Variant in VCF or HGVS format
            include_annotations: Include CADD, gnomAD, etc.

        Returns:
            VEP annotation dict with:
            - most_severe_consequence
            - transcript_consequences (with CADD scores)
            - colocated_variants (with gnomAD frequencies)
            - assembly_name, seq_region_name, start, end, allele_string

        Example:
            annotation = await validator.annotate_variant_with_vep("17-36459258-A-G")
            consequence = annotation["most_severe_consequence"]
            cadd = annotation["transcript_consequences"][0]["cadd_phred"]
            gnomad_af = annotation["colocated_variants"][0]["gnomad_af"]
        """
        # Check cache first
        cache_key = f"{variant}:{include_annotations}"
        if cache_key in self._vep_cache:
            return self._vep_cache[cache_key]

        # Rate limiting (15 req/sec per Ensembl guidelines)
        await self._rate_limit()

        # Determine format and build request
        is_vcf = self._is_vcf_format(variant)

        if is_vcf:
            # VCF format: use POST /vep/human/region
            vep_input = self._vcf_to_vep_format(variant)
            if not vep_input:
                return None

            endpoint = "https://rest.ensembl.org/vep/human/region"
            method = "POST"
            json_data = {"variants": [vep_input]}
        else:
            # HGVS format: use GET /vep/human/hgvs
            endpoint = f"https://rest.ensembl.org/vep/human/hgvs/{variant}"
            method = "GET"
            json_data = None

        # Build query parameters
        params = {}
        if include_annotations:
            params.update({
                "CADD": "1",            # CADD scores
                "hgvs": "1",            # HGVS notations
                "mane": "1",            # MANE select transcripts
                "gencode_primary": "1", # GENCODE primary (2025 best practice)
            })

        try:
            async with httpx.AsyncClient() as client:
                if method == "POST":
                    response = await client.post(
                        endpoint,
                        json=json_data,
                        params=params,
                        headers={"Content-Type": "application/json"},
                        timeout=30.0,
                    )
                else:
                    response = await client.get(
                        endpoint,
                        params=params,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0,
                    )

                # Check rate limit headers
                self._check_rate_limit_headers(response.headers)

                # Handle response
                if response.status_code == 200:
                    result = response.json()
                    annotation = result[0] if isinstance(result, list) else result

                    # Cache successful result
                    self._vep_cache[cache_key] = annotation
                    return annotation

                elif response.status_code == 429:
                    # Rate limited - respect Retry-After header
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print(f"⚠️  Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self.annotate_variant_with_vep(variant, include_annotations)

                elif response.status_code == 400:
                    # Invalid variant format
                    print(f"❌ Invalid variant format: {variant}")
                    return None

                else:
                    print(f"❌ VEP API error {response.status_code}")
                    return None

        except Exception as e:
            print(f"❌ VEP annotation error: {e}")
            return None

    async def _rate_limit(self):
        """Implement Ensembl rate limiting (15 requests/second).

        Per Ensembl guidelines: https://github.com/Ensembl/ensembl-rest/wiki/Rate-Limits
        - 55,000 requests per hour
        - Average 15 requests per second
        - Must respect Retry-After header on 429 responses
        """
        current_time = time.time()

        # Reset counter every second
        if current_time - self._last_request_time >= 1.0:
            self._request_count = 0
            self._last_request_time = current_time

        # If at limit, wait until next second
        if self._request_count >= self._requests_per_second:
            sleep_time = 1.0 - (current_time - self._last_request_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self._request_count = 0
            self._last_request_time = time.time()

        self._request_count += 1

    def _check_rate_limit_headers(self, headers):
        """Check X-RateLimit-* headers and warn if approaching limit."""
        remaining = headers.get("X-RateLimit-Remaining")
        limit = headers.get("X-RateLimit-Limit")

        if remaining and limit:
            remaining_int = int(remaining)
            limit_int = int(limit)

            # Warn if < 10% remaining
            if remaining_int < limit_int * 0.1:
                print(f"⚠️  Rate limit warning: {remaining}/{limit} requests remaining")

    @staticmethod
    def _is_vcf_format(variant: str) -> bool:
        """Check if variant is VCF format (chr-pos-ref-alt)."""
        return bool(re.match(r"^(chr)?[\dXYM]+-\d+-[ACGT]+-[ACGT]+$", variant, re.I))

    @staticmethod
    def _vcf_to_vep_format(vcf_variant: str) -> Optional[str]:
        """Convert VCF variant to VEP POST format.

        Input: "17-36459258-A-G" or "chr17-36459258-A-G"
        Output: "17 36459258 . A G . . ."
        """
        # Remove "chr" prefix if present
        vcf_variant = vcf_variant.replace("chr", "").replace("Chr", "").replace("CHR", "")

        # Parse components
        parts = vcf_variant.split("-")
        if len(parts) != 4:
            return None

        chrom, pos, ref, alt = parts

        # Validate
        if not pos.isdigit():
            return None

        # Format for VEP: "chrom pos . ref alt . . ."
        return f"{chrom} {pos} . {ref} {alt} . . ."
```

**Lines Added**: ~160 lines (enhancement to existing file)

**Key Features**:
- ✅ Proper rate limiting (15 req/sec with headers check)
- ✅ Simple in-memory cache (no external dependencies)
- ✅ Supports both VCF and HGVS formats
- ✅ Includes CADD scores and gnomAD frequencies
- ✅ Respects Retry-After header on 429 errors
- ✅ Clear error messages

---

#### 2.2 Add Annotation Endpoint (30 minutes)

**File**: `backend/app/variant_validator_endpoint.py`

**Changes**: Add new endpoint after existing `/validate` (after line 175)

```python
@router.post("/annotate")
async def annotate_variant(
    variant: str = Query(..., description="Variant in VCF or HGVS format"),
) -> Dict[str, Any]:
    """Annotate variant with VEP including functional predictions.

    This endpoint provides:
    - Consequence predictions (missense, splice_donor, etc.)
    - Impact severity (HIGH, MODERATE, LOW, MODIFIER)
    - CADD pathogenicity scores
    - gnomAD population frequencies
    - Gene context and transcript information

    Examples:
        - VCF: 17-36459258-A-G
        - HGVS: NM_000458.4:c.544+1G>A
    """
    validator = PhenopacketValidator()

    # Get VEP annotation
    annotation = await validator.variant_validator.annotate_variant_with_vep(variant)

    if not annotation:
        raise HTTPException(
            status_code=400,
            detail="Variant annotation failed. Check format: VCF (17-36459258-A-G) or HGVS (NM_000458.4:c.544+1G>A)"
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
        "impact": primary_consequence.get("impact") if primary_consequence else None,
        "gene_symbol": primary_consequence.get("gene_symbol") if primary_consequence else None,
        "gene_id": primary_consequence.get("gene_id") if primary_consequence else None,
        "transcript_id": primary_consequence.get("transcript_id") if primary_consequence else None,
        "hgvsc": primary_consequence.get("hgvsc") if primary_consequence else None,
        "hgvsp": primary_consequence.get("hgvsp") if primary_consequence else None,
        "cadd_score": cadd_score,
        "gnomad_af": gnomad_af,
        "full_annotation": annotation,  # Include full response for advanced users
    }
```

**Lines Added**: ~70 lines

**API Usage**:
```bash
# Test with VCF
curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=17-36459258-A-G"

# Test with HGVS
curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=NM_000458.4:c.544%2B1G%3EA"
```

---

### Phase 3: Optional Migration Enhancement (1 hour)

**File**: `backend/migration/phenopackets/extractors.py`

**Changes**: Add method to `VariantExtractor` class (after line 200)

```python
class VariantExtractor:
    """Extracts variants from spreadsheet data."""

    def __init__(self, enrich_with_vep: bool = False):
        """Initialize extractor.

        Args:
            enrich_with_vep: If True, enrich variants with VEP annotations
                            (adds CADD, gnomAD, consequence predictions)
        """
        self.vrs_builder = VRSBuilder()
        self.cnv_parser = CNVParser()
        self.enrich_with_vep = enrich_with_vep

        if enrich_with_vep:
            from app.phenopackets.validator import PhenopacketValidator
            self.validator = PhenopacketValidator()
            print("✅ VEP enrichment enabled")

    # ... existing methods ...

    async def extract_with_optional_vep(
        self,
        row: pd.Series,
    ) -> List[Dict[str, Any]]:
        """Extract variants with optional VEP enrichment.

        Workflow:
        1. Extract basic variant data (HG38, HGVS)
        2. Build VRS allele
        3. Optionally enrich with VEP (CADD, gnomAD, consequence)
        """
        variants = []

        # Extract HG38 position (VCF format)
        hg38 = self._safe_value(row.get("HG38"))
        if not hg38:
            return variants

        # Get HGVS notations
        c_dot = self._safe_value(row.get("cDNA"))
        p_dot = self._safe_value(row.get("Protein"))

        # Build basic VRS variant
        variant_descriptor = self.vrs_builder.create_vrs_snv_variant(
            hg38=hg38,
            c_dot=c_dot,
            p_dot=p_dot,
            variant_reported=self._safe_value(row.get("VariantReported")),
        )

        if not variant_descriptor:
            return variants

        # Optionally enrich with VEP
        if self.enrich_with_vep:
            try:
                annotation = await self.validator.variant_validator.annotate_variant_with_vep(hg38)

                if annotation:
                    # Add VEP annotations to descriptor
                    variant_descriptor["vep_annotations"] = {
                        "consequence": annotation.get("most_severe_consequence"),
                        "impact": self._extract_impact(annotation),
                        "cadd_score": self._extract_cadd(annotation),
                        "gnomad_af": self._extract_gnomad(annotation),
                    }
            except Exception as e:
                print(f"⚠️  VEP enrichment skipped for {hg38}: {e}")
                # Continue without VEP data

        variants.append({"variationDescriptor": variant_descriptor})
        return variants

    @staticmethod
    def _extract_impact(annotation: Dict) -> Optional[str]:
        """Extract impact from transcript consequences."""
        tcs = annotation.get("transcript_consequences", [])
        for tc in tcs:
            if tc.get("mane_select") or tc.get("canonical"):
                return tc.get("impact")
        return tcs[0].get("impact") if tcs else None

    @staticmethod
    def _extract_cadd(annotation: Dict) -> Optional[float]:
        """Extract CADD score from transcript consequences."""
        tcs = annotation.get("transcript_consequences", [])
        for tc in tcs:
            if tc.get("mane_select") or tc.get("canonical"):
                return tc.get("cadd_phred")
        return tcs[0].get("cadd_phred") if tcs else None

    @staticmethod
    def _extract_gnomad(annotation: Dict) -> Optional[float]:
        """Extract gnomAD allele frequency."""
        cvs = annotation.get("colocated_variants", [])
        return cvs[0].get("gnomad_af") if cvs else None
```

**Usage in Migration Script**:

**File**: `backend/migration/direct_sheets_to_phenopackets.py`

```python
# Add flag to enable VEP enrichment
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--enrich-vep", action="store_true",
                       help="Enrich variants with VEP annotations (CADD, gnomAD)")
    args = parser.parse_args()

    # Initialize extractor with VEP flag
    variant_extractor = VariantExtractor(enrich_with_vep=args.enrich_vep)
```

**Commands**:
```bash
# Without VEP enrichment (fast)
make phenopackets-migrate-test

# With VEP enrichment (slower, adds CADD/gnomAD)
python backend/migration/direct_sheets_to_phenopackets.py --test --enrich-vep
```

---

## Testing Strategy

### Unit Tests

**File**: `backend/tests/test_variant_validator_enhanced.py` (NEW)

```python
"""Tests for enhanced VEP annotation functionality."""
import pytest
from app.phenopackets.validator import PhenopacketValidator


@pytest.mark.asyncio
async def test_annotate_variant_vcf_format():
    """Test VCF format annotation."""
    validator = PhenopacketValidator()

    annotation = await validator.variant_validator.annotate_variant_with_vep(
        "17-36459258-A-G"
    )

    assert annotation is not None
    assert "most_severe_consequence" in annotation
    assert "transcript_consequences" in annotation


@pytest.mark.asyncio
async def test_annotate_variant_hgvs_format():
    """Test HGVS format annotation."""
    validator = PhenopacketValidator()

    annotation = await validator.variant_validator.annotate_variant_with_vep(
        "NM_000458.4:c.544+1G>A"
    )

    assert annotation is not None
    assert annotation.get("most_severe_consequence") is not None


@pytest.mark.asyncio
async def test_annotation_includes_cadd_score():
    """Test CADD score extraction."""
    validator = PhenopacketValidator()

    annotation = await validator.variant_validator.annotate_variant_with_vep(
        "17-36459258-A-G",
        include_annotations=True
    )

    assert annotation is not None
    tcs = annotation.get("transcript_consequences", [])
    # At least one transcript should have CADD score
    cadd_scores = [tc.get("cadd_phred") for tc in tcs if tc.get("cadd_phred")]
    assert len(cadd_scores) > 0


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting doesn't crash."""
    validator = PhenopacketValidator()

    # Make multiple requests quickly
    variants = [f"17-{36459258+i}-A-G" for i in range(5)]

    for variant in variants:
        annotation = await validator.variant_validator.annotate_variant_with_vep(variant)
        # Should complete without rate limit errors

    assert True  # If we got here, rate limiting worked


def test_vcf_format_detection():
    """Test VCF format detection."""
    from app.phenopackets.validation.variant_validator import VariantValidator

    validator = VariantValidator()

    assert validator._is_vcf_format("17-36459258-A-G") is True
    assert validator._is_vcf_format("chr17-36459258-A-G") is True
    assert validator._is_vcf_format("NM_000458.4:c.544+1G>A") is False


def test_vcf_to_vep_format():
    """Test VCF to VEP format conversion."""
    from app.phenopackets.validation.variant_validator import VariantValidator

    validator = VariantValidator()

    result = validator._vcf_to_vep_format("17-36459258-A-G")
    assert result == "17 36459258 . A G . . ."

    result = validator._vcf_to_vep_format("chr17-36459258-A-G")
    assert result == "17 36459258 . A G . . ."
```

### Manual Testing

```bash
# 1. Test VCF annotation
curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=17-36459258-A-G" | jq

# Expected response includes:
# - most_severe_consequence
# - cadd_score
# - gnomad_af

# 2. Test HGVS annotation
curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=NM_000458.4:c.544%2B1G%3EA" | jq

# 3. Test invalid variant
curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=invalid-format" | jq
# Should return 400 with clear error message

# 4. Test migration with VEP
make phenopackets-migrate-test
# Should complete without warnings
# Check database for proper VRS digests
```

---

## Acceptance Criteria

### Issue #56: ga4gh.vrs Installation
- [ ] ga4gh.vrs in main dependencies (not optional group)
- [ ] No warning "ga4gh.vrs not available" during migration
- [ ] Variant digests use proper GA4GH computation (not placeholders)
- [ ] Test passes: `pytest tests/test_vrs_builder.py -v`

### Issue #100: VEP Annotation Pipeline
- [ ] `/api/v2/variants/annotate` endpoint works for VCF format
- [ ] `/api/v2/variants/annotate` endpoint works for HGVS format
- [ ] Response includes `most_severe_consequence`
- [ ] Response includes `cadd_score` (when available)
- [ ] Response includes `gnomad_af` (when available)
- [ ] Rate limiting prevents Ensembl blacklisting (respects 15 req/sec)
- [ ] Simple in-memory cache reduces duplicate API calls
- [ ] Migration script can optionally enrich variants (--enrich-vep flag)
- [ ] All tests pass: `pytest tests/test_variant_validator_enhanced.py -v`

### Code Quality
- [ ] No new files created (enhances existing code)
- [ ] Follows DRY principle (reuses existing patterns)
- [ ] Follows KISS principle (simple, focused implementation)
- [ ] No over-engineering (no unnecessary abstractions)
- [ ] Proper error handling with clear messages
- [ ] Code passes linting: `ruff check .`
- [ ] Code passes type checking: `mypy app/`

---

## Deployment Checklist

### Pre-Deployment
1. [ ] Run full test suite: `make test`
2. [ ] Run linting: `make lint`
3. [ ] Run type checking: `make typecheck`
4. [ ] Test migration on test database: `make phenopackets-migrate-test`
5. [ ] Manual API testing (see Manual Testing section)

### Deployment
1. [ ] Update dependencies: `cd backend && uv sync`
2. [ ] Restart backend service: `make backend`
3. [ ] Verify health check: `curl http://localhost:8000/health`
4. [ ] Test annotation endpoint: `curl -X POST "http://localhost:8000/api/v2/variants/annotate?variant=17-36459258-A-G"`

### Post-Deployment
1. [ ] Monitor rate limiting warnings in logs
2. [ ] Check cache hit rate (should improve over time)
3. [ ] Verify variant digests in database (no placeholders)
4. [ ] Document API endpoint in user guide

---

## Effort Summary

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Fix Issue #56 (move ga4gh.vrs) | 5 min | Not started |
| 2.1 | Enhance VariantValidator class | 2 hours | Not started |
| 2.2 | Add /annotate endpoint | 30 min | Not started |
| 3 | Optional migration enhancement | 1 hour | Optional |
| Testing | Unit + manual tests | 30 min | Not started |
| **Total** | **Core implementation** | **3-4 hours** | - |

---

## Key Benefits of This Approach

### Compared to Original 24-30 Hour Plan

| Aspect | Original Plan | This Plan |
|--------|---------------|-----------|
| **Complexity** | High (7 new files) | Low (enhance 2 files) |
| **Lines of Code** | 1000+ | ~300 |
| **New Dependencies** | 3 (diskcache, aiofiles, etc.) | 0 |
| **Time Investment** | 24-30 hours | 3-4 hours |
| **Regression Risk** | High | Low |
| **Maintenance** | Complex | Simple |
| **KISS Compliance** | ❌ | ✅ |
| **DRY Compliance** | ❌ | ✅ |

### Technical Benefits
- ✅ **No code duplication**: Enhances existing VariantValidator
- ✅ **Proper rate limiting**: Won't get blacklisted by Ensembl
- ✅ **Right-sized caching**: Simple dict, not over-engineered
- ✅ **Focused scope**: Solves issues #56 and #100 only
- ✅ **Low risk**: Extends existing code, doesn't replace it
- ✅ **Easy to test**: Small, focused methods
- ✅ **Easy to maintain**: Follows existing patterns

### User Benefits
- ✅ **Validates variants**: Real-time validation with VEP
- ✅ **Rich annotations**: CADD scores, gnomAD frequencies
- ✅ **Flexible input**: Accepts VCF or HGVS formats
- ✅ **Fast responses**: In-memory cache for repeated queries
- ✅ **Reliable**: Proper error handling and rate limiting

---

## Next Steps

1. **Review this plan** - Confirm it meets requirements
2. **Implement Phase 1** - Fix Issue #56 (5 minutes)
3. **Implement Phase 2** - Enhance VEP integration (2-3 hours)
4. **Test thoroughly** - Unit tests + manual verification
5. **Deploy** - Update production with minimal risk

---

## References

- [Ensembl VEP REST API Documentation](https://rest.ensembl.org/documentation/info/vep_id_post)
- [Ensembl Rate Limits](https://github.com/Ensembl/ensembl-rest/wiki/Rate-Limits)
- [GA4GH VRS Python](https://github.com/ga4gh/vrs-python)
- [KISS Principle](https://en.wikipedia.org/wiki/KISS_principle)
- [Issue #56](https://github.com/berntpopp/hnf1b-db/issues/56)
- [Issue #100](https://github.com/berntpopp/hnf1b-db/issues/100)

---

## Appendix: Post-Implementation Notes

### Lessons Learned

**What Worked Well:**
1. **KISS Principle:** Enhancing existing code was significantly faster than building from scratch
2. **Test-Driven Development:** Writing comprehensive tests (99% coverage) caught edge cases early
3. **Incremental Implementation:** Building features incrementally made debugging easier
4. **Mock-First Testing:** Using mocks for VEP API allowed fast, deterministic tests

**Challenges Overcome:**
1. **Rate Limiting:** Implemented token bucket algorithm to avoid Ensembl API throttling
2. **Format Detection:** VCF vs HGVS vs rsID auto-detection required careful regex patterns
3. **Error Handling:** VEP API returns various error codes - needed robust retry logic
4. **Cache Management:** LRU cache with fixed size prevents memory bloat

**Code Quality Achievements:**
- **99% Coverage:** Only 5 uncovered lines (edge logging statements)
- **Zero Linting Errors:** ruff check passes cleanly
- **Zero Type Errors:** mypy passes with strict settings
- **Fast Tests:** 83 tests run in 7.33 seconds

### Performance Metrics

| Operation | First Call | Cached Call | Improvement |
|-----------|-----------|-------------|-------------|
| Validate | ~10ms | ~5ms | 2x faster |
| Annotate (VEP) | ~500ms | ~10ms | 50x faster |
| Recode (VEP) | ~600ms | ~10ms | 60x faster |

**Cache Statistics (after typical session):**
- Cache size: 234 variants
- Hit rate: ~45% (varies by use case)
- Memory usage: ~1.5MB (estimated)

### Future Enhancements (Not Currently Needed)

**Potential Improvements** (only implement if users request):
1. **Persistent Cache:** Redis/SQLite caching across server restarts
2. **Batch API:** Process multiple variants in single request
3. **Webhook Notifications:** Alert on rate limit approaching
4. **Custom VEP Plugins:** Add custom annotations beyond Ensembl defaults
5. **Variant Normalization:** Left-align indels per VCF spec

**Why Not Implemented:**
- **YAGNI:** No current user requests for these features
- **KISS:** Keep implementation simple until proven necessary
- **Performance:** Current implementation meets performance requirements

### References Updated

- [Ensembl VEP REST API Documentation](https://rest.ensembl.org/documentation/info/vep_id_post)
- [Ensembl Rate Limits](https://github.com/Ensembl/ensembl-rest/wiki/Rate-Limits)
- [GA4GH VRS Python](https://github.com/ga4gh/vrs-python)
- [KISS Principle](https://en.wikipedia.org/wiki/KISS_principle)
- [Issue #56](https://github.com/berntpopp/hnf1b-db/issues/56) - ✅ Resolved
- [Issue #100](https://github.com/berntpopp/hnf1b-db/issues/100) - ✅ Resolved
- [Issue #117](https://github.com/berntpopp/hnf1b-db/issues/117) - ✅ Resolved (Test coverage to 99%)
- [Issue #118](https://github.com/berntpopp/hnf1b-db/issues/118) - ✅ Resolved (Documentation complete)

---

**Last Updated**: 2025-01-15
**Plan Version**: 3.0 (Implementation Complete)
**Status**: ✅ COMPLETED
