# Issue #57: bug(backend): investigate variant deduplication (864 variants in 864 individuals)

## Overview

Suspicious 1:1 ratio - 864 variants in 864 individuals suggests no variant deduplication is occurring.

**Observed:** 864 variants across 864 phenopackets (1:1 ratio)
**Expected:** ~400-500 unique variants with ~1300 total variant entries (many phenopackets sharing common variants)

## Why This Matters

### Problem

**Current State:**
- 864 phenopackets in database
- Each phenopacket appears to have a unique variant
- 1:1 ratio suggests no variant sharing/deduplication
- Contradicts HNF1B disease genetics (common recurrent variants expected)

**Why This Is Suspicious:**

1. **HNF1B Disease Genetics:**
   - HNF1B is a single gene disorder
   - Recurrent variants are common (e.g., 17q12 deletion, specific point mutations)
   - Expected: Multiple individuals with same variants
   - Observed: Every individual has unique variant (unlikely)

2. **Literature Evidence:**
   - Common 17q12 deletion (~30% of cases)
   - Recurrent missense mutations (e.g., p.R177X, p.R276X)
   - Expected variant sharing across cohort
   - 1:1 ratio contradicts this

3. **Data Quality:**
   - If every variant is unique, possible issues:
     - Variant IDs not standardized (different representations of same variant)
     - VRS digest computation incorrect
     - Migration script not deduplicating
     - Data entry inconsistencies

### Impact

**If Bug Confirmed:**
- ❌ Inflated variant count (864 instead of ~400-500)
- ❌ Cannot track recurrent variants
- ❌ Cannot identify variant hotspots
- ❌ Variant aggregation queries give misleading results
- ❌ Waste of storage (duplicate variant data)
- ❌ Poor performance (no variant reuse)

**If Not a Bug:**
- ✅ Cohort truly has 864 unique variants
- ✅ Expected for diverse international cohort
- ✅ Need to document this finding

## Investigation Plan

### Step 1: Count Unique Variants by VRS ID

**SQL Query:**
```sql
-- Count total phenopackets, variant entries, and unique variants
SELECT
  COUNT(DISTINCT pp.id) as total_phenopackets,
  COUNT(*) as total_variant_entries,
  COUNT(DISTINCT (gi->'variantInterpretation'->'variation'->>'id')) as unique_vrs_ids
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL;
```

**Expected Results:**

**Scenario A (Bug - No Deduplication):**
```
total_phenopackets | total_variant_entries | unique_vrs_ids
------------------|-----------------------|----------------
       864        |         864           |      864
```
→ **Problem:** 1:1:1 ratio suggests no variant sharing

**Scenario B (Correct - With Deduplication):**
```
total_phenopackets | total_variant_entries | unique_vrs_ids
------------------|-----------------------|----------------
       864        |        1300           |      450
```
→ **Good:** Multiple phenopackets share variants (~2.9 phenopackets per variant average)

**Scenario C (Diverse Cohort):**
```
total_phenopackets | total_variant_entries | unique_vrs_ids
------------------|-----------------------|----------------
       864        |         900           |      850
```
→ **Acceptable:** Mostly unique variants with some sharing

### Step 2: Check for Recurrent Variants

**SQL Query:**
```sql
-- Find variants present in multiple phenopackets
SELECT
  gi->'variantInterpretation'->'variation'->>'id' as vrs_id,
  gi->'variantInterpretation'->'variation'->>'label' as variant_label,
  COUNT(DISTINCT pp.id) as phenopacket_count,
  array_agg(DISTINCT pp.phenopacket_id) as phenopacket_ids
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL
GROUP BY vrs_id, variant_label
HAVING COUNT(DISTINCT pp.id) > 1
ORDER BY phenopacket_count DESC
LIMIT 20;
```

**Expected Results:**

**If Working Correctly:**
```
vrs_id                                    | variant_label                    | phenopacket_count
-----------------------------------------|----------------------------------|-------------------
ga4gh:VA.EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_ | NM_000458.3:c.1337A>G (p.R177X) |        45
ga4gh:VA.v4gbL4vhMfZ3LT8ZNPGJ0GlfbkJq4nkf | 17q12 deletion                   |       120
ga4gh:VA.xyz123...                       | NM_000458.3:c.828C>T (p.R276X)  |        30
...
```
→ **Good:** Multiple phenopackets share common variants

**If Bug:**
```
(No results - all variants unique)
```
→ **Problem:** No recurrent variants detected

### Step 3: Check Variant Label Distribution

**SQL Query:**
```sql
-- Group by variant LABEL (human-readable) instead of VRS ID
SELECT
  gi->'variantInterpretation'->'variation'->>'label' as variant_label,
  COUNT(DISTINCT pp.id) as phenopacket_count,
  COUNT(DISTINCT gi->'variantInterpretation'->'variation'->>'id') as unique_vrs_ids
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL
GROUP BY variant_label
HAVING COUNT(DISTINCT pp.id) > 1
ORDER BY phenopacket_count DESC
LIMIT 20;
```

**Purpose:** Check if same variant has different VRS IDs (digest computation issue)

**Expected Results:**

**If VRS Digests Correct:**
```
variant_label                            | phenopacket_count | unique_vrs_ids
-----------------------------------------|-------------------|---------------
17q12 deletion                           |       120         |       1
NM_000458.3:c.1337A>G (p.R177X)         |        45         |       1
```
→ **Good:** Each variant label maps to single VRS ID

**If VRS Digests Broken:**
```
variant_label                            | phenopacket_count | unique_vrs_ids
-----------------------------------------|-------------------|---------------
17q12 deletion                           |       120         |      120
NM_000458.3:c.1337A>G (p.R177X)         |        45         |       45
```
→ **Problem:** Same variant has multiple VRS IDs (non-deterministic digest)

### Step 4: Check for Placeholder Digests

**SQL Query:**
```sql
-- Check if variants use placeholder digests
SELECT
  COUNT(*) as total_variants,
  COUNT(*) FILTER (WHERE gi->'variantInterpretation'->'variation'->>'id' LIKE '%PLACEHOLDER%') as placeholder_count,
  COUNT(*) FILTER (WHERE gi->'variantInterpretation'->'variation'->>'id' ~ '^ga4gh:VA\.[A-Za-z0-9_-]{32}$') as valid_vrs_count
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL;
```

**Expected Results:**

**If GA4GH VRS Installed (Issue #56 fixed):**
```
total_variants | placeholder_count | valid_vrs_count
---------------|-------------------|----------------
     864       |        0          |      864
```
→ **Good:** All variants have valid VRS IDs

**If Placeholders Used:**
```
total_variants | placeholder_count | valid_vrs_count
---------------|-------------------|----------------
     864       |       864         |        0
```
→ **Problem:** All variants use placeholders (see Issue #56)

### Step 5: Sample Variant Inspection

**SQL Query:**
```sql
-- Inspect 5 sample variants in detail
SELECT
  pp.phenopacket_id,
  gi->'variantInterpretation'->'variation'->>'id' as vrs_id,
  gi->'variantInterpretation'->'variation'->>'label' as variant_label,
  gi->'variantInterpretation'->>'acmgPathogenicityClassification' as pathogenicity
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL
LIMIT 5;
```

**Purpose:** Manually inspect variant data structure and quality

## Root Cause Analysis

### Possible Causes

**1. VRS Digest Computation Issue**
- **Symptom:** Same variant label has different VRS IDs
- **Cause:** Non-deterministic digest computation
- **Related:** Issue #20 (used `hash()` instead of `sha512t24u`)
- **Fix:** Ensure deterministic VRS digest computation
- **Test:** Same variant should always produce same VRS ID

**2. Placeholder Digests (Issue #56)**
- **Symptom:** All VRS IDs contain "PLACEHOLDER"
- **Cause:** ga4gh.vrs not installed
- **Fix:** Install ga4gh.vrs (see Issue #56)
- **Test:** VRS IDs should match pattern `ga4gh:VA.[A-Za-z0-9_-]{32}`

**3. No Variant Normalization**
- **Symptom:** Same variant with different representations
- **Example:**
  - Variant A: `NM_000458.3:c.1337A>G`
  - Variant B: `NM_000458.4:c.1337A>G` (different transcript version)
  - Variant C: `chr17:36098040:A:G` (genomic coordinates)
- **Cause:** Migration script doesn't normalize variants
- **Fix:** Implement variant normalization (complex - future work)

**4. Truly Diverse Cohort**
- **Symptom:** 864 unique variants in 864 individuals
- **Cause:** International cohort with many private/novel variants
- **Evidence:** HNF1B has >500 known variants in ClinVar
- **Conclusion:** Not a bug, document finding

**5. Data Entry Inconsistencies**
- **Symptom:** Slight variations in variant representation
- **Example:**
  - `p.R177X` vs `p.Arg177Ter` vs `p.Arg177*`
- **Cause:** Manual data entry from literature
- **Fix:** Standardize variant nomenclature (HGVS strict)

## Expected Outcomes

### Scenario A: Bug Confirmed - Placeholder Digests

**Evidence:**
- All variants have placeholder VRS IDs
- Same variant label appears multiple times with different IDs

**Action:**
1. Fix Issue #56 (install ga4gh.vrs)
2. Re-run migration with proper VRS digests
3. Verify variant deduplication after re-migration

**Timeline:** 1 day (depends on Issue #56)

### Scenario B: Bug Confirmed - Non-Deterministic Digests

**Evidence:**
- Valid VRS IDs (not placeholders)
- Same variant label has multiple VRS IDs
- Related to Issue #20 (non-deterministic hash)

**Action:**
1. Fix VRS digest computation in migration script
2. Re-run migration
3. Add tests for digest determinism

**Timeline:** 2 days

### Scenario C: Bug Confirmed - Missing Deduplication Logic

**Evidence:**
- Valid VRS IDs
- Deterministic digests
- No variant sharing detected (all unique)
- But literature suggests recurrent variants exist

**Action:**
1. Add deduplication logic to migration script
2. Create `variants` table (normalized variant storage)
3. Reference variants from phenopackets by ID
4. Re-run migration

**Timeline:** 3-4 days (requires schema change)

### Scenario D: No Bug - Diverse Cohort

**Evidence:**
- Valid VRS IDs
- Deterministic digests
- Some variant sharing detected (5-10%)
- Most variants truly unique

**Action:**
1. Document finding (HNF1B cohort has high variant diversity)
2. No migration changes needed
3. Update README with variant statistics

**Timeline:** 1 hour (documentation only)

## Implementation (If Bug Confirmed)

### Option 1: Normalize Variants in Migration Script

**Modify:** `backend/migration/direct_sheets_to_phenopackets.py`

**Add deduplication logic:**
```python
# Track unique variants by VRS ID
unique_variants = {}

for row in data:
    variant = build_variant(row)
    vrs_id = variant['id']

    # Deduplicate by VRS ID
    if vrs_id not in unique_variants:
        unique_variants[vrs_id] = variant

    # Reference variant by ID in phenopacket
    phenopacket['interpretations'][0]['diagnosis']['genomicInterpretations'][0]['variantInterpretation']['variation'] = {
        'id': vrs_id  # Reference only, full data in unique_variants
    }
```

**Pros:**
- ✅ Simple fix in migration script
- ✅ No schema changes
- ✅ Works with existing JSONB structure

**Cons:**
- ⚠️ Still stores full variant data in each phenopacket (duplicated)
- ⚠️ No separate variants table for queries

### Option 2: Create Normalized Variants Table

**New Schema:**
```sql
CREATE TABLE variants (
    vrs_id VARCHAR(100) PRIMARY KEY,
    label TEXT NOT NULL,
    variation JSONB NOT NULL,  -- Full VRS Variation object
    gene_symbol VARCHAR(20),
    pathogenicity VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_variants_gene ON variants(gene_symbol);
CREATE INDEX idx_variants_pathogenicity ON variants(pathogenicity);
```

**Phenopacket References Variant:**
```json
{
  "interpretations": [{
    "diagnosis": {
      "genomicInterpretations": [{
        "variantInterpretation": {
          "variationId": "ga4gh:VA.EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_",
          // Full variation data retrieved via JOIN
        }
      }]
    }
  }]
}
```

**Pros:**
- ✅ True normalization (no duplication)
- ✅ Efficient variant queries
- ✅ Easy variant aggregation
- ✅ Follows relational best practices

**Cons:**
- ⚠️ Schema change required
- ⚠️ Alembic migration needed
- ⚠️ API changes needed (JOIN variants on lookup)
- ⚠️ More complex implementation (3-4 days)

### Option 3: Hybrid Approach (Recommended)

**Keep JSONB phenopackets as-is (GA4GH compliant)**
**Add materialized view for variant deduplication:**

```sql
-- Materialized view for unique variants
CREATE MATERIALIZED VIEW unique_variants AS
SELECT DISTINCT ON (gi->'variantInterpretation'->'variation'->>'id')
  gi->'variantInterpretation'->'variation'->>'id' as vrs_id,
  gi->'variantInterpretation'->'variation'->>'label' as label,
  gi->'variantInterpretation'->'variation' as variation,
  COUNT(*) OVER (PARTITION BY gi->'variantInterpretation'->'variation'->>'id') as phenopacket_count
FROM phenopackets pp,
  jsonb_array_elements(pp.phenopacket->'interpretations') AS interp,
  jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') AS gi
WHERE gi->'variantInterpretation' IS NOT NULL;

CREATE UNIQUE INDEX idx_unique_variants_vrs_id ON unique_variants(vrs_id);
```

**Pros:**
- ✅ No phenopacket schema changes (GA4GH compliant)
- ✅ Efficient variant queries via materialized view
- ✅ Easy to implement (1 hour)
- ✅ Can be refreshed periodically

**Cons:**
- ⚠️ Materialized view needs manual refresh
- ⚠️ Still stores full variant in each phenopacket

## Acceptance Criteria

### Investigation Complete
- [ ] SQL query run to count unique variants
- [ ] Recurrent variant query run to check sharing
- [ ] Variant label distribution analyzed
- [ ] Placeholder digest check completed
- [ ] Sample variants inspected manually

### Decision Made
- [ ] Root cause identified (placeholder/non-deterministic/no-dedup/diverse)
- [ ] Decision made: bug fix needed OR no bug (diverse cohort)
- [ ] If bug: implementation approach chosen (Option 1/2/3)

### If Bug Fix Needed
- [ ] Implementation plan documented
- [ ] Timeline estimated
- [ ] Schema changes identified (if any)
- [ ] Migration script updated
- [ ] Tests added for variant deduplication
- [ ] Re-migration completed
- [ ] Verification queries confirm deduplication

### Documentation
- [ ] Findings documented in issue
- [ ] README updated with variant statistics
- [ ] Migration documentation updated
- [ ] Known limitations documented (if any)

## Files Modified (If Bug Fix)

**Investigation Only:**
- None (SQL queries only)

**If Bug Fix (Option 1 - Migration Script):**
- `backend/migration/direct_sheets_to_phenopackets.py` (~50 lines changed)
- `backend/migration/vrs/vrs_builder.py` (~20 lines changed)

**If Bug Fix (Option 2 - Normalized Table):**
- `backend/alembic/versions/xxxx_add_variants_table.py` (new migration)
- `backend/app/phenopackets/models.py` (~50 lines added)
- `backend/app/phenopackets/endpoints.py` (~100 lines changed)
- `backend/migration/direct_sheets_to_phenopackets.py` (~100 lines changed)

**If Bug Fix (Option 3 - Materialized View):**
- `backend/alembic/versions/xxxx_add_unique_variants_view.py` (new migration)
- `backend/app/phenopackets/endpoints.py` (~30 lines added)

## Dependencies

**Blocked by:**
- Issue #56 (ga4gh.vrs installation) - **MUST BE FIXED FIRST**

**Blocks:**
- Variant aggregation queries
- Variant statistics accuracy
- Production data quality

**Requires:**
- Database access
- SQL query execution
- Migration script access

## Timeline

**Investigation Only:** 1 hour

**If Bug Fix:**
- Option 1 (Migration Script): 1 day
- Option 2 (Normalized Table): 3-4 days
- Option 3 (Materialized View): 2 hours

**Total (Investigation + Fix):** 1 hour to 4 days (depends on findings)

## Priority

**P1 (High)** - Data quality investigation

**Rationale:**
- Affects data integrity and variant statistics
- Must be resolved before production deployment
- Quick investigation (1 hour)
- High impact if bug confirmed

**Recommended Timeline:** Investigate immediately (before Issue #52-53)

## Labels

`backend`, `data-quality`, `investigation`, `variants`, `vrs`, `bug`, `p1`

## Related Issues

- Issue #20: Migration script determinism (non-deterministic hash)
- Issue #56: Install ga4gh.vrs (placeholder digests)
- Issue #X: Variant aggregation endpoint (depends on deduplication)

## Testing Verification

### Test 1: Run Investigation Queries
```bash
# Connect to database
psql -d hnf1b_phenopackets -U hnf1b_user

# Run all investigation queries (Step 1-5)
# Document results
```

### Test 2: Verify VRS Digest Determinism
```python
# If Issue #56 fixed:
from ga4gh.core import sha512t24u

variant_data = b'chr17:36098040:A:G'
digest1 = sha512t24u(variant_data)
digest2 = sha512t24u(variant_data)

assert digest1 == digest2, "Digests must be deterministic"
```

### Test 3: Check for Common HNF1B Variants
```sql
-- After fix, verify recurrent variants detected
SELECT
  variant_label,
  phenopacket_count
FROM unique_variants
WHERE phenopacket_count > 10
ORDER BY phenopacket_count DESC;

-- Expect to see:
-- 17q12 deletion (>50 cases)
-- Common missense mutations (>10 cases each)
```

## Known Issues

### Issue 1: Transcript Version Differences
**Problem:** Same variant with different transcript versions
**Example:** `NM_000458.3` vs `NM_000458.4`
**Impact:** Treated as different variants
**Mitigation:** Normalize to latest transcript version (future work)

### Issue 2: HGVS Nomenclature Variations
**Problem:** Different protein notation styles
**Example:** `p.R177X` vs `p.Arg177Ter` vs `p.Arg177*`
**Impact:** Same variant has different labels
**Mitigation:** Strict HGVS validation (future work)

### Issue 3: Genomic vs Transcript Coordinates
**Problem:** Same variant in genomic vs transcript coordinates
**Example:**
- Genomic: `chr17:g.36098040A>G`
- Transcript: `NM_000458.3:c.1337A>G`
**Impact:** Treated as different variants (but VRS should normalize)
**Mitigation:** VRS normalization should handle this

## Future Enhancements (Not in Scope)

- [ ] Variant normalization (left-align indels, canonical transcripts)
- [ ] Variant annotation pipeline (VEP, ClinVar, gnomAD)
- [ ] Variant frequency tracking in cohort
- [ ] Genotype-phenotype correlation analysis
- [ ] Integration with external variant databases
- [ ] Variant pathogenicity prediction
- [ ] Structural variant support (CNVs >50bp)

## Security Considerations

No security impact - data quality investigation only.

## Performance Considerations

**Investigation Queries:**
- May take 5-10 seconds on 864 phenopackets
- Use EXPLAIN ANALYZE for query optimization
- Add indexes if queries are slow

**Materialized View (Option 3):**
- Refresh time: ~1 second for 864 phenopackets
- Scales linearly with phenopacket count
- Refresh strategy: manual or scheduled (daily)
