# User Guide Documentation

This directory contains user-focused documentation with practical examples, workflows, and tutorials for using the HNF1B Database.

## Available Guides

### Variant Annotation User Guide
**File:** [variant-annotation.md](variant-annotation.md)

Comprehensive guide for using the variant annotation system in real-world scenarios.

**Topics Covered:**
1. **Getting Started** - Authentication, prerequisites, variant formats
2. **Basic Workflows** - Validate, annotate, and recode variants
3. **Use Cases**:
   - Clinical interpretation (pathogenicity assessment)
   - Research analysis (batch processing)
   - Phenopacket integration (VRS compliance)
   - Fixing invalid notations
4. **Understanding Results** - Consequence terms, impact ratings, CADD scores, gnomAD frequencies
5. **Troubleshooting** - Common issues and solutions
6. **Best Practices** - Validation, caching, error handling
7. **FAQ** - Common questions answered

**Target Audience:**
- Researchers analyzing HNF1B variants
- Clinicians interpreting genetic tests
- Bioinformaticians integrating variant data
- Data curators adding variants to phenopackets

---

## Quick Start

### For Clinicians

**Goal:** Interpret a patient's genetic test result

1. **Validate the variant notation:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/validate \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"notation": "NM_000458.4:c.544+1G>A"}'
   ```

2. **Get clinical annotation:**
   ```bash
   curl -X POST http://localhost:8000/api/v2/variants/annotate \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"variant": "NM_000458.4:c.544+1G>A"}'
   ```

3. **Interpret the results:**
   - **Consequence:** `splice_donor_variant` → Disrupts RNA splicing
   - **Impact:** `HIGH` → Likely pathogenic
   - **CADD:** `34.0` → Highly deleterious (>30 = pathogenic)
   - **gnomAD:** `0.0001` → Very rare (compatible with disease)

**Conclusion:** Likely pathogenic variant consistent with HNF1B disease

---

### For Researchers

**Goal:** Batch annotate 50 variants from published studies

**Python Script:**
```python
import requests
import pandas as pd

# Configuration
BASE_URL = "http://localhost:8000/api/v2"
TOKEN = "your-jwt-token"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Input: List of rsIDs
rs_ids = ["rs56116432", "rs1801131", ...]

results = []
for rs_id in rs_ids:
    # Recode to get HGVS
    recode_response = requests.post(
        f"{BASE_URL}/variants/recode",
        headers=headers,
        json={"variant": rs_id}
    )
    hgvsc = recode_response.json()["hgvsc"][0]

    # Annotate
    annotate_response = requests.post(
        f"{BASE_URL}/variants/annotate",
        headers=headers,
        json={"variant": hgvsc}
    )
    annotation = annotate_response.json()

    results.append({
        "rsID": rs_id,
        "HGVS": hgvsc,
        "Gene": annotation["gene_symbol"],
        "Consequence": annotation["most_severe_consequence"],
        "Impact": annotation["impact"],
        "CADD": annotation.get("cadd_score", "N/A")
    })

# Save to CSV
df = pd.DataFrame(results)
df.to_csv("variant_annotations.csv", index=False)
```

---

### For Bioinformaticians

**Goal:** Convert VCF variants to HGVS for clinical reporting

**Command Line:**
```bash
# Read VCF file and convert each variant
cat variants.vcf | awk 'NR>1 {print $1"-"$2"-"$4"-"$5}' | while read variant; do
    curl -X POST http://localhost:8000/api/v2/variants/recode \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"variant\": \"$variant\"}" \
      | jq -r '.hgvsc[0]'
done > variants_hgvs.txt
```

---

## Related Documentation

- **API Reference:** [../api/variant-annotation.md](../api/variant-annotation.md) - Detailed API specs
- **Developer Guide:** [../variant-annotation-implementation-plan.md](../variant-annotation-implementation-plan.md) - Implementation details
- **Backend README:** [../../backend/README.md](../../backend/README.md) - Setup instructions

---

## Common Workflows

### Workflow 1: Literature to Database

**Scenario:** You found an HNF1B variant (rsID) in a paper and want to add it to the database.

**Steps:**
1. **Recode rsID → HGVS**
   - Input: `rs56116432`
   - Output: `NM_000458.4:c.544+1G>A`

2. **Annotate for clinical details**
   - Get consequence, impact, CADD score
   - Verify pathogenicity

3. **Recode HGVS → VCF**
   - Input: `NM_000458.4:c.544+1G>A`
   - Output: `17-36459258-A-G`

4. **Add to phenopacket**
   - Use VCF format for database storage
   - Include HGVS in interpretation field

---

### Workflow 2: Clinical Report to Phenopacket

**Scenario:** Patient genetic test report lists variant in HGVS format.

**Steps:**
1. **Validate HGVS notation**
   - Catch formatting errors early
   - Get suggestions for fixes

2. **Annotate with VEP**
   - Confirm gene (HNF1B)
   - Check consequence and impact
   - Review population frequency

3. **Convert to VRS format**
   - Use SPDI from recoding
   - Build VRS Allele structure
   - Add to phenopacket

4. **Store in database**
   - Phenopacket CRUD operations
   - Searchable by variant coordinates

---

### Workflow 3: Batch Processing

**Scenario:** You have 100 variants from multiple sources (HGVS, VCF, rsID) and need standardized annotations.

**Steps:**
1. **Normalize all formats**
   - Recode everything to HGVS coding
   - Ensure consistent transcript (NM_*)

2. **Batch annotate**
   - Add small delay (100ms) between requests
   - Cache speeds up repeated queries
   - Handle rate limits automatically

3. **Export to CSV**
   - rsID, HGVS, VCF, Gene, Consequence, Impact, CADD, gnomAD
   - Ready for publication or reporting

---

## Frequently Asked Questions

### General Questions

**Q: Which variant format should I use?**
A:
- **Clinical reports:** HGVS (NM_* coding notation)
- **Bioinformatics:** VCF (chromosome-position-ref-alt)
- **Literature references:** rsID (when available)
- **Database queries:** All formats supported

**Q: How do I know if a variant is pathogenic?**
A: Use ACMG guidelines with VEP data:
- **PVS1:** HIGH impact (splice site, frameshift, stop gained)
- **PM2:** Absent from gnomAD (< 0.0001 frequency)
- **PP3:** High CADD score (> 25)
- Combine with clinical/functional evidence

**Q: What if my variant isn't found?**
A:
- Novel variants may not be in Ensembl database
- Try VCF coordinates instead of HGVS
- Verify reference genome (GRCh38)
- Check sequencing data quality

### Technical Questions

**Q: How fast is the annotation?**
A:
- First request: ~500ms (VEP API call)
- Cached request: ~10ms (LRU cache hit)
- Rate limit: 15 requests/second

**Q: Can I annotate non-HNF1B variants?**
A: Yes! The API works for any human gene variant.

**Q: How do I handle rate limits?**
A:
- Add 100ms delay between requests
- Use caching for repeated queries
- Monitor `X-RateLimit-Remaining` header

---

## Troubleshooting Guide

### Issue: "Variant not found" (404)

**Possible Causes:**
- Novel variant not in Ensembl
- Wrong reference genome
- Invalid coordinates

**Solutions:**
1. Try alternative notation (VCF ↔ HGVS)
2. Verify variant is real (check sequencing)
3. Use liftover for GRCh37 variants

### Issue: "Rate limit exceeded" (429)

**Possible Causes:**
- Too many requests (>15/second)

**Solutions:**
1. Wait for automatic retry
2. Add client-side rate limiting
3. Use caching to reduce API calls

### Issue: Invalid notation errors

**Possible Causes:**
- Missing colon in HGVS
- Wrong separators in VCF
- Malformed transcript ID

**Solutions:**
1. Use `/validate` endpoint first
2. Check `/suggest` for corrections
3. Review notation format examples

---

## Best Practices

### 1. Always Validate First
Catch formatting errors before expensive annotation calls.

### 2. Cache Repeated Queries
Implement client-side caching to reduce API load.

### 3. Handle Errors Gracefully
Check for 404, 429, 400 errors and retry appropriately.

### 4. Monitor Rate Limits
Watch `X-RateLimit-Remaining` header to avoid throttling.

### 5. Document Your Workflow
Log annotation metadata (VEP version, date, assembly) for reproducibility.

---

## Support

**For Usage Questions:**
- Review this user guide
- Check [../api/variant-annotation.md](../api/variant-annotation.md) for API details
- Search [GitHub Issues](https://github.com/yourusername/hnf1b-db/issues)

**For Bug Reports:**
- Open a GitHub issue with tag `variant-annotation`
- Include example variant and error message
- Specify API version and environment

**For Feature Requests:**
- Open a GitHub issue with tag `enhancement`
- Describe the use case and expected behavior

---

**Last Updated:** 2025-01-15
**Guide Version:** 1.0
**API Version:** v2
