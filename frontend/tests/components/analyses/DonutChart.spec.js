/**
 * Unit tests for DonutChart component
 *
 * Tests cover:
 * - Component renders with chart data
 * - Accessibility attributes (role, aria-labelledby, title, desc)
 * - Export menu renders and emits events
 * - Export handlers are called correctly
 *
 * Note: Uses shallowMount with Vuetify stubs to avoid full Vuetify resolution.
 *
 * @module tests/components/analyses/DonutChart
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, flushPromises } from '@vue/test-utils';
import DonutChart from '@/components/analyses/DonutChart.vue';
import * as exportUtils from '@/utils/export';

// Stub Vuetify components to avoid resolution errors
const vuetifyStubs = {
  'v-menu': {
    template: '<div class="v-menu"><slot /><slot name="activator" :props="{}" /></div>',
  },
  'v-btn': {
    template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>',
    props: ['variant', 'size', 'color'],
    emits: ['click'],
  },
  'v-icon': {
    template: '<i class="v-icon"><slot /></i>',
    props: ['start', 'size'],
  },
  'v-list': {
    template: '<div class="v-list"><slot /></div>',
    props: ['density'],
  },
  'v-list-item': {
    template:
      '<div class="v-list-item" @click="$emit(\'click\')"><slot /><slot name="prepend" /></div>',
    emits: ['click'],
  },
  'v-list-item-title': {
    template: '<span class="v-list-item-title"><slot /></span>',
  },
};

// Stub ChartExportMenu to emit events
const ChartExportMenuStub = {
  name: 'ChartExportMenu',
  template: `
    <div class="chart-export-menu">
      <button class="export-png-btn" @click="$emit('export-png')">PNG</button>
      <button class="export-csv-btn" @click="$emit('export-csv')">CSV</button>
    </div>
  `,
  emits: ['export-png', 'export-csv'],
};

/**
 * Sample chart data for testing
 */
const fixture_chartData = {
  total_count: 100,
  grouped_counts: [
    { _id: 'Male', count: 60 },
    { _id: 'Female', count: 40 },
  ],
};

/**
 * Helper function to mount DonutChart with common options
 * @param {Object} props - Component props
 * @returns {Wrapper} Vue test utils wrapper
 */
function mountChart(props = {}) {
  return shallowMount(DonutChart, {
    props: {
      chartData: fixture_chartData,
      ...props,
    },
    global: {
      stubs: {
        ...vuetifyStubs,
        ChartExportMenu: ChartExportMenuStub,
      },
    },
    attachTo: document.body,
  });
}

describe('DonutChart', () => {
  beforeEach(() => {
    // Mock export utilities
    vi.spyOn(exportUtils, 'exportToPNG').mockImplementation(() => {});
    vi.spyOn(exportUtils, 'exportToCSV').mockImplementation(() => {});
    vi.spyOn(exportUtils, 'getTimestamp').mockReturnValue('2026-01-20');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders chart container', () => {
      const wrapper = mountChart();
      expect(wrapper.find('.donut-chart-container').exists()).toBe(true);
    });

    it('renders chart wrapper', () => {
      const wrapper = mountChart();
      expect(wrapper.find('.chart-wrapper').exists()).toBe(true);
    });

    it('renders chart div with ref', () => {
      const wrapper = mountChart();
      expect(wrapper.find('.chart').exists()).toBe(true);
    });

    it('renders legend div', () => {
      const wrapper = mountChart();
      expect(wrapper.find('.legend').exists()).toBe(true);
    });

    it('renders chart header with export menu', () => {
      const wrapper = mountChart();
      expect(wrapper.find('.chart-header').exists()).toBe(true);
      expect(wrapper.find('.chart-export-menu').exists()).toBe(true);
    });

    it('has correct component name', () => {
      const wrapper = mountChart();
      expect(wrapper.vm.$options.name).toBe('DonutChart');
    });
  });

  describe('SVG creation', async () => {
    it('creates SVG element on mount', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const svg = wrapper.find('.chart svg');
      expect(svg.exists()).toBe(true);
    });

    it('creates SVG with correct dimensions', async () => {
      const wrapper = mountChart({ width: 400, height: 300 });
      await flushPromises();

      const svg = wrapper.find('.chart svg');
      expect(svg.attributes('width')).toBe('400');
      expect(svg.attributes('height')).toBe('300');
    });

    it('creates slice paths for each data item', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const slices = wrapper.findAll('.chart svg path.slice');
      expect(slices.length).toBe(2); // Male and Female
    });
  });

  describe('accessibility', () => {
    it('adds role="img" to SVG', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const svg = wrapper.find('.chart svg');
      expect(svg.attributes('role')).toBe('img');
    });

    it('adds aria-labelledby to SVG', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const svg = wrapper.find('.chart svg');
      const ariaLabelledby = svg.attributes('aria-labelledby');
      expect(ariaLabelledby).toBeTruthy();
      expect(ariaLabelledby).toContain('donut-title-');
      expect(ariaLabelledby).toContain('donut-desc-');
    });

    it('creates title element in SVG', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const title = wrapper.find('.chart svg title');
      expect(title.exists()).toBe(true);
      expect(title.text()).toBe('Distribution Chart');
    });

    it('creates desc element with data description', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const desc = wrapper.find('.chart svg desc');
      expect(desc.exists()).toBe(true);
      expect(desc.text()).toContain('100 total items');
      expect(desc.text()).toContain('Male');
      expect(desc.text()).toContain('Female');
    });

    it('adds aria-hidden to slice paths', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const slices = wrapper.findAll('.chart svg path.slice');
      slices.forEach((slice) => {
        expect(slice.attributes('aria-hidden')).toBe('true');
      });
    });

    it('adds aria-hidden to central text', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const text = wrapper.find('.chart svg text');
      expect(text.attributes('aria-hidden')).toBe('true');
    });
  });

  describe('export functionality', () => {
    it('renders ChartExportMenu component', () => {
      const wrapper = mountChart();
      expect(wrapper.findComponent({ name: 'ChartExportMenu' }).exists()).toBe(true);
    });

    it('calls exportToPNG when export-png event is emitted', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const pngBtn = wrapper.find('.export-png-btn');
      await pngBtn.trigger('click');
      await flushPromises();

      expect(exportUtils.exportToPNG).toHaveBeenCalled();
    });

    it('calls exportToCSV when export-csv event is emitted', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const csvBtn = wrapper.find('.export-csv-btn');
      await csvBtn.trigger('click');
      await flushPromises();

      expect(exportUtils.exportToCSV).toHaveBeenCalled();
    });

    it('exports PNG with correct filename and scale', async () => {
      const wrapper = mountChart();
      await flushPromises();

      wrapper.vm.handleExportPNG();

      expect(exportUtils.exportToPNG).toHaveBeenCalledWith(
        expect.any(SVGSVGElement),
        'donut-chart-2026-01-20',
        2
      );
    });

    it('exports CSV with correct headers', async () => {
      const wrapper = mountChart();
      await flushPromises();

      wrapper.vm.handleExportCSV();

      expect(exportUtils.exportToCSV).toHaveBeenCalledWith(
        expect.any(Array),
        ['category', 'count', 'percentage'],
        'donut-chart-2026-01-20'
      );
    });

    it('exports CSV with correct data', async () => {
      const wrapper = mountChart();
      await flushPromises();

      wrapper.vm.handleExportCSV();

      const callArgs = exportUtils.exportToCSV.mock.calls[0];
      const exportedData = callArgs[0];

      expect(exportedData).toHaveLength(2);
      expect(exportedData[0]).toEqual({
        category: 'Male',
        count: 60,
        percentage: '60.0',
      });
      expect(exportedData[1]).toEqual({
        category: 'Female',
        count: 40,
        percentage: '40.0',
      });
    });
  });

  describe('props', () => {
    it('requires chartData prop', () => {
      const props = DonutChart.props;
      expect(props.chartData.required).toBe(true);
    });

    it('has default width of 600', () => {
      const props = DonutChart.props;
      expect(props.width.default).toBe(600);
    });

    it('has default height of 500', () => {
      const props = DonutChart.props;
      expect(props.height.default).toBe(500);
    });

    it('has default margin of 50', () => {
      const props = DonutChart.props;
      expect(props.margin.default).toBe(50);
    });

    it('has exportable prop with default false', () => {
      const props = DonutChart.props;
      expect(props.exportable.default).toBe(false);
    });

    it('has colorMap prop with default null', () => {
      const props = DonutChart.props;
      expect(props.colorMap.default).toBe(null);
    });
  });

  describe('data reactivity', () => {
    it('re-renders chart when chartData changes', async () => {
      const wrapper = mountChart();
      await flushPromises();

      const renderSpy = vi.spyOn(wrapper.vm, 'renderChart');

      await wrapper.setProps({
        chartData: {
          total_count: 200,
          grouped_counts: [
            { _id: 'A', count: 100 },
            { _id: 'B', count: 100 },
          ],
        },
      });

      await flushPromises();

      expect(renderSpy).toHaveBeenCalled();
    });
  });

  describe('methods', () => {
    it('has arcTween method', () => {
      const wrapper = mountChart();
      expect(typeof wrapper.vm.arcTween).toBe('function');
    });

    it('has renderChart method', () => {
      const wrapper = mountChart();
      expect(typeof wrapper.vm.renderChart).toBe('function');
    });

    it('has handleExportPNG method', () => {
      const wrapper = mountChart();
      expect(typeof wrapper.vm.handleExportPNG).toBe('function');
    });

    it('has handleExportCSV method', () => {
      const wrapper = mountChart();
      expect(typeof wrapper.vm.handleExportCSV).toBe('function');
    });
  });

  describe('edge cases', () => {
    it('handles empty grouped_counts array', async () => {
      const wrapper = mountChart({
        chartData: {
          total_count: 0,
          grouped_counts: [],
        },
      });
      await flushPromises();

      const slices = wrapper.findAll('.chart svg path.slice');
      expect(slices.length).toBe(0);
    });

    it('handles missing grouped_counts', async () => {
      const wrapper = mountChart({
        chartData: {
          total_count: 0,
        },
      });
      await flushPromises();

      // Should not throw error
      expect(wrapper.find('.chart svg').exists()).toBe(true);
    });

    it('does not call exportToPNG when no SVG exists', async () => {
      const wrapper = mountChart();

      // Mock querySelector to return null
      const chartRef = wrapper.vm.$refs.chart;
      vi.spyOn(chartRef, 'querySelector').mockReturnValue(null);

      wrapper.vm.handleExportPNG();

      expect(exportUtils.exportToPNG).not.toHaveBeenCalled();
    });

    it('does not call exportToCSV when no chartData.grouped_counts', async () => {
      const wrapper = mountChart({
        chartData: {
          total_count: 0,
        },
      });

      wrapper.vm.handleExportCSV();

      expect(exportUtils.exportToCSV).not.toHaveBeenCalled();
    });
  });
});
