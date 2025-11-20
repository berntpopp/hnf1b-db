<template>
  <div class="variant-comparison-container">
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'VariantComparisonChart',
  props: {
    comparisonData: {
      type: Object,
      default: () => null,
    },
    width: {
      type: Number,
      default: 1200,
    },
    height: {
      type: Number,
      default: 600,
    },
    margin: {
      type: Object,
      default: () => ({ top: 60, right: 200, bottom: 80, left: 350 }),
    },
  },
  watch: {
    comparisonData: {
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
      d3.select(this.$refs.chart).selectAll('*').remove();

      if (
        !this.comparisonData ||
        !this.comparisonData.phenotypes ||
        this.comparisonData.phenotypes.length === 0
      ) {
        d3.select(this.$refs.chart)
          .append('div')
          .style('text-align', 'center')
          .style('padding', '40px')
          .style('color', '#666')
          .text('No comparison data available');
        return;
      }

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

      const data = this.comparisonData.phenotypes;
      const group1Name = this.comparisonData.group1_name;
      const group2Name = this.comparisonData.group2_name;

      // Y scale for phenotypes (categorical)
      const y = d3
        .scaleBand()
        .domain(data.map((d) => d.hpo_label))
        .range([0, svgHeight])
        .padding(0.3);

      // X scale for percentages (0-100)
      const x = d3.scaleLinear().domain([0, 100]).range([0, svgWidth]);

      // Color scale for groups
      const colorGroup1 = '#2196F3'; // Blue for group 1
      const colorGroup2 = '#FF9800'; // Orange for group 2

      // Draw bars for each group
      const barHeight = y.bandwidth() / 2;

      // Group 1 bars (top half of each band)
      svg
        .selectAll('.bar-group1')
        .data(data)
        .enter()
        .append('rect')
        .attr('class', 'bar-group1')
        .attr('x', 0)
        .attr('y', (d) => y(d.hpo_label))
        .attr('width', (d) => x(d.group1_percentage))
        .attr('height', barHeight - 2)
        .attr('fill', colorGroup1)
        .attr('opacity', 0.8)
        .on('mouseover', function (event, d) {
          d3.select(this).attr('opacity', 1);
          svg
            .append('text')
            .attr('class', 'hover-text')
            .attr('x', x(d.group1_percentage) + 5)
            .attr('y', y(d.hpo_label) + barHeight / 2)
            .attr('dy', '.35em')
            .text(`${d.group1_present}/${d.group1_total} (${d.group1_percentage.toFixed(1)}%)`)
            .attr('font-size', '12px')
            .attr('fill', '#333');
        })
        .on('mouseout', function () {
          d3.select(this).attr('opacity', 0.8);
          svg.selectAll('.hover-text').remove();
        });

      // Group 2 bars (bottom half of each band)
      svg
        .selectAll('.bar-group2')
        .data(data)
        .enter()
        .append('rect')
        .attr('class', 'bar-group2')
        .attr('x', 0)
        .attr('y', (d) => y(d.hpo_label) + barHeight + 2)
        .attr('width', (d) => x(d.group2_percentage))
        .attr('height', barHeight - 2)
        .attr('fill', colorGroup2)
        .attr('opacity', 0.8)
        .on('mouseover', function (event, d) {
          d3.select(this).attr('opacity', 1);
          svg
            .append('text')
            .attr('class', 'hover-text')
            .attr('x', x(d.group2_percentage) + 5)
            .attr('y', y(d.hpo_label) + barHeight + barHeight / 2 + 2)
            .attr('dy', '.35em')
            .text(`${d.group2_present}/${d.group2_total} (${d.group2_percentage.toFixed(1)}%)`)
            .attr('font-size', '12px')
            .attr('fill', '#333');
        })
        .on('mouseout', function () {
          d3.select(this).attr('opacity', 0.8);
          svg.selectAll('.hover-text').remove();
        });

      // Add p-value and significance indicators
      svg
        .selectAll('.p-value-text')
        .data(data)
        .enter()
        .append('text')
        .attr('class', 'p-value-text')
        .attr('x', svgWidth + 10)
        .attr('y', (d) => y(d.hpo_label) + y.bandwidth() / 2)
        .attr('dy', '.35em')
        .attr('font-size', '11px')
        .attr('fill', (d) => (d.significant ? '#D32F2F' : '#666'))
        .attr('font-weight', (d) => (d.significant ? 'bold' : 'normal'))
        .text((d) => {
          if (d.p_value === null) return 'N/A';
          if (d.p_value < 0.001) return 'p < 0.001 ***';
          if (d.p_value < 0.01) return `p = ${d.p_value.toFixed(3)} **`;
          if (d.p_value < 0.05) return `p = ${d.p_value.toFixed(3)} *`;
          return `p = ${d.p_value.toFixed(3)}`;
        });

      // Add effect size (Cohen's h) next to p-value
      svg
        .selectAll('.effect-size-text')
        .data(data)
        .enter()
        .append('text')
        .attr('class', 'effect-size-text')
        .attr('x', svgWidth + 100)
        .attr('y', (d) => y(d.hpo_label) + y.bandwidth() / 2)
        .attr('dy', '.35em')
        .attr('font-size', '10px')
        .attr('fill', '#666')
        .text((d) => {
          if (d.effect_size === null) return '';
          const h = d.effect_size;
          const label = h < 0.2 ? 'small' : h < 0.5 ? 'medium' : 'large';
          return `h = ${h.toFixed(2)} (${label})`;
        });

      // Y axis (phenotype labels with HPO IDs)
      svg
        .append('g')
        .call(d3.axisLeft(y))
        .selectAll('text')
        .style('font-size', '12px')
        .each(function (d) {
          const phenotype = data.find((p) => p.hpo_label === d);
          if (phenotype) {
            d3.select(this).text(`${d} (${phenotype.hpo_id})`);
          }
        });

      // X axis (percentage)
      svg
        .append('g')
        .attr('transform', `translate(0,${svgHeight})`)
        .call(
          d3
            .axisBottom(x)
            .ticks(10)
            .tickFormat((d) => `${d}%`)
        )
        .selectAll('text')
        .style('font-size', '11px');

      // Title
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -40)
        .attr('text-anchor', 'middle')
        .style('font-size', '18px')
        .style('font-weight', 'bold')
        .text(`${group1Name} vs ${group2Name} - Phenotype Prevalence Comparison`);

      // Subtitle with group sizes
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -20)
        .attr('text-anchor', 'middle')
        .style('font-size', '13px')
        .style('fill', '#666')
        .text(
          `${group1Name}: n=${this.comparisonData.group1_count} | ${group2Name}: n=${this.comparisonData.group2_count}`
        );

      // Legend
      const legend = svg.append('g').attr('transform', `translate(${svgWidth + 10}, -40)`);

      legend
        .append('rect')
        .attr('x', 0)
        .attr('y', 0)
        .attr('width', 15)
        .attr('height', 15)
        .attr('fill', colorGroup1);

      legend.append('text').attr('x', 20).attr('y', 12).style('font-size', '12px').text(group1Name);

      legend
        .append('rect')
        .attr('x', 0)
        .attr('y', 20)
        .attr('width', 15)
        .attr('height', 15)
        .attr('fill', colorGroup2);

      legend.append('text').attr('x', 20).attr('y', 32).style('font-size', '12px').text(group2Name);

      // X-axis label
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', svgHeight + 50)
        .attr('text-anchor', 'middle')
        .style('font-size', '13px')
        .style('font-weight', 'bold')
        .text('Prevalence (%)');
    },
  },
};
</script>

<style scoped>
.variant-comparison-container {
  width: 100%;
  overflow-x: auto;
}
</style>
