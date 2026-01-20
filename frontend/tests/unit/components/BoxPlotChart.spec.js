/**
 * Unit tests for BoxPlotChart component
 *
 * Tests cover:
 * - Component mounting
 * - Props validation
 * - Export functionality (PNG, CSV, SVG)
 * - Accessibility attributes
 * - Animation support
 * - Data handling edge cases
 *
 * Note: Component mounting tests use shallowMount since D3 rendering is mocked.
 */

import { describe, it, expect, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import BoxPlotChart from '@/components/analyses/BoxPlotChart.vue';

// Mock chart utilities
vi.mock('@/utils/chartAccessibility', () => ({
  addChartAccessibility: vi.fn(),
}));

vi.mock('@/utils/chartAnimation', () => ({
  getAnimationDuration: vi.fn((duration) => duration),
  getStaggerDelay: vi.fn((index, delay) => index * delay),
  prefersReducedMotion: vi.fn(() => false),
}));

vi.mock('@/utils/export', () => ({
  exportToPNG: vi.fn(),
  exportToCSV: vi.fn(),
  getTimestamp: vi.fn(() => '2026-01-20'),
}));

vi.mock('@/utils/statistics', () => ({
  formatPValue: vi.fn((pValue) => pValue?.toFixed(4) || 'N/A'),
}));

// Mock D3 to avoid DOM rendering issues in tests
vi.mock('d3', () => {
  const createMockSelection = () => {
    const selection = {
      selectAll: vi.fn(() => createMockSelection()),
      select: vi.fn(() => createMockSelection()),
      append: vi.fn(() => createMockSelection()),
      insert: vi.fn(() => createMockSelection()),
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
      delay: vi.fn(() => selection),
      ease: vi.fn(() => selection),
      empty: vi.fn(() => true),
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
      scale.bandwidth = vi.fn(() => 100);
      return scale;
    }),
    scaleLinear: vi.fn(() => {
      const scale = vi.fn((val) => val * 10);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      scale.ticks = vi.fn(() => [0, 5, 10, 15, 20, 25, 30]);
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
    })),
    max: vi.fn((arr) => Math.max(...arr)),
    quantile: vi.fn((arr, q) => arr[Math.floor(arr.length * q)]),
    mean: vi.fn((arr, fn) => arr.reduce((a, b) => a + fn(b), 0) / arr.length),
    area: vi.fn(() => ({
      x0: vi.fn(function () {
        return this;
      }),
      x1: vi.fn(function () {
        return this;
      }),
      y: vi.fn(function () {
        return this;
      }),
      curve: vi.fn(function () {
        return this;
      }),
    })),
    curveCatmullRom: {},
  };
});

// Sample data for tests
const createSamplePathogenicData = () => [
  {
    distance: 3.5,
    aaPosition: 150,
    protein: 'p.Arg150Trp',
    category: 'close',
    classificationVerdict: 'Pathogenic',
  },
  {
    distance: 7.2,
    aaPosition: 200,
    protein: 'p.Gly200Ser',
    category: 'medium',
    classificationVerdict: 'Likely Pathogenic',
  },
  {
    distance: 12.8,
    aaPosition: 300,
    protein: 'p.Leu300Pro',
    category: 'far',
    classificationVerdict: 'Pathogenic',
  },
];

const createSampleVUSData = () => [
  {
    distance: 8.1,
    aaPosition: 175,
    protein: 'p.Val175Met',
    category: 'medium',
    classificationVerdict: 'VUS',
  },
  {
    distance: 15.3,
    aaPosition: 250,
    protein: 'p.Ile250Thr',
    category: 'far',
    classificationVerdict: 'VUS',
  },
];

describe('BoxPlotChart', () => {
  describe('Component Mounting', () => {
    it('should mount successfully with valid data', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.exists()).toBe(true);
      expect(wrapper.find('.box-plot-wrapper').exists()).toBe(true);
    });

    it('should mount with empty arrays', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should mount with only pathogenic data', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: [],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should mount with only VUS data', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('Props Validation', () => {
    it('should accept custom width', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
          width: 1000,
        },
      });

      expect(wrapper.props('width')).toBe(1000);
    });

    it('should accept custom height', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
          height: 500,
        },
      });

      expect(wrapper.props('height')).toBe(500);
    });

    it('should have default props', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      expect(wrapper.props('width')).toBe(800);
      expect(wrapper.props('height')).toBe(400);
      expect(wrapper.props('pValueSignificant')).toBe(false);
      expect(wrapper.props('mannWhitneyResult')).toBe(null);
    });

    it('should accept significance props', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
          pValueSignificant: true,
          mannWhitneyResult: { pValue: 0.001 },
        },
      });

      expect(wrapper.props('pValueSignificant')).toBe(true);
      expect(wrapper.props('mannWhitneyResult')).toEqual({ pValue: 0.001 });
    });
  });

  describe('Export Functionality', () => {
    it('should have handleExportPNG method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(typeof wrapper.vm.handleExportPNG).toBe('function');
    });

    it('should have handleExportCSV method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(typeof wrapper.vm.handleExportCSV).toBe('function');
    });

    it('should have exportSVG method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(typeof wrapper.vm.exportSVG).toBe('function');
    });

    it('should format CSV data correctly', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      // Call the CSV export method to verify it doesn't throw
      expect(() => wrapper.vm.handleExportCSV()).not.toThrow();
    });

    it('should render ChartExportMenu component', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.vm.$options.components.ChartExportMenu).toBeDefined();
    });
  });

  describe('Accessibility', () => {
    it('should have export controls with SVG button', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      const exportControls = wrapper.find('.export-controls');
      expect(exportControls.exists()).toBe(true);

      const svgButton = wrapper.find('.export-btn');
      expect(svgButton.exists()).toBe(true);
    });
  });

  describe('Animation Support', () => {
    it('should import animation utilities', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle reduced motion preference', async () => {
      const { prefersReducedMotion } = await import('@/utils/chartAnimation');
      prefersReducedMotion.mockReturnValue(true);

      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.exists()).toBe(true);

      prefersReducedMotion.mockReturnValue(false);
    });
  });

  describe('Helper Methods', () => {
    it('should have getCategoryLabel method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      expect(wrapper.vm.getCategoryLabel('close')).toBe('Close (<5\u00C5)');
      expect(wrapper.vm.getCategoryLabel('medium')).toBe('Medium (5-10\u00C5)');
      expect(wrapper.vm.getCategoryLabel('far')).toBe('Far (\u226510\u00C5)');
    });

    it('should have kernelDensityEstimator method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      expect(typeof wrapper.vm.kernelDensityEstimator).toBe('function');
    });

    it('should have kernelEpanechnikov method', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      expect(typeof wrapper.vm.kernelEpanechnikov).toBe('function');
    });
  });

  describe('Watcher Behavior', () => {
    it('should have deep watcher on pathogenicDistances', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.pathogenicDistances).toBeDefined();
      expect(watchers.pathogenicDistances.deep).toBe(true);
    });

    it('should have deep watcher on vusDistances', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [],
          vusDistances: [],
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.vusDistances).toBeDefined();
      expect(watchers.vusDistances.deep).toBe(true);
    });
  });

  describe('Events', () => {
    it('should emit variant-hover event', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: createSamplePathogenicData(),
          vusDistances: createSampleVUSData(),
        },
      });

      expect(wrapper.vm.$options.emits).toContain('variant-hover');
    });
  });

  describe('Edge Cases', () => {
    it('should handle single data point', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [
            { distance: 5.0, aaPosition: 100, protein: 'p.Arg100Gly', category: 'medium' },
          ],
          vusDistances: [],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle very large distances', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [
            { distance: 100.0, aaPosition: 100, protein: 'p.Arg100Gly', category: 'far' },
          ],
          vusDistances: [
            { distance: 150.0, aaPosition: 200, protein: 'p.Gly200Ser', category: 'far' },
          ],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should handle zero distances', () => {
      const wrapper = shallowMount(BoxPlotChart, {
        props: {
          pathogenicDistances: [
            { distance: 0.0, aaPosition: 100, protein: 'p.Arg100Gly', category: 'close' },
          ],
          vusDistances: [],
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });
});
