// src/stores/variantStore.js - Pinia store for progressive variant loading
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getVariants } from '@/api';

/**
 * Pinia store for managing variant data with progressive loading.
 *
 * Implements progressive loading by clinical relevance:
 * 1. PATHOGENIC variants first (fast first paint)
 * 2. LIKELY_PATHOGENIC second
 * 3. VUS + LIKELY_BENIGN in parallel
 *
 * @see plan/01-active/home-page-loading-optimization.md
 */
export const useVariantStore = defineStore('variants', () => {
  // ==================== STATE ====================
  const variants = ref([]);
  const loadingState = ref('idle'); // idle | loading | partial | complete
  const loadedClassifications = ref(new Set());
  const lastFetchTime = ref(null);
  const error = ref(null);

  // Cache TTL (5 minutes - appropriate for open research database)
  const CACHE_TTL = 5 * 60 * 1000;

  // HNF1B gene boundaries (GRCh38) - centralized for DRY
  const HNF1B_START = 37686430;
  const HNF1B_END = 37745059;

  // Classification loading order by clinical relevance
  const CLASSIFICATION_PRIORITY = [
    'PATHOGENIC',
    'LIKELY_PATHOGENIC',
    'UNCERTAIN_SIGNIFICANCE',
    'LIKELY_BENIGN',
  ];

  // ==================== CNV DETECTION (DRY) ====================

  /**
   * Check if a variant is a CNV that extends beyond HNF1B gene boundaries.
   * Only large structural variants that span beyond HNF1B should be in CNV track.
   *
   * Centralized here to avoid duplication across components.
   *
   * @param {Object} variant - Variant object with hg38 field
   * @returns {boolean} True if variant is a large CNV extending beyond HNF1B
   */
  function isCNV(variant) {
    if (!variant?.hg38) return false;

    // Check for range notation: 17:start-end:DEL/DUP
    const match = variant.hg38.match(/:(\d+)-(\d+):/);
    if (match) {
      const start = parseInt(match[1]);
      const end = parseInt(match[2]);
      const size = end - start;

      // Only consider it a "CNV track variant" if:
      // 1. Size >= 50bp (structural variant)
      // 2. Extends beyond HNF1B gene boundaries
      const extendsBeyondHNF1B = start < HNF1B_START || end > HNF1B_END;
      return size >= 50 && extendsBeyondHNF1B;
    }
    return false;
  }

  // ==================== GETTERS ====================

  /**
   * SNV variants (point mutations, splice variants, small indels).
   * Filters out large CNVs that extend beyond HNF1B.
   */
  const snvVariants = computed(() => variants.value.filter((v) => !isCNV(v)));

  /**
   * CNV variants (large structural variants extending beyond HNF1B).
   */
  const cnvVariants = computed(() => variants.value.filter((v) => isCNV(v)));

  /**
   * Whether PATHOGENIC variants have been loaded (enables first paint).
   */
  const hasPathogenic = computed(() => loadedClassifications.value.has('PATHOGENIC'));

  /**
   * Whether the cache is stale (> 5 minutes old).
   */
  const isStale = computed(() => {
    if (!lastFetchTime.value) return true;
    return Date.now() - lastFetchTime.value > CACHE_TTL;
  });

  /**
   * Whether all classifications have been loaded.
   */
  const isComplete = computed(() => loadingState.value === 'complete');

  /**
   * Total variant count.
   */
  const totalCount = computed(() => variants.value.length);

  // ==================== ACTIONS ====================

  /**
   * Fetch variants for a specific classification.
   * Uses the API's classification filter to reduce payload size.
   *
   * @param {string} classification - ACMG classification to fetch
   * @returns {Promise<void>}
   */
  async function fetchByClassification(classification) {
    // Skip if already loaded
    if (loadedClassifications.value.has(classification)) {
      window.logService.debug('Classification already loaded, skipping', { classification });
      return;
    }

    try {
      const response = await getVariants({
        classification,
        pageSize: 500, // Sufficient for any single classification
      });

      // Merge without duplicates (use variant_id as unique key)
      const existingIds = new Set(variants.value.map((v) => v.variant_id));
      const newVariants = response.data.filter((v) => !existingIds.has(v.variant_id));
      variants.value.push(...newVariants);

      loadedClassifications.value.add(classification);
      lastFetchTime.value = Date.now();

      window.logService.debug('Variants loaded by classification', {
        classification,
        newCount: newVariants.length,
        totalCount: variants.value.length,
      });
    } catch (err) {
      error.value = err.message;
      window.logService.error('Failed to fetch variants', {
        classification,
        error: err.message,
      });
      throw err;
    }
  }

  /**
   * Progressive loading: Load variants by clinical relevance priority.
   *
   * Timeline:
   * - 0ms: Start loading PATHOGENIC
   * - ~100ms: PATHOGENIC loaded → first paint possible
   * - ~200ms: LIKELY_PATHOGENIC loading
   * - ~400ms: VUS + BENIGN loading in parallel
   * - ~600ms: Complete
   *
   * @returns {Promise<void>}
   */
  async function fetchProgressively() {
    // Skip if cache is fresh and complete
    if (!isStale.value && loadingState.value === 'complete') {
      window.logService.debug('Using cached variants', {
        count: variants.value.length,
        age: Date.now() - lastFetchTime.value,
      });
      return;
    }

    loadingState.value = 'loading';
    error.value = null;

    try {
      // Phase 1: PATHOGENIC (highest priority - enables fast first paint)
      await fetchByClassification('PATHOGENIC');
      loadingState.value = 'partial'; // Signal: first paint now possible

      // Phase 2: LIKELY_PATHOGENIC
      await fetchByClassification('LIKELY_PATHOGENIC');

      // Phase 3: VUS + BENIGN (parallel - lower priority)
      await Promise.all([
        fetchByClassification('UNCERTAIN_SIGNIFICANCE'),
        fetchByClassification('LIKELY_BENIGN'),
      ]);

      loadingState.value = 'complete';
      window.logService.info('Progressive variant loading complete', {
        totalVariants: variants.value.length,
        snvCount: snvVariants.value.length,
        cnvCount: cnvVariants.value.length,
      });
    } catch (err) {
      // Partial data is still usable for visualization
      loadingState.value = 'partial';
      window.logService.warn('Progressive loading partially failed', {
        error: err.message,
        loadedCount: variants.value.length,
      });
    }
  }

  /**
   * Fetch all variants in a single request (fallback for specific needs).
   *
   * @returns {Promise<void>}
   */
  async function fetchAll() {
    if (!isStale.value && loadingState.value === 'complete') {
      return;
    }

    loadingState.value = 'loading';
    error.value = null;

    try {
      const response = await getVariants({
        pageSize: 1000, // Get all variants
      });

      variants.value = response.data;
      lastFetchTime.value = Date.now();

      // Mark all classifications as loaded
      CLASSIFICATION_PRIORITY.forEach((c) => loadedClassifications.value.add(c));
      loadingState.value = 'complete';
    } catch (err) {
      error.value = err.message;
      window.logService.error('Failed to fetch all variants', { error: err.message });
      throw err;
    }
  }

  /**
   * Invalidate the cache, forcing a fresh fetch on next request.
   */
  function invalidateCache() {
    lastFetchTime.value = null;
    loadedClassifications.value.clear();
    loadingState.value = 'idle';
    window.logService.debug('Variant cache invalidated');
  }

  /**
   * Clear all state (for testing or cleanup).
   */
  function $reset() {
    variants.value = [];
    loadingState.value = 'idle';
    loadedClassifications.value = new Set();
    lastFetchTime.value = null;
    error.value = null;
  }

  return {
    // State
    variants,
    loadingState,
    loadedClassifications,
    lastFetchTime,
    error,

    // Getters
    snvVariants,
    cnvVariants,
    hasPathogenic,
    isStale,
    isComplete,
    totalCount,

    // Actions
    fetchByClassification,
    fetchProgressively,
    fetchAll,
    invalidateCache,
    $reset,

    // Utilities
    isCNV,

    // Constants (exposed for testing)
    HNF1B_START,
    HNF1B_END,
    CACHE_TTL,
  };
});
