# Home Page Loading Performance Optimization

**Date:** December 5, 2025
**Branch:** `feat/lighthouse-optimizations`
**Status:** Active
**Related:** [Issue #93](../docs/issues/issue-93-incremental-variant-loading.md), [ADR-001](../docs/adr/001-json-api-pagination.md)

---

## Problem Statement

The home page loads all 198 variants (75KB) in a single request, causing:
- **287ms TTFB** for variant data
- **670ms perceived latency** shown in footer
- Client-side filtering of SNV vs CNV (wasteful)
- No caching between page visits

---

## Solution: Progressive Loading with Pinia

Load variants by clinical relevance priority, caching in Pinia store:

```
Timeline:
0ms     → Stats API (164 bytes, fast)
100ms   → PATHOGENIC (41 variants, 15KB) → FIRST PAINT
300ms   → LIKELY_PATHOGENIC (92 variants) → UPDATE
600ms   → VUS + BENIGN (65 variants) → COMPLETE
```

**Result:** 65% faster first paint (100ms vs 287ms)

---

## 1. Current State

### API Response Times

| Endpoint | TTFB | Size | Status |
|----------|------|------|--------|
| `/aggregate/summary` | 235ms | 164 bytes | OK |
| `/aggregate/all-variants?limit=1000` | 287ms | 75KB | **Bottleneck** |
| `/reference/genes/HNF1B/domains` | 6ms | 115 bytes | OK |

### Variant Distribution

| Classification | Count | Priority |
|---------------|-------|----------|
| PATHOGENIC | 41 | 1st (immediate) |
| LIKELY_PATHOGENIC | 92 | 2nd (background) |
| UNCERTAIN_SIGNIFICANCE | 60 | 3rd |
| LIKELY_BENIGN | 5 | 3rd |

### Existing Optimizations (Keep)

- Brotli + Gzip compression (`vite.config.js`)
- Code splitting with manualChunks
- Vuetify treeshaking
- Skeleton loaders during fetch
- Animated stats (nice UX)

---

## 2. Implementation

### 2.1 Pinia Variant Store

```javascript
// frontend/src/stores/variantStore.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getVariants } from '@/api';

export const useVariantStore = defineStore('variants', () => {
  // State
  const variants = ref([]);
  const loadingState = ref('idle'); // idle | loading | partial | complete
  const loadedClassifications = ref(new Set());
  const lastFetchTime = ref(null);
  const error = ref(null);

  // Cache TTL (5 minutes - appropriate for open research database)
  const CACHE_TTL = 5 * 60 * 1000;

  // HNF1B gene boundaries for CNV detection
  const HNF1B_START = 37686430;
  const HNF1B_END = 37745059;

  // CNV detection (centralized - DRY)
  function isCNV(variant) {
    if (!variant?.hg38) return false;
    const match = variant.hg38.match(/:(\d+)-(\d+):/);
    if (match) {
      const start = parseInt(match[1]);
      const end = parseInt(match[2]);
      const size = end - start;
      const extendsBeyond = start < HNF1B_START || end > HNF1B_END;
      return size >= 50 && extendsBeyond;
    }
    return false;
  }

  // Getters
  const snvVariants = computed(() => variants.value.filter((v) => !isCNV(v)));
  const cnvVariants = computed(() => variants.value.filter((v) => isCNV(v)));
  const hasPathogenic = computed(() => loadedClassifications.value.has('PATHOGENIC'));
  const isStale = computed(() => {
    if (!lastFetchTime.value) return true;
    return Date.now() - lastFetchTime.value > CACHE_TTL;
  });

  // Actions
  async function fetchByClassification(classification) {
    if (loadedClassifications.value.has(classification)) return;

    try {
      const response = await getVariants({
        classification,
        page_size: 500,
      });

      // Merge without duplicates
      const existingIds = new Set(variants.value.map((v) => v.variant_id));
      const newVariants = response.data.filter((v) => !existingIds.has(v.variant_id));
      variants.value.push(...newVariants);

      loadedClassifications.value.add(classification);
      lastFetchTime.value = Date.now();

      window.logService.debug('Variants loaded', {
        classification,
        count: newVariants.length,
        total: variants.value.length,
      });
    } catch (err) {
      error.value = err.message;
      window.logService.error('Failed to fetch variants', { classification, error: err.message });
      throw err;
    }
  }

  async function fetchProgressively() {
    if (!isStale.value && loadingState.value === 'complete') return;

    loadingState.value = 'loading';

    try {
      // Phase 1: PATHOGENIC (fast first paint)
      await fetchByClassification('PATHOGENIC');
      loadingState.value = 'partial';

      // Phase 2: LIKELY_PATHOGENIC
      await fetchByClassification('LIKELY_PATHOGENIC');

      // Phase 3: VUS + BENIGN (parallel)
      await Promise.all([
        fetchByClassification('UNCERTAIN_SIGNIFICANCE'),
        fetchByClassification('LIKELY_BENIGN'),
      ]);

      loadingState.value = 'complete';
    } catch {
      loadingState.value = 'partial'; // Partial data still usable
    }
  }

  async function fetchCNVsOnly() {
    try {
      const response = await getVariants({ variant_type: 'CNV', page_size: 100 });
      const nonCNVs = variants.value.filter((v) => !isCNV(v));
      variants.value = [...nonCNVs, ...response.data];
    } catch (err) {
      window.logService.error('Failed to fetch CNV variants', { error: err.message });
    }
  }

  function invalidateCache() {
    lastFetchTime.value = null;
    loadedClassifications.value.clear();
    loadingState.value = 'idle';
  }

  return {
    variants,
    loadingState,
    error,
    snvVariants,
    cnvVariants,
    hasPathogenic,
    isStale,
    fetchProgressively,
    fetchByClassification,
    fetchCNVsOnly,
    invalidateCache,
    isCNV,
  };
});
```

### 2.2 Updated Home.vue

```javascript
// Home.vue
import { useVariantStore } from '@/stores/variantStore';

export default {
  setup() {
    const variantStore = useVariantStore();

    const snvVariants = computed(() => variantStore.snvVariants);
    const cnvVariants = computed(() => variantStore.cnvVariants);
    const snvVariantsLoaded = computed(() => variantStore.hasPathogenic);
    const cnvVariantsLoaded = computed(() => variantStore.cnvVariants.length > 0);

    onMounted(async () => {
      fetchStats();
      await variantStore.fetchProgressively();
    });

    const handleTabChange = (tab) => {
      if (tab === 'region' && !cnvVariantsLoaded.value) {
        variantStore.fetchCNVsOnly();
      }
    };

    return { snvVariants, cnvVariants, snvVariantsLoaded, cnvVariantsLoaded, handleTabChange };
  },
};
```

### 2.3 Lazy Load D3/NGL with defineAsyncComponent

```javascript
// Home.vue - Async components for heavy visualizations
import { defineAsyncComponent } from 'vue';

const HNF1BProteinVisualization = defineAsyncComponent({
  loader: () => import('@/components/gene/HNF1BProteinVisualization.vue'),
  loadingComponent: { template: '<v-skeleton-loader type="image" height="400" />' },
  delay: 200,
});

const ProteinStructure3D = defineAsyncComponent({
  loader: () => import('@/components/gene/ProteinStructure3D.vue'),
  loadingComponent: { template: '<v-skeleton-loader type="image" height="400" />' },
  delay: 200,
});
```

---

## 3. Backend Enhancements

### 3.1 HTTP Cache Headers

```python
# backend/app/phenopackets/routers/aggregations.py
from fastapi import Response

@router.get("/all-variants")
async def aggregate_all_variants(response: Response, ...):
    response.headers["Cache-Control"] = "public, max-age=300"
    # ... existing logic
```

### 3.2 Add `is_cnv` Filter Parameter

```python
is_cnv: Optional[bool] = Query(
    None,
    description="Filter by CNV status. true=large CNVs beyond HNF1B boundaries, false=SNVs"
)

HNF1B_START = 37686430
HNF1B_END = 37745059

if is_cnv is not None:
    if is_cnv:
        where_clauses.append(f"""
            vd->>'hg38' ~ '^\\d+:\\d+-\\d+:(DEL|DUP)$'
            AND (
                CAST(SPLIT_PART(SPLIT_PART(vd->>'hg38', ':', 2), '-', 1) AS INTEGER) < {HNF1B_START}
                OR CAST(SPLIT_PART(SPLIT_PART(vd->>'hg38', ':', 2), '-', 2) AS INTEGER) > {HNF1B_END}
            )
        """)
    else:
        where_clauses.append(f"""NOT (...)""")  # Inverse of above
```

### 3.3 Redis Caching (Optional)

```python
# For high-traffic scenarios
CACHE_TTL = 300  # 5 minutes

@router.get("/all-variants")
async def aggregate_all_variants(...):
    cache_key = build_cache_key("variants", params)
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await query_variants(...)
    await redis.setex(cache_key, CACHE_TTL, json.dumps(result))
    return result
```

---

## 4. Performance Projections

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| First paint | 287ms | ~100ms | **65% faster** |
| Full data | 287ms | ~600ms | Progressive |
| Repeat visit | 287ms | 0ms (cached) | **100% faster** |
| Initial payload | 75KB | 15KB first | **80% smaller** |

---

## 5. Implementation Checklist

### Phase 1: Frontend

- [ ] Create `frontend/src/stores/variantStore.js`
- [ ] Move `isCNV()` logic to store (DRY)
- [ ] Implement progressive loading actions
- [ ] Update `Home.vue` to use store
- [ ] Add `defineAsyncComponent` for D3/NGL components
- [ ] Update loading states in visualizations

### Phase 2: Backend

- [ ] Add `Cache-Control` headers to aggregations
- [ ] Add `is_cnv` query parameter
- [ ] Add tests for new filter
- [ ] (Optional) Add Redis caching

### Phase 3: API Client

- [ ] Update `getVariants()` for `is_cnv` parameter
- [ ] Verify classification filter works correctly

### Phase 4: Validation

- [ ] Run Lighthouse audit
- [ ] Verify smooth visualization updates
- [ ] Test cache invalidation
- [ ] Performance regression tests

---

## 6. Principles Applied

| Principle | Application |
|-----------|-------------|
| **DRY** | `isCNV()` centralized in store (not duplicated) |
| **KISS** | Use existing `classification` filter |
| **SRP** | Store handles variants only |
| **Progressive Enhancement** | PATHOGENIC first |
| **Cache-First** | Pinia with 5-min TTL |

---

## References

- [Pinia Documentation](https://pinia.vuejs.org/core-concepts/actions.html)
- [Vue.js Performance Guide](https://vuejs.org/guide/best-practices/performance)
- [ADR-001: JSON:API Pagination](../../docs/adr/001-json-api-pagination.md)
- [Issue #93: Incremental Variant Loading](../../docs/issues/issue-93-incremental-variant-loading.md)
