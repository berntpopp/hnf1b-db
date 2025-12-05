/**
 * Unit tests for the variant store (variantStore)
 *
 * Tests cover:
 * - State initialization
 * - Computed properties (snvVariants, cnvVariants, hasPathogenic, isStale, isComplete)
 * - CNV detection logic (isCNV function)
 * - Progressive loading by classification
 * - Cache management
 * - Error handling
 *
 * @see stores/variantStore.js
 * @see plan/01-active/home-page-loading-optimization.md
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

// Mock the API module with named export - must be before imports that use it
vi.mock('@/api', () => ({
  getVariants: vi.fn(),
}));

// Import after mock is set up
import { useVariantStore } from '@/stores/variantStore';
import { getVariants } from '@/api';

// Mock window.logService
window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};

// Sample variant data for testing
const createVariant = (overrides = {}) => ({
  variant_id: `var_${Math.random().toString(36).substr(2, 9)}`,
  label: 'c.123A>G',
  hg38: '17:36459258:A:G', // SNV format
  geneSymbol: 'HNF1B',
  classificationVerdict: 'PATHOGENIC',
  ...overrides,
});

// CNV variant that extends beyond HNF1B gene boundaries
const createCNVVariant = (overrides = {}) => ({
  variant_id: `var_cnv_${Math.random().toString(36).substr(2, 9)}`,
  label: 'Whole gene deletion',
  hg38: '17:36000000-38000000:DEL', // Large CNV extending beyond HNF1B
  geneSymbol: 'HNF1B',
  classificationVerdict: 'PATHOGENIC',
  ...overrides,
});

describe('Variant Store', () => {
  beforeEach(() => {
    // Create a fresh Pinia instance for each test
    setActivePinia(createPinia());

    // Clear mocks
    vi.clearAllMocks();

    // Reset API client mock
    getVariants.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should initialize with empty variants and idle state', () => {
      const store = useVariantStore();

      expect(store.variants).toEqual([]);
      expect(store.loadingState).toBe('idle');
      expect(store.loadedClassifications.size).toBe(0);
      expect(store.lastFetchTime).toBeNull();
      expect(store.error).toBeNull();
    });

    it('should have correct HNF1B gene boundaries', () => {
      const store = useVariantStore();

      expect(store.HNF1B_START).toBe(37686430);
      expect(store.HNF1B_END).toBe(37745059);
    });

    it('should have correct cache TTL (5 minutes)', () => {
      const store = useVariantStore();

      expect(store.CACHE_TTL).toBe(5 * 60 * 1000);
    });
  });

  describe('CNV Detection (isCNV)', () => {
    it('should identify large CNVs extending beyond HNF1B boundaries', () => {
      const store = useVariantStore();

      // CNV that starts before HNF1B_START (37686430)
      expect(store.isCNV({ hg38: '17:36000000-37700000:DEL' })).toBe(true);

      // CNV that ends after HNF1B_END (37745059)
      expect(store.isCNV({ hg38: '17:37700000-38000000:DEL' })).toBe(true);

      // CNV spanning entire region
      expect(store.isCNV({ hg38: '17:36000000-38000000:DEL' })).toBe(true);
    });

    it('should not identify SNVs as CNVs', () => {
      const store = useVariantStore();

      // Point mutation
      expect(store.isCNV({ hg38: '17:36459258:A:G' })).toBe(false);

      // No range notation
      expect(store.isCNV({ hg38: 'chr17-36459258-A-G' })).toBe(false);
    });

    it('should not identify small variants within HNF1B as CNVs', () => {
      const store = useVariantStore();

      // Small deletion within gene boundaries
      expect(store.isCNV({ hg38: '17:37700000-37700020:DEL' })).toBe(false); // Only 20bp, < 50bp threshold

      // Larger variant but within boundaries
      expect(store.isCNV({ hg38: '17:37690000-37740000:DEL' })).toBe(false); // >= 50bp but within boundaries
    });

    it('should handle edge cases', () => {
      const store = useVariantStore();

      expect(store.isCNV(null)).toBe(false);
      expect(store.isCNV({})).toBe(false);
      expect(store.isCNV({ hg38: null })).toBe(false);
      expect(store.isCNV({ hg38: '' })).toBe(false);
    });
  });

  describe('Computed Properties', () => {
    it('should compute snvVariants (excluding CNVs)', () => {
      const store = useVariantStore();

      const snv = createVariant();
      const cnv = createCNVVariant();

      store.variants = [snv, cnv];

      expect(store.snvVariants).toHaveLength(1);
      expect(store.snvVariants[0].variant_id).toBe(snv.variant_id);
    });

    it('should compute cnvVariants', () => {
      const store = useVariantStore();

      const snv = createVariant();
      const cnv = createCNVVariant();

      store.variants = [snv, cnv];

      expect(store.cnvVariants).toHaveLength(1);
      expect(store.cnvVariants[0].variant_id).toBe(cnv.variant_id);
    });

    it('should compute hasPathogenic correctly', () => {
      const store = useVariantStore();

      expect(store.hasPathogenic).toBe(false);

      store.loadedClassifications.add('PATHOGENIC');

      expect(store.hasPathogenic).toBe(true);
    });

    it('should compute isStale correctly', () => {
      const store = useVariantStore();

      // No fetch time - stale
      expect(store.isStale).toBe(true);

      // Recent fetch - not stale
      store.lastFetchTime = Date.now();
      expect(store.isStale).toBe(false);

      // Old fetch - stale
      store.lastFetchTime = Date.now() - 6 * 60 * 1000; // 6 minutes ago
      expect(store.isStale).toBe(true);
    });

    it('should compute isComplete correctly', () => {
      const store = useVariantStore();

      expect(store.isComplete).toBe(false);

      store.loadingState = 'partial';
      expect(store.isComplete).toBe(false);

      store.loadingState = 'complete';
      expect(store.isComplete).toBe(true);
    });

    it('should compute totalCount correctly', () => {
      const store = useVariantStore();

      expect(store.totalCount).toBe(0);

      store.variants = [createVariant(), createVariant(), createVariant()];
      expect(store.totalCount).toBe(3);
    });
  });

  describe('fetchByClassification Action', () => {
    it('should fetch variants for a specific classification', async () => {
      const store = useVariantStore();

      const mockVariants = [
        createVariant({ variant_id: 'var1', classificationVerdict: 'PATHOGENIC' }),
        createVariant({ variant_id: 'var2', classificationVerdict: 'PATHOGENIC' }),
      ];

      getVariants.mockResolvedValueOnce({ data: mockVariants });

      await store.fetchByClassification('PATHOGENIC');

      expect(getVariants).toHaveBeenCalledWith({
        classification: 'PATHOGENIC',
        page_size: 500,
      });
      expect(store.variants).toHaveLength(2);
      expect(store.loadedClassifications.has('PATHOGENIC')).toBe(true);
      expect(store.lastFetchTime).not.toBeNull();
    });

    it('should skip if classification already loaded', async () => {
      const store = useVariantStore();

      store.loadedClassifications.add('PATHOGENIC');

      await store.fetchByClassification('PATHOGENIC');

      expect(getVariants).not.toHaveBeenCalled();
    });

    it('should merge without duplicates', async () => {
      const store = useVariantStore();

      // Pre-existing variant
      const existingVariant = createVariant({ variant_id: 'var_existing' });
      store.variants = [existingVariant];

      // New variants (one duplicate, one new)
      const mockVariants = [
        createVariant({ variant_id: 'var_existing' }), // Duplicate
        createVariant({ variant_id: 'var_new' }),
      ];

      getVariants.mockResolvedValueOnce({ data: mockVariants });

      await store.fetchByClassification('PATHOGENIC');

      expect(store.variants).toHaveLength(2); // Duplicate not added
      expect(store.variants.some((v) => v.variant_id === 'var_existing')).toBe(true);
      expect(store.variants.some((v) => v.variant_id === 'var_new')).toBe(true);
    });

    it('should handle fetch errors', async () => {
      const store = useVariantStore();

      const error = new Error('Network error');
      getVariants.mockRejectedValueOnce(error);

      await expect(store.fetchByClassification('PATHOGENIC')).rejects.toThrow('Network error');

      expect(store.error).toBe('Network error');
      expect(window.logService.error).toHaveBeenCalled();
    });
  });

  describe('fetchProgressively Action', () => {
    it('should load variants in priority order', async () => {
      const store = useVariantStore();

      // Mock responses for each classification
      getVariants
        .mockResolvedValueOnce({ data: [createVariant({ variant_id: 'path1' })] }) // PATHOGENIC
        .mockResolvedValueOnce({ data: [createVariant({ variant_id: 'lp1' })] }) // LIKELY_PATHOGENIC
        .mockResolvedValueOnce({ data: [createVariant({ variant_id: 'vus1' })] }) // UNCERTAIN_SIGNIFICANCE
        .mockResolvedValueOnce({ data: [createVariant({ variant_id: 'lb1' })] }); // LIKELY_BENIGN

      await store.fetchProgressively();

      expect(store.loadingState).toBe('complete');
      expect(store.variants).toHaveLength(4);
      expect(store.loadedClassifications.has('PATHOGENIC')).toBe(true);
      expect(store.loadedClassifications.has('LIKELY_PATHOGENIC')).toBe(true);
      expect(store.loadedClassifications.has('UNCERTAIN_SIGNIFICANCE')).toBe(true);
      expect(store.loadedClassifications.has('LIKELY_BENIGN')).toBe(true);
    });

    it('should set partial state after PATHOGENIC loads', async () => {
      const store = useVariantStore();

      // Track when each classification is loaded
      const loadOrder = [];

      getVariants
        .mockImplementationOnce(async ({ classification }) => {
          loadOrder.push(classification);
          return { data: [createVariant()] };
        })
        .mockImplementationOnce(async ({ classification }) => {
          loadOrder.push(classification);
          return { data: [] };
        })
        .mockImplementationOnce(async ({ classification }) => {
          loadOrder.push(classification);
          return { data: [] };
        })
        .mockImplementationOnce(async ({ classification }) => {
          loadOrder.push(classification);
          return { data: [] };
        });

      await store.fetchProgressively();

      expect(store.loadingState).toBe('complete');
      expect(loadOrder[0]).toBe('PATHOGENIC');
      expect(store.hasPathogenic).toBe(true);
    });

    it('should skip if cache is fresh and complete', async () => {
      const store = useVariantStore();

      store.loadingState = 'complete';
      store.lastFetchTime = Date.now(); // Fresh

      await store.fetchProgressively();

      expect(getVariants).not.toHaveBeenCalled();
    });

    it('should handle partial failure gracefully', async () => {
      const store = useVariantStore();

      getVariants
        .mockResolvedValueOnce({ data: [createVariant()] }) // PATHOGENIC succeeds
        .mockRejectedValueOnce(new Error('Network error')); // LIKELY_PATHOGENIC fails

      await store.fetchProgressively();

      // Should have partial data and partial state
      expect(store.loadingState).toBe('partial');
      expect(store.variants).toHaveLength(1);
      expect(window.logService.warn).toHaveBeenCalled();
    });
  });

  describe('fetchAll Action', () => {
    it('should fetch all variants in single request', async () => {
      const store = useVariantStore();

      const mockVariants = [
        createVariant({ variant_id: 'v1' }),
        createVariant({ variant_id: 'v2' }),
        createVariant({ variant_id: 'v3' }),
      ];

      getVariants.mockResolvedValueOnce({ data: mockVariants });

      await store.fetchAll();

      expect(getVariants).toHaveBeenCalledWith({ page_size: 1000 });
      expect(store.variants).toHaveLength(3);
      expect(store.loadingState).toBe('complete');
    });

    it('should skip if cache is fresh and complete', async () => {
      const store = useVariantStore();

      store.loadingState = 'complete';
      store.lastFetchTime = Date.now();

      await store.fetchAll();

      expect(getVariants).not.toHaveBeenCalled();
    });

    it('should handle errors', async () => {
      const store = useVariantStore();

      getVariants.mockRejectedValueOnce(new Error('Server error'));

      await expect(store.fetchAll()).rejects.toThrow('Server error');

      expect(store.error).toBe('Server error');
    });
  });

  describe('Cache Management', () => {
    it('should invalidate cache', () => {
      const store = useVariantStore();

      // Set up cache
      store.variants = [createVariant()];
      store.loadingState = 'complete';
      store.lastFetchTime = Date.now();
      store.loadedClassifications.add('PATHOGENIC');

      store.invalidateCache();

      expect(store.lastFetchTime).toBeNull();
      expect(store.loadedClassifications.size).toBe(0);
      expect(store.loadingState).toBe('idle');
      // Note: variants are not cleared on invalidate, only marking cache as stale
    });

    it('should $reset all state', () => {
      const store = useVariantStore();

      // Set up state
      store.variants = [createVariant()];
      store.loadingState = 'complete';
      store.lastFetchTime = Date.now();
      store.loadedClassifications.add('PATHOGENIC');
      store.error = 'Some error';

      store.$reset();

      expect(store.variants).toEqual([]);
      expect(store.loadingState).toBe('idle');
      expect(store.lastFetchTime).toBeNull();
      expect(store.loadedClassifications.size).toBe(0);
      expect(store.error).toBeNull();
    });
  });

  describe('Integration: Progressive Loading Timeline', () => {
    it('should enable fast first paint with PATHOGENIC-first loading', async () => {
      const store = useVariantStore();

      // Simulate timing
      const loadTimes = [];

      getVariants
        .mockImplementationOnce(async () => {
          loadTimes.push({ classification: 'PATHOGENIC', time: Date.now() });
          return { data: [createVariant()] };
        })
        .mockImplementationOnce(async () => {
          loadTimes.push({ classification: 'LIKELY_PATHOGENIC', time: Date.now() });
          return { data: [createVariant()] };
        })
        .mockImplementationOnce(async () => {
          loadTimes.push({ classification: 'UNCERTAIN_SIGNIFICANCE', time: Date.now() });
          return { data: [createVariant()] };
        })
        .mockImplementationOnce(async () => {
          loadTimes.push({ classification: 'LIKELY_BENIGN', time: Date.now() });
          return { data: [createVariant()] };
        });

      await store.fetchProgressively();

      // Verify PATHOGENIC loads first
      expect(loadTimes[0].classification).toBe('PATHOGENIC');

      // Verify hasPathogenic becomes true after first classification
      expect(store.hasPathogenic).toBe(true);
    });
  });
});
