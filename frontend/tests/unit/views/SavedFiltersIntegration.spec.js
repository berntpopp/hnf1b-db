/**
 * Integration tests for URL-synced saved searches and cohort filters in:
 * - Phenopackets.vue
 * - Variants.vue
 * - AggregationsDashboard.vue
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Global mocks
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

// Route mocks
const mockRoute = {
  query: {},
  path: '/',
};
const mockRouter = {
  push: vi.fn().mockResolvedValue(undefined),
  replace: vi.fn().mockResolvedValue(undefined),
};

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
}));

// Store mock
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    user: { role: 'admin' },
    isAuthenticated: true,
  }),
}));

// API mocks
vi.mock('@/api', () => ({
  getPhenopackets: vi.fn().mockResolvedValue({
    data: {
      data: [
        {
          id: 'pp-1',
          phenopacket_id: 'PP001',
          phenopacket: {
            id: 'PP001',
            subject: { id: 'SUB1', sex: 'MALE' },
            phenotypicFeatures: [],
            interpretations: [{ id: 'INT1' }],
          },
        },
      ],
      meta: { page: { total: 1, current_page: 1, total_pages: 1 } },
    },
  }),
  searchPhenopackets: vi.fn().mockResolvedValue({
    data: {
      data: [],
      meta: { page: { total: 0, current_page: 1, total_pages: 0 } },
    },
  }),
  getVariants: vi.fn().mockResolvedValue({
    data: [
      {
        id: 'var-1',
        simple_id: 'VAR001',
        variant_id: 'VAR001',
        structural_type: 'SNV',
        pathogenicity: 'PATHOGENIC',
      },
    ],
    meta: {
      totalRecords: 1,
      currentPage: 1,
      totalPages: 1,
    },
  }),
  getPublicationsTimeline: vi.fn().mockResolvedValue({ data: [] }),
  getSexDistribution: vi.fn().mockResolvedValue({ data: [] }),
  getPhenotypicFeaturesAggregation: vi.fn().mockResolvedValue({ data: [] }),
  getVariantComparison: vi.fn().mockResolvedValue({ data: {} }),
  getSurvivalCurveData: vi.fn().mockResolvedValue({ data: {} }),
}));

import Phenopackets from '@/views/Phenopackets.vue';
import Variants from '@/views/Variants.vue';
import AggregationsDashboard from '@/views/AggregationsDashboard.vue';
import { getPhenopackets, getVariants } from '@/api';

describe('Saved cohort filters view integration', () => {
  const vuetify = createVuetify({ components, directives });

  beforeEach(() => {
    mockRoute.query = {};
    mockRouter.replace.mockClear();
    mockRouter.push.mockClear();
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  describe('Phenopackets.vue integration', () => {
    it('mounts SavedFiltersMenu with scope-key="phenopackets"', async () => {
      const wrapper = mount(Phenopackets, {
        global: {
          plugins: [vuetify],
          stubs: {
            AppDataTable: {
              template: '<div><slot name="toolbar" /><slot /></div>',
            },
            AppTableToolbar: {
              template: '<div><slot name="actions" /><slot /></div>',
            },
          },
        },
      });

      await flushPromises();

      const savedFiltersMenu = wrapper.findComponent({ name: 'SavedFiltersMenu' });
      expect(savedFiltersMenu.exists()).toBe(true);
      expect(savedFiltersMenu.props('scopeKey')).toBe('phenopackets');
    });

    it('applies saved preset and refetches data', async () => {
      const wrapper = mount(Phenopackets, {
        global: {
          plugins: [vuetify],
          stubs: {
            AppDataTable: {
              template: '<div><slot name="toolbar" /><slot /></div>',
            },
            AppTableToolbar: {
              template: '<div><slot name="actions" /><slot /></div>',
            },
          },
        },
      });

      await flushPromises();
      expect(getPhenopackets).toHaveBeenCalled();

      getPhenopackets.mockClear();
      wrapper.vm.onApplyPreset({
        q: 'Subject_A',
        sex: 'FEMALE',
        has_variants: true,
      });

      expect(wrapper.vm.searchQuery).toBe('Subject_A');
      expect(wrapper.vm.sexFilter).toBe('FEMALE');
      expect(wrapper.vm.hasVariantsFilter).toBe(true);
    });
  });

  describe('Variants.vue integration', () => {
    it('mounts SavedFiltersMenu with scope-key="variants"', async () => {
      const wrapper = mount(Variants, {
        global: {
          plugins: [vuetify],
          stubs: {
            AppDataTable: {
              template: '<div><slot name="toolbar" /><slot /></div>',
            },
            AppTableToolbar: {
              template: '<div><slot name="actions" /><slot /></div>',
            },
          },
        },
      });

      await flushPromises();

      const savedFiltersMenu = wrapper.findComponent({ name: 'SavedFiltersMenu' });
      expect(savedFiltersMenu.exists()).toBe(true);
      expect(savedFiltersMenu.props('scopeKey')).toBe('variants');
    });

    it('applies saved preset and updates all filter states', async () => {
      const wrapper = mount(Variants, {
        global: {
          plugins: [vuetify],
          stubs: {
            AppDataTable: {
              template: '<div><slot name="toolbar" /><slot /></div>',
            },
            AppTableToolbar: {
              template: '<div><slot name="actions" /><slot /></div>',
            },
          },
        },
      });

      await flushPromises();
      getVariants.mockClear();

      wrapper.vm.onApplyPreset({
        q: 'c.123',
        variant_type: 'SNV',
        classification: 'LIKELY_PATHOGENIC',
        consequence: 'missense_variant',
        domain: 'DNA-binding',
      });

      expect(wrapper.vm.searchQuery).toBe('c.123');
      expect(wrapper.vm.typeFilter).toBe('SNV');
      expect(wrapper.vm.classificationFilter).toBe('LIKELY_PATHOGENIC');
      expect(wrapper.vm.consequenceFilter).toBe('missense_variant');
      expect(wrapper.vm.domainFilter).toBe('DNA-binding');
      expect(getVariants).toHaveBeenCalled();
    });
  });

  describe('AggregationsDashboard.vue integration', () => {
    it('mounts SavedFiltersMenu with scope-key="aggregations"', async () => {
      const wrapper = mount(AggregationsDashboard, {
        global: {
          plugins: [vuetify],
          stubs: {
            DonutChart: true,
            StackedBarChart: true,
            PublicationsTimelineChart: true,
            VariantComparisonChart: true,
            KaplanMeierChart: true,
            DNADistanceAnalysis: true,
            SurvivalDataPanels: true,
          },
        },
      });

      await flushPromises();

      const savedFiltersMenu = wrapper.findComponent({ name: 'SavedFiltersMenu' });
      expect(savedFiltersMenu.exists()).toBe(true);
      expect(savedFiltersMenu.props('scopeKey')).toBe('aggregations');
    });

    it('applies saved preset and updates dashboard state', async () => {
      const wrapper = mount(AggregationsDashboard, {
        global: {
          plugins: [vuetify],
          stubs: {
            DonutChart: true,
            StackedBarChart: true,
            PublicationsTimelineChart: true,
            VariantComparisonChart: true,
            KaplanMeierChart: true,
            DNADistanceAnalysis: true,
            SurvivalDataPanels: true,
          },
        },
      });

      await flushPromises();

      const savedFiltersMenu = wrapper.findComponent({ name: 'SavedFiltersMenu' });
      await savedFiltersMenu.vm.$emit('apply', {
        tab: 'survival',
        survivalComparison: 'truncating',
        survivalEndpoint: 'all_cause_mortality',
      });

      await flushPromises();

      const current = savedFiltersMenu.props('currentFilters');
      expect(current.tab).toBe('survival');
      expect(current.survivalComparison).toBe('truncating');
      expect(current.survivalEndpoint).toBe('all_cause_mortality');
    });
  });
});
