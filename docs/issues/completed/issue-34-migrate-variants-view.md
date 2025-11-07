# Issue #34: feat(frontend): migrate variants view to phenopacket interpretations

## Overview

The variants view (`frontend/src/views/Variants.vue`) displays data from a separate variants table that no longer exists. Needs migration to extract variants from `phenopacket.interpretations[]` structure.

**Current State:** `/variants` → Shows variants from normalized variants table (404)
**Required State:** `/variants` → Display variants extracted from phenopacket interpretations

## Why This Matters

### Current Implementation (Broken)

```javascript
// GET /api/variants/ → 404 Not Found
const variants = [
  {
    variant_id: "V001",
    variant_ref: "NM_000458.3:c.123A>G",
    detection_method: "NGS",
    segregation: "De novo"
  }
];
```

**Problem:** Variants table doesn't exist. Data now lives in phenopacket interpretations.

### New Implementation (Phenopackets v2)

```javascript
// Extract variants from all phenopackets
// GET /api/v2/phenopackets/aggregate/variants

const variants = [
  {
    variant_id: "var:HNF1B:17:36459258-37832869:DEL",
    label: "HNF1B DEL (1.37Mb)",
    gene: {
      symbol: "HNF1B",
      hgnc_id: "HGNC:5024"
    },
    vcf: {
      chrom: "17",
      pos: 36459258,
      ref: "T",
      alt: "<DEL>"
    },
    pathogenicity: "PATHOGENIC",
    phenopacket_count: 42,  // How many individuals have this variant
    phenopacket_ids: ["phenopacket-1", "phenopacket-2", ...]
  }
];
```

## Data Extraction Strategy

### Variants Location in Phenopackets

```javascript
phenopacket.interpretations[].diagnosis.genomicInterpretations[].variantInterpretation
```

Full path:
```javascript
phenopacket: {
  interpretations: [
    {
      diagnosis: {
        genomicInterpretations: [
          {
            variantInterpretation: {
              acmgPathogenicityClassification: "PATHOGENIC",
              variationDescriptor: {
                id: "var:HNF1B:17:36459258-37832869:DEL",
                label: "HNF1B DEL (1.37Mb)",
                geneContext: {
                  valueId: "HGNC:5024",
                  symbol: "HNF1B"
                },
                vcfRecord: {
                  genomeAssembly: "GRCh38",
                  chrom: "17",
                  pos: 36459258,
                  ref: "T",
                  alt: "<DEL>"
                },
                structuralType: {
                  id: "SO:0000159",
                  label: "deletion"
                }
              }
            }
          }
        ]
      }
    }
  ]
}
```

### Backend Aggregation Needed

**New Endpoint (Backend Issue):**
```http
GET /api/v2/phenopackets/aggregate/variants?limit=100

Response:
[
  {
    "variant_id": "var:HNF1B:17:36459258-37832869:DEL",
    "label": "HNF1B DEL (1.37Mb)",
    "gene_symbol": "HNF1B",
    "gene_id": "HGNC:5024",
    "structural_type": "deletion",
    "pathogenicity": "PATHOGENIC",
    "phenopacket_count": 42,
    "vcf_string": "chr17:36459258-T-<DEL>"
  },
  ...
]
```

**Note:** This requires backend work to aggregate unique variants across all phenopackets.

---

## Backend Endpoint Specification

### Endpoint Contract

```http
GET /api/v2/phenopackets/aggregate/variants

Query Parameters:
- limit (int, optional): Maximum variants to return (default: 100)
- pathogenicity (str, optional): Filter by ACMG classification
  Values: PATHOGENIC | LIKELY_PATHOGENIC | UNCERTAIN_SIGNIFICANCE | LIKELY_BENIGN | BENIGN
- gene (str, optional): Filter by gene symbol (e.g., "HNF1B")
- skip (int, optional): Pagination offset (default: 0)

Response: 200 OK
[
  {
    "variant_id": "var:HNF1B:17:36459258-37832869:DEL",  // VRS ID or custom identifier
    "label": "HNF1B DEL (1.37Mb)",
    "gene_symbol": "HNF1B",
    "gene_id": "HGNC:5024",
    "structural_type": "deletion",  // from SO ontology
    "pathogenicity": "PATHOGENIC",  // ACMG classification
    "phenopacket_count": 42,        // number of individuals
    "vcf_string": "chr17:36459258-T-<DEL>"
  }
]
```

### Uniqueness Criteria

**Problem:** How to determine "unique" variants across phenopackets?

**Recommended Strategy:**
```python
# Uniqueness determined by VRS variant ID
# If VRS ID not available, fallback to genomic coordinates

def get_variant_key(variant_interpretation):
    """
    Uniqueness key for variant deduplication.

    Priority:
    1. VRS ID (variationDescriptor.id)
    2. Genomic coordinates (chrom:pos:ref:alt)
    3. Label hash (fallback)
    """
    vd = variant_interpretation.get('variationDescriptor', {})

    # Option 1: VRS ID (preferred)
    if vd.get('id'):
        return vd['id']

    # Option 2: VCF coordinates
    vcf = vd.get('vcfRecord', {})
    if vcf.get('chrom') and vcf.get('pos'):
        return f"{vcf['chrom']}:{vcf['pos']}:{vcf.get('ref', '')}:{vcf.get('alt', '')}"

    # Option 3: Label (last resort)
    return vd.get('label', 'unknown')
```

**Special Cases:**
- **Same variant, different pathogenicity**: Keep separate entries (important clinical distinction)
- **Missing VRS ID**: Use genomic coordinates as fallback
- **Structural variants**: Use start:end coordinates for CNVs

### Aggregation Algorithm

```python
# Pseudocode for backend implementation

async def aggregate_variants(limit=100, pathogenicity=None, gene=None):
    """
    Aggregate unique variants across all phenopackets.

    Returns: List of unique variants with phenopacket counts
    """

    # Query: Extract all variants from JSONB
    query = """
        SELECT DISTINCT
            vi.variant_interpretation->>'variationDescriptor'->'id' AS variant_id,
            vi.variant_interpretation->>'variationDescriptor'->'label' AS label,
            vi.variant_interpretation->>'acmgPathogenicityClassification' AS pathogenicity,
            COUNT(DISTINCT p.id) AS phenopacket_count,
            ARRAY_AGG(DISTINCT p.id) AS phenopacket_ids
        FROM phenopackets p,
            JSONB_ARRAY_ELEMENTS(p.jsonb->'interpretations') AS interp,
            JSONB_ARRAY_ELEMENTS(interp->'diagnosis'->'genomicInterpretations') AS gi,
            LATERAL (
                SELECT gi->'variantInterpretation' AS variant_interpretation
            ) AS vi
        WHERE vi.variant_interpretation IS NOT NULL
    """

    # Apply filters
    if pathogenicity:
        query += f" AND vi.variant_interpretation->>'acmgPathogenicityClassification' = '{pathogenicity}'"

    if gene:
        query += f" AND vi.variant_interpretation->'variationDescriptor'->'geneContext'->>'symbol' = '{gene}'"

    # Group by variant_id
    query += """
        GROUP BY variant_id, label, pathogenicity
        ORDER BY phenopacket_count DESC
        LIMIT :limit
    """

    results = await db.execute(query, {"limit": limit})

    # Format response
    return [
        {
            "variant_id": row.variant_id,
            "label": row.label,
            "pathogenicity": row.pathogenicity,
            "phenopacket_count": row.phenopacket_count,
            "phenopacket_ids": row.phenopacket_ids
        }
        for row in results
    ]
```

### Performance Requirements

**Target Performance:**
- Response time: **< 500ms** for top 100 variants
- Response time: **< 1000ms** for filtered queries
- Pagination: Support up to **1000 variants** total

**Required Database Indexes:**

```sql
-- GIN index for JSONB path queries
CREATE INDEX idx_phenopackets_variants_gin ON phenopackets
USING GIN ((jsonb -> 'interpretations'));

-- Index for variant pathogenicity filtering
CREATE INDEX idx_phenopackets_variant_pathogenicity ON phenopackets
USING GIN ((jsonb -> 'interpretations' -> 'diagnosis' -> 'genomicInterpretations'));

-- Composite index for gene filtering
CREATE INDEX idx_phenopackets_gene_context ON phenopackets
USING GIN ((jsonb -> 'interpretations' -> 'diagnosis' -> 'genomicInterpretations' -> 'variantInterpretation' -> 'variationDescriptor' -> 'geneContext'));
```

**Performance Considerations:**
- 864 phenopackets × ~1.5 variants each = **~1300 variant records**
- With pathogenicity filter: **~650 pathogenic/likely pathogenic variants**
- Deduplication by VRS ID reduces to **~200-400 unique variants**
- JSONB extraction is expensive - **indexes are critical**

### Error Handling

```python
# Expected error cases

# 1. No variants found
Response: 200 OK
[]

# 2. Invalid pathogenicity value
Response: 400 Bad Request
{
  "error": "Invalid pathogenicity value. Must be one of: PATHOGENIC, LIKELY_PATHOGENIC, ..."
}

# 3. Database timeout
Response: 504 Gateway Timeout
{
  "error": "Query timeout. Try reducing limit or adding filters."
}
```

### Testing Requirements

**Backend tests must verify:**
- [ ] Correct deduplication (same variant in multiple phenopackets counted once)
- [ ] Phenopacket count accuracy
- [ ] Pathogenicity filter works
- [ ] Gene filter works
- [ ] Pagination works
- [ ] Performance: Top 100 variants in < 500ms
- [ ] Handles missing VRS IDs gracefully
- [ ] Empty result set returns `[]` not error

## Required Changes

### 1. Update API Client

**File:** `frontend/src/api/index.js`

```javascript
/**
 * Get aggregated variants across all phenopackets
 */
export async function getVariantsAggregation({ limit = 100, pathogenicity = null } = {}) {
  const params = { limit };
  if (pathogenicity) params.pathogenicity = pathogenicity;
  return apiClient.get('/phenopackets/aggregate/variants', { params });
}

/**
 * Get phenopackets containing a specific variant
 */
export async function getPhenopacketsByVariant(variantId, { skip = 0, limit = 10 } = {}) {
  return apiClient.get(`/phenopackets/by-variant/${variantId}`, {
    params: { skip, limit }
  });
}
```

### 2. Update Variants View

**File:** `frontend/src/views/Variants.vue`

**New Table Structure:**

| Column | Data Source | Sortable |
|--------|-------------|----------|
| Variant ID | `variant_id` | Yes |
| Label | `label` | Yes |
| Gene | `gene_symbol` | Yes |
| Type | `structural_type` or VCF ref→alt | Yes |
| Pathogenicity | `pathogenicity` (ACMG) | Yes |
| Individuals | `phenopacket_count` (clickable) | Yes |

**Implementation:**

```vue
<template>
  <v-container>
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="variants"
      :loading="loading"
      :items-length="totalItems"
      hide-default-footer
      class="elevation-1"
      density="compact"
      @update:options="onOptionsUpdate"
    >
      <!-- Variant ID as chip with link -->
      <template #item.variant_id="{ item }">
        <v-chip
          color="blue-lighten-2"
          small
          link
          variant="flat"
          :to="`/variants/${item.variant_id}`"
        >
          {{ truncateId(item.variant_id) }}
          <v-icon right size="small">mdi-dna</v-icon>
        </v-chip>
      </template>

      <!-- Label with tooltip -->
      <template #item.label="{ item }">
        <v-tooltip location="top">
          <template #activator="{ props }">
            <span v-bind="props" class="text-truncate" style="max-width: 200px">
              {{ item.label }}
            </span>
          </template>
          <span>{{ item.label }}</span>
        </v-tooltip>
      </template>

      <!-- Gene with HGNC link -->
      <template #item.gene_symbol="{ item }">
        <v-chip
          :href="`https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${item.gene_id}`"
          target="_blank"
          color="green"
          size="small"
          variant="flat"
        >
          {{ item.gene_symbol }}
          <v-icon right size="small">mdi-open-in-new</v-icon>
        </v-chip>
      </template>

      <!-- Pathogenicity with color coding -->
      <template #item.pathogenicity="{ item }">
        <v-chip
          :color="getPathogenicityColor(item.pathogenicity)"
          size="small"
          variant="flat"
        >
          {{ formatPathogenicity(item.pathogenicity) }}
        </v-chip>
      </template>

      <!-- Phenopacket count (clickable) -->
      <template #item.phenopacket_count="{ item }">
        <v-chip
          color="purple"
          size="small"
          link
          variant="flat"
          @click="showPhenopacketsForVariant(item.variant_id)"
        >
          {{ item.phenopacket_count }} individuals
          <v-icon right size="small">mdi-account-multiple</v-icon>
        </v-chip>
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import { getVariantsAggregation } from '@/api';

export default {
  name: 'Variants',
  data() {
    return {
      variants: [],
      loading: false,
      totalItems: 0,
      headers: [
        { title: 'Variant ID', value: 'variant_id', sortable: true, width: '180px' },
        { title: 'Label', value: 'label', sortable: true, width: '250px' },
        { title: 'Gene', value: 'gene_symbol', sortable: true, width: '100px' },
        { title: 'Type', value: 'structural_type', sortable: true, width: '120px' },
        { title: 'Pathogenicity', value: 'pathogenicity', sortable: true, width: '150px' },
        { title: 'Individuals', value: 'phenopacket_count', sortable: true, width: '120px', align: 'center' },
      ],
      options: {
        page: 1,
        itemsPerPage: 20,
        sortBy: [],
      },
    };
  },
  watch: {
    options: {
      handler() {
        this.fetchVariants();
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    async fetchVariants() {
      this.loading = true;
      try {
        const { itemsPerPage } = this.options;
        const response = await getVariantsAggregation({ limit: itemsPerPage });
        this.variants = response.data;
        this.totalItems = response.data.length;
      } catch (error) {
        console.error('Error fetching variants:', error);
      } finally {
        this.loading = false;
      }
    },

    truncateId(id) {
      // Shorten long VRS IDs: "var:HNF1B:17:36459258-37832869:DEL" → "var:HNF1B:17:...DEL"
      if (id.length > 30) {
        const parts = id.split(':');
        return `${parts[0]}:${parts[1]}:${parts[2]}:...${parts[parts.length - 1]}`;
      }
      return id;
    },

    getPathogenicityColor(classification) {
      const colors = {
        PATHOGENIC: 'red',
        LIKELY_PATHOGENIC: 'orange',
        UNCERTAIN_SIGNIFICANCE: 'grey',
        LIKELY_BENIGN: 'light-blue',
        BENIGN: 'green',
      };
      return colors[classification] || 'grey';
    },

    formatPathogenicity(classification) {
      const labels = {
        PATHOGENIC: 'Pathogenic',
        LIKELY_PATHOGENIC: 'Likely Pathogenic',
        UNCERTAIN_SIGNIFICANCE: 'VUS',
        LIKELY_BENIGN: 'Likely Benign',
        BENIGN: 'Benign',
      };
      return labels[classification] || classification;
    },

    showPhenopacketsForVariant(variantId) {
      // Navigate to filtered phenopackets list
      this.$router.push({
        path: '/phenopackets',
        query: { variant: variantId }
      });
    },
  },
};
</script>
```

## Implementation Checklist

### Phase 1: Backend Aggregation Endpoint
- [ ] Create `/api/v2/phenopackets/aggregate/variants` endpoint (Backend issue)
- [ ] Aggregate unique variants across all phenopackets
- [ ] Return variant counts and phenopacket IDs
- [ ] Add filtering by pathogenicity, gene

### Phase 2: API Client
- [ ] Add `getVariantsAggregation()` function
- [ ] Add `getPhenopacketsByVariant()` function
- [ ] Test endpoints return correct data

### Phase 3: Variants View
- [ ] Update table headers for new data structure
- [ ] Implement variant ID truncation
- [ ] Add pathogenicity color coding
- [ ] Make phenopacket count clickable (links to filtered list)
- [ ] Add HGNC gene links
- [ ] Update pagination/sorting

### Phase 4: Testing
- [ ] Test variant list displays correctly
- [ ] Test clicking variant navigates to detail page
- [ ] Test clicking phenopacket count filters list
- [ ] Test HGNC links open correctly
- [ ] Test no 404 errors

## Acceptance Criteria

### Functionality
- [ ] Variants list displays all unique variants
- [ ] Each variant shows correct gene, type, pathogenicity
- [ ] Phenopacket count shows how many individuals have variant
- [ ] Clicking variant ID navigates to detail page
- [ ] Clicking phenopacket count shows individuals with variant
- [ ] No 404 errors from old endpoints

### Data Display
- [ ] Variant IDs shown (truncated if long)
- [ ] Variant labels shown with tooltip
- [ ] Gene symbols with HGNC links
- [ ] Pathogenicity color-coded (red=pathogenic, orange=likely, grey=VUS)
- [ ] Individual count shown

### UI/UX
- [ ] Table sortable by all columns
- [ ] Responsive layout
- [ ] Loading spinner during fetch
- [ ] Empty state if no variants

### Code Quality
- [ ] ESLint passes
- [ ] No console errors
- [ ] Props validated
- [ ] Methods documented

## Dependencies

**Depends On:**
- Issue #30 (API client) - ✅ Required
- **Backend issue:** Create `/aggregate/variants` endpoint - ⚠️ **BLOCKER**

**Blocks:**
- Issue #35 (Variant detail page)

## Files to Modify

```
frontend/src/api/
└── index.js                   # Add getVariantsAggregation()

frontend/src/views/
└── Variants.vue              # Complete rewrite (200+ lines)
```

## Priority

**P1 (High)** - Core functionality

## Labels

`frontend`, `views`, `phenopackets`, `migration`, `p1`

## Timeline

- **Phase 1:** Backend endpoint - 6 hours (Backend team)
- **Phase 2:** API client - 2 hours
- **Phase 3:** View implementation - 8 hours
- **Phase 4:** Testing - 2 hours

**Total:** 12 hours (2 days) - Frontend only
