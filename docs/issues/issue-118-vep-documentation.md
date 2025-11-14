# Issue #118: docs: document VEP annotation API and user guide

## Overview

Create comprehensive documentation for the VEP (Variant Effect Predictor) annotation system, including API reference, user guide, and developer documentation. This ensures users and developers can effectively use and maintain the variant annotation functionality.

**Problem**: The VEP annotation system (#100) and UI component (#116) lack user-facing documentation, making it difficult for users to understand how to annotate variants, interpret results, or troubleshoot issues.

**Solution**: Create three-tier documentation covering API reference (technical details), user guide (how-to with examples), and developer guide (architecture and maintenance).

## Why This Matters

**Current State**:
```
# No documentation exists for:
- VEP annotation API endpoints ❌
- How to use the variant annotator UI ❌
- What CADD scores and gnomAD frequencies mean ❌
- Supported variant formats (VCF vs HGVS) ❌
- Rate limiting and error handling ❌

# Users have questions like:
"How do I annotate a variant?" ❓
"What does CADD score 28.5 mean?" ❓
"Why is my HGVS variant rejected?" ❓
"What's the difference between VCF and HGVS?" ❓
```

**Target State**:
```markdown
# docs/api/variant-annotation.md
## POST /api/v2/variants/annotate

Annotate a genetic variant using Ensembl VEP...

### Request Parameters
- `variant` (string, required): Variant in VCF or HGVS format
  - VCF: `chr:pos:ref:alt` (e.g., `17:41234470:T:A`)
  - HGVS: `transcript:change` (e.g., `ENST00000357654:c.123A>G`)

### Response Fields
- `cadd_phred` (float): CADD pathogenicity score (0-99, higher = more deleterious)
  - >20: Top 1% most deleterious variants
  - >30: Top 0.1% most deleterious variants
- `gnomad_af` (float): Population allele frequency (0-1)
  - <0.01: Rare variant
  - >0.05: Common variant

✅ Users can self-serve answers
```

**Benefits**:
1. **User self-service**: Reduces support requests
2. **Onboarding**: New users can learn quickly
3. **API adoption**: Clear examples encourage usage
4. **Maintenance**: Developers understand architecture
5. **Quality**: Documentation-driven development reveals gaps

## Required Changes

### 1. API Reference Documentation

**File**: `docs/api/variant-annotation.md` (NEW, ~250 lines)

**Structure**:

```markdown
# Variant Annotation API Reference

## Overview

The Variant Annotation API provides programmatic access to Ensembl VEP (Variant Effect Predictor) for annotating genetic variants with functional consequences, pathogenicity scores, and population frequencies.

**Base URL**: `/api/v2/variants`

**Authentication**: Required (JWT bearer token)

**Rate Limiting**: 15 requests/second (enforced client-side)

---

## Endpoints

### POST /api/v2/variants/annotate

Annotate a single genetic variant with VEP predictions.

**URL**: `POST /api/v2/variants/annotate`

**Authentication**: Required

**Content-Type**: `application/json`

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `variant` | string | Yes | Variant identifier in VCF or HGVS format |

**Supported Formats**:

1. **VCF Format** (Genomic Coordinates)
   - Pattern: `chr:pos:ref:alt` or `chr-pos-ref-alt`
   - Examples:
     - `17:41234470:T:A` (chromosome 17, position 41234470, T→A)
     - `X:123456:G:C` (X chromosome variant)
     - `chr1-12345-ATCG-A` (deletion, ATCG→A)

2. **HGVS Format** (Transcript-based)
   - Pattern: `transcript:c.change` or `transcript:p.change`
   - Examples:
     - `ENST00000357654:c.123A>G` (coding sequence change)
     - `NM_000546.5:c.215C>G` (RefSeq transcript)
     - `ENST00000269305:p.Arg248Trp` (protein change)

#### Request Example

**VCF Format**:
```bash
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variant": "17:41234470:T:A"
  }'
```

**HGVS Format**:
```bash
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variant": "ENST00000357654:c.123A>G"
  }'
```

#### Response Structure

**Success Response (200 OK)**:

```json
{
  "input": "17:41234470:T:A",
  "assembly_name": "GRCh38",
  "seq_region_name": "17",
  "start": 41234470,
  "end": 41234470,
  "allele_string": "T/A",
  "strand": 1,
  "most_severe_consequence": "missense_variant",
  "transcript_consequences": [
    {
      "transcript_id": "ENST00000357654",
      "gene_id": "ENSG00000141510",
      "gene_symbol": "TP53",
      "consequence_terms": ["missense_variant"],
      "impact": "MODERATE",
      "cadd_phred": 28.5,
      "cadd_raw": 4.123,
      "polyphen_prediction": "probably_damaging",
      "polyphen_score": 0.95,
      "sift_prediction": "deleterious",
      "sift_score": 0.01
    }
  ],
  "colocated_variants": [
    {
      "id": "rs121913343",
      "minor_allele": "A",
      "minor_allele_freq": 0.0001,
      "frequencies": {
        "gnomAD": {
          "gnomad_af": 0.00012,
          "gnomad_afr_af": 0.00005,
          "gnomad_eas_af": 0.0
        }
      }
    }
  ],
  "vep_version": "112",
  "cache_timestamp": "2025-01-14T10:30:00Z"
}
```

#### Response Fields

**Top-level Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `input` | string | Original variant identifier |
| `assembly_name` | string | Reference genome assembly (GRCh38) |
| `seq_region_name` | string | Chromosome/contig name |
| `start` | integer | Genomic start position (1-based) |
| `end` | integer | Genomic end position (1-based) |
| `allele_string` | string | Reference/alternate alleles |
| `strand` | integer | Genomic strand (1=forward, -1=reverse) |
| `most_severe_consequence` | string | Most severe predicted consequence |
| `transcript_consequences` | array | Per-transcript annotations (see below) |
| `colocated_variants` | array | Known variants at same position |
| `vep_version` | string | Ensembl VEP version used |
| `cache_timestamp` | string | When result was cached (ISO 8601) |

**Transcript Consequence Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `transcript_id` | string | Ensembl transcript ID (e.g., ENST00000357654) |
| `gene_id` | string | Ensembl gene ID (e.g., ENSG00000141510) |
| `gene_symbol` | string | HGNC gene symbol (e.g., TP53) |
| `consequence_terms` | array | List of consequence types (see [Consequence Glossary](#consequence-glossary)) |
| `impact` | string | Severity: `HIGH`, `MODERATE`, `LOW`, `MODIFIER` |
| `cadd_phred` | float | CADD Phred-scaled score (0-99, higher = more deleterious) |
| `cadd_raw` | float | CADD raw score |
| `polyphen_prediction` | string | PolyPhen-2 prediction: `benign`, `possibly_damaging`, `probably_damaging` |
| `polyphen_score` | float | PolyPhen-2 score (0-1, higher = more damaging) |
| `sift_prediction` | string | SIFT prediction: `tolerated`, `deleterious` |
| `sift_score` | float | SIFT score (0-1, lower = more damaging) |

**Population Frequency Fields** (in `colocated_variants.frequencies.gnomAD`):

| Field | Type | Description |
|-------|------|-------------|
| `gnomad_af` | float | Overall allele frequency in gnomAD (0-1) |
| `gnomad_afr_af` | float | African/African-American frequency |
| `gnomad_amr_af` | float | Latino/Admixed American frequency |
| `gnomad_eas_af` | float | East Asian frequency |
| `gnomad_nfe_af` | float | Non-Finnish European frequency |
| `gnomad_sas_af` | float | South Asian frequency |

#### Consequence Glossary

Common consequence terms (see [Ensembl documentation](https://www.ensembl.org/info/genome/variation/prediction/predicted_data.html) for full list):

| Term | Impact | Description |
|------|--------|-------------|
| `transcript_ablation` | HIGH | Deletion removes entire transcript |
| `splice_acceptor_variant` | HIGH | Variant in splice acceptor site (AG) |
| `splice_donor_variant` | HIGH | Variant in splice donor site (GT) |
| `stop_gained` | HIGH | Nonsense mutation (premature stop codon) |
| `frameshift_variant` | HIGH | Insertion/deletion causes frameshift |
| `stop_lost` | HIGH | Stop codon mutated to amino acid |
| `start_lost` | HIGH | Start codon (ATG) mutated |
| `missense_variant` | MODERATE | Amino acid substitution |
| `inframe_insertion` | MODERATE | Insertion preserving reading frame |
| `inframe_deletion` | MODERATE | Deletion preserving reading frame |
| `splice_region_variant` | LOW | Variant near splice site (±3bp) |
| `synonymous_variant` | LOW | Silent mutation (no amino acid change) |
| `5_prime_UTR_variant` | MODIFIER | Variant in 5' untranslated region |
| `3_prime_UTR_variant` | MODIFIER | Variant in 3' untranslated region |
| `intron_variant` | MODIFIER | Intronic variant (not near splice site) |

#### Error Responses

**400 Bad Request** - Invalid variant format:
```json
{
  "detail": "Invalid variant format. Use VCF (chr:pos:ref:alt) or HGVS (transcript:c.change)"
}
```

**401 Unauthorized** - Missing or invalid JWT token:
```json
{
  "detail": "Not authenticated"
}
```

**404 Not Found** - Variant not found in Ensembl database:
```json
{
  "detail": "Variant not found in Ensembl VEP database"
}
```

**429 Too Many Requests** - Rate limit exceeded:
```json
{
  "detail": "Rate limit exceeded. Maximum 15 requests/second."
}
```

**500 Internal Server Error** - VEP API error:
```json
{
  "detail": "VEP annotation failed: Ensembl API timeout"
}
```

**503 Service Unavailable** - Ensembl VEP service down:
```json
{
  "detail": "Ensembl VEP service temporarily unavailable"
}
```

---

## Interpreting Scores

### CADD Score (Combined Annotation Dependent Depletion)

**Range**: 0-99 (Phred-scaled)

**Interpretation**:
- **>10**: Top 10% most deleterious variants
- **>20**: Top 1% most deleterious variants (likely pathogenic)
- **>30**: Top 0.1% most deleterious variants (very likely pathogenic)

**Example**:
```
CADD = 28.5 → Top 0.3% most deleterious variants
Interpretation: Likely pathogenic
```

**Reference**: [CADD v1.6 documentation](https://cadd.gs.washington.edu/)

### gnomAD Allele Frequency

**Range**: 0-1 (0% to 100%)

**Interpretation**:
- **<0.0001 (0.01%)**: Very rare, possibly pathogenic if HIGH impact
- **<0.01 (1%)**: Rare, consider pathogenicity assessment
- **>0.05 (5%)**: Common, likely benign polymorphism

**ACMG Guidelines** (Richards et al., 2015):
- **BS1 (Benign Strong)**: AF >0.05 in any population
- **PM2 (Pathogenic Moderate)**: Absent or very rare (AF <0.0001)

**Example**:
```
gnomad_af = 0.00012 (0.012%)
Interpretation: Very rare, supports pathogenicity if HIGH impact
```

### PolyPhen-2 Score

**Range**: 0-1

**Predictions**:
- **0.0-0.446**: Benign
- **0.447-0.908**: Possibly damaging
- **0.909-1.0**: Probably damaging

### SIFT Score

**Range**: 0-1

**Predictions**:
- **0.0-0.05**: Deleterious (damaging)
- **>0.05**: Tolerated (benign)

**Note**: Lower SIFT scores = more damaging (opposite of PolyPhen)

---

## Rate Limiting

**Limit**: 15 requests/second (client-side enforcement)

**Implementation**:
- Uses token bucket algorithm
- Requests queued if limit exceeded
- No 429 errors from client rate limiter

**Server-side limits** (Ensembl VEP):
- 15 requests/second per IP
- 55,000 requests/hour per IP

**Best Practices**:
- Batch variants when possible
- Cache results (24-hour TTL)
- Use VCF format for faster lookups

---

## Caching

**Backend Cache** (Redis):
- **TTL**: 24 hours
- **Key format**: `vep:v2:{variant_normalized}`
- **Invalidation**: Automatic expiration

**Frontend Cache** (Browser):
- Results stored in component state
- Cleared on page refresh

**Cache Hit Rate**: Check `cache_timestamp` field:
- Present → Cache hit
- Null → Fresh VEP API call

---

## Examples

### Example 1: Annotate Missense Variant

**Variant**: TP53 p.Arg248Trp (common cancer mutation)

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17:7674220:C:T"}'
```

**Response**:
```json
{
  "most_severe_consequence": "missense_variant",
  "transcript_consequences": [{
    "gene_symbol": "TP53",
    "impact": "MODERATE",
    "cadd_phred": 29.7,
    "polyphen_prediction": "probably_damaging",
    "sift_prediction": "deleterious"
  }],
  "colocated_variants": [{
    "id": "rs121913343",
    "frequencies": {"gnomAD": {"gnomad_af": 0.000008}}
  }]
}
```

**Interpretation**:
- High CADD score (29.7) → Top 0.1% deleterious
- Very rare (AF = 0.0008%) → PM2 (ACMG)
- PolyPhen/SIFT agree → Probably damaging
- **Conclusion**: Likely pathogenic

### Example 2: Annotate Synonymous Variant

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "ENST00000357654:c.123A>G"}'
```

**Response**:
```json
{
  "most_severe_consequence": "synonymous_variant",
  "transcript_consequences": [{
    "impact": "LOW",
    "cadd_phred": 8.2
  }]
}
```

**Interpretation**:
- Synonymous (silent mutation) → No amino acid change
- Low CADD score → Likely benign
- **Conclusion**: Benign

---

## Related Documentation

- **User Guide**: [docs/user-guide/variant-annotation.md](../user-guide/variant-annotation.md)
- **Developer Guide**: [docs/variant-annotation-implementation-plan.md](../variant-annotation-implementation-plan.md)
- **API Overview**: [docs/api/README.md](README.md)
```

### 2. User Guide Documentation

**File**: `docs/user-guide/variant-annotation.md` (NEW, ~200 lines)

**Structure**:

```markdown
# Variant Annotation User Guide

## Overview

The Variant Annotator allows you to predict the functional impact of genetic variants using Ensembl VEP (Variant Effect Predictor). This guide explains how to use the tool and interpret results.

---

## Accessing the Variant Annotator

### Via Web Interface

1. **Navigate** to the Variant Annotator:
   - Main menu → "Tools" → "Variant Annotator"
   - Direct URL: `http://localhost:5173/variant-annotator`

2. **Enter variant**: Type or paste a variant identifier

3. **Click "Annotate"**: Results appear within 2-5 seconds

### Via API

See [API Reference](../api/variant-annotation.md) for programmatic access.

---

## Entering Variants

### Supported Formats

#### 1. VCF Format (Genomic Coordinates)

**Pattern**: `chromosome:position:reference:alternate`

**Examples**:
```
17:41234470:T:A          ✅ Valid (chromosome 17)
chr17:41234470:T:A       ✅ Valid (with "chr" prefix)
X:123456:G:C             ✅ Valid (X chromosome)
17-41234470-T-A          ✅ Valid (dash separator)

17:41234470              ❌ Invalid (missing ref/alt)
invalid-format           ❌ Invalid (unrecognized)
```

**When to Use VCF**:
- You have genomic coordinates from sequencing
- You want to check a specific position
- Fastest format for annotation

#### 2. HGVS Format (Transcript-based)

**Pattern**: `transcript:c.change` or `transcript:p.change`

**Examples**:
```
ENST00000357654:c.123A>G           ✅ Valid (Ensembl transcript, coding)
NM_000546.5:c.215C>G               ✅ Valid (RefSeq transcript)
ENST00000269305:p.Arg248Trp        ✅ Valid (protein change)

c.123A>G                           ❌ Invalid (missing transcript)
ENST00000357654                    ❌ Invalid (missing change)
```

**When to Use HGVS**:
- You have a transcript-specific variant
- You're validating literature variants
- You need protein-level changes

### Format Auto-detection

The tool automatically detects the format:
```
Input: 17:41234470:T:A
Detected: VCF format ✅

Input: ENST00000357654:c.123A>G
Detected: HGVS format ✅

Input: not-a-variant
Detected: Invalid format ❌
```

---

## Understanding Results

### Results Panel

After annotation, you'll see:

```
┌─────────────────────────────────────────────────────┐
│ Variant Annotation Results                          │
├─────────────────────────────────────────────────────┤
│ Input Variant: 17:41234470:T:A                     │
│ Assembly: GRCh38                                    │
│                                                     │
│ Most Severe Consequence: missense_variant           │
│ Impact: MODERATE                                    │
│                                                     │
│ Pathogenicity Scores:                               │
│   CADD: 28.5 (Top 0.3% most deleterious)           │
│   PolyPhen: 0.95 (Probably damaging)                │
│   SIFT: 0.01 (Deleterious)                          │
│                                                     │
│ Population Frequency:                               │
│   gnomAD: 0.00012 (0.012% - Very rare)             │
│                                                     │
│ Affected Gene: TP53                                 │
│ Transcript: ENST00000357654                         │
│                                                     │
│ dbSNP: rs121913343                                  │
└─────────────────────────────────────────────────────┘
```

### Key Fields Explained

#### Consequence

**What it is**: The predicted effect on the gene/protein

**Common values**:
- `missense_variant` → Changes amino acid (MODERATE impact)
- `synonymous_variant` → Silent mutation (LOW impact)
- `stop_gained` → Premature stop codon (HIGH impact)
- `frameshift_variant` → Reading frame shift (HIGH impact)
- `splice_donor_variant` → Affects splicing (HIGH impact)

**Color coding**:
- 🔴 RED (HIGH): Likely loss of function
- 🟡 YELLOW (MODERATE): May affect function
- 🟢 GREEN (LOW): Unlikely to affect function
- ⚪ GRAY (MODIFIER): Non-coding, unknown impact

#### Impact

**Severity levels**:
- **HIGH**: Likely loss of function (stop gain, frameshift, splice site)
- **MODERATE**: May affect function (missense, in-frame indel)
- **LOW**: Unlikely to affect function (synonymous, splice region)
- **MODIFIER**: Unknown impact (UTR, intron, intergenic)

#### CADD Score

**What it is**: Measures how "deleterious" a variant is

**Range**: 0-99 (higher = more damaging)

**Interpretation**:
```
CADD Score    Percentile         Interpretation
───────────────────────────────────────────────
0-10          Common             Likely benign
10-20         Top 10%            Possibly pathogenic
20-30         Top 1%             Likely pathogenic
>30           Top 0.1%           Very likely pathogenic
```

**Example**:
```
CADD = 28.5
→ Top 0.3% most deleterious variants
→ Strong evidence for pathogenicity
```

#### gnomAD Frequency

**What it is**: How common the variant is in the general population

**Range**: 0-1 (0% to 100%)

**ACMG Rules**:
```
Frequency     ACMG Code    Interpretation
─────────────────────────────────────────────
>5%           BS1          Benign (too common)
1-5%          -            Likely benign
0.01-1%       -            Uncertain significance
<0.01%        PM2          Supports pathogenicity (rare)
Absent        PM2          Supports pathogenicity
```

**Example**:
```
gnomad_af = 0.00012 (0.012%)
→ Very rare variant
→ PM2 (Pathogenic Moderate) if HIGH impact
```

#### PolyPhen-2 & SIFT

**PolyPhen-2** (predicts damaging effect):
- 0.0-0.446 → Benign
- 0.447-0.908 → Possibly damaging
- 0.909-1.0 → Probably damaging

**SIFT** (predicts tolerance):
- 0.0-0.05 → Deleterious ⚠️
- >0.05 → Tolerated ✅

**Note**: SIFT is inverted (lower = worse)

---

## Example Workflows

### Workflow 1: Clinical Variant Assessment

**Scenario**: Patient has sequencing result showing variant `17:7674220:C:T`

**Steps**:
1. Enter variant in VCF format: `17:7674220:C:T`
2. Click "Annotate"
3. Review results:
   - Consequence: `missense_variant` (amino acid change)
   - CADD: 29.7 (top 0.1% deleterious)
   - gnomAD AF: 0.000008 (very rare)
   - PolyPhen: Probably damaging
   - SIFT: Deleterious
4. **Interpretation**: Likely pathogenic (matches ACMG criteria)
5. Export results (JSON/CSV) for clinical report

### Workflow 2: Literature Variant Validation

**Scenario**: Paper reports TP53 p.Arg248Trp mutation

**Steps**:
1. Convert to HGVS: `ENST00000269305:p.Arg248Trp`
2. Enter in Variant Annotator
3. Compare results with paper:
   - Paper: "Pathogenic, CADD = 29.7"
   - Tool: CADD = 29.7 ✅ Match
4. Check population frequency:
   - gnomAD AF = 0.000008 (very rare) ✅
5. **Conclusion**: Literature report validated

### Workflow 3: Batch Annotation

**Scenario**: Annotate 50 variants from VCF file

**Option A - Web Interface**:
1. Use variant annotator, one at a time
2. Export each result to CSV
3. Combine CSV files

**Option B - API Script** (Recommended):
```bash
# variants.txt contains one variant per line
while read variant; do
  curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"variant\": \"$variant\"}" \
    >> results.json
  sleep 0.07  # Respect 15 req/sec rate limit
done < variants.txt
```

---

## Troubleshooting

### Error: "Invalid variant format"

**Cause**: Variant doesn't match VCF or HGVS pattern

**Solution**:
- ✅ VCF: `17:41234470:T:A` (chr:pos:ref:alt)
- ✅ HGVS: `ENST00000357654:c.123A>G`
- ❌ Wrong: `17:41234470` (missing ref/alt)

### Error: "Variant not found"

**Cause**: Variant doesn't exist in Ensembl database

**Solution**:
- Check chromosome name (use "17" not "chr17" for HGVS)
- Verify position against genome build (GRCh38)
- Ensure transcript ID is valid (ENST... or NM_...)

### Error: "Rate limit exceeded"

**Cause**: Too many requests (>15/second)

**Solution**:
- Wait 1 second before next request
- Use API batch endpoint (future feature)
- Check if backend rate limiter is working

### Annotation is slow (>10 seconds)

**Possible causes**:
1. **Ensembl VEP API latency**: Check [Ensembl status](https://www.ensembl.org/)
2. **Network issues**: Test with `curl https://rest.ensembl.org/`
3. **Cache disabled**: Ensure Redis is running

**Solution**:
- Wait and retry
- Use cached results (re-submit same variant)
- Contact administrator if persistent

---

## Best Practices

### 1. Use VCF format when possible
- Faster than HGVS (direct coordinate lookup)
- Avoids transcript version issues

### 2. Cache results
- Results are cached for 24 hours
- Re-submitting same variant is instant

### 3. Interpret scores holistically
- Don't rely on single score (CADD alone)
- Check consequence type + frequency + multiple predictors
- Follow ACMG guidelines for clinical interpretation

### 4. Verify against ClinVar
- Check [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) for known pathogenic variants
- VEP scores support clinical classification, not replace it

### 5. Document your interpretation
- Export results (JSON/CSV)
- Include VEP version, date, and assembly
- Note which scores/criteria used for classification

---

## Related Resources

- **API Documentation**: [docs/api/variant-annotation.md](../api/variant-annotation.md)
- **ACMG Guidelines**: Richards et al. (2015), *Genetics in Medicine*
- **CADD Scores**: https://cadd.gs.washington.edu/
- **gnomAD Database**: https://gnomad.broadinstitute.org/
- **Ensembl VEP**: https://www.ensembl.org/info/docs/tools/vep/
```

### 3. Developer Guide Updates

**File**: `docs/variant-annotation-implementation-plan.md` (UPDATE existing file)

**Add new section** (at end of file):

```markdown
---

## Documentation

### API Reference

See [docs/api/variant-annotation.md](api/variant-annotation.md) for:
- Endpoint specifications
- Request/response formats
- Error codes
- Rate limiting details
- Scoring interpretation

### User Guide

See [docs/user-guide/variant-annotation.md](user-guide/variant-annotation.md) for:
- Web interface usage
- Variant format examples
- Results interpretation
- Troubleshooting
- Best practices

### Architecture Overview

**Components**:
1. **Frontend** (`frontend/src/components/VariantAnnotator.vue`)
   - User input validation
   - Format auto-detection
   - Results visualization
   - Error handling

2. **Backend API** (`backend/app/api/variant_validator.py`)
   - Ensembl VEP integration
   - Rate limiting (15 req/sec)
   - Redis caching (24h TTL)
   - Response normalization

3. **External Service** (Ensembl REST API)
   - VEP annotation engine
   - GRCh38 reference genome
   - Consequence predictions
   - Population frequencies

**Data Flow**:
```
User Input (VCF/HGVS)
    ↓
Frontend Validation
    ↓
POST /api/v2/variants/annotate
    ↓
Rate Limiter (15 req/sec)
    ↓
Cache Check (Redis)
    ↓ (miss)
Ensembl VEP API
    ↓
Cache Store (24h TTL)
    ↓
Response Normalization
    ↓
Frontend Display
```

### Testing

See [docs/issues/issue-117-vep-annotation-tests.md](issues/issue-117-vep-annotation-tests.md) for:
- Unit test coverage
- Integration tests
- Error handling tests
- Performance benchmarks

### Deployment Considerations

**Prerequisites**:
- Redis server (for caching)
- Internet access (Ensembl API)
- JWT authentication enabled

**Environment Variables**:
```bash
# backend/.env
REDIS_URL=redis://localhost:6379/0
VEP_CACHE_TTL=86400  # 24 hours
VEP_RATE_LIMIT=15    # requests/second
```

**Monitoring**:
- Track VEP API latency
- Monitor cache hit rate
- Alert on 429 rate limit errors

**Scaling**:
- Rate limiter is client-side (per-instance)
- For high traffic, implement server-side rate limiter
- Consider VEP API caching proxy
```

### 4. README Updates

**File**: `README.md` (UPDATE existing file)

**Add to "Features" section**:

```markdown
### Variant Annotation
- Ensembl VEP integration for functional variant prediction
- Support for VCF and HGVS formats
- CADD scores, PolyPhen-2, SIFT, gnomAD frequencies
- Real-time annotation with 24-hour caching
- See [Variant Annotation User Guide](docs/user-guide/variant-annotation.md)
```

**Add to "Documentation" section**:

```markdown
## Documentation

- **User Guides**:
  - [Variant Annotation Guide](docs/user-guide/variant-annotation.md)
- **API Reference**:
  - [Variant Annotation API](docs/api/variant-annotation.md)
- **Developer Guides**:
  - [Variant Annotation Implementation](docs/variant-annotation-implementation-plan.md)
```

### 5. OpenAPI/Swagger Documentation

**File**: `backend/app/api/variants.py` (UPDATE existing file)

**Add Pydantic models with docstrings**:

```python
from pydantic import BaseModel, Field

class VariantAnnotationRequest(BaseModel):
    """Request model for variant annotation endpoint."""

    variant: str = Field(
        ...,
        description="Variant identifier in VCF (chr:pos:ref:alt) or HGVS (transcript:c.change) format",
        examples=[
            "17:41234470:T:A",
            "ENST00000357654:c.123A>G"
        ]
    )

class TranscriptConsequence(BaseModel):
    """Transcript-level consequence annotation."""

    transcript_id: str = Field(..., description="Ensembl transcript ID")
    gene_symbol: str = Field(..., description="HGNC gene symbol")
    consequence_terms: list[str] = Field(..., description="List of consequence types")
    impact: str = Field(..., description="Severity: HIGH, MODERATE, LOW, MODIFIER")
    cadd_phred: float | None = Field(None, description="CADD Phred-scaled score (0-99)")
    polyphen_prediction: str | None = Field(None, description="PolyPhen-2 prediction")
    sift_prediction: str | None = Field(None, description="SIFT prediction")

class VariantAnnotationResponse(BaseModel):
    """Response model for variant annotation endpoint."""

    input: str = Field(..., description="Original variant identifier")
    assembly_name: str = Field(..., description="Reference genome assembly")
    most_severe_consequence: str = Field(..., description="Most severe predicted consequence")
    transcript_consequences: list[TranscriptConsequence] = Field(..., description="Per-transcript annotations")
    vep_version: str = Field(..., description="Ensembl VEP version used")

    class Config:
        json_schema_extra = {
            "example": {
                "input": "17:41234470:T:A",
                "assembly_name": "GRCh38",
                "most_severe_consequence": "missense_variant",
                "transcript_consequences": [{
                    "transcript_id": "ENST00000357654",
                    "gene_symbol": "TP53",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "cadd_phred": 28.5,
                    "polyphen_prediction": "probably_damaging",
                    "sift_prediction": "deleterious"
                }],
                "vep_version": "112"
            }
        }

@router.post(
    "/annotate",
    response_model=VariantAnnotationResponse,
    summary="Annotate a genetic variant",
    description="Annotate a variant using Ensembl VEP to predict functional consequences, pathogenicity scores, and population frequencies.",
    responses={
        200: {"description": "Successful annotation"},
        400: {"description": "Invalid variant format"},
        401: {"description": "Authentication required"},
        404: {"description": "Variant not found in Ensembl database"},
        429: {"description": "Rate limit exceeded (max 15 req/sec)"},
        500: {"description": "VEP API error"},
    },
    tags=["Variant Annotation"]
)
async def annotate_variant(
    request: VariantAnnotationRequest,
    current_user: User = Depends(get_current_user)
) -> VariantAnnotationResponse:
    """
    Annotate a genetic variant with functional predictions.

    Supports two input formats:
    - **VCF**: `chr:pos:ref:alt` (e.g., `17:41234470:T:A`)
    - **HGVS**: `transcript:c.change` (e.g., `ENST00000357654:c.123A>G`)

    Returns consequence predictions, pathogenicity scores (CADD, PolyPhen, SIFT),
    and population frequencies (gnomAD).

    Rate limited to 15 requests/second (client-side).
    Results cached for 24 hours (Redis).
    """
    # Implementation...
```

**Generate Swagger docs**:

FastAPI automatically generates OpenAPI docs at:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## Implementation Checklist

### Phase 1: API Reference Documentation (30 minutes)
- [ ] Create `docs/api/variant-annotation.md`
- [ ] Write endpoint specifications (URL, auth, parameters)
- [ ] Document request/response formats with examples
- [ ] Add consequence glossary table
- [ ] Document scoring interpretation (CADD, gnomAD, PolyPhen, SIFT)
- [ ] Add error response examples
- [ ] Document rate limiting and caching

### Phase 2: User Guide Documentation (30 minutes)
- [ ] Create `docs/user-guide/variant-annotation.md`
- [ ] Write "Getting Started" section with screenshots
- [ ] Document variant format examples (VCF vs HGVS)
- [ ] Explain results panel and key fields
- [ ] Add example workflows (clinical assessment, literature validation)
- [ ] Create troubleshooting section
- [ ] Document best practices

### Phase 3: Developer Guide Updates (15 minutes)
- [ ] Update `docs/variant-annotation-implementation-plan.md`
- [ ] Add architecture overview diagram
- [ ] Document data flow
- [ ] Add testing references
- [ ] Document deployment considerations
- [ ] Add environment variable documentation

### Phase 4: README & Navigation (10 minutes)
- [ ] Update `README.md` with variant annotation features
- [ ] Add documentation links to README
- [ ] Create `docs/api/README.md` (API index)
- [ ] Create `docs/user-guide/README.md` (user guide index)
- [ ] Verify all cross-links work

### Phase 5: OpenAPI/Swagger Documentation (15 minutes)
- [ ] Update `backend/app/api/variants.py` with Pydantic docstrings
- [ ] Add request/response model examples
- [ ] Add endpoint descriptions and tags
- [ ] Test Swagger UI at http://localhost:8000/docs
- [ ] Verify all fields documented

### Phase 6: Review & Polish (10 minutes)
- [ ] Proofread all documentation
- [ ] Test all code examples (curl commands)
- [ ] Verify screenshot references exist
- [ ] Check for broken links
- [ ] Get feedback from team member

## Testing Verification

### Manual Test Steps

**1. Verify API Documentation Accuracy**:

```bash
# Test curl example from docs/api/variant-annotation.md
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17:41234470:T:A"}'

# Verify response matches documented structure
```

**Expected**: Response matches documented JSON structure

**2. Test Swagger UI**:

```bash
# Start backend
cd backend
make backend

# Open Swagger UI
open http://localhost:8000/docs

# Find "Variant Annotation" section
# Click "Try it out" for POST /api/v2/variants/annotate
# Enter: {"variant": "17:41234470:T:A"}
# Click "Execute"
```

**Expected**: Swagger UI shows documented request/response models

**3. Verify User Guide Examples**:

Follow each workflow in `docs/user-guide/variant-annotation.md`:
- Workflow 1: Clinical variant assessment
- Workflow 2: Literature validation
- Workflow 3: Batch annotation script

**Expected**: All examples work as documented

**4. Check Documentation Links**:

```bash
# Check for broken markdown links
cd docs
grep -r "\[.*\](.*\.md)" . | while read line; do
  file=$(echo "$line" | cut -d: -f1)
  link=$(echo "$line" | sed 's/.*(\(.*\.md\)).*/\1/')
  if [ ! -f "$(dirname $file)/$link" ]; then
    echo "Broken link in $file: $link"
  fi
done
```

**Expected**: No broken links

**5. Verify README Updates**:

```bash
# Check README has variant annotation section
grep -A 5 "Variant Annotation" README.md
```

**Expected**: README contains variant annotation features and doc links

## Acceptance Criteria

- [ ] **API Documentation**: Complete reference in `docs/api/variant-annotation.md`
  - All endpoints documented
  - Request/response examples included
  - Error codes documented
  - Scoring interpretation explained

- [ ] **User Guide**: Practical guide in `docs/user-guide/variant-annotation.md`
  - Format examples (VCF, HGVS)
  - Results interpretation
  - Example workflows
  - Troubleshooting section

- [ ] **Developer Guide**: Architecture documented in `variant-annotation-implementation-plan.md`
  - Data flow diagram
  - Testing references
  - Deployment notes

- [ ] **OpenAPI/Swagger**: Auto-generated docs at `/docs`
  - Pydantic models with docstrings
  - Endpoint descriptions
  - Example requests/responses

- [ ] **README Updated**: Links to all documentation added

- [ ] **Accuracy Verified**: All curl examples tested and work

- [ ] **Links Verified**: No broken cross-references

## Files Modified/Created

### New Files (3 files, ~600 lines total)
1. `docs/api/variant-annotation.md` (~250 lines)
   - Endpoint specifications
   - Request/response formats
   - Scoring interpretation
   - Examples and error codes

2. `docs/user-guide/variant-annotation.md` (~200 lines)
   - Getting started guide
   - Format examples
   - Results interpretation
   - Workflows and troubleshooting

3. `docs/api/README.md` (~30 lines)
   - API documentation index
   - Links to all API docs

4. `docs/user-guide/README.md` (~30 lines)
   - User guide index
   - Links to all guides

### Modified Files (3 files)
5. `docs/variant-annotation-implementation-plan.md` (~90 lines added)
   - Documentation section
   - Architecture overview
   - Testing references
   - Deployment notes

6. `README.md` (~20 lines modified)
   - Variant annotation features
   - Documentation links

7. `backend/app/api/variants.py` (~50 lines modified)
   - Pydantic model docstrings
   - Endpoint descriptions
   - OpenAPI examples

## Dependencies

**Blocks**:
- None (documentation is independent)

**Blocked By**:
- ✅ #100 - VEP annotation API implementation (COMPLETED)
- ⏳ #116 - Frontend UI component (IN PROGRESS)
  - User guide can be written without UI, but screenshots need UI
  - Can document API and developer guide immediately

**Related**:
- #117 - VEP annotation tests (documentation references test coverage)
- See `docs/variant-annotation-implementation-plan.md` for implementation details

## Performance Impact

**Before** (No Documentation):
- User onboarding: ~2 hours (trial and error)
- Support requests: ~5/week (format questions, score interpretation)
- API adoption: Low (unclear how to use)

**After** (Complete Documentation):
- User onboarding: ~15 minutes (read user guide)
- Support requests: ~1/week (edge cases only)
- API adoption: High (clear examples, Swagger UI)
- Developer maintenance: Faster (architecture documented)

**Cost**: ~0 (documentation is static content)

## Timeline

**Estimated Effort**: 1-1.5 hours

**Breakdown**:
- Phase 1 (API reference): 30 minutes
- Phase 2 (User guide): 30 minutes
- Phase 3 (Developer guide): 15 minutes
- Phase 4 (README & navigation): 10 minutes
- Phase 5 (OpenAPI/Swagger): 15 minutes
- Phase 6 (Review & polish): 10 minutes

**Total**: ~1.5 hours

**Can be parallelized with**:
- #116 (Frontend UI) - Add screenshots when UI is ready
- #117 (Tests) - Reference test coverage when tests are complete

## Priority & Labels

**Priority**: **P2 (Medium)** - Important for usability but not blocking

**Rationale**:
- VEP API works without documentation (#100 complete)
- Frontend UI can be used without written guide (#116)
- Tests validate functionality (#117)
- **BUT**: Documentation is essential for:
  - User adoption (self-service onboarding)
  - API discoverability (Swagger UI)
  - Maintenance (architecture understanding)
  - Support reduction (troubleshooting guide)

**Labels**:
- `docs` - Documentation task
- `user-experience` - Improves usability
- `api` - API documentation
- `p2-medium` - Medium priority
- `good-first-issue` - Can be done by someone learning the codebase
