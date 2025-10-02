<template>
  <div class="donut-chart-container">
    <!-- The div where the chart will be rendered -->
    <div ref="chart" />
  </div>
</template>

<script>
// Import D3 and utilities for exporting.
import * as d3 from 'd3';

export default {
  name: 'DonutChart',
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
    /** Color scheme for the donut slices */
    colorScheme: {
      type: Array,
      default: () => d3.schemeDark2,
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
     * Render the donut chart using D3.
     */
    renderChart() {
      // Remove any existing chart content.
      d3.select(this.$refs.chart).selectAll('*').remove();

      const { width, height, margin } = this;
      const radius = Math.min(width, height) / 2 - margin;

      // Create the SVG element.
      const svg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .append('g')
        .attr('transform', `translate(${width / 2}, ${height / 2})`);


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
      const color = d3.scaleOrdinal().domain(Object.keys(dataObj)).range(this.colorScheme);

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

      // Define the outer arc for label positioning.
      const outerArc = d3
        .arc()
        .innerRadius(radius * 0.9)
        .outerRadius(radius * 0.9);

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

      // Helper function: compute the mid-angle of a slice.
      const midAngle = (d) => d.startAngle + (d.endAngle - d.startAngle) / 2;

      // Append labels for each slice.
      // Each label shows the group name and its percentage (one decimal), then gets wrapped if too long.
      const labels = svg
        .selectAll('text.label')
        .data(dataReady)
        .enter()
        .append('text')
        .attr('class', 'label')
        .attr('dy', '.35em')
        .attr('fill', '#111')
        .attr('transform', (d) => {
          const pos = outerArc.centroid(d);
          pos[0] = radius * (midAngle(d) < Math.PI ? 1 : -1);
          return `translate(${pos})`;
        })
        .style('text-anchor', (d) => (midAngle(d) < Math.PI ? 'start' : 'end'))
        .text((d) => {
          const percentage = ((d.data[1] / totalValue) * 100).toFixed(1);
          return `${d.data[0]} (${percentage}%)`;
        });

      // Call the wrap function on the labels with a maximum width of 100 pixels.
      labels.call(wrap, 100);

      // Append polylines connecting slices and labels.
      svg
        .selectAll('polyline')
        .data(dataReady)
        .enter()
        .append('polyline')
        .attr('stroke', 'black')
        .style('fill', 'none')
        .attr('stroke-width', 1)
        .attr('points', (d) => {
          const posA = arc.centroid(d); // Center of the slice.
          const posB = outerArc.centroid(d); // Position on the outerArc.
          const posC = outerArc.centroid(d); // Label position (adjusted).
          posC[0] = radius * (midAngle(d) < Math.PI ? 1 : -1);
          return [posA, posB, posC];
        });

      // Append a central text element that shows the total count.
      svg
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '40px')
        .attr('fill', '#5CB85C')
        .text(totalValue);
    },
  },
};

/**
 * A helper function that wraps SVG text by breaking lines at whitespace.
 * If the text length exceeds the specified width, additional <tspan> elements are added.
 *
 * @param {d3.Selection} text - A D3 selection containing one or more text elements.
 * @param {number} width - The maximum width (in pixels) for a line of text.
 */
function wrap(text, width) {
  text.each(function () {
    const text = d3.select(this);
    const words = text.text().split(/\s+/).reverse();
    let word;
    let line = [];
    let lineNumber = 0;
    const lineHeight = 1.1; // ems
    const y = text.attr('y') || 0;
    const dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text
      .text(null)
      .append('tspan')
      .attr('x', 0)
      .attr('y', y)
      .attr('dy', dy + 'em');
    while ((word = words.pop())) {
      line.push(word);
      tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop();
        tspan.text(line.join(' '));
        line = [word];
        tspan = text
          .append('tspan')
          .attr('x', 0)
          .attr('y', y)
          .attr('dy', ++lineNumber * lineHeight + dy + 'em')
          .text(word);
      }
    }
  });
}
</script>

<style scoped>
.donut-chart-container {
  position: relative;
  width: 100%;
  max-width: 600px;
  margin: auto;
}

/* Tooltip styling */
.tooltip {
  pointer-events: none;
  font-size: 14px;
  color: #333;
}
</style>
