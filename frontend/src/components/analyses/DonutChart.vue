<template>
  <div class="donut-chart-container">
    <div class="chart-header">
      <ChartExportMenu @export-png="handleExportPNG" @export-csv="handleExportCSV" />
    </div>
    <div class="chart-wrapper">
      <!-- The div where the chart will be rendered -->
      <div ref="chart" class="chart" />
      <!-- Legend -->
      <div ref="legend" class="legend" />
    </div>
  </div>
</template>

<script>
// Import D3 and utilities for accessibility, animation, and export.
import * as d3 from 'd3';
import { addChartAccessibility, generateDonutDescription } from '@/utils/chartAccessibility';
import { getAnimationDuration, getStaggerDelay } from '@/utils/chartAnimation';
import { exportToPNG, exportToCSV, getTimestamp } from '@/utils/export';
import ChartExportMenu from '@/components/common/ChartExportMenu.vue';

export default {
  name: 'DonutChart',
  components: {
    ChartExportMenu,
  },
  props: {
    /**
     * The data to be plotted.
     * Expected format:
     * {
     *   total_count: Number,
     *   grouped_counts: [ { _id: string, count: number }, … ]
     * }
     */
    chartData: {
      type: Object,
      required: true,
    },
    /** Width of the chart (in pixels) */
    width: {
      type: Number,
      default: 600,
    },
    /** Height of the chart (in pixels) */
    height: {
      type: Number,
      default: 500,
    },
    /** Margin (in pixels) used to compute the donut radius */
    margin: {
      type: Number,
      default: 50,
    },
    /** Color scheme for the donut slices (fallback when colorMap not provided) */
    colorScheme: {
      type: Array,
      default: () => [...d3.schemeCategory10, ...d3.schemePaired],
    },
    /**
     * Color map for semantic coloring (label -> color).
     * When provided, labels are mapped to specific colors.
     * Example: { 'Pathogenic': '#D32F2F', 'Benign': '#388E3C' }
     */
    colorMap: {
      type: Object,
      default: null,
    },
    /**
     * If true, shows an export button that lets the user download the chart as PNG.
     */
    exportable: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiDownload: 'mdi-download',
      chartId: Math.random().toString(36).substring(2, 9),
      isInitialRender: true,
    };
  },
  watch: {
    // Redraw the chart if the data changes.
    chartData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
  },
  mounted() {
    this.renderChart();
  },
  methods: {
    /**
     * Create an arc tween function for smooth transitions.
     * Interpolates from the starting angle to the ending angle.
     * @param {Function} arc - D3 arc generator
     * @returns {Function} Tween function for D3 transitions
     */
    arcTween(arc) {
      return function (d) {
        const interpolate = d3.interpolate(this._current || { startAngle: 0, endAngle: 0 }, d);
        this._current = interpolate(1);
        return function (t) {
          return arc(interpolate(t));
        };
      };
    },

    /**
     * Render the donut chart using D3.
     */
    renderChart() {
      // Remove any existing chart content.
      d3.select(this.$refs.chart).selectAll('*').remove();

      const { width, height, margin } = this;
      const radius = Math.min(width, height) / 2 - margin;

      // Create the root SVG element.
      const rootSvg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

      // Create inner group for chart content
      const svg = rootSvg.append('g').attr('transform', `translate(${width / 2}, ${height / 2})`);

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

      // Add accessibility attributes to SVG
      const titleId = `donut-title-${this.chartId}`;
      const descId = `donut-desc-${this.chartId}`;
      const accessibilityData = dataEntries.map(([label, count]) => ({ label, count }));
      const description = generateDonutDescription(accessibilityData, totalValue);
      addChartAccessibility(rootSvg, titleId, descId, 'Distribution Chart', description);

      // Calculate animation parameters
      const duration = this.isInitialRender ? getAnimationDuration(400) : getAnimationDuration(200);
      const staggerDelayMs = 50;
      const arcTweenFn = this.arcTween(arc);

      // Append the donut slices with staggered entry animation.
      const slices = svg
        .selectAll('path.slice')
        .data(dataReady)
        .enter()
        .append('path')
        .attr('class', 'slice')
        .attr('fill', (d) => color(d.data[0]))
        .attr('stroke', 'white')
        .style('stroke-width', '2px')
        .style('opacity', 0.7)
        .attr('aria-hidden', 'true') // Decorative - data is in the description
        .each(function () {
          this._current = { startAngle: 0, endAngle: 0 };
        });

      // Apply animated transition if duration > 0, otherwise set path immediately
      if (duration > 0) {
        slices
          .transition()
          .duration(duration)
          .delay((d, i) => getStaggerDelay(i, staggerDelayMs))
          .attrTween('d', arcTweenFn)
          .on('end', function (d) {
            // Attach mouse event handlers after animation completes
            d3.select(this)
              .on('mouseover', (event) => {
                d3.select(event.currentTarget).style('stroke', 'black');
                tooltip.transition().duration(200).style('opacity', 1);
                tooltip.html(
                  `Group: <strong>${d.data[0]}</strong><br>Count: <strong>${d.data[1]}</strong>`
                );
              })
              .on('mousemove', (event) => {
                const rect = this.closest('.chart').getBoundingClientRect();
                tooltip
                  .style('left', event.clientX - rect.left + 5 + 'px')
                  .style('top', event.clientY - rect.top + 5 + 'px');
              })
              .on('mouseout', (event) => {
                d3.select(event.currentTarget).style('stroke', 'white');
                tooltip.transition().duration(200).style('opacity', 0);
              });
          });
      } else {
        // No animation - set path immediately and attach events
        slices.attr('d', arc);
        slices
          .on('mouseover', (event, d) => {
            d3.select(event.currentTarget).style('stroke', 'black');
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip.html(
              `Group: <strong>${d.data[0]}</strong><br>Count: <strong>${d.data[1]}</strong>`
            );
          })
          .on('mousemove', (event) => {
            const rect = this.$refs.chart.getBoundingClientRect();
            tooltip
              .style('left', event.clientX - rect.left + 5 + 'px')
              .style('top', event.clientY - rect.top + 5 + 'px');
          })
          .on('mouseout', (event) => {
            d3.select(event.currentTarget).style('stroke', 'white');
            tooltip.transition().duration(200).style('opacity', 0);
          });
      }

      // Mark initial render complete
      this.isInitialRender = false;

      // Append a central text element that shows the total count.
      svg
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '40px')
        .attr('fill', '#5CB85C')
        .attr('aria-hidden', 'true') // Decorative - total is in the description
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

    /**
     * Export the chart as a PNG image at 2x resolution.
     */
    handleExportPNG() {
      const svg = this.$refs.chart?.querySelector('svg');
      if (!svg) return;
      const filename = `donut-chart-${getTimestamp()}`;
      exportToPNG(svg, filename, 2);
    },

    /**
     * Export the chart data as a CSV file.
     */
    handleExportCSV() {
      if (!this.chartData?.grouped_counts) return;
      const total = this.chartData.total_count || 0;
      const data = this.chartData.grouped_counts.map((item) => ({
        category: item._id,
        count: item.count,
        percentage: total > 0 ? ((item.count / total) * 100).toFixed(1) : '0.0',
      }));
      const filename = `donut-chart-${getTimestamp()}`;
      exportToCSV(data, ['category', 'count', 'percentage'], filename);
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

.chart-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.chart-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 40px;
}

.chart {
  flex-shrink: 0;
}

.legend {
  flex: 1;
  min-width: 250px;
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
</style>
