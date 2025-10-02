<!-- src/components/analyses/TimePlot.vue -->
<template>
  <div class="time-plot-container">
    <!-- Control to select display mode -->
    <v-select
      v-model="selectedDisplayType"
      :items="displayOptions"
      item-title="label"
      item-value="value"
      label="Display Mode"
      dense
      outlined
      class="mb-3"
    />
    <!-- The div where the chart will be rendered -->
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'TimePlot',
  props: {
    chartData: {
      type: Object,
      required: true,
    },
    width: {
      type: Number,
      default: 900,
    },
    height: {
      type: Number,
      default: 400,
    },
    margin: {
      type: Object,
      default: () => ({ top: 20, right: 50, bottom: 50, left: 70 }),
    },
  },
  data() {
    return {
      selectedDisplayType: 'overall', // 'overall' or 'byType'
      displayOptions: [
        { label: 'Overall', value: 'overall' },
        { label: 'By Type', value: 'byType' },
      ],
    };
  },
  watch: {
    chartData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    selectedDisplayType() {
      this.renderChart();
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
      // Clear existing chart.
      d3.select(this.$refs.chart).selectAll('*').remove();

      const { width, height, margin } = this;
      const svgWidth = width - margin.left - margin.right;
      const svgHeight = height - margin.top - margin.bottom;

      const svg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Create a tooltip that will follow the cursor.
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

      // Choose data based on selected display mode.
      let dataToPlot =
        this.selectedDisplayType === 'overall' ? this.chartData.overall : this.chartData.byType;
      if (!dataToPlot || dataToPlot.length === 0) return;

      // Filter out null dates and parse them.
      dataToPlot = dataToPlot
        .filter((d) => d.monthDate !== null)
        .map((d) => ({ ...d, monthDate: d3.isoParse(d.monthDate) }));

      // Create X and Y axes.
      const x = d3
        .scaleTime()
        .domain(d3.extent(dataToPlot, (d) => d.monthDate))
        .range([0, svgWidth]);
      svg.append('g').attr('transform', `translate(0, ${svgHeight})`).call(d3.axisBottom(x));

      const maxY = d3.max(dataToPlot, (d) => d.cumulativeCount);
      const y = d3.scaleLinear().domain([0, maxY]).range([svgHeight, 0]);
      svg.append('g').call(d3.axisLeft(y));

      // Line generator.
      const line = d3
        .line()
        .x((d) => x(d.monthDate))
        .y((d) => y(d.cumulativeCount))
        .curve(d3.curveMonotoneX);

      if (this.selectedDisplayType === 'overall') {
        // Draw a single line.
        svg
          .append('path')
          .datum(dataToPlot)
          .attr('fill', 'none')
          .attr('stroke', '#69b3a2')
          .attr('stroke-width', 3)
          .attr('d', line);

        // Add circles at data points.
        svg
          .selectAll('circle')
          .data(dataToPlot)
          .enter()
          .append('circle')
          .attr('cx', (d) => x(d.monthDate))
          .attr('cy', (d) => y(d.cumulativeCount))
          .attr('r', 4)
          .attr('fill', '#69b3a2')
          .on('mouseover', (event, d) => {
            d3.select(event.currentTarget).attr('r', 6);
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip
              .html(`Date: ${d.monthDate.toLocaleDateString()}<br>Cumulative: ${d.cumulativeCount}`)
              .style(
                'left',
                event.clientX - this.$refs.chart.getBoundingClientRect().left + 5 + 'px'
              )
              .style(
                'top',
                event.clientY - this.$refs.chart.getBoundingClientRect().top + 5 + 'px'
              );
          })
          .on('mousemove', (event) => {
            const rect = this.$refs.chart.getBoundingClientRect();
            tooltip
              .style('left', event.clientX - rect.left + 5 + 'px')
              .style('top', event.clientY - rect.top + 5 + 'px');
          })
          .on('mouseout', (event) => {
            d3.select(event.currentTarget).attr('r', 4);
            tooltip.transition().duration(200).style('opacity', 0);
          });
      } else if (this.selectedDisplayType === 'byType') {
        // Group data by publication_type.
        const dataByType = d3.group(dataToPlot, (d) => d.publication_type);
        const types = Array.from(dataByType.keys());
        const color = d3.scaleOrdinal().domain(types).range(d3.schemeSet2);

        // Draw a line for each type and add circles.
        dataByType.forEach((values, type) => {
          svg
            .append('path')
            .datum(values)
            .attr('fill', 'none')
            .attr('stroke', color(type))
            .attr('stroke-width', 3)
            .attr('class', type) // assign class for toggling.
            .attr('d', line);
          svg
            .selectAll(`circle.${type}`)
            .data(values)
            .enter()
            .append('circle')
            .attr('class', type)
            .attr('cx', (d) => x(d.monthDate))
            .attr('cy', (d) => y(d.cumulativeCount))
            .attr('r', 4)
            .attr('fill', color(type))
            .on('mouseover', (event, d) => {
              d3.select(event.currentTarget).attr('r', 6);
              tooltip.transition().duration(200).style('opacity', 1);
              tooltip
                .html(
                  `Type: ${type}<br>Date: ${d.monthDate.toLocaleDateString()}<br>Cumulative: ${d.cumulativeCount}`
                )
                .style(
                  'left',
                  event.clientX - this.$refs.chart.getBoundingClientRect().left + 5 + 'px'
                )
                .style(
                  'top',
                  event.clientY - this.$refs.chart.getBoundingClientRect().top + 5 + 'px'
                );
            })
            .on('mousemove', (event) => {
              const rect = this.$refs.chart.getBoundingClientRect();
              tooltip
                .style('left', event.clientX - rect.left + 5 + 'px')
                .style('top', event.clientY - rect.top + 5 + 'px');
            })
            .on('mouseout', (event) => {
              d3.select(event.currentTarget).attr('r', 4);
              tooltip.transition().duration(200).style('opacity', 0);
            });
        });

        // Add interactive legend on the left side.
        const legend = svg
          .selectAll('.legend')
          .data(types)
          .join('g')
          .attr('class', 'legend')
          .attr('transform', (d, i) => `translate(${-margin.left + 10}, ${i * 20})`);

        legend
          .append('rect')
          .attr('x', 0)
          .attr('y', 0)
          .attr('width', 18)
          .attr('height', 18)
          .style('fill', (d) => color(d))
          .style('cursor', 'pointer')
          .on('click', function (event, d) {
            // Toggle the opacity of all elements with the class equal to d.
            const currentOpacity = svg.selectAll('.' + d).style('opacity');
            svg
              .selectAll('.' + d)
              .transition()
              .style('opacity', currentOpacity == 1 ? 0 : 1);
          });
        legend
          .append('text')
          .attr('x', 25)
          .attr('y', 9)
          .attr('dy', '.35em')
          .style('text-anchor', 'start')
          .text((d) => d)
          .style('cursor', 'pointer')
          .on('click', function (event, d) {
            const currentOpacity = svg.selectAll('.' + d).style('opacity');
            svg
              .selectAll('.' + d)
              .transition()
              .style('opacity', currentOpacity == 1 ? 0 : 1);
          });
      }
    },
  },
};
</script>

<style scoped>
.time-plot-container {
  width: 100%;
  max-width: 900px;
  margin: auto;
}
.tooltip {
  pointer-events: none;
  font-size: 14px;
  color: #333;
}
</style>
