/**
 * Unit tests for StackedBarChart component
 *
 * Tests cover:
 * - Component rendering
 * - Accessibility attributes (role, aria-labelledby, title, desc)
 * - Export functionality (PNG and CSV)
 * - Animation configuration
 * - CKD aggregation logic
 * - Props validation
 *
 * Note: D3 rendering is mocked to focus on component logic.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import StackedBarChart from '@/components/analyses/StackedBarChart.vue';

// Mock D3 to avoid DOM rendering issues in tests
vi.mock('d3', () => {
  const mockSelection = () => ({
    selectAll: vi.fn(() => ({
      remove: vi.fn(),
      data: vi.fn(() => ({
        enter: vi.fn(() => ({
          append: vi.fn(() => mockSelection()),
        })),
        join: vi.fn(() => mockSelection()),
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
    insert: vi.fn(function () {
      return this;
    }),
    datum: vi.fn(() => mockSelection()),
    on: vi.fn(function () {
      return this;
    }),
    transition: vi.fn(function () {
      return this;
    }),
    duration: vi.fn(function () {
      return this;
    }),
    delay: vi.fn(function () {
      return this;
    }),
    html: vi.fn(function () {
      return this;
    }),
    each: vi.fn(function () {
      return this;
    }),
  });

  return {
    select: vi.fn(() => mockSelection()),
    scaleBand: vi.fn(() => {
      const scale = vi.fn((val) => val);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      scale.padding = vi.fn(() => scale);
      scale.bandwidth = vi.fn(() => 20);
      return scale;
    }),
    scaleLinear: vi.fn(() => {
      const scale = vi.fn((val) => val * 10);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      scale.nice = vi.fn(() => scale);
      return scale;
    }),
    scaleOrdinal: vi.fn(() => {
      const scale = vi.fn((i) => `#color${i}`);
      scale.domain = vi.fn(() => scale);
      scale.range = vi.fn(() => scale);
      return scale;
    }),
    max: vi.fn((arr, fn) => {
      if (!arr || arr.length === 0) return 0;
      const values = arr.map(fn || ((x) => x));
      return Math.max(...values.filter((v) => v !== undefined && v !== null));
    }),
    stack: vi.fn(() => ({
      keys: vi.fn(() => vi.fn(() => [])),
    })),
    axisBottom: vi.fn(() => ({
      ticks: vi.fn(function () {
        return this;
      }),
    })),
    axisLeft: vi.fn(() => vi.fn()),
  };
});

// Mock chartAccessibility
vi.mock('@/utils/chartAccessibility', () => ({
  addChartAccessibility: vi.fn(),
  generateBarChartDescription: vi.fn(() => 'Bar chart description'),
}));

// Mock chartAnimation
vi.mock('@/utils/chartAnimation', () => ({
  getAnimationDuration: vi.fn(() => 400),
  getStaggerDelay: vi.fn((index, delay) => index * delay),
}));

// Mock export utilities
vi.mock('@/utils/export', () => ({
  exportToPNG: vi.fn(),
  exportToCSV: vi.fn(),
  getTimestamp: vi.fn(() => '2026-01-20'),
}));

// Sample chart data for testing
const createSampleChartData = () => [
  {
    label: 'Renal cyst',
    count: 450,
    details: {
      hpo_id: 'HP:0000107',
      present_count: 450,
      absent_count: 200,
      not_reported_count: 50,
    },
  },
  {
    label: 'Diabetes mellitus',
    count: 300,
    details: {
      hpo_id: 'HP:0000819',
      present_count: 300,
      absent_count: 350,
      not_reported_count: 50,
    },
  },
  {
    label: 'Hypomagnesemia',
    count: 250,
    details: {
      hpo_id: 'HP:0002917',
      present_count: 250,
      absent_count: 400,
      not_reported_count: 50,
    },
  },
];

// Sample CKD data for aggregation testing
const createCKDChartData = () => [
  {
    label: 'Chronic kidney disease',
    count: 100,
    details: {
      hpo_id: 'HP:0012622',
      present_count: 100,
      absent_count: 200,
      not_reported_count: 400,
    },
  },
  {
    label: 'Stage 3 chronic kidney disease',
    count: 80,
    details: {
      hpo_id: 'HP:0012625',
      present_count: 80,
      absent_count: 220,
      not_reported_count: 400,
    },
  },
  {
    label: 'Stage 5 chronic kidney disease',
    count: 50,
    details: {
      hpo_id: 'HP:0003774',
      present_count: 50,
      absent_count: 250,
      not_reported_count: 400,
    },
  },
  {
    label: 'Renal cyst',
    count: 450,
    details: {
      hpo_id: 'HP:0000107',
      present_count: 450,
      absent_count: 200,
      not_reported_count: 50,
    },
  },
];

describe('StackedBarChart', () => {
  describe('Component Mounting', () => {
    it('should mount successfully with valid data', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.exists()).toBe(true);
      expect(wrapper.find('.stacked-bar-chart-container').exists()).toBe(true);
    });

    it('should mount with empty data', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: [],
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.exists()).toBe(true);
    });

    it('should mount with null data', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: null,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('Props Validation', () => {
    it('should accept custom displayLimit', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
          displayLimit: 10,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.props('displayLimit')).toBe(10);
    });

    it('should accept custom width and height', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
          width: 800,
          height: 500,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.props('width')).toBe(800);
      expect(wrapper.props('height')).toBe(500);
    });

    it('should accept custom margin', () => {
      const customMargin = { top: 50, right: 100, bottom: 150, left: 250 };
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
          margin: customMargin,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.props('margin')).toEqual(customMargin);
    });

    it('should accept custom colorRange', () => {
      const customColors = ['#FF0000', '#00FF00', '#0000FF'];
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
          colorRange: customColors,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.props('colorRange')).toEqual(customColors);
    });

    it('should have default props', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.props('displayLimit')).toBe(20);
      expect(wrapper.props('width')).toBe(1000);
      expect(wrapper.props('height')).toBe(600);
      expect(wrapper.props('colorRange')).toEqual(['#4CAF50', '#F44336', '#9E9E9E']);
    });
  });

  describe('ChartExportMenu Integration', () => {
    it('should render ChartExportMenu component', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.findComponent({ name: 'ChartExportMenu' }).exists()).toBe(true);
    });

    it('should have chart-header container for export menu', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(wrapper.find('.chart-header').exists()).toBe(true);
    });
  });

  describe('Export Functionality', () => {
    let wrapper;
    let exportToCSV;
    let getTimestamp;

    beforeEach(async () => {
      // Re-import mocks to get fresh references
      const exportModule = await import('@/utils/export');
      exportToCSV = exportModule.exportToCSV;
      getTimestamp = exportModule.getTimestamp;

      // Clear mock calls
      vi.clearAllMocks();

      wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });
    });

    it('should have handleExportPNG method', () => {
      expect(typeof wrapper.vm.handleExportPNG).toBe('function');
    });

    it('should have handleExportCSV method', () => {
      expect(typeof wrapper.vm.handleExportCSV).toBe('function');
    });

    it('should call exportToCSV with correct data structure', () => {
      wrapper.vm.handleExportCSV();

      expect(exportToCSV).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            phenotype: expect.any(String),
            hpo_id: expect.any(String),
            present_count: expect.any(Number),
            absent_count: expect.any(Number),
            not_reported_count: expect.any(Number),
            penetrance_percent: expect.any(String),
          }),
        ]),
        [
          'phenotype',
          'hpo_id',
          'present_count',
          'absent_count',
          'not_reported_count',
          'penetrance_percent',
        ],
        'phenotype-prevalence-2026-01-20'
      );
    });

    it('should calculate penetrance correctly in CSV export', () => {
      wrapper.vm.handleExportCSV();

      const exportCall = exportToCSV.mock.calls[0];
      const exportedData = exportCall[0];

      // First item: Renal cyst - 450 present, 200 absent
      // Penetrance = 450 / (450 + 200) * 100 = 69.2%
      const renalCyst = exportedData.find((d) => d.phenotype === 'Renal cyst');
      expect(renalCyst.penetrance_percent).toBe('69.2');
    });

    it('should use correct filename format for exports', () => {
      wrapper.vm.handleExportCSV();

      expect(getTimestamp).toHaveBeenCalled();
      expect(exportToCSV).toHaveBeenCalledWith(
        expect.anything(),
        expect.anything(),
        'phenotype-prevalence-2026-01-20'
      );
    });
  });

  describe('CKD Aggregation Logic', () => {
    it('should aggregate CKD stages into a single entry', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createCKDChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const aggregated = wrapper.vm.aggregateCKDStages(createCKDChartData());

      // Should have aggregated CKD + non-CKD entries
      // Original: 3 CKD entries + 1 non-CKD = 4
      // After aggregation: 1 CKD entry + 1 non-CKD = 2
      expect(aggregated.length).toBe(2);
    });

    it('should use max present count for aggregated CKD entry', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createCKDChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const aggregated = wrapper.vm.aggregateCKDStages(createCKDChartData());
      const ckdEntry = aggregated.find((d) => d.label === 'Chronic Kidney Disease');

      // Max present count among CKD stages is 100 (from HP:0012622)
      expect(ckdEntry.details.present_count).toBe(100);
    });

    it('should return original data if no CKD entries', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const result = wrapper.vm.aggregateCKDStages(createSampleChartData());

      expect(result).toEqual(createSampleChartData());
    });

    it('should mark aggregated CKD entry with aggregated HPO ID', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createCKDChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const aggregated = wrapper.vm.aggregateCKDStages(createCKDChartData());
      const ckdEntry = aggregated.find((d) => d.label === 'Chronic Kidney Disease');

      expect(ckdEntry.details.hpo_id).toBe('HP:0012622 (aggregated)');
    });
  });

  describe('Accessibility', () => {
    it('should call addChartAccessibility when rendering chart', async () => {
      const { addChartAccessibility } = await import('@/utils/chartAccessibility');

      shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(addChartAccessibility).toHaveBeenCalled();
    });

    it('should call generateBarChartDescription with chart data', async () => {
      const { generateBarChartDescription } = await import('@/utils/chartAccessibility');

      shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(generateBarChartDescription).toHaveBeenCalled();
    });
  });

  describe('Animation', () => {
    it('should call getAnimationDuration when rendering chart', async () => {
      const { getAnimationDuration } = await import('@/utils/chartAnimation');

      shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(getAnimationDuration).toHaveBeenCalledWith(400);
    });
  });

  describe('Watcher Behavior', () => {
    it('should have deep watcher on chartData', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.chartData).toBeDefined();
      expect(watchers.chartData.deep).toBe(true);
    });

    it('should have watcher on displayLimit', () => {
      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      const watchers = wrapper.vm.$options.watch;
      expect(watchers.displayLimit).toBeDefined();
    });
  });

  describe('Lifecycle Hooks', () => {
    it('should add resize listener on mount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      expect(addEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      addEventListenerSpy.mockRestore();
    });

    it('should remove resize listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      wrapper.unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));
      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Data Transformation', () => {
    it('should limit data based on displayLimit prop', async () => {
      const { exportToCSV } = await import('@/utils/export');
      vi.clearAllMocks();

      const wrapper = shallowMount(StackedBarChart, {
        props: {
          chartData: createSampleChartData(),
          displayLimit: 2,
        },
        global: {
          stubs: {
            ChartExportMenu: true,
          },
        },
      });

      // Call handleExportCSV to verify data is limited
      wrapper.vm.handleExportCSV();

      const exportedData = exportToCSV.mock.calls[0][0];
      expect(exportedData.length).toBe(2);
    });
  });
});
