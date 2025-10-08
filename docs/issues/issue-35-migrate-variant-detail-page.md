# Issue #35: feat(frontend): migrate variant detail page to interpretation view

## Overview

The variant detail page (`frontend/src/views/PageVariant.vue`) displays data from a separate variants table. Needs migration to show detailed variant information from phenopacket interpretations, including all individuals with this variant.

**Current State:** `/variants/:variant_id` → Shows single variant from variants table (404)
**Required State:** `/variants/:variant_id` → Display variant details + all phenopackets containing it

## Why This Matters

### Current Implementation (Broken)

```javascript
// GET /api/variants/V001 → 404 Not Found
const variant = {
  variant_id: "V001",
  variant_ref: "NM_000458.3:c.123A>G",
  gene: "HNF1B",
  detection_method: "NGS",
  pathogenicity: "PATHOGENIC"
};
```

**Problem:** Variants table doesn't exist. Need to query phenopackets containing this variant.

### New Implementation (Phenopackets v2)

```javascript
// GET /api/v2/phenopackets/by-variant/var:HNF1B:17:36459258-37832869:DEL
{
  variant: {
    id: "var:HNF1B:17:36459258-37832869:DEL",
    label: "HNF1B DEL (1.37Mb)",
    gene: {
      symbol: "HNF1B",
      hgnc_id: "HGNC:5024"
    },
    vcf: {
      genomeAssembly: "GRCh38",
      chrom: "17",
      pos: 36459258,
      ref: "T",
      alt: "<DEL>"
    },
    structural_type: "deletion",
    pathogenicity: "PATHOGENIC"
  },
  phenopackets: [
    {
      phenopacket_id: "phenopacket-1",
      subject_id: "patient-001",
      sex: "FEMALE",
      primary_disease: "HNF1B-related disorder",
      interpretation_status: "CAUSATIVE"
    },
    // ... 41 more
  ],
  count: 42
}
```

## Required Changes

### 1. Update API Client

**File:** `frontend/src/api/index.js`

```javascript
/**
 * Get variant details and all phenopackets containing it
 */
export async function getVariantDetails(variantId) {
  return apiClient.get(`/phenopackets/by-variant/${variantId}`);
}
```

### 2. Page Layout Structure

```vue
<template>
  <v-container fluid>
    <!-- Header: Variant Summary -->
    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-title class="text-h4">
            <v-icon left color="primary">mdi-dna</v-icon>
            {{ variant.label }}
          </v-card-title>
          <v-card-subtitle>
            <v-chip color="blue" class="mr-2">
              {{ variant.gene.symbol }}
            </v-chip>
            <v-chip :color="getPathogenicityColor(variant.pathogenicity)">
              {{ variant.pathogenicity }}
            </v-chip>
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <!-- 2-Column Layout -->
    <v-row>
      <!-- Left: Variant Details -->
      <v-col cols="12" md="6">
        <VariantDetailsCard :variant="variant" />
      </v-col>

      <!-- Right: Gene Context -->
      <v-col cols="12" md="6">
        <GeneContextCard :gene="variant.gene" />
      </v-col>

      <!-- VCF Record (Full Width) -->
      <v-col cols="12">
        <VcfRecordCard :vcf="variant.vcf" />
      </v-col>

      <!-- Affected Individuals Table (Full Width) -->
      <v-col cols="12">
        <AffectedIndividualsCard
          :phenopackets="phenopackets"
          :variant-id="variant.id"
        />
      </v-col>
    </v-row>
  </v-container>
</template>
```

### 3. Component Cards

#### VariantDetailsCard.vue

```vue
<template>
  <v-card outlined>
    <v-card-title class="bg-blue-lighten-5">
      <v-icon left>mdi-information</v-icon>
      Variant Details
    </v-card-title>
    <v-card-text>
      <v-list density="compact">
        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            VRS ID
          </v-list-item-title>
          <v-list-item-subtitle class="text-mono">
            {{ variant.id }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Label
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ variant.label }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="variant.structural_type">
          <v-list-item-title class="font-weight-bold">
            Type
          </v-list-item-title>
          <v-list-item-subtitle>
            <v-chip size="small" color="purple">
              {{ variant.structural_type }}
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            ACMG Classification
          </v-list-item-title>
          <v-list-item-subtitle>
            <v-chip
              :color="getPathogenicityColor(variant.pathogenicity)"
              size="small"
            >
              {{ variant.pathogenicity }}
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>
```

#### GeneContextCard.vue

```vue
<template>
  <v-card outlined>
    <v-card-title class="bg-green-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Gene Context
    </v-card-title>
    <v-card-text>
      <v-list density="compact">
        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Gene Symbol
          </v-list-item-title>
          <v-list-item-subtitle>
            <v-chip
              :href="`https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${gene.hgnc_id}`"
              target="_blank"
              color="green"
              size="small"
            >
              {{ gene.symbol }}
              <v-icon right size="small">mdi-open-in-new</v-icon>
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            HGNC ID
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ gene.hgnc_id }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            External Links
          </v-list-item-title>
          <v-list-item-subtitle>
            <v-btn
              :href="`https://www.ncbi.nlm.nih.gov/gene/?term=${gene.symbol}`"
              target="_blank"
              size="small"
              variant="text"
              color="primary"
            >
              NCBI Gene
              <v-icon right size="small">mdi-open-in-new</v-icon>
            </v-btn>
            <v-btn
              :href="`https://www.omim.org/search?search=${gene.symbol}`"
              target="_blank"
              size="small"
              variant="text"
              color="primary"
            >
              OMIM
              <v-icon right size="small">mdi-open-in-new</v-icon>
            </v-btn>
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>
```

#### VcfRecordCard.vue

```vue
<template>
  <v-card outlined>
    <v-card-title class="bg-orange-lighten-5">
      <v-icon left>mdi-file-code</v-icon>
      VCF Record
    </v-card-title>
    <v-card-text>
      <v-list density="compact">
        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Genome Assembly
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ vcf.genomeAssembly }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Chromosome
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ vcf.chrom }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Position
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ vcf.pos.toLocaleString() }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Reference
          </v-list-item-title>
          <v-list-item-subtitle class="text-mono">
            {{ vcf.ref }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            Alternate
          </v-list-item-title>
          <v-list-item-subtitle class="text-mono">
            {{ vcf.alt }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-divider class="my-2" />

        <v-list-item>
          <v-list-item-title class="font-weight-bold">
            VCF String
          </v-list-item-title>
          <v-list-item-subtitle>
            <code class="text-caption">
              chr{{ vcf.chrom }}:{{ vcf.pos }}-{{ vcf.ref }}-{{ vcf.alt }}
            </code>
            <v-btn
              icon="mdi-content-copy"
              size="x-small"
              variant="text"
              @click="copyToClipboard(vcfString)"
            />
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>
```

#### AffectedIndividualsCard.vue

```vue
<template>
  <v-card outlined>
    <v-card-title class="bg-purple-lighten-5">
      <v-icon left>mdi-account-multiple</v-icon>
      Affected Individuals ({{ phenopackets.length }})
    </v-card-title>
    <v-card-text>
      <v-data-table
        :headers="headers"
        :items="phenopackets"
        density="compact"
        :items-per-page="10"
      >
        <!-- Phenopacket ID as link -->
        <template #item.phenopacket_id="{ item }">
          <v-chip
            :to="`/phenopackets/${item.phenopacket_id}`"
            color="lime-lighten-2"
            size="small"
            link
          >
            {{ item.phenopacket_id }}
            <v-icon right size="small">mdi-open-in-new</v-icon>
          </v-chip>
        </template>

        <!-- Sex with icon -->
        <template #item.sex="{ item }">
          <v-icon :color="getSexColor(item.sex)" size="small" class="mr-1">
            {{ getSexIcon(item.sex) }}
          </v-icon>
          {{ formatSex(item.sex) }}
        </template>

        <!-- Interpretation status -->
        <template #item.interpretation_status="{ item }">
          <v-chip
            :color="getInterpretationColor(item.interpretation_status)"
            size="small"
          >
            {{ item.interpretation_status }}
          </v-chip>
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>
```

---

## Backend Endpoint Specification

### Endpoint Contract

```http
GET /api/v2/phenopackets/by-variant/{variant_id}

Path Parameters:
- variant_id (str, required): VRS variant ID or genomic coordinate string
  Examples:
  - "var:HNF1B:17:36459258-37832869:DEL"
  - "chr17:36459258-T-<DEL>"

Query Parameters:
- skip (int, optional): Pagination offset for phenopackets list (default: 0)
- limit (int, optional): Max phenopackets to return (default: 50)
- include_full_phenopackets (bool, optional): Return full phenopackets or summaries (default: false)

Response: 200 OK
{
  "variant": {
    "id": "var:HNF1B:17:36459258-37832869:DEL",
    "label": "HNF1B DEL (1.37Mb)",
    "gene": {
      "symbol": "HNF1B",
      "hgnc_id": "HGNC:5024"
    },
    "vcf": {
      "genomeAssembly": "GRCh38",
      "chrom": "17",
      "pos": 36459258,
      "ref": "T",
      "alt": "<DEL>"
    },
    "structural_type": "deletion",
    "pathogenicity": "PATHOGENIC"
  },
  "phenopackets": [
    {
      "phenopacket_id": "phenopacket-001",
      "subject_id": "PATIENT-001",
      "sex": "FEMALE",
      "primary_disease": "MONDO:0013894",
      "interpretation_status": "CAUSATIVE"
    }
  ],
  "total_count": 42,
  "skip": 0,
  "limit": 50
}

Response: 404 Not Found
{
  "error": "Variant not found",
  "variant_id": "invalid-id"
}
```

### Variant Matching Logic

**Problem:** How to match variant_id from URL to variants in phenopackets?

**Recommended Strategy:**

```python
def find_phenopackets_by_variant(variant_id: str):
    """
    Find all phenopackets containing a specific variant.

    Matching logic:
    1. Exact VRS ID match (preferred)
    2. Genomic coordinate match (fallback)
    3. Label fuzzy match (last resort)
    """

    # Normalize input
    normalized_id = normalize_variant_id(variant_id)

    # Query phenopackets
    query = """
        SELECT DISTINCT
            p.id,
            p.jsonb->>'subject'->>'id' AS subject_id,
            vi.variant_interpretation
        FROM phenopackets p,
            JSONB_ARRAY_ELEMENTS(p.jsonb->'interpretations') AS interp,
            JSONB_ARRAY_ELEMENTS(interp->'diagnosis'->'genomicInterpretations') AS gi,
            LATERAL (
                SELECT gi->'variantInterpretation' AS variant_interpretation
            ) AS vi
        WHERE (
            -- Match 1: Exact VRS ID
            vi.variant_interpretation->'variationDescriptor'->>'id' = :variant_id
            OR
            -- Match 2: Genomic coordinates (if variant_id is coordinate string)
            (vi.variant_interpretation->'variationDescriptor'->'vcfRecord'->>'chrom' = :chrom
             AND vi.variant_interpretation->'variationDescriptor'->'vcfRecord'->>'pos' = :pos
             AND vi.variant_interpretation->'variationDescriptor'->'vcfRecord'->>'ref' = :ref
             AND vi.variant_interpretation->'variationDescriptor'->'vcfRecord'->>'alt' = :alt)
            OR
            -- Match 3: Label match (URL-encoded labels)
            vi.variant_interpretation->'variationDescriptor'->>'label' = :variant_id
        )
        LIMIT :limit OFFSET :skip
    """

    # Handle coordinate-based lookup
    if "chr" in variant_id and ":" in variant_id:
        # Parse "chr17:36459258-T-<DEL>" format
        chrom, rest = variant_id.split(":")
        chrom = chrom.replace("chr", "")  # Normalize "chr17" → "17"
        pos, ref, alt = parse_vcf_string(rest)
        params = {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}
    else:
        params = {"variant_id": normalized_id}

    return await db.execute(query, {**params, "limit": limit, "skip": skip})
```

**Edge Cases:**
- **VRS ID variations**: Handle both `var:HNF1B:...` and URL-encoded versions
- **Chromosome naming**: Normalize `chr17` and `17` to match consistently
- **Reference genome mismatch**: If variant lifted from GRCh37 to GRCh38, coordinates differ
- **Missing VRS IDs**: Some variants may only have labels - match by label as fallback

### Response Format Options

**Problem:** Should endpoint return full phenopackets or summaries?

**Recommendation:** **Summaries by default** (faster), full phenopackets on request

```python
# Summary format (default - fast)
{
  "phenopacket_id": "phenopacket-001",
  "subject_id": "PATIENT-001",
  "sex": "FEMALE",
  "primary_disease": "MONDO:0013894",
  "disease_label": "HNF1B-related disorder",
  "interpretation_status": "CAUSATIVE",
  "phenotype_count": 8
}

# Full phenopacket (include_full_phenopackets=true - slow)
{
  "id": "phenopacket-001",
  "subject": { ... },  # Full subject object
  "phenotypicFeatures": [ ... ],  # All phenotypes
  "diseases": [ ... ],  # All diseases
  "interpretations": [ ... ]  # All interpretations
}
```

**Performance Impact:**
- Summaries: ~50ms for 42 phenopackets
- Full phenopackets: ~300ms for 42 phenopackets (due to JSONB size)

### Performance Requirements

**Target Performance:**
- Response time: **< 200ms** for summary format (default)
- Response time: **< 1000ms** for full phenopackets (include_full_phenopackets=true)
- Pagination: Support up to **100 affected individuals**

**Required Database Indexes:**

```sql
-- Index for variant ID lookups
CREATE INDEX idx_phenopackets_variant_id ON phenopackets
USING GIN ((jsonb -> 'interpretations' -> 'diagnosis' -> 'genomicInterpretations' -> 'variantInterpretation' -> 'variationDescriptor' -> 'id'));

-- Index for VCF coordinate lookups (fallback)
CREATE INDEX idx_phenopackets_vcf_coords ON phenopackets
USING GIN ((jsonb -> 'interpretations' -> 'diagnosis' -> 'genomicInterpretations' -> 'variantInterpretation' -> 'variationDescriptor' -> 'vcfRecord'));

-- Index for label lookups (last resort)
CREATE INDEX idx_phenopackets_variant_label ON phenopackets
USING GIN ((jsonb -> 'interpretations' -> 'diagnosis' -> 'genomicInterpretations' -> 'variantInterpretation' -> 'variationDescriptor' -> 'label'));
```

### Error Handling

```python
# 1. Variant not found in any phenopacket
Response: 404 Not Found
{
  "error": "Variant not found",
  "variant_id": "var:HNF1B:17:99999999-99999999:DEL",
  "searched_phenopackets": 864
}

# 2. Invalid variant ID format
Response: 400 Bad Request
{
  "error": "Invalid variant ID format",
  "variant_id": "not-a-valid-id",
  "expected_formats": [
    "var:GENE:CHROM:START-END:TYPE",
    "chrCHROM:POS-REF-ALT",
    "Variant label string"
  ]
}

# 3. Empty result (variant exists but no phenopackets match)
Response: 200 OK
{
  "variant": { ... },  # Variant metadata inferred from first match
  "phenopackets": [],
  "total_count": 0
}
```

### Variant Metadata Extraction

**Problem:** Where does variant metadata come from if no longer stored in separate table?

**Solution:** Extract from first matching phenopacket's variantInterpretation

```python
async def get_variant_metadata(variant_id: str):
    """
    Extract variant metadata from first phenopacket containing it.

    This avoids needing a separate variants table.
    """
    query = """
        SELECT
            vi.variant_interpretation->'variationDescriptor' AS vd,
            vi.variant_interpretation->>'acmgPathogenicityClassification' AS pathogenicity
        FROM phenopackets p,
            JSONB_ARRAY_ELEMENTS(p.jsonb->'interpretations') AS interp,
            JSONB_ARRAY_ELEMENTS(interp->'diagnosis'->'genomicInterpretations') AS gi,
            LATERAL (
                SELECT gi->'variantInterpretation' AS variant_interpretation
            ) AS vi
        WHERE vi.variant_interpretation->'variationDescriptor'->>'id' = :variant_id
        LIMIT 1  -- Only need one to extract metadata
    """

    result = await db.execute(query, {"variant_id": variant_id})
    if not result:
        raise VariantNotFoundError(variant_id)

    # Extract metadata from variationDescriptor
    vd = result[0]["vd"]
    return {
        "id": vd.get("id"),
        "label": vd.get("label"),
        "gene": vd.get("geneContext", {}),
        "vcf": vd.get("vcfRecord", {}),
        "structural_type": vd.get("structuralType", {}).get("label"),
        "pathogenicity": result[0]["pathogenicity"]
    }
```

### Testing Requirements

**Backend tests must verify:**
- [ ] Exact VRS ID match works
- [ ] Genomic coordinate match works (chr17:pos-ref-alt format)
- [ ] Handles URL-encoded variant IDs
- [ ] Returns correct phenopacket count
- [ ] Pagination works (skip/limit)
- [ ] Summary format is fast (< 200ms)
- [ ] Full phenopacket format works
- [ ] 404 for non-existent variants
- [ ] 400 for malformed variant IDs
- [ ] Handles variants with missing VRS IDs (label fallback)
- [ ] Normalizes chromosome names (chr17 vs 17)

---

## Implementation Checklist

### Phase 1: Backend Endpoint
- [ ] Create `/api/v2/phenopackets/by-variant/{id}` endpoint (Backend issue)
- [ ] Implement variant matching logic (VRS ID → coordinates → label)
- [ ] Return variant details + list of phenopackets
- [ ] Add pagination for affected individuals
- [ ] Add summary vs full phenopacket toggle

### Phase 2: API Client
- [ ] Add `getVariantDetails()` function
- [ ] Test endpoint returns correct data

### Phase 3: Component Cards
- [ ] Create `VariantDetailsCard.vue`
- [ ] Create `GeneContextCard.vue`
- [ ] Create `VcfRecordCard.vue`
- [ ] Create `AffectedIndividualsCard.vue`

### Phase 4: Main Page
- [ ] Implement `PageVariant.vue` with new layout
- [ ] Add loading state
- [ ] Add error handling (404 if variant not found)
- [ ] Integrate all card components

### Phase 5: Testing
- [ ] Test variant page loads correctly
- [ ] Test all external links work (HGNC, NCBI, OMIM)
- [ ] Test clicking affected individual navigates correctly
- [ ] Test copy VCF string button
- [ ] Test 404 handling for invalid variant IDs

## Acceptance Criteria

### Functionality
- [ ] Page displays complete variant information
- [ ] Shows all individuals with this variant
- [ ] External gene links work (HGNC, NCBI, OMIM)
- [ ] VCF string copy-to-clipboard works
- [ ] Clicking individual navigates to phenopacket detail

### Data Display
- [ ] VRS variant ID shown
- [ ] Gene symbol with HGNC link
- [ ] VCF record details (chrom, pos, ref, alt)
- [ ] ACMG pathogenicity classification color-coded
- [ ] List of affected individuals with key info

### UI/UX
- [ ] 2-column responsive layout
- [ ] Color-coded cards by section
- [ ] Loading spinner during fetch
- [ ] Error message on 404
- [ ] Monospace font for technical IDs

### Code Quality
- [ ] ESLint passes
- [ ] Reusable card components
- [ ] Props validated
- [ ] No console errors

## Dependencies

**Depends On:**
- Issue #34 (Variants view) - Navigation
- **Backend issue:** Create `/by-variant/{id}` endpoint - ⚠️ **BLOCKER**

**Blocks:**
- None

## Files to Create/Modify

```
frontend/src/api/
└── index.js                                # Add getVariantDetails()

frontend/src/views/
└── PageVariant.vue                         # Rewrite (250+ lines)

frontend/src/components/variant/           # NEW
├── VariantDetailsCard.vue                 # NEW (80 lines)
├── GeneContextCard.vue                    # NEW (100 lines)
├── VcfRecordCard.vue                      # NEW (120 lines)
└── AffectedIndividualsCard.vue            # NEW (150 lines)
```

## Priority

**P1 (High)** - Core functionality

## Labels

`frontend`, `views`, `components`, `phenopackets`, `p1`

## Timeline

- **Phase 1:** Backend endpoint - 4 hours (Backend team)
- **Phase 2:** API client - 1 hour
- **Phase 3:** Component cards - 4 hours
- **Phase 4:** Main page - 3 hours
- **Phase 5:** Testing - 2 hours

**Total:** 10 hours (1.5 days) - Frontend only
