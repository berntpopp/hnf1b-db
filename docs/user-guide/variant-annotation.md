# Variant Annotation User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Basic Workflows](#basic-workflows)
4. [Use Cases](#use-cases)
5. [Understanding Results](#understanding-results)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [FAQ](#faq)

---

## Introduction

### What is Variant Annotation?

Variant annotation is the process of adding biological context to genetic variants (changes in DNA sequences). The HNF1B Database uses the [Ensembl Variant Effect Predictor (VEP)](https://www.ensembl.org/vep) to provide:

- **Consequence predictions:** How does this variant affect genes/proteins?
- **Clinical significance:** Is this variant known to be disease-causing?
- **Population frequencies:** How common is this variant?
- **Functional predictions:** What is the predicted impact?

### Who Should Use This Guide?

This guide is designed for:
- **Researchers:** Analyzing HNF1B variants in patient data
- **Clinicians:** Interpreting genetic test results
- **Bioinformaticians:** Integrating variant data into pipelines
- **Data curators:** Adding variants to phenopackets

### What You'll Learn

- How to validate and annotate variants
- Understanding variant notation formats
- Interpreting VEP annotation results
- Converting between notation formats
- Troubleshooting common issues

---

## Getting Started

### Prerequisites

**1. Access to HNF1B Database**
- API endpoint URL (e.g., `http://localhost:8000/api/v2`)
- User account with authentication

**2. Authentication Token**
```bash
# Login to get JWT token
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}'

# Save token for later use
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**3. Understanding Variant Formats**

The API accepts three notation formats:

| Format | Example | When to Use |
|--------|---------|-------------|
| **HGVS** | `NM_000458.4:c.544+1G>A` | Lab reports, publications |
| **VCF** | `17-36459258-A-G` | Sequencing data, pipelines |
| **rsID** | `rs56116432` | Literature references |

---

## Basic Workflows

### Workflow 1: Validate a Variant

**Use Case:** You have a variant from a genetic test report and want to verify it's correctly formatted.

**Step-by-Step:**

```bash
# 1. Validate the variant notation
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'
```

**Expected Response (Valid):**
```json
{
  "valid": true,
  "variant": "NM_000458.4:c.544+1G>A",
  "format": "hgvs",
  "message": "Valid variant notation"
}
```

**Response if Invalid:**
```json
{
  "valid": false,
  "variant": "NM_000458.4c.544+1G>A",
  "format": "unknown",
  "message": "Invalid HGVS notation",
  "suggestions": [
    "Missing ':' after transcript ID",
    "Did you mean: NM_000458.4:c.544+1G>A?"
  ]
}
```

**What to Do Next:**
- ✅ If valid → Proceed to annotation
- ❌ If invalid → Use suggestions to fix, then re-validate

---

### Workflow 2: Annotate a Variant

**Use Case:** You have a validated variant and need detailed biological information.

**Step-by-Step:**

```bash
# 1. Request annotation
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'
```

**Expected Response (Abbreviated):**
```json
{
  "input": "NM_000458.4:c.544+1G>A",
  "annotation": {
    "id": "rs56116432",
    "most_severe_consequence": "splice_donor_variant",
    "transcript_consequences": [
      {
        "gene_symbol": "HNF1B",
        "consequence_terms": ["splice_donor_variant"],
        "impact": "HIGH",
        "hgvsc": "ENST00000366667.8:c.544+1G>A",
        "cadd_phred": 34.0
      }
    ],
    "colocated_variants": [
      {
        "id": "rs56116432",
        "gnomad_af": 0.0001
      }
    ]
  }
}
```

**Key Information Extracted:**
- **Variant ID:** `rs56116432` (for literature searches)
- **Gene:** `HNF1B` (confirms correct gene)
- **Consequence:** `splice_donor_variant` (affects RNA splicing)
- **Impact:** `HIGH` (likely pathogenic)
- **CADD Score:** `34.0` (deleteriousness prediction)
- **Frequency:** `0.0001` (0.01% in gnomAD - very rare)

---

### Workflow 3: Convert Variant Formats

**Use Case:** You have an rsID from a paper and need HGVS notation for clinical reporting.

**Step-by-Step:**

```bash
# 1. Recode from rsID to all formats
curl -X POST http://localhost:8000/api/v2/variants/recode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "rs56116432"}'
```

**Expected Response:**
```json
{
  "input": "rs56116432",
  "recoding": {
    "id": ["rs56116432"],
    "hgvsg": ["NC_000017.11:g.36459258A>G"],
    "hgvsc": [
      "ENST00000366667.8:c.544+1G>A",
      "NM_000458.4:c.544+1G>A"
    ],
    "hgvsp": [],
    "vcf_string": "17:36459258-36459258:A:G"
  }
}
```

**How to Use Each Format:**
- **HGVS genomic** (`NC_000017.11:g.36459258A>G`): Reference genome coordinate
- **HGVS coding** (`NM_000458.4:c.544+1G>A`): Clinical reports, publications
- **VCF** (`17:36459258-36459258:A:G`): Bioinformatics pipelines

---

## Use Cases

### Use Case 1: Clinical Interpretation

**Scenario:** A patient's genetic test reports `NM_000458.4:c.544+1G>A`. Is this variant clinically significant?

**Steps:**

1. **Validate the variant:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/validate \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"variant": "NM_000458.4:c.544+1G>A"}'
   ```
   ✅ Result: Valid HGVS notation

2. **Annotate for clinical details:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/annotate \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"variant": "NM_000458.4:c.544+1G>A"}'
   ```

3. **Extract clinical information:**
   - **Consequence:** `splice_donor_variant` → Disrupts RNA splicing
   - **Impact:** `HIGH` → Loss of gene function likely
   - **CADD Score:** `34.0` → Highly deleterious (>30 = pathogenic)
   - **Frequency:** `0.0001` (gnomAD) → Extremely rare
   - **ClinVar:** Check `clin_sig` field for known pathogenicity

4. **Clinical Interpretation:**
   - ✅ **HIGH impact** + **splice site** + **rare** → Likely pathogenic
   - ✅ Consistent with HNF1B-related disease
   - ⚠️ Confirm with ACMG guidelines and additional evidence

---

### Use Case 2: Research Analysis

**Scenario:** You're analyzing 50 HNF1B variants from published studies (provided as rsIDs). You need HGVS notations and consequence predictions.

**Batch Processing Script (Python):**

```python
import requests
import pandas as pd

# Configuration
BASE_URL = "http://localhost:8000/api/v2"
TOKEN = "your-jwt-token"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Input: List of rsIDs
rs_ids = ["rs56116432", "rs1801131", "rs1801133"]  # Add your 50 rsIDs

results = []

for rs_id in rs_ids:
    # Step 1: Recode to get HGVS notation
    recode_response = requests.post(
        f"{BASE_URL}/variants/recode",
        headers=headers,
        json={"variant": rs_id}
    )
    recoding = recode_response.json()
    hgvsc = recoding["recoding"]["hgvsc"][0] if recoding["recoding"]["hgvsc"] else None

    if not hgvsc:
        print(f"⚠️ No HGVS notation for {rs_id}")
        continue

    # Step 2: Annotate to get consequence
    annotate_response = requests.post(
        f"{BASE_URL}/variants/annotate",
        headers=headers,
        json={"variant": hgvsc}
    )
    annotation = annotate_response.json()

    # Extract key fields
    transcript = annotation["annotation"]["transcript_consequences"][0]
    results.append({
        "rsID": rs_id,
        "HGVS": hgvsc,
        "Gene": transcript["gene_symbol"],
        "Consequence": transcript["consequence_terms"][0],
        "Impact": transcript["impact"],
        "CADD": transcript.get("cadd_phred", "N/A")
    })

# Save to CSV
df = pd.DataFrame(results)
df.to_csv("variant_annotations.csv", index=False)
print(f"✅ Annotated {len(results)} variants → variant_annotations.csv")
```

**Output CSV:**
| rsID | HGVS | Gene | Consequence | Impact | CADD |
|------|------|------|-------------|--------|------|
| rs56116432 | NM_000458.4:c.544+1G>A | HNF1B | splice_donor_variant | HIGH | 34.0 |
| ... | ... | ... | ... | ... | ... |

---

### Use Case 3: Phenopacket Integration

**Scenario:** You're adding a variant to a patient phenopacket and need VRS-compliant identifiers.

**Steps:**

1. **Annotate variant to get genomic coordinates:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/annotate \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"variant": "NM_000458.4:c.544+1G>A"}'
   ```

2. **Extract genomic information:**
   ```json
   {
     "seq_region_name": "17",
     "start": 36459258,
     "end": 36459258,
     "allele_string": "A/G"
   }
   ```

3. **Recode to get SPDI format:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/recode \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"variant": "NM_000458.4:c.544+1G>A"}'
   ```

4. **Extract SPDI for VRS:**
   ```json
   {
     "spdi": {
       "seq_id": "NC_000017.11",
       "position": 36459257,
       "deleted_sequence": "A",
       "inserted_sequence": "G"
     }
   }
   ```

5. **Add to phenopacket:**
   ```json
   {
     "id": "variant-1",
     "variation": {
       "allele": {
         "sequenceLocation": {
           "sequenceId": "NC_000017.11",
           "sequenceInterval": {
             "startNumber": 36459257,
             "endNumber": 36459258
           }
         },
         "literalSequenceExpression": {
           "sequence": "G"
         }
       }
     }
   }
   ```

---

### Use Case 4: Fixing Invalid Notations

**Scenario:** You have variant notations from various sources with formatting errors.

**Common Errors and Fixes:**

**Error 1: Missing colon in HGVS**
```bash
# Invalid: NM_000458.4c.544+1G>A
curl -X GET http://localhost:8000/api/v2/variants/suggest/NM_000458.4c.544+1G>A \
  -H "Authorization: Bearer $TOKEN"

# Suggestion: "Add ':' after transcript ID → NM_000458.4:c.544+1G>A"
# Fixed: NM_000458.4:c.544+1G>A
```

**Error 2: Wrong VCF separator**
```bash
# Invalid: 17:36459258:A:G
curl -X GET http://localhost:8000/api/v2/variants/suggest/17:36459258:A:G \
  -H "Authorization: Bearer $TOKEN"

# Suggestion: "Use '-' separator for VCF format → 17-36459258-A-G"
# Fixed: 17-36459258-A-G
```

**Error 3: Missing dot in protein notation**
```bash
# Invalid: p.Arg182Trp (should be p.Arg182Trp, but often written without dot)
# Most systems accept this, but be aware of:
# - pArg182Trp (missing dot) ❌
# - p.Arg182Trp (correct) ✅
```

---

## Understanding Results

### Consequence Terms

VEP uses [Sequence Ontology (SO)](http://www.sequenceontology.org/) terms to describe variant effects:

| Term | Impact | Clinical Significance | Example |
|------|--------|-----------------------|---------|
| **splice_donor_variant** | HIGH | Likely pathogenic | Disrupts GT splice site |
| **splice_acceptor_variant** | HIGH | Likely pathogenic | Disrupts AG splice site |
| **stop_gained** | HIGH | Likely pathogenic | Premature stop codon |
| **frameshift_variant** | HIGH | Likely pathogenic | Reading frame disrupted |
| **missense_variant** | MODERATE | Variable | Amino acid change |
| **synonymous_variant** | LOW | Likely benign | No amino acid change |
| **intron_variant** | MODIFIER | Likely benign | Deep intronic |

**Clinical Interpretation Guidelines:**
- **HIGH impact:** Strong evidence for pathogenicity
- **MODERATE impact:** Requires functional/segregation data
- **LOW impact:** Usually benign (exceptions exist)
- **MODIFIER:** Likely benign

### Impact Ratings

| Impact | Description | Clinical Action |
|--------|-------------|-----------------|
| **HIGH** | Loss of function likely | Report as likely pathogenic (with evidence) |
| **MODERATE** | Functional change possible | Investigate further (functional assays, co-segregation) |
| **LOW** | Minimal functional effect | Usually benign (check frequency/conservation) |
| **MODIFIER** | Regulatory/non-coding | Consider only if other evidence supports pathogenicity |

### CADD Scores

**CADD (Combined Annotation Dependent Depletion)** predicts deleteriousness:

| CADD Score | Interpretation | Action |
|------------|----------------|--------|
| **>30** | Highly deleterious (top 0.1%) | Strong evidence for pathogenicity |
| **20-30** | Deleterious (top 1%) | Moderate evidence for pathogenicity |
| **10-20** | Possibly deleterious | Weak evidence |
| **<10** | Likely benign | Consider benign (unless other evidence) |

**Example:**
- `CADD = 34.0` → Top 0.01% most deleterious variants
- Interpretation: Strong computational evidence for pathogenicity

### Population Frequencies (gnomAD)

**gnomAD allele frequency** indicates how common a variant is:

| Frequency | Interpretation | Clinical Significance |
|-----------|----------------|----------------------|
| **>0.01 (1%)** | Common | Likely benign (unless high penetrance disease) |
| **0.001-0.01 (0.1-1%)** | Uncommon | Unlikely to cause rare disease |
| **<0.0001 (0.01%)** | Rare | Compatible with pathogenicity |
| **Absent** | Novel | Compatible with pathogenicity (de novo likely) |

**Example:**
- `gnomad_af = 0.0001` → Present in 1 in 10,000 people
- Interpretation: Rare enough to cause HNF1B disease

**ACMG Criteria:**
- **PM2 (Moderate evidence):** Absent from gnomAD
- **BS1 (Strong benign):** Allele frequency >5% in any population

---

## Troubleshooting

### Common Issues

#### Issue 1: "Variant not found in VEP database" (404)

**Causes:**
- Novel variant not yet in Ensembl database
- Incorrect reference genome (GRCh37 vs GRCh38)
- Invalid genomic coordinates

**Solutions:**
1. Verify variant is real (check sequencing data quality)
2. Try alternative notation (VCF → HGVS or vice versa)
3. Check reference genome version (ensure GRCh38)
4. Use liftover tools if variant is on GRCh37

**Example:**
```bash
# If HGVS fails, try VCF coordinates
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17-36459258-A-G"}'
```

---

#### Issue 2: "Rate limit exceeded" (429)

**Causes:**
- Too many requests in short time window (>15 requests/second)

**Solutions:**
1. **Wait and retry:** API automatically retries with backoff
2. **Implement client-side rate limiting:**
   ```python
   import time

   for variant in variants:
       annotate_variant(variant)
       time.sleep(0.1)  # 10 requests/second (under limit)
   ```
3. **Use caching:** Don't re-annotate same variants

---

#### Issue 3: "Invalid authentication credentials" (401)

**Causes:**
- Expired JWT token (tokens expire after 24 hours)
- Missing `Authorization` header
- Incorrect token format

**Solutions:**
1. **Re-authenticate to get fresh token:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "your-username", "password": "your-password"}'
   ```

2. **Verify header format:**
   ```bash
   # ❌ Wrong: "Token eyJ..."
   # ✅ Correct: "Bearer eyJ..."
   ```

---

#### Issue 4: Slow Response Times

**Causes:**
- VEP API latency (~500ms per request)
- Network issues
- Rate limiting delays

**Solutions:**
1. **Use cached variants:**
   - First call: ~500ms (VEP API)
   - Subsequent calls: ~10ms (cache hit)

2. **Validate before annotating:**
   ```bash
   # Quick validation (10ms) before slow annotation (500ms)
   validate → annotate
   ```

3. **Batch process during off-peak hours**

---

## Best Practices

### 1. Always Validate First

**Why:** Catch formatting errors before expensive VEP calls

```bash
# ✅ Good: Validate → Annotate
curl -X POST .../validate -d '{"variant": "..."}'
# If valid:
curl -X POST .../annotate -d '{"variant": "..."}'

# ❌ Bad: Annotate directly (may fail with cryptic errors)
curl -X POST .../annotate -d '{"variant": "..."}'
```

### 2. Cache Repeated Queries

**Why:** Reduce API load and improve response times

```python
# ✅ Good: Check cache first
cache = {}

def get_annotation(variant):
    if variant in cache:
        return cache[variant]  # Instant return

    annotation = api.annotate(variant)
    cache[variant] = annotation
    return annotation
```

### 3. Handle Errors Gracefully

**Why:** VEP API can be unavailable or return unexpected errors

```python
# ✅ Good: Robust error handling
try:
    annotation = api.annotate(variant)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print(f"⚠️ Variant not found: {variant}")
    elif e.response.status_code == 429:
        print(f"⏳ Rate limited. Retrying in 2s...")
        time.sleep(2)
        annotation = api.annotate(variant)  # Retry
    else:
        raise  # Re-raise unexpected errors
```

### 4. Use Appropriate Notation

**Why:** Different contexts require different formats

| Context | Preferred Format | Example |
|---------|-----------------|---------|
| Clinical reports | HGVS (RefSeq NM_*) | `NM_000458.4:c.544+1G>A` |
| Publications | HGVS + rsID | `NM_000458.4:c.544+1G>A (rs56116432)` |
| Bioinformatics | VCF | `17-36459258-A-G` |
| Database queries | rsID | `rs56116432` |

### 5. Monitor Rate Limits

**Why:** Avoid throttling and service degradation

```python
# ✅ Good: Check rate limit headers
response = requests.post(url, headers=headers, json=data)
remaining = int(response.headers.get("X-RateLimit-Remaining", 100))

if remaining < 10:
    print(f"⚠️ Only {remaining} requests left. Slowing down...")
    time.sleep(1)
```

### 6. Document Your Variants

**Why:** Reproducibility and transparency

```python
# ✅ Good: Log annotation metadata
annotation_log = {
    "variant": "NM_000458.4:c.544+1G>A",
    "annotated_at": "2025-01-15T10:30:00Z",
    "vep_version": "110",
    "assembly": "GRCh38",
    "consequence": "splice_donor_variant",
    "cadd_score": 34.0
}
```

---

## FAQ

### Q1: Which HGVS transcript should I use (RefSeq vs Ensembl)?

**Answer:** Use **RefSeq transcripts (NM_*)** for clinical reporting, as they're standard in medical labs. Ensembl transcripts (ENST*) are acceptable for research.

**Example:**
- **Clinical report:** `NM_000458.4:c.544+1G>A` ✅
- **Research paper:** `ENST00000366667.8:c.544+1G>A` ✅ (but also list RefSeq)

**Conversion:**
```bash
# Use recode to get both
curl -X POST .../recode -d '{"variant": "rs56116432"}'
# Returns both NM_* and ENST* notations
```

---

### Q2: How do I know if a variant is pathogenic?

**Answer:** Use **ACMG guidelines** with VEP annotation data:

**Evidence from VEP:**
- **PVS1:** HIGH impact (splice site, frameshift, stop gained)
- **PM1:** Located in functional domain (check consequence)
- **PM2:** Absent from gnomAD (`gnomad_af` is null or <0.0001)
- **PP3:** High CADD score (>25)

**Example Classification:**
```
Variant: NM_000458.4:c.544+1G>A
- Consequence: splice_donor_variant → PVS1 (very strong)
- gnomAD frequency: 0.0001 → PM2 (moderate)
- CADD: 34.0 → PP3 (supporting)

→ Classification: Likely Pathogenic (PVS1 + PM2 + PP3)
```

**Important:** Always combine computational evidence with:
- Segregation data
- Functional assays
- Clinical phenotype correlation

---

### Q3: What if my variant isn't in Ensembl?

**Answer:** Novel variants won't have annotations. Solutions:

1. **Use VCF coordinates:** VEP can predict consequences even without rsID
   ```bash
   curl -X POST .../annotate -d '{"variant": "17-36459258-A-G"}'
   ```

2. **Check reference genome:** Ensure using GRCh38 (not GRCh37)

3. **Verify variant is real:** Check sequencing quality (depth, allele balance)

4. **Alternative tools:**
   - [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) (known pathogenic variants)
   - [LOVD](https://www.lovd.nl/) (gene-specific databases)

---

### Q4: How often should I re-annotate variants?

**Answer:** Re-annotate when:
- **VEP database updated** (every 3 months) - new frequencies, consequences
- **ClinVar updated** (monthly) - new clinical classifications
- **Publishing results** - ensure latest annotations

**Not needed when:**
- Variant already annotated this month
- Using cached data for preliminary analysis
- Annotations are stable (well-characterized variants)

---

### Q5: Can I annotate structural variants (CNVs, deletions)?

**Answer:** The current API focuses on SNVs and small indels. For structural variants:

**Not supported:**
- Large deletions (>50bp)
- Copy number variants (CNVs)
- Inversions, translocations

**Supported:**
- Small indels (<50bp): `NM_000458.4:c.544delG`
- Multi-nucleotide variants: `NM_000458.4:c.544_546delGAT`

**Alternative for CNVs:**
- Use HNF1B-specific deletions in phenopackets
- Consult [ClinGen](https://www.clinicalgenome.org/) for CNV interpretation

---

### Q6: What's the difference between HGVS genomic and coding notation?

**Answer:**

| Notation | Format | Use Case | Example |
|----------|--------|----------|---------|
| **Genomic (g.)** | `NC_*:g.position` | Reference genome coordinate | `NC_000017.11:g.36459258A>G` |
| **Coding (c.)** | `NM_*:c.position` | Transcript-relative position | `NM_000458.4:c.544+1G>A` |

**When to use each:**
- **Genomic (g.):** Bioinformatics, liftover, exact chromosome position
- **Coding (c.):** Clinical reports, exon/intron positions, protein prediction

**Conversion:**
```bash
# Use recode to get both
curl -X POST .../recode -d '{"variant": "NM_000458.4:c.544+1G>A"}'
# Returns:
# - hgvsg: ["NC_000017.11:g.36459258A>G"]
# - hgvsc: ["NM_000458.4:c.544+1G>A"]
```

---

### Q7: How do I interpret splice variants (e.g., c.544+1G>A)?

**Answer:**

**Notation breakdown:**
- `c.544` = last nucleotide of exon 4
- `+1` = first nucleotide of intron (splice donor site)
- `G>A` = reference G changed to A

**Splice sites:**
- **Donor site:** `GT` at exon-intron boundary (c.N+1, c.N+2)
- **Acceptor site:** `AG` at intron-exon boundary (c.N-1, c.N-2)

**Clinical significance:**
- **+1 or +2 (donor):** HIGH impact - disrupts splicing → PVS1
- **-1 or -2 (acceptor):** HIGH impact - disrupts splicing → PVS1
- **+3 to +6:** Moderate impact - may affect splicing
- **>+6:** Usually benign - deep intronic

**Example:**
```
c.544+1G>A
- Position: First base of intron (splice donor)
- Effect: Destroys GT→AT (no longer recognized as splice site)
- Result: Exon skipping or cryptic splice site activation
- Impact: HIGH (loss of function)
```

---

### Q8: Can I use this API for non-HNF1B genes?

**Answer:** **Yes!** The VEP annotation API works for any human gene. While this database focuses on HNF1B disease, the annotation endpoints accept variants from any gene.

**Examples:**
```bash
# HNF1B variant
curl -X POST .../annotate -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# PAX2 variant (also causes CAKUT)
curl -X POST .../annotate -d '{"variant": "NM_003987.4:c.194G>A"}'

# BRCA1 variant
curl -X POST .../annotate -d '{"variant": "NM_007294.3:c.5266dupC"}'
```

---

## Additional Resources

### External Tools

- **[Mutalyzer](https://mutalyzer.nl/)** - HGVS notation checker
- **[VariantValidator](https://variantvalidator.org/)** - Comprehensive variant validation
- **[ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/)** - Clinical variant database
- **[gnomAD](https://gnomad.broadinstitute.org/)** - Population frequency data
- **[ACMG Guidelines](https://www.acmg.net/)** - Variant interpretation standards

### Recommended Reading

- [HGVS Nomenclature Official Site](https://varnomen.hgvs.org/)
- [VEP Documentation](https://www.ensembl.org/info/docs/tools/vep/index.html)
- [ACMG Standards (2015)](https://pubmed.ncbi.nlm.nih.gov/25741868/)
- [Sequence Ontology](http://www.sequenceontology.org/)

### API Documentation

- **API Reference:** [docs/api/variant-annotation.md](/docs/api/variant-annotation.md)
- **Developer Guide:** [docs/variant-annotation-implementation-plan.md](/docs/variant-annotation-implementation-plan.md)

---

## Getting Help

**For Technical Issues:**
- GitHub Issues: [hnf1b-db/issues](https://github.com/yourusername/hnf1b-db/issues)
- Tag: `variant-annotation`

**For Clinical Interpretation:**
- Consult with clinical geneticist or genetic counselor
- Use ACMG guidelines with computational evidence

**For API Questions:**
- Check API reference documentation
- Review example code in this guide

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-15 | Initial user guide release |

---

**Last Updated:** 2025-01-15
**API Version:** v2
**VEP Version:** 110 (Ensembl)
