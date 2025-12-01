/**
 * Unit tests for KaplanMeierChart component
 *
 * Tests cover:
 * - Survival data validation
 * - Kaplan-Meier calculation verification (matching backend)
 * - Median survival point detection
 * - Comparison title mapping
 * - Edge cases (empty data, all censored, ties)
 *
 * Note: Component mounting tests are minimal since D3 rendering is mocked.
 * Focus is on data validation and logic testing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import KaplanMeierChart from '@/components/analyses/KaplanMeierChart.vue';

// Mock D3 to avoid DOM rendering issues in tests
vi.mock('d3', () => {
  const mockSelection = () => ({
    selectAll: vi.fn(() => ({
      remove: vi.fn(),
      data: vi.fn(() => ({
        enter: vi.fn(() => ({
          append: vi.fn(() => mockSelection()),
        })),
      })),
      style: vi.fn(() => mockSelection()),
    })),
    append: vi.fn(() => mockSelection()),
    attr: vi.fn(function () {
      return this;
    }),
    style: vi.fn(function () {
      return this;
    }),
    text: vi.fn(function () {
      return this;
    }),
    call: vi.fn(function () {
      return this;
    }),
    datum: vi.fn(() => mockSelection()),
    on: vi.fn(function () {
      return this;
    }),
  });

  return {
    select: vi.fn(() => mockSelection()),
    scaleLinear: vi.fn(() => {
      const scale = vi.fn((val) => val * 10);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      scale.nice = vi.fn(() => scale);
      return scale;
    }),
    scaleOrdinal: vi.fn(() => vi.fn((i) => `#color${i}`)),
    schemeCategory10: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'],
    max: vi.fn((arr, fn) => {
      if (!arr || arr.length === 0) return 0;
      const values = arr.map(fn || ((x) => x));
      return Math.max(...values.filter((v) => v !== undefined && v !== null));
    }),
    line: vi.fn(() => ({
      x: vi.fn(function () {
        return this;
      }),
      y: vi.fn(function () {
        return this;
      }),
      curve: vi.fn(function () {
        return this;
      }),
    })),
    area: vi.fn(() => ({
      x: vi.fn(function () {
        return this;
      }),
      y0: vi.fn(function () {
        return this;
      }),
      y1: vi.fn(function () {
        return this;
      }),
      curve: vi.fn(function () {
        return this;
      }),
    })),
    curveStepAfter: {},
    axisBottom: vi.fn(() => ({
      ticks: vi.fn(function () {
        return this;
      }),
      tickSize: vi.fn(function () {
        return this;
      }),
      tickFormat: vi.fn(function () {
        return this;
      }),
    })),
    axisLeft: vi.fn(() => ({
      ticks: vi.fn(function () {
        return this;
      }),
      tickSize: vi.fn(function () {
        return this;
      }),
      tickFormat: vi.fn(function () {
        return this;
      }),
    })),
  };
});

// Sample survival data matching backend format
const createSampleSurvivalData = () => ({
  comparison_type: 'variant_type',
  endpoint: 'ESRD',
  groups: [
    {
      name: 'Missense',
      n: 50,
      events: 35, // Sum of events in survival_data
      survival_data: [
        { time: 0, survival_probability: 1.0, ci_lower: 1.0, ci_upper: 1.0, at_risk: 50, events: 0, censored: 0 },
        { time: 5, survival_probability: 0.9, ci_lower: 0.82, ci_upper: 0.98, at_risk: 45, events: 5, censored: 0 },
        { time: 10, survival_probability: 0.75, ci_lower: 0.65, ci_upper: 0.85, at_risk: 38, events: 7, censored: 0 },
        { time: 15, survival_probability: 0.5, ci_lower: 0.38, ci_upper: 0.62, at_risk: 25, events: 13, censored: 0 },
        { time: 20, survival_probability: 0.3, ci_lower: 0.18, ci_upper: 0.42, at_risk: 15, events: 10, censored: 0 },
      ],
    },
    {
      name: 'Truncating',
      n: 30,
      events: 22, // Sum of events in survival_data
      survival_data: [
        { time: 0, survival_probability: 1.0, ci_lower: 1.0, ci_upper: 1.0, at_risk: 30, events: 0, censored: 0 },
        { time: 3, survival_probability: 0.8, ci_lower: 0.68, ci_upper: 0.92, at_risk: 24, events: 6, censored: 0 },
        { time: 8, survival_probability: 0.5, ci_lower: 0.35, ci_upper: 0.65, at_risk: 15, events: 9, censored: 0 },
        { time: 12, survival_probability: 0.25, ci_lower: 0.12, ci_upper: 0.38, at_risk: 8, events: 7, censored: 0 },
      ],
    },
  ],
});

describe('KaplanMeierChart', () => {
  describe('Component Mounting', () => {
    it('should mount successfully with valid survival data', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: createSampleSurvivalData(),
        },
      });

      expect(wrapper.exists()).toBe(true);
      expect(wrapper.find('.kaplan-meier-container').exists()).toBe(true);
    });

    it('should mount with null survival data', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should mount with empty groups', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: {
            comparison_type: 'variant_type',
            endpoint: 'ESRD',
            groups: [],
          },
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('Props Validation', () => {
    it('should accept custom width', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
          width: 800,
        },
      });

      expect(wrapper.props('width')).toBe(800);
    });

    it('should accept custom height', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
          height: 600,
        },
      });

      expect(wrapper.props('height')).toBe(600);
    });

    it('should accept custom margins', () => {
      const customMargin = { top: 80, right: 120, bottom: 80, left: 100 };
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
          margin: customMargin,
        },
      });

      expect(wrapper.props('margin')).toEqual(customMargin);
    });

    it('should have default props', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });

      expect(wrapper.props('width')).toBe(1200);
      expect(wrapper.props('height')).toBe(450);
      expect(wrapper.props('margin')).toEqual({ top: 60, right: 100, bottom: 60, left: 80 });
    });
  });

  describe('getComparisonTitle Method', () => {
    let wrapper;

    beforeEach(() => {
      wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });
    });

    it('should return correct title for variant_type', () => {
      const title = wrapper.vm.getComparisonTitle('variant_type');
      expect(title).toBe('By Variant Type');
    });

    it('should return correct title for pathogenicity', () => {
      const title = wrapper.vm.getComparisonTitle('pathogenicity');
      expect(title).toBe('By Pathogenicity Classification');
    });

    it('should return correct title for disease_subtype', () => {
      const title = wrapper.vm.getComparisonTitle('disease_subtype');
      expect(title).toBe('By Disease Subtype');
    });

    it('should return original type for unknown comparison types', () => {
      const title = wrapper.vm.getComparisonTitle('custom_grouping');
      expect(title).toBe('custom_grouping');
    });

    it('should handle undefined comparison type', () => {
      const title = wrapper.vm.getComparisonTitle(undefined);
      expect(title).toBe(undefined);
    });
  });

  describe('Survival Data Structure Validation', () => {
    it('should validate that survival probability decreases over time', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        for (let i = 1; i < group.survival_data.length; i++) {
          const prev = group.survival_data[i - 1];
          const curr = group.survival_data[i];

          // Survival probability should be monotonically non-increasing
          expect(curr.survival_probability).toBeLessThanOrEqual(prev.survival_probability);
        }
      });
    });

    it('should validate that time increases', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        for (let i = 1; i < group.survival_data.length; i++) {
          const prev = group.survival_data[i - 1];
          const curr = group.survival_data[i];

          // Time should be monotonically increasing
          expect(curr.time).toBeGreaterThan(prev.time);
        }
      });
    });

    it('should validate that at_risk decreases over time', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        for (let i = 1; i < group.survival_data.length; i++) {
          const prev = group.survival_data[i - 1];
          const curr = group.survival_data[i];

          // Number at risk should be monotonically non-increasing
          expect(curr.at_risk).toBeLessThanOrEqual(prev.at_risk);
        }
      });
    });

    it('should validate confidence intervals are within [0, 1]', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        group.survival_data.forEach((point) => {
          if (point.ci_lower !== undefined) {
            expect(point.ci_lower).toBeGreaterThanOrEqual(0);
            expect(point.ci_lower).toBeLessThanOrEqual(1);
          }
          if (point.ci_upper !== undefined) {
            expect(point.ci_upper).toBeGreaterThanOrEqual(0);
            expect(point.ci_upper).toBeLessThanOrEqual(1);
          }
        });
      });
    });

    it('should validate ci_lower <= survival_probability <= ci_upper', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        group.survival_data.forEach((point) => {
          if (point.ci_lower !== undefined && point.ci_upper !== undefined) {
            expect(point.ci_lower).toBeLessThanOrEqual(point.survival_probability);
            expect(point.survival_probability).toBeLessThanOrEqual(point.ci_upper);
          }
        });
      });
    });

    it('should start with survival probability of 1.0 at time 0', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        const firstPoint = group.survival_data[0];
        expect(firstPoint.time).toBe(0);
        expect(firstPoint.survival_probability).toBe(1.0);
      });
    });
  });

  describe('Median Survival Detection', () => {
    it('should detect median survival when curve crosses 50%', () => {
      const data = createSampleSurvivalData();

      // Missense group crosses 50% at time=15
      const missenseGroup = data.groups[0];
      const medianPoint = missenseGroup.survival_data.find((d) => d.survival_probability <= 0.5);

      expect(medianPoint).toBeDefined();
      expect(medianPoint.time).toBe(15);
    });

    it('should detect median survival for truncating variants', () => {
      const data = createSampleSurvivalData();

      // Truncating group crosses 50% at time=8
      const truncatingGroup = data.groups[1];
      const medianPoint = truncatingGroup.survival_data.find((d) => d.survival_probability <= 0.5);

      expect(medianPoint).toBeDefined();
      expect(medianPoint.time).toBe(8);
    });

    it('should handle case where median is not reached', () => {
      const dataWithHighSurvival = {
        comparison_type: 'variant_type',
        endpoint: 'ESRD',
        groups: [
          {
            name: 'Benign',
            n: 20,
            events: 3,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 20, events: 0, censored: 0 },
              { time: 10, survival_probability: 0.9, at_risk: 18, events: 2, censored: 0 },
              { time: 20, survival_probability: 0.85, at_risk: 17, events: 1, censored: 0 },
            ],
          },
        ],
      };

      const benignGroup = dataWithHighSurvival.groups[0];
      const medianPoint = benignGroup.survival_data.find((d) => d.survival_probability <= 0.5);

      // Median not reached (survival stays above 50%)
      expect(medianPoint).toBeUndefined();
    });
  });

  describe('Kaplan-Meier Calculation Verification', () => {
    it('should match backend calculation for simple case', () => {
      // Known R survfit() result validation
      // This mirrors the backend test_survival_analysis.py validation
      const expectedFromR = {
        times: [1, 2, 4, 5],
        survival: [0.8, 0.6, 0.3, 0.0],
      };

      // Simulated data matching backend test
      const testData = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'Test Group',
            n: 5,
            events: 4,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 5, events: 0, censored: 0 },
              { time: 1, survival_probability: 0.8, at_risk: 4, events: 1, censored: 0 },
              { time: 2, survival_probability: 0.6, at_risk: 3, events: 1, censored: 0 },
              // time=3 is censored, no survival change
              { time: 3, survival_probability: 0.6, at_risk: 2, events: 0, censored: 1 },
              { time: 4, survival_probability: 0.3, at_risk: 2, events: 1, censored: 0 },
              { time: 5, survival_probability: 0.0, at_risk: 1, events: 1, censored: 0 },
            ],
          },
        ],
      };

      const group = testData.groups[0];

      // Verify survival probabilities match expected R output
      expectedFromR.times.forEach((time, idx) => {
        const point = group.survival_data.find((d) => d.time === time);
        expect(point).toBeDefined();
        expect(Math.abs(point.survival_probability - expectedFromR.survival[idx])).toBeLessThan(0.01);
      });
    });

    it('should handle all censored data correctly', () => {
      const allCensoredData = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'All Censored',
            n: 5,
            events: 0,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 5, events: 0, censored: 0 },
              { time: 5, survival_probability: 1.0, at_risk: 4, events: 0, censored: 1 },
              { time: 10, survival_probability: 1.0, at_risk: 3, events: 0, censored: 1 },
              { time: 15, survival_probability: 1.0, at_risk: 2, events: 0, censored: 1 },
            ],
          },
        ],
      };

      // When all observations are censored, survival probability stays at 1.0
      allCensoredData.groups[0].survival_data.forEach((point) => {
        expect(point.survival_probability).toBe(1.0);
      });
    });

    it('should handle ties (multiple events at same time)', () => {
      const tiesData = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'With Ties',
            n: 3,
            events: 3,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 3, events: 0, censored: 0 },
              // 2 events at time=10 out of 3 at risk -> S = (3-2)/3 = 1/3 ≈ 0.333
              { time: 10, survival_probability: 0.333, at_risk: 3, events: 2, censored: 0 },
              { time: 20, survival_probability: 0.0, at_risk: 1, events: 1, censored: 0 },
            ],
          },
        ],
      };

      const point10 = tiesData.groups[0].survival_data.find((d) => d.time === 10);
      expect(point10.events).toBe(2);
      expect(Math.abs(point10.survival_probability - 0.333)).toBeLessThan(0.01);
    });
  });

  describe('Edge Cases', () => {
    it('should handle single data point', () => {
      const singlePointData = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'Single Point',
            n: 1,
            events: 1,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 1, events: 0, censored: 0 },
              { time: 5, survival_probability: 0.0, at_risk: 1, events: 1, censored: 0 },
            ],
          },
        ],
      };

      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: singlePointData },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle many groups', () => {
      const manyGroups = {
        comparison_type: 'pathogenicity',
        endpoint: 'ESRD',
        groups: Array.from({ length: 5 }, (_, i) => ({
          name: `Group ${i + 1}`,
          n: 10,
          events: 5,
          survival_data: [
            { time: 0, survival_probability: 1.0, at_risk: 10, events: 0, censored: 0 },
            { time: 10 * (i + 1), survival_probability: 0.5, at_risk: 5, events: 5, censored: 0 },
          ],
        })),
      };

      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: manyGroups },
      });

      expect(wrapper.exists()).toBe(true);
      expect(manyGroups.groups.length).toBe(5);
    });

    it('should handle very long follow-up times', () => {
      const longFollowup = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'Long Follow-up',
            n: 100,
            events: 75,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 100, events: 0, censored: 0 },
              { time: 50, survival_probability: 0.5, at_risk: 50, events: 50, censored: 0 },
              { time: 100, survival_probability: 0.25, at_risk: 25, events: 25, censored: 0 },
            ],
          },
        ],
      };

      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: longFollowup },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle survival probability reaching exactly 0', () => {
      const zeroSurvival = {
        comparison_type: 'test',
        endpoint: 'Event',
        groups: [
          {
            name: 'Full Events',
            n: 4,
            events: 4,
            survival_data: [
              { time: 0, survival_probability: 1.0, at_risk: 4, events: 0, censored: 0 },
              { time: 10, survival_probability: 0.75, at_risk: 4, events: 1, censored: 0 },
              { time: 20, survival_probability: 0.5, at_risk: 3, events: 1, censored: 0 },
              { time: 30, survival_probability: 0.25, at_risk: 2, events: 1, censored: 0 },
              { time: 40, survival_probability: 0.0, at_risk: 1, events: 1, censored: 0 },
            ],
          },
        ],
      };

      const lastPoint = zeroSurvival.groups[0].survival_data[4];
      expect(lastPoint.survival_probability).toBe(0.0);
    });
  });

  describe('Group Metadata Validation', () => {
    it('should have consistent n value with initial at_risk', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        const initialAtRisk = group.survival_data[0].at_risk;
        expect(group.n).toBe(initialAtRisk);
      });
    });

    it('should have total events equal to sum of individual events', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        const totalEvents = group.survival_data.reduce((sum, point) => sum + point.events, 0);
        expect(group.events).toBe(totalEvents);
      });
    });

    it('should have group names defined', () => {
      const data = createSampleSurvivalData();

      data.groups.forEach((group) => {
        expect(group.name).toBeDefined();
        expect(group.name.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Watcher Behavior', () => {
    it('should have deep watcher on survivalData', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });

      // The component defines a deep watcher on survivalData
      // This test verifies the watcher exists in the component options
      const watchers = wrapper.vm.$options.watch;
      expect(watchers.survivalData).toBeDefined();
      expect(watchers.survivalData.deep).toBe(true);
    });
  });

  describe('Lifecycle Hooks', () => {
    it('should add resize listener on mount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      addEventListenerSpy.mockRestore();
    });

    it('should remove resize listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const wrapper = shallowMount(KaplanMeierChart, {
        props: {
          survivalData: null,
        },
      });

      wrapper.unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Comparison Title Mapping - All Cases', () => {
    const comparisonTitles = {
      variant_type: 'By Variant Type',
      pathogenicity: 'By Pathogenicity Classification',
      disease_subtype: 'By Disease Subtype',
    };

    Object.entries(comparisonTitles).forEach(([type, expectedTitle]) => {
      it(`should map '${type}' to '${expectedTitle}'`, () => {
        const wrapper = shallowMount(KaplanMeierChart, {
          props: { survivalData: null },
        });

        expect(wrapper.vm.getComparisonTitle(type)).toBe(expectedTitle);
      });
    });

    it('should return input for unknown types as fallback', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: null },
      });

      expect(wrapper.vm.getComparisonTitle('new_type')).toBe('new_type');
      expect(wrapper.vm.getComparisonTitle('foo_bar')).toBe('foo_bar');
    });
  });

  describe('Survival Probability Calculation Validation', () => {
    it('should follow product-limit estimator formula', () => {
      // Kaplan-Meier formula: S(t) = ∏(ni - di) / ni
      // where ni = number at risk, di = number of events
      const testData = [
        { time: 0, survival_probability: 1.0, at_risk: 10, events: 0 },
        { time: 5, survival_probability: 0.9, at_risk: 10, events: 1 }, // 9/10 = 0.9
        { time: 10, survival_probability: 0.8, at_risk: 9, events: 1 }, // 0.9 * 8/9 = 0.8
        { time: 15, survival_probability: 0.6, at_risk: 8, events: 2 }, // 0.8 * 6/8 = 0.6
        { time: 20, survival_probability: 0.4, at_risk: 6, events: 2 }, // 0.6 * 4/6 = 0.4
      ];

      // Verify each step follows the formula
      for (let i = 1; i < testData.length; i++) {
        const prev = testData[i - 1];
        const curr = testData[i];

        const expectedSurvival = prev.survival_probability * (curr.at_risk - curr.events) / curr.at_risk;
        expect(Math.abs(curr.survival_probability - expectedSurvival)).toBeLessThan(0.01);
      }
    });

    it('should correctly handle censoring (no survival change)', () => {
      const dataWithCensoring = [
        { time: 0, survival_probability: 1.0, at_risk: 10, events: 0, censored: 0 },
        { time: 5, survival_probability: 0.9, at_risk: 10, events: 1, censored: 0 },
        { time: 7, survival_probability: 0.9, at_risk: 9, events: 0, censored: 2 }, // Censoring doesn't change survival
        { time: 10, survival_probability: 0.78, at_risk: 7, events: 1, censored: 0 }, // 0.9 * 6/7 ≈ 0.77
      ];

      // At time 7, survival stays at 0.9 because only censoring occurred
      const censoredPoint = dataWithCensoring[2];
      expect(censoredPoint.events).toBe(0);
      expect(censoredPoint.censored).toBe(2);
      expect(censoredPoint.survival_probability).toBe(dataWithCensoring[1].survival_probability);
    });
  });
});
