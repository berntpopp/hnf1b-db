<template>
  <div class="donut-chart-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />
    <div class="chart-wrapper">
      <div ref="chart" class="chart" aria-hidden="true" />
      <div ref="legend" class="legend" />
    </div>
    <details class="chart-data-table">
      <summary>View data as table</summary>
      <table>
        <thead>
          <tr>
            <th v-for="c in exportColumns" :key="c.key">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in exportRows" :key="i">
            <td v-for="c in exportColumns" :key="c.key">{{ r[c.key] }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>

<script>
// Import D3 and utilities for exporting.
import * as d3 from 'd3';
import { ref, computed } from 'vue';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';

export default {
  name: 'DonutChart',
  components: { ChartExportMenu },
  props: {
    /**
     * The data to be plotted.
     * Expected format:
     * {
     *   total_count: Number,
     *   grouped_counts: [ { _id: string, count: number }, … ]
     * }
     */
    chartData: { type: Object, required: true },
    /** Width of the chart (in pixels) */
    width: { type: Number, default: 600 },
    /** Height of the chart (in pixels) */
    height: { type: Number, default: 500 },
    /** Margin (in pixels) used to compute the donut radius */
    margin: { type: Number, default: 50 },
    /** Color scheme for the donut slices (fallback when colorMap not provided) */
    colorScheme: {
      type: Array,
      default: () => [...d3.schemeCategory10, ...d3.schemePaired],
    },
    /**
     * Color map for semantic coloring (label -> color).
     */
    colorMap: { type: Object, default: null },
    /** Human-readable chart name used for ARIA + export filenames. */
    chartName: { type: String, default: 'Donut chart' },
  },
  setup(props) {
    const svgEl = ref(null);
    const exportRows = computed(() => {
      const entries = props.chartData?.grouped_counts ?? [];
      const total = props.chartData?.total_count ?? entries.reduce((s, e) => s + e.count, 0);
      return entries.map((e) => ({
        group: e._id,
        count: e.count,
        percent: total ? ((e.count / total) * 100).toFixed(1) : '0.0',
      }));
    });
    const exportColumns = [
      { key: 'group', label: 'Group' },
      { key: 'count', label: 'Count' },
      { key: 'percent', label: 'Percent' },
    ];
    const summary = computed(() => {
      const entries = props.chartData?.grouped_counts ?? [];
      const total = props.chartData?.total_count ?? entries.reduce((s, e) => s + e.count, 0);
      if (!entries.length) return `${props.chartName}: no data.`;
      const parts = entries.map(
        (e) => `${e._id}: ${e.count} (${total ? ((e.count / total) * 100).toFixed(1) : '0.0'}%)`
      );
      return `${props.chartName}. ${parts.join(', ')}. Total ${total}.`;
    });
    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    return { svgEl, exportRows, exportColumns, ...a11y };
  },
  data() {
    return {};
  },
  watch: {
    // Redraw the chart if the data changes.
    chartData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    // Re-render when the responsive width/height change so the donut and its
    // centre label scale down to fit narrow (mobile) containers.
    width() {
      this.renderChart();
    },
    height() {
      this.renderChart();
    },
  },
  mounted() {
    this.renderChart();
  },
  methods: {
    /**
     * Render the donut chart using D3.
     */
    renderChart() {
      // Remove any existing chart content.
      d3.select(this.$refs.chart).selectAll('*').remove();

      const { width, height, margin } = this;
      const radius = Math.min(width, height) / 2 - margin;

      // Create the SVG element. Capture the root <svg> so the export menu can read it.
      // Drive the rendered size with CSS (width:100%; height:auto; max-width) so
      // the SVG scales to its container on mobile instead of forcing a fixed
      // pixel width that overflows / clips the donut. The viewBox keeps the
      // internal coordinate system intact.
      const svgRoot = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('width', '100%')
        .style('height', 'auto')
        .style('max-width', `${width}px`);
      this.svgEl = svgRoot.node();
      const svg = svgRoot.append('g').attr('transform', `translate(${width / 2}, ${height / 2})`);

      // Create a tooltip div within the chart container.
      const tooltip = d3
        .select(this.$refs.chart)
        .append('div')
        .attr('class', 'tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background-color', 'white')
        .style('border', '1px solid #ccc')
        .style('padding', '8px')
        .style('border-radius', '4px');

      // Process input data.
      const dataObj = {};
      if (this.chartData.grouped_counts && Array.isArray(this.chartData.grouped_counts)) {
        this.chartData.grouped_counts.forEach((item) => {
          dataObj[item._id] = item.count;
        });
      }
      const dataEntries = Object.entries(dataObj);
      const totalValue =
        this.chartData.total_count || dataEntries.reduce((sum, [, value]) => sum + value, 0);

      // Set up the color scale.
      // Use colorMap for semantic coloring if provided, otherwise fall back to colorScheme
      const colorMap = this.colorMap;
      const fallbackColor = d3.scaleOrdinal().domain(Object.keys(dataObj)).range(this.colorScheme);
      const color = (label) => {
        if (colorMap && colorMap[label]) {
          return colorMap[label];
        }
        return fallbackColor(label);
      };

      // Compute the positions for each slice.
      const pie = d3
        .pie()
        .sort(null)
        .value((d) => d[1]);
      const dataReady = pie(dataEntries);

      // Define the arc generator for the donut slices.
      const arc = d3
        .arc()
        .innerRadius(radius * 0.5) // Size of the donut hole.
        .outerRadius(radius * 0.8);

      // Append the donut slices.
      svg
        .selectAll('path.slice')
        .data(dataReady)
        .enter()
        .append('path')
        .attr('class', 'slice')
        .attr('d', arc)
        .attr('fill', (d) => color(d.data[0]))
        .attr('stroke', 'white')
        .style('stroke-width', '2px')
        .style('opacity', 0.7)
        .on('mouseover', (event, d) => {
          d3.select(event.currentTarget).style('stroke', 'black');
          tooltip.transition().duration(200).style('opacity', 1);
          tooltip.html(
            `Group: <strong>${d.data[0]}</strong><br>Count: <strong>${d.data[1]}</strong>`
          );
        })
        .on('mousemove', (event) => {
          // Recalculate container's bounding rectangle on each mousemove.
          const rect = this.$refs.chart.getBoundingClientRect();
          tooltip
            .style('left', event.clientX - rect.left + 5 + 'px')
            .style('top', event.clientY - rect.top + 5 + 'px');
        })
        .on('mouseout', (event) => {
          d3.select(event.currentTarget).style('stroke', 'white');
          tooltip.transition().duration(200).style('opacity', 0);
        });

      // Append a central text element that shows the total count.
      // Scale the font to the donut hole (innerRadius = radius * 0.5) so the
      // full label always fits, even at 320–360px container widths, instead of
      // a fixed 40px that clips on small donuts.
      const holeRadius = radius * 0.5;
      const labelLen = String(totalValue).length || 1;
      const centerFont = Math.max(
        14,
        Math.min(40, Math.floor((holeRadius * 1.7) / Math.max(labelLen, 2)))
      );
      svg
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', `${centerFont}px`)
        .attr('fill', '#5CB85C')
        .text(totalValue);

      // Create legend
      const legend = d3.select(this.$refs.legend);
      legend.selectAll('*').remove();

      const legendItems = legend
        .selectAll('.legend-item')
        .data(dataReady)
        .enter()
        .append('div')
        .attr('class', 'legend-item')
        .style('display', 'flex')
        .style('align-items', 'center')
        .style('margin-bottom', '8px')
        .style('cursor', 'pointer')
        .on('mouseover', function (event, d) {
          // Highlight corresponding slice
          svg.selectAll('path.slice').style('opacity', (slice) => (slice === d ? 1 : 0.3));
        })
        .on('mouseout', function () {
          // Reset all slices
          svg.selectAll('path.slice').style('opacity', 0.7);
        });

      // Add color box
      legendItems
        .append('div')
        .style('width', '16px')
        .style('height', '16px')
        .style('background-color', (d) => color(d.data[0]))
        .style('margin-right', '8px')
        .style('border', '1px solid #999')
        .style('flex-shrink', '0');

      // Add label
      legendItems
        .append('div')
        .style('font-size', '14px')
        .style('line-height', '1.2')
        .html((d) => {
          const percentage = ((d.data[1] / totalValue) * 100).toFixed(1);
          return `<strong>${d.data[0]}</strong>: ${d.data[1]} (${percentage}%)`;
        });
    },
  },
};
</script>

<style scoped>
.donut-chart-container {
  position: relative;
  width: 100%;
  margin: auto;
}

.chart-wrapper {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 24px;
}

.chart {
  /* Fill the row but allow shrinking so the SVG (width:100%) scales down on
     narrow screens instead of forcing horizontal overflow. */
  flex: 1 1 280px;
  min-width: 0;
  position: relative;
}

.chart :deep(svg) {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
}

.legend {
  flex: 1 1 220px;
  /* No min-width that would exceed a 320px viewport; the legend wraps below the
     donut on phones and sits beside it on wider screens. */
  min-width: 0;
  max-height: 500px;
  overflow-y: auto;
  padding: 10px;
}

/* Tooltip styling */
.tooltip {
  pointer-events: none;
  font-size: 14px;
  color: #333;
}

.chart-data-table {
  margin-top: 16px;
  font-size: 14px;
}
.chart-data-table summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.chart-data-table table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.chart-data-table th,
.chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
}
</style>
