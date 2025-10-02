<template>
  <div class="stacked-bar-chart-container">
    <!-- The div where the chart will be rendered -->
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'StackedBarChart',
  props: {
    /**
     * The data to be plotted.
     * Expected format:
     * {
     *   results: [
     *     {
     *       phenotype_id: string,
     *       name: string,
     *       counts: { yes: number, no: number, "not reported": number }
     *     },
     *     ...
     *   ]
     * }
     */
    chartData: {
      type: Object,
      required: true,
    },
    width: {
      type: Number,
      default: 900, // Increased width for a wider plot.
    },
    height: {
      type: Number,
      default: 300,
    },
    margin: {
      type: Object,
      default: () => ({ top: 10, right: 30, bottom: 150, left: 100 }),
    },
    // Color palette for the subgroups.
    colorRange: {
      type: Array,
      default: () => ['#C7EFCF', '#FE5F55', '#EEF5DB'],
    },
  },
  watch: {
    chartData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
  },
  mounted() {
    this.renderChart();
    window.addEventListener('resize', this.renderChart);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.renderChart);
  },
  methods: {
    renderChart() {
      // Remove any existing chart content.
      d3.select(this.$refs.chart).selectAll('*').remove();

      const { width, height, margin } = this;
      const svgWidth = width - margin.left - margin.right;
      const svgHeight = height - margin.top - margin.bottom;

      // Append the SVG element.
      const svg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Transform the API data into a flat format.
      const rawData = this.chartData.results;
      if (!rawData) return;
      const data = rawData.map((d) => ({
        group: d.name, // Use the phenotype name as the group label.
        yes: d.counts.yes,
        no: d.counts.no,
        'not reported': d.counts['not reported'],
      }));

      // Define subgroups and groups.
      const subgroups = ['yes', 'no', 'not reported'];
      const groups = data.map((d) => d.group);

      // Add X axis.
      const x = d3.scaleBand().domain(groups).range([0, svgWidth]).padding(0.2);
      svg
        .append('g')
        .attr('transform', `translate(0, ${svgHeight})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .attr('transform', 'translate(-10,0)rotate(-45)')
        .style('text-anchor', 'end');

      // Add Y axis.
      const maxY = d3.max(data, (d) => d.yes + d.no + d['not reported']);
      const y = d3.scaleLinear().domain([0, maxY]).range([svgHeight, 0]);
      svg.append('g').call(d3.axisLeft(y));

      // Color scale.
      const color = d3.scaleOrdinal().domain(subgroups).range(this.colorRange);

      // Stack the data per subgroup.
      const stackedData = d3.stack().keys(subgroups)(data);

      // Create a tooltip.
      const tooltip = d3
        .select(this.$refs.chart)
        .append('div')
        .attr('class', 'tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background-color', 'white')
        .style('border', '1px solid #ccc')
        .style('padding', '10px')
        .style('border-radius', '5px');

      // Show the bars.
      svg
        .append('g')
        .selectAll('g')
        .data(stackedData)
        .join('g')
        .attr('fill', (d) => color(d.key))
        .selectAll('rect')
        .data((d) => d)
        .join('rect')
        .attr('x', (d) => x(d.data.group))
        .attr('y', (d) => y(d[1]))
        .attr('height', (d) => y(d[0]) - y(d[1]))
        .attr('width', x.bandwidth())
        .attr('stroke', 'grey')
        .on('mouseover', function (event, d) {
          const subgroupName = d3.select(this.parentNode).datum().key;
          const subgroupValue = d.data[subgroupName];
          tooltip
            .html(
              `Subgroup: <strong>${subgroupName}</strong><br>Value: <strong>${subgroupValue}</strong>`
            )
            .transition()
            .duration(200)
            .style('opacity', 1);
          d3.select(this).style('stroke', 'black');
        })
        .on('mousemove', (event) => {
          // Recalculate container's bounding rectangle on each mousemove.
          const rect = this.$refs.chart.getBoundingClientRect();
          tooltip
            .style('left', event.clientX - rect.left + 5 + 'px')
            .style('top', event.clientY - rect.top + 5 + 'px');
        })
        .on('mouseleave', function () {
          tooltip.transition().duration(200).style('opacity', 0);
          d3.select(this).style('stroke', 'grey');
        });
    },
  },
};
</script>

<style scoped>
.stacked-bar-chart-container {
  max-width: 1200px;
  width: 100%;
  margin: auto;
}
.tooltip {
  pointer-events: none;
  font-size: 14px;
  color: #333;
}
</style>
