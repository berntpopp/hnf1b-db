# Issue #56: fix(backend): install ga4gh.vrs for production-ready variant digests

## Overview

Migration script warns: `ga4gh.vrs not available - variant digests will use placeholder values`

**Current:** ga4gh.vrs in optional `phenopackets` dependency group, not installed by default
**Target:** ga4gh.vrs installed and available for proper GA4GH VRS 2.0 variant digest computation

## Why This Matters

### Problem

**Current Behavior:**
```bash
# During phenopacket migration:
WARNING: ga4gh.vrs not available - variant digests will use placeholder values
WARNING: Variants will not be fully GA4GH VRS 2.0 compliant
```

**Impact:**
- ❌ Variant IDs use placeholder digests instead of proper cryptographic hashes
- ❌ Non-standard variant identifiers affecting data interoperability
- ❌ Cannot exchange data with other GA4GH-compliant systems
- ❌ Violates GA4GH VRS 2.0 specification
- ❌ Not production-ready

**Example Non-Compliant Variant:**
```json
{
  "id": "ga4gh:VA.PLACEHOLDER_DIGEST_c7a1e2b3d4f5",  // ❌ Not valid
  "type": "Allele",
  "location": {
    "id": "ga4gh:SL.PLACEHOLDER_DIGEST_a1b2c3d4",  // ❌ Not valid
    "sequenceReference": {
      "refgetAccession": "SQ.PLACEHOLDER_abc123"  // ❌ Not valid
    }
  }
}
```

### Solution

**Install ga4gh.vrs library:**
```bash
cd backend
uv sync --group phenopackets
```

**Result:**
- ✅ Proper cryptographic digest computation
- ✅ GA4GH VRS 2.0 compliant variant identifiers
- ✅ Data interoperability with other systems
- ✅ Production-ready variant representation

**Example Compliant Variant:**
```json
{
  "id": "ga4gh:VA.EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_",  // ✅ Valid digest
  "type": "Allele",
  "location": {
    "id": "ga4gh:SL.v4gbL4vhMfZ3LT8ZNPGJ0GlfbkJq4nkf",  // ✅ Valid digest
    "sequenceReference": {
      "refgetAccession": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul"  // ✅ Valid RefSeq
    }
  }
}
```

## Current State

### Dependency Configuration

**File:** `backend/pyproject.toml`

```toml
[dependency-groups]
phenopackets = [
    "ga4gh-vrs>=2.1.3",  # Line 56 - OPTIONAL group
    "biocommons-seqrepo>=0.6.12",
    "bioutils>=0.5.7"
]
```

**Problem:** `ga4gh.vrs` is in an optional dependency group, not installed by default.

### Installation Check

**Check if ga4gh.vrs is installed:**
```bash
cd backend
uv run python -c "import ga4gh.vrs; print(ga4gh.vrs.__version__)"
```

**Expected Output (if not installed):**
```
ModuleNotFoundError: No module named 'ga4gh.vrs'
```

### Migration Script Behavior

**File:** `backend/migration/vrs/vrs_builder.py`

**Lines 10-20:**
```python
try:
    from ga4gh.vrs import models
    from ga4gh.vrs.dataproxy import SeqRepoRESTDataProxy
    from ga4gh.core import sha512t24u
    VRS_AVAILABLE = True
except ImportError:
    logger.warning(
        "ga4gh.vrs not available - variant digests will use placeholder values. "
        "Install with: uv sync --group phenopackets"
    )
    VRS_AVAILABLE = False
```

**If VRS_AVAILABLE = False:**
- Uses placeholder digests: `PLACEHOLDER_DIGEST_<random>`
- Variants not GA4GH compliant
- Data cannot be exchanged with other systems

## Fix Options

### Option 1: Install Optional Group (Quick Fix)

**For development:**
```bash
cd backend
uv sync --group phenopackets
```

**Pros:**
- ✅ Quick fix (5 minutes)
- ✅ Installs all phenopacket-related dependencies
- ✅ Works immediately

**Cons:**
- ⚠️ Developers must remember to run with `--group phenopackets`
- ⚠️ CI/CD must explicitly install optional group
- ⚠️ Not installed by default in production

### Option 2: Move to Main Dependencies (Recommended)

**Edit:** `backend/pyproject.toml`

**Move from optional group to main dependencies:**
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "ga4gh-vrs>=2.1.3",  # GA4GH VRS 2.0 for variant representation
    "biocommons-seqrepo>=0.6.12",  # Sequence repository for VRS
    "bioutils>=0.5.7",  # Bioinformatics utilities
]

[dependency-groups]
phenopackets = [
    # Remove ga4gh-vrs from here (now in main dependencies)
]
```

**Then install:**
```bash
cd backend
uv sync
```

**Pros:**
- ✅ Installed by default
- ✅ Production-ready
- ✅ CI/CD installs automatically
- ✅ Developers don't need to remember optional flags
- ✅ Proper GA4GH VRS 2.0 compliance

**Cons:**
- ⚠️ Slightly larger dependency footprint (~5MB)
- ⚠️ Requires pyproject.toml change

### Option 3: Document Optional Group (Status Quo)

**Keep in optional group, document in README:**

```markdown
## GA4GH VRS Compliance

For production deployments with variant data, install the phenopackets group:

\`\`\`bash
uv sync --group phenopackets
\`\`\`

This enables proper GA4GH VRS 2.0 compliant variant digests.
```

**Pros:**
- ✅ No code changes needed
- ✅ Keeps main dependencies lean

**Cons:**
- ❌ Easy to forget in production
- ❌ Not beginner-friendly
- ❌ CI/CD must be configured correctly
- ❌ Data quality risk if forgotten

## Recommended Solution

**Use Option 2: Move to Main Dependencies**

**Rationale:**
- HNF1B-DB is a **genomic database** - variant representation is core functionality
- GA4GH VRS compliance is essential for data interoperability
- Production deployments should have this by default
- Small dependency cost (~5MB) is acceptable
- Reduces risk of misconfiguration

## Implementation Steps

### Step 1: Move Dependencies (5 min)

**Edit:** `backend/pyproject.toml`

```toml
[project]
dependencies = [
    # ... existing dependencies ...

    # GA4GH VRS dependencies (moved from optional group)
    "ga4gh-vrs>=2.1.3",
    "biocommons-seqrepo>=0.6.12",
    "bioutils>=0.5.7",
]

[dependency-groups]
phenopackets = [
    # Optional: Add any future phenopacket-specific tools here
]
```

### Step 2: Reinstall Dependencies (2 min)

```bash
cd backend
uv sync
```

### Step 3: Verify Installation (1 min)

```bash
uv run python -c "import ga4gh.vrs; print('✓ ga4gh.vrs version:', ga4gh.vrs.__version__)"
uv run python -c "from ga4gh.core import sha512t24u; print('✓ SHA512t24u available')"
```

**Expected Output:**
```
✓ ga4gh.vrs version: 2.1.3
✓ SHA512t24u available
```

### Step 4: Test Migration (5 min)

```bash
# Run migration script (dry run)
uv run python -m migration.direct_sheets_to_phenopackets --dry-run

# Check logs - should NOT see warning:
# ✓ No "ga4gh.vrs not available" warning
# ✓ Variant digests use proper computation
```

### Step 5: Verify Variant Digests (5 min)

**Query database for variant:**
```sql
SELECT
    phenopacket_id,
    jsonb_path_query(
        phenopacket,
        '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.variation'
    ) AS variant
FROM phenopackets
WHERE phenopacket -> 'interpretations' IS NOT NULL
LIMIT 1;
```

**Check variant ID format:**
```json
{
  "id": "ga4gh:VA.EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_"
  // ✓ Should NOT contain "PLACEHOLDER"
  // ✓ Should be 32 characters after "ga4gh:VA."
  // ✓ Should use base64url encoding (- and _)
}
```

## Acceptance Criteria

### Installation
- [ ] `ga4gh.vrs` library installed (version ≥2.1.3)
- [ ] `biocommons-seqrepo` installed (version ≥0.6.12)
- [ ] `bioutils` installed (version ≥0.5.7)
- [ ] Dependencies in main `[project.dependencies]` section
- [ ] `uv sync` installs VRS dependencies by default

### Functionality
- [ ] No "ga4gh.vrs not available" warning during migration
- [ ] Variant digests use proper SHA512t24u computation
- [ ] Variant IDs follow format: `ga4gh:VA.<base64url_32chars>`
- [ ] Location IDs follow format: `ga4gh:SL.<base64url_32chars>`
- [ ] No "PLACEHOLDER" strings in variant IDs

### Data Quality
- [ ] All variants in database have proper GA4GH VRS 2.0 IDs
- [ ] Variant digests are deterministic (same variant → same ID)
- [ ] RefSeq accessions use proper format
- [ ] Data is interoperable with other GA4GH systems

### Documentation
- [ ] README updated with VRS dependency information
- [ ] Migration documentation mentions VRS requirement
- [ ] CI/CD pipeline installs dependencies correctly

## Files Modified

### Primary Changes
- `backend/pyproject.toml` (~5 lines changed)
  - Move `ga4gh-vrs` to main dependencies
  - Move `biocommons-seqrepo` to main dependencies
  - Move `bioutils` to main dependencies

### Documentation Updates
- `backend/README.md` (~10 lines added)
  - Document GA4GH VRS dependency
  - Explain variant digest computation
- `backend/CLAUDE.md` (~5 lines updated)
  - Update dependency installation instructions

### Testing Updates
- `backend/.github/workflows/ci.yml` (~5 lines updated, if applicable)
  - Ensure CI installs dependencies correctly

**Total changes:** ~25 lines across 3-4 files

## Dependencies

**Blocked by:** None - independent fix

**Blocks:**
- Proper GA4GH VRS 2.0 compliance
- Data interoperability with external systems
- Production deployment readiness

**Requires:**
- `ga4gh.vrs>=2.1.3`
- `biocommons-seqrepo>=0.6.12`
- `bioutils>=0.5.7`

## Timeline

**Estimated:** 30 minutes

**Breakdown:**
- Step 1 (Edit pyproject.toml): 5 minutes
- Step 2 (Reinstall): 2 minutes
- Step 3 (Verify): 1 minute
- Step 4 (Test migration): 5 minutes
- Step 5 (Verify digests): 5 minutes
- Documentation: 10 minutes
- Testing: 5 minutes

**Total:** ~33 minutes (round to 30 min)

## Priority

**P1 (High)** - Data quality / GA4GH compliance

**Rationale:**
- Affects data quality and interoperability
- Required for production deployment
- GA4GH VRS compliance is essential
- Quick fix (30 minutes)
- Prevents future data migration issues

**Recommended Timeline:** Fix before production deployment

## Labels

`backend`, `dependencies`, `data-quality`, `ga4gh`, `vrs`, `p1`, `bug`

## Testing Verification

### Test 1: Library Import
```bash
cd backend
uv run python -c "import ga4gh.vrs; print('✓ ga4gh.vrs:', ga4gh.vrs.__version__)"
```

**Expected:** `✓ ga4gh.vrs: 2.1.3` (or higher)

### Test 2: Digest Computation
```bash
uv run python -c "
from ga4gh.core import sha512t24u
digest = sha512t24u('test_data'.encode())
print('✓ Digest:', digest)
print('✓ Length:', len(digest))
assert len(digest) == 32, 'Digest should be 32 chars'
"
```

**Expected:**
```
✓ Digest: EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_
✓ Length: 32
```

### Test 3: Migration Warning Check
```bash
uv run python -m migration.direct_sheets_to_phenopackets --dry-run 2>&1 | grep -i "vrs not available"
```

**Expected:** No output (warning should not appear)

### Test 4: Variant ID Format
```sql
-- Check variant IDs in database
SELECT
    phenopacket_id,
    jsonb_path_query(
        phenopacket,
        '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.variation.id'
    ) AS variant_id
FROM phenopackets
WHERE phenopacket -> 'interpretations' IS NOT NULL
LIMIT 5;
```

**Expected:**
```
variant_id: "ga4gh:VA.EgHPXXhULTwoP4-ACfs-YCXaeUQJBjH_"
variant_id: "ga4gh:VA.v4gbL4vhMfZ3LT8ZNPGJ0GlfbkJq4nkf"
...
```

**Should NOT see:**
```
variant_id: "ga4gh:VA.PLACEHOLDER_DIGEST_c7a1e2b3d4f5"  // ❌ Bad
```

### Test 5: Deterministic Digests
```bash
uv run python -c "
from ga4gh.vrs import models
from ga4gh.core import sha512t24u

# Create same variant twice
data = b'chr17:41234470:G:A'
digest1 = sha512t24u(data)
digest2 = sha512t24u(data)

assert digest1 == digest2, 'Digests should be deterministic'
print('✓ Digests are deterministic')
"
```

**Expected:** `✓ Digests are deterministic`

## Known Issues

### Issue 1: SeqRepo Data
**Problem:** `biocommons-seqrepo` requires external sequence data
**Impact:** RefSeq accessions may still use placeholders if SeqRepo not configured
**Workaround:** Migration script uses RefGet placeholders (acceptable for now)
**Future:** Set up local SeqRepo instance for full compliance

### Issue 2: VRS 2.0 vs 1.x
**Problem:** Some older tools use VRS 1.x
**Impact:** Minor compatibility issues with legacy systems
**Mitigation:** VRS 2.0 is current standard, backward compatibility exists

## Future Enhancements (Not in Scope)

- [ ] Set up local SeqRepo instance for full RefSeq resolution
- [ ] Add VRS validation tests to CI/CD pipeline
- [ ] Implement VRS digest caching for performance
- [ ] Add VRS normalization (canonical alleles)
- [ ] Support for complex variants (structural variants, CNVs)
- [ ] Integration with VRS Python API for variant lookups

## Security Considerations

### Dependency Trust
- `ga4gh.vrs` is official GA4GH library (trusted source)
- Maintained by Global Alliance for Genomics and Health
- Used by major genomics projects worldwide
- Regular security updates

### Data Integrity
- Cryptographic digests ensure data integrity
- Deterministic computation enables verification
- Placeholder digests were insecure (guessable)
- Proper digests prevent ID collisions

## Performance Considerations

### Installation Time
- `ga4gh.vrs` installation: ~30 seconds
- Dependencies download: ~5MB
- No impact on application startup time

### Runtime Performance
- Digest computation: <1ms per variant
- No performance degradation
- Caching can be added if needed (not in scope)

### Memory Usage
- `ga4gh.vrs` library: ~10MB memory footprint
- Acceptable for backend server
- No impact on frontend

## Rollback Strategy

If issues arise:

1. **Revert pyproject.toml:**
   ```bash
   git checkout HEAD -- pyproject.toml
   uv sync
   ```

2. **Optional group still works:**
   ```bash
   uv sync --group phenopackets  # If needed
   ```

**Impact:** Minimal - reverts to placeholder digests (non-compliant but functional)

## Related Issues

- Issue #20: Migration script determinism (used `hash()` instead of `sha512t24u`)
- Issue #X: VRS builder implementation (already expects ga4gh.vrs)
- Issue #X: Phenopacket migration (generates variants)

## Reference Documentation

- [GA4GH VRS Specification](https://vrs.ga4gh.org/)
- [VRS Python Library](https://github.com/ga4gh/vrs-python)
- [RefGet Specification](https://samtools.github.io/hts-specs/refget.html)
- [Migration VRS Builder Code](../backend/migration/vrs/vrs_builder.py)
