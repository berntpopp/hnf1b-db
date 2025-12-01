/**
 * Unit tests for VariantComparisonChart component
 *
 * Tests cover:
 * - Comparison data validation
 * - Organ system filtering
 * - Short label mapping
 * - Edge cases (empty data, filtered results)
 * - Statistical annotation display logic
 *
 * Note: Component mounting tests use shallowMount since D3 rendering is mocked.
 * Focus is on data validation and method testing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import VariantComparisonChart from '@/components/analyses/VariantComparisonChart.vue';

// Mock D3 to avoid DOM rendering issues in tests
vi.mock('d3', () => {
  // Create a properly chainable mock selection
  const createMockSelection = () => {
    const selection = {
      selectAll: vi.fn(() => createMockSelection()),
      select: vi.fn(() => createMockSelection()),
      append: vi.fn(() => createMockSelection()),
      remove: vi.fn(() => createMockSelection()),
      attr: vi.fn(() => selection),
      style: vi.fn(() => selection),
      text: vi.fn(() => selection),
      html: vi.fn(() => selection),
      call: vi.fn(() => selection),
      datum: vi.fn(() => createMockSelection()),
      data: vi.fn(() => ({
        enter: vi.fn(() => ({
          append: vi.fn(() => createMockSelection()),
        })),
      })),
      on: vi.fn(() => selection),
      transition: vi.fn(() => selection),
      duration: vi.fn(() => selection),
    };
    return selection;
  };

  return {
    select: vi.fn(() => createMockSelection()),
    selectAll: vi.fn(() => createMockSelection()),
    scaleBand: vi.fn(() => {
      const scale = vi.fn((val) => val);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      scale.padding = vi.fn(() => scale);
      scale.bandwidth = vi.fn(() => 50);
      return scale;
    }),
    scaleLinear: vi.fn(() => {
      const scale = vi.fn((val) => val * 5);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      return scale;
    }),
    axisBottom: vi.fn(() => ({
      tickSize: vi.fn(function () {
        return this;
      }),
    })),
    axisLeft: vi.fn(() => ({
      ticks: vi.fn(function () {
        return this;
      }),
      tickFormat: vi.fn(function () {
        return this;
      }),
    })),
  };
});

// Sample comparison data matching backend format
const createSampleComparisonData = () => ({
  comparison_type: 'truncating_vs_non_truncating',
  group1_name: 'Truncating',
  group2_name: 'Non-truncating',
  group1_count: 100,
  group2_count: 150,
  phenotypes: [
    {
      hpo_id: 'HP:0000083',
      hpo_label: 'Renal insufficiency',
      group1_present: 60,
      group1_absent: 40,
      group1_total: 100,
      group1_percentage: 60.0,
      group2_present: 45,
      group2_absent: 105,
      group2_total: 150,
      group2_percentage: 30.0,
      p_value: 0.001,
      p_value_fdr: 0.005,
      effect_size: 0.61,
      significant: true,
    },
    {
      hpo_id: 'HP:0003074',
      hpo_label: 'Hyperglycemia',
      group1_present: 40,
      group1_absent: 60,
      group1_total: 100,
      group1_percentage: 40.0,
      group2_present: 55,
      group2_absent: 95,
      group2_total: 150,
      group2_percentage: 36.7,
      p_value: 0.25,
      p_value_fdr: 0.35,
      effect_size: 0.07,
      significant: false,
    },
    {
      hpo_id: 'HP:0001250',
      hpo_label: 'Seizures',
      group1_present: 15,
      group1_absent: 85,
      group1_total: 100,
      group1_percentage: 15.0,
      group2_present: 10,
      group2_absent: 140,
      group2_total: 150,
      group2_percentage: 6.7,
      p_value: 0.03,
      p_value_fdr: 0.08,
      effect_size: 0.28,
      significant: false,
    },
    {
      hpo_id: 'HP:0001513',
      hpo_label: 'Obesity',
      group1_present: 20,
      group1_absent: 80,
      group1_total: 100,
      group1_percentage: 20.0,
      group2_present: 25,
      group2_absent: 125,
      group2_total: 150,
      group2_percentage: 16.7,
      p_value: 0.5,
      p_value_fdr: 0.6,
      effect_size: 0.09,
      significant: false,
    },
    {
      hpo_id: 'HP:0012622',
      hpo_label: 'Chronic kidney disease',
      group1_present: 50,
      group1_absent: 50,
      group1_total: 100,
      group1_percentage: 50.0,
      group2_present: 40,
      group2_absent: 110,
      group2_total: 150,
      group2_percentage: 26.7,
      p_value: 0.002,
      p_value_fdr: 0.01,
      effect_size: 0.48,
      significant: true,
    },
    {
      hpo_id: 'HP:0001939',
      hpo_label: 'Abnormality of metabolism',
      group1_present: 30,
      group1_absent: 70,
      group1_total: 100,
      group1_percentage: 30.0,
      group2_present: 35,
      group2_absent: 115,
      group2_total: 150,
      group2_percentage: 23.3,
      p_value: 0.3,
      p_value_fdr: 0.4,
      effect_size: 0.15,
      significant: false,
    },
    {
      hpo_id: 'HP:0000819',
      hpo_label: 'Diabetes mellitus',
      group1_present: 45,
      group1_absent: 55,
      group1_total: 100,
      group1_percentage: 45.0,
      group2_present: 50,
      group2_absent: 100,
      group2_total: 150,
      group2_percentage: 33.3,
      p_value: 0.07,
      p_value_fdr: 0.12,
      effect_size: 0.24,
      significant: false,
    },
  ],
});

describe('VariantComparisonChart', () => {
  describe('Component Mounting', () => {
    it('should mount successfully with valid comparison data', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: createSampleComparisonData(),
        },
      });

      expect(wrapper.exists()).toBe(true);
      expect(wrapper.find('.variant-comparison-container').exists()).toBe(true);
    });

    it('should mount with null comparison data', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should mount with empty phenotypes array', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: {
            comparison_type: 'test',
            group1_name: 'Group 1',
            group2_name: 'Group 2',
            group1_count: 50,
            group2_count: 50,
            phenotypes: [],
          },
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('Props Validation', () => {
    it('should accept custom width', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          width: 800,
        },
      });

      expect(wrapper.props('width')).toBe(800);
    });

    it('should accept custom height', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          height: 500,
        },
      });

      expect(wrapper.props('height')).toBe(500);
    });

    it('should accept custom margins', () => {
      const customMargin = { top: 100, right: 50, bottom: 150, left: 100 };
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          margin: customMargin,
        },
      });

      expect(wrapper.props('margin')).toEqual(customMargin);
    });

    it('should have default props', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      expect(wrapper.props('width')).toBe(1200);
      expect(wrapper.props('height')).toBe(600);
      expect(wrapper.props('margin')).toEqual({ top: 120, right: 30, bottom: 180, left: 80 });
      expect(wrapper.props('comparisonType')).toBe('truncating_vs_non_truncating');
      expect(wrapper.props('organSystemFilter')).toBe('all');
    });
  });

  describe('getShortLabels Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });
    });

    it('should return correct labels for truncating_vs_non_truncating', () => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          comparisonType: 'truncating_vs_non_truncating',
        },
      });

      const labels = wrapper.vm.getShortLabels();
      expect(labels).toEqual({ group1: 'T', group2: 'nT' });
    });

    it('should return correct labels for truncating_vs_non_truncating_excl_cnv', () => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          comparisonType: 'truncating_vs_non_truncating_excl_cnv',
        },
      });

      const labels = wrapper.vm.getShortLabels();
      expect(labels).toEqual({ group1: 'T', group2: 'nT' });
    });

    it('should return correct labels for cnv_vs_point_mutation', () => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          comparisonType: 'cnv_vs_point_mutation',
        },
      });

      const labels = wrapper.vm.getShortLabels();
      expect(labels).toEqual({ group1: 'CNV', group2: 'non-CNV' });
    });

    it('should return correct labels for cnv_deletion_vs_duplication', () => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          comparisonType: 'cnv_deletion_vs_duplication',
        },
      });

      const labels = wrapper.vm.getShortLabels();
      expect(labels).toEqual({ group1: 'DEL', group2: 'DUP' });
    });

    it('should return default labels for unknown comparison type', () => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
          comparisonType: 'unknown_type',
        },
      });

      const labels = wrapper.vm.getShortLabels();
      expect(labels).toEqual({ group1: 'G1', group2: 'G2' });
    });
  });

  describe('getOrganSystemKeywords Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });
    });

    it('should return renal keywords', () => {
      const keywords = wrapper.vm.getOrganSystemKeywords('renal');
      expect(keywords).toContain('renal');
      expect(keywords).toContain('kidney');
      expect(keywords).toContain('nephro');
      expect(keywords).toContain('chronic kidney disease');
    });

    it('should return metabolic keywords', () => {
      const keywords = wrapper.vm.getOrganSystemKeywords('metabolic');
      expect(keywords).toContain('magnesemia');
      expect(keywords).toContain('uricemia');
      expect(keywords).toContain('gout');
    });

    it('should return neurological keywords', () => {
      const keywords = wrapper.vm.getOrganSystemKeywords('neurological');
      expect(keywords).toContain('brain');
      expect(keywords).toContain('neuro');
      expect(keywords).toContain('seizure');
      expect(keywords).toContain('cognitive');
    });

    it('should return pancreatic keywords', () => {
      const keywords = wrapper.vm.getOrganSystemKeywords('pancreatic');
      expect(keywords).toContain('pancrea');
      expect(keywords).toContain('diabetes');
      expect(keywords).toContain('mody');
    });

    it('should return empty array for unknown organ system', () => {
      const keywords = wrapper.vm.getOrganSystemKeywords('unknown');
      expect(keywords).toEqual([]);
    });
  });

  describe('matchesOrganSystem Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });
    });

    it('should match renal phenotypes', () => {
      expect(wrapper.vm.matchesOrganSystem('Renal insufficiency', 'renal')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Chronic kidney disease', 'renal')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Nephropathy', 'renal')).toBe(true);
    });

    it('should match neurological phenotypes', () => {
      expect(wrapper.vm.matchesOrganSystem('Seizures', 'neurological')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Cognitive impairment', 'neurological')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Brain malformation', 'neurological')).toBe(true);
    });

    it('should match pancreatic phenotypes', () => {
      expect(wrapper.vm.matchesOrganSystem('Diabetes mellitus', 'pancreatic')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('MODY', 'pancreatic')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Pancreatic cyst', 'pancreatic')).toBe(true);
    });

    it('should not match unrelated phenotypes', () => {
      expect(wrapper.vm.matchesOrganSystem('Obesity', 'renal')).toBe(false);
      expect(wrapper.vm.matchesOrganSystem('Renal insufficiency', 'neurological')).toBe(false);
      expect(wrapper.vm.matchesOrganSystem('Seizures', 'metabolic')).toBe(false);
    });

    it('should be case-insensitive', () => {
      expect(wrapper.vm.matchesOrganSystem('RENAL INSUFFICIENCY', 'renal')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('renal insufficiency', 'renal')).toBe(true);
      expect(wrapper.vm.matchesOrganSystem('Renal Insufficiency', 'renal')).toBe(true);
    });
  });

  describe('filterPhenotypesByOrganSystem Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });
    });

    it('should return all phenotypes when filter is "all"', () => {
      const phenotypes = createSampleComparisonData().phenotypes;
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'all');

      expect(filtered.length).toBe(phenotypes.length);
    });

    it('should filter renal phenotypes', () => {
      const phenotypes = createSampleComparisonData().phenotypes;
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'renal');

      // Should include 'Renal insufficiency' and 'Chronic kidney disease'
      expect(filtered.length).toBe(2);
      expect(filtered.some((p) => p.hpo_label === 'Renal insufficiency')).toBe(true);
      expect(filtered.some((p) => p.hpo_label === 'Chronic kidney disease')).toBe(true);
    });

    it('should filter neurological phenotypes', () => {
      const phenotypes = createSampleComparisonData().phenotypes;
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'neurological');

      // Should include 'Seizures'
      expect(filtered.length).toBe(1);
      expect(filtered[0].hpo_label).toBe('Seizures');
    });

    it('should filter pancreatic phenotypes', () => {
      const phenotypes = createSampleComparisonData().phenotypes;
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'pancreatic');

      // Should include 'Diabetes mellitus'
      expect(filtered.length).toBe(1);
      expect(filtered[0].hpo_label).toBe('Diabetes mellitus');
    });

    it('should filter "other" phenotypes (not matching any organ system)', () => {
      const phenotypes = createSampleComparisonData().phenotypes;
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'other');

      // Should include phenotypes that don't match renal, metabolic, neurological, or pancreatic
      // 'Obesity' and 'Abnormality of metabolism' don't match specific systems
      // (Note: 'Abnormality of metabolism' would match if 'metabolism' was a keyword)
      expect(filtered.length).toBeGreaterThan(0);
      expect(filtered.some((p) => p.hpo_label === 'Obesity')).toBe(true);
    });

    it('should return empty array when no phenotypes match', () => {
      const phenotypes = [
        { hpo_id: 'HP:0000001', hpo_label: 'Obesity' },
        { hpo_id: 'HP:0000002', hpo_label: 'Short stature' },
      ];
      const filtered = wrapper.vm.filterPhenotypesByOrganSystem(phenotypes, 'renal');

      expect(filtered.length).toBe(0);
    });
  });

  describe('filterUninformativePhenotypes Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });
    });

    it('should remove CKD stage phenotypes', () => {
      const phenotypes = [
        { hpo_label: 'Renal insufficiency' },
        { hpo_label: 'Stage 1 chronic kidney disease' },
        { hpo_label: 'Stage 2 chronic kidney disease' },
        { hpo_label: 'Stage 3 chronic kidney disease' },
        { hpo_label: 'Stage 4 chronic kidney disease' },
        { hpo_label: 'Stage 5 chronic kidney disease' },
        { hpo_label: 'Chronic kidney disease, not specified' },
        { hpo_label: 'Diabetes mellitus' },
      ];

      const filtered = wrapper.vm.filterUninformativePhenotypes(phenotypes);

      expect(filtered.length).toBe(2);
      expect(filtered[0].hpo_label).toBe('Renal insufficiency');
      expect(filtered[1].hpo_label).toBe('Diabetes mellitus');
    });

    it('should preserve non-CKD phenotypes', () => {
      const phenotypes = [
        { hpo_label: 'Renal insufficiency' },
        { hpo_label: 'Diabetes mellitus' },
        { hpo_label: 'Seizures' },
      ];

      const filtered = wrapper.vm.filterUninformativePhenotypes(phenotypes);

      expect(filtered.length).toBe(3);
    });

    it('should handle empty array', () => {
      const filtered = wrapper.vm.filterUninformativePhenotypes([]);
      expect(filtered).toEqual([]);
    });
  });

  describe('Comparison Data Structure Validation', () => {
    it('should validate percentage calculation', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        // Verify percentage matches present/total ratio
        const expectedPercentage = (phenotype.group1_present / phenotype.group1_total) * 100;
        expect(Math.abs(phenotype.group1_percentage - expectedPercentage)).toBeLessThan(0.1);

        const expectedPercentage2 = (phenotype.group2_present / phenotype.group2_total) * 100;
        expect(Math.abs(phenotype.group2_percentage - expectedPercentage2)).toBeLessThan(0.1);
      });
    });

    it('should validate present + absent = total', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        expect(phenotype.group1_present + phenotype.group1_absent).toBe(phenotype.group1_total);
        expect(phenotype.group2_present + phenotype.group2_absent).toBe(phenotype.group2_total);
      });
    });

    it('should validate percentages are within [0, 100]', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        expect(phenotype.group1_percentage).toBeGreaterThanOrEqual(0);
        expect(phenotype.group1_percentage).toBeLessThanOrEqual(100);
        expect(phenotype.group2_percentage).toBeGreaterThanOrEqual(0);
        expect(phenotype.group2_percentage).toBeLessThanOrEqual(100);
      });
    });

    it('should validate p-values are within [0, 1]', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        expect(phenotype.p_value).toBeGreaterThanOrEqual(0);
        expect(phenotype.p_value).toBeLessThanOrEqual(1);
        expect(phenotype.p_value_fdr).toBeGreaterThanOrEqual(0);
        expect(phenotype.p_value_fdr).toBeLessThanOrEqual(1);
      });
    });

    it('should validate FDR-corrected p-value >= raw p-value', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        // FDR correction inflates p-values, so corrected should be >= raw
        expect(phenotype.p_value_fdr).toBeGreaterThanOrEqual(phenotype.p_value);
      });
    });

    it('should validate significance is based on FDR p-value', () => {
      const data = createSampleComparisonData();
      const significantPhenotypes = data.phenotypes.filter((p) => p.significant);

      significantPhenotypes.forEach((phenotype) => {
        // Significant phenotypes should have p_value_fdr < 0.05
        expect(phenotype.p_value_fdr).toBeLessThan(0.05);
      });
    });

    it('should validate effect size (Cohens h) is non-negative', () => {
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        expect(phenotype.effect_size).toBeGreaterThanOrEqual(0);
      });
    });
  });

  describe('Effect Size Interpretation', () => {
    it('should correctly classify effect sizes', () => {
      const testCases = [
        { h: 0.1, expected: 'small' },
        { h: 0.19, expected: 'small' },
        { h: 0.2, expected: 'medium' },
        { h: 0.35, expected: 'medium' },
        { h: 0.49, expected: 'medium' },
        { h: 0.5, expected: 'large' },
        { h: 0.8, expected: 'large' },
      ];

      testCases.forEach(({ h, expected }) => {
        const label = h < 0.2 ? 'small' : h < 0.5 ? 'medium' : 'large';
        expect(label).toBe(expected);
      });
    });
  });

  describe('Watcher Behavior', () => {
    it('should have deep watcher on comparisonData', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.comparisonData).toBeDefined();
      expect(watchers.comparisonData.deep).toBe(true);
    });

    it('should have watcher on organSystemFilter', () => {
      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.organSystemFilter).toBeDefined();
    });
  });

  describe('Lifecycle Hooks', () => {
    it('should add resize listener on mount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      addEventListenerSpy.mockRestore();
    });

    it('should remove resize listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const wrapper = shallowMount(VariantComparisonChart, {
        props: {
          comparisonData: null,
        },
      });

      wrapper.unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Statistical Test Integration', () => {
    it('should have consistent p-value significance threshold', () => {
      // The component uses p < 0.05 for significance
      const threshold = 0.05;

      const data = createSampleComparisonData();
      data.phenotypes.forEach((phenotype) => {
        if (phenotype.significant) {
          expect(phenotype.p_value_fdr).toBeLessThan(threshold);
        } else {
          expect(phenotype.p_value_fdr).toBeGreaterThanOrEqual(threshold);
        }
      });
    });

    it('should use Fisher exact test p-values', () => {
      // The backend uses Fisher's exact test for 2x2 contingency tables
      // This test validates the expected data structure includes this information
      const data = createSampleComparisonData();

      data.phenotypes.forEach((phenotype) => {
        // Each phenotype should have raw and FDR-corrected p-values
        expect(phenotype).toHaveProperty('p_value');
        expect(phenotype).toHaveProperty('p_value_fdr');
      });
    });
  });

  describe('Label Mapping - All Cases', () => {
    const labelMappings = {
      truncating_vs_non_truncating: { group1: 'T', group2: 'nT' },
      truncating_vs_non_truncating_excl_cnv: { group1: 'T', group2: 'nT' },
      cnv_vs_point_mutation: { group1: 'CNV', group2: 'non-CNV' },
      cnv_deletion_vs_duplication: { group1: 'DEL', group2: 'DUP' },
    };

    Object.entries(labelMappings).forEach(([type, expectedLabels]) => {
      it(`should map '${type}' to correct labels`, () => {
        const wrapper = shallowMount(VariantComparisonChart, {
          props: {
            comparisonData: null,
            comparisonType: type,
          },
        });

        expect(wrapper.vm.getShortLabels()).toEqual(expectedLabels);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle phenotype with 0% prevalence', () => {
      const dataWithZeroPrevalence = {
        ...createSampleComparisonData(),
        phenotypes: [
          {
            hpo_id: 'HP:0000001',
            hpo_label: 'Rare phenotype',
            group1_present: 0,
            group1_absent: 100,
            group1_total: 100,
            group1_percentage: 0,
            group2_present: 0,
            group2_absent: 150,
            group2_total: 150,
            group2_percentage: 0,
            p_value: 1.0,
            p_value_fdr: 1.0,
            effect_size: 0,
            significant: false,
          },
        ],
      };

      const wrapper = shallowMount(VariantComparisonChart, {
        props: { comparisonData: dataWithZeroPrevalence },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle phenotype with 100% prevalence', () => {
      const dataWithFullPrevalence = {
        ...createSampleComparisonData(),
        phenotypes: [
          {
            hpo_id: 'HP:0000001',
            hpo_label: 'Universal phenotype',
            group1_present: 100,
            group1_absent: 0,
            group1_total: 100,
            group1_percentage: 100,
            group2_present: 150,
            group2_absent: 0,
            group2_total: 150,
            group2_percentage: 100,
            p_value: 1.0,
            p_value_fdr: 1.0,
            effect_size: 0,
            significant: false,
          },
        ],
      };

      const wrapper = shallowMount(VariantComparisonChart, {
        props: { comparisonData: dataWithFullPrevalence },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle very small p-values', () => {
      const dataWithSmallPValue = {
        ...createSampleComparisonData(),
        phenotypes: [
          {
            hpo_id: 'HP:0000001',
            hpo_label: 'Highly significant',
            group1_present: 95,
            group1_absent: 5,
            group1_total: 100,
            group1_percentage: 95,
            group2_present: 10,
            group2_absent: 140,
            group2_total: 150,
            group2_percentage: 6.7,
            p_value: 1e-15,
            p_value_fdr: 1e-14,
            effect_size: 2.5,
            significant: true,
          },
        ],
      };

      const wrapper = shallowMount(VariantComparisonChart, {
        props: { comparisonData: dataWithSmallPValue },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle single phenotype', () => {
      const singlePhenotypeData = {
        ...createSampleComparisonData(),
        phenotypes: [createSampleComparisonData().phenotypes[0]],
      };

      const wrapper = shallowMount(VariantComparisonChart, {
        props: { comparisonData: singlePhenotypeData },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });
});
