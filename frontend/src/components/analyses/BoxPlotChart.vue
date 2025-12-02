<!-- D3 Box Plot / Violin Plot Chart for DNA Distance Analysis -->
<template>
  <div ref="chartContainer" class="chart-container" />
</template>

<script>
import * as d3 from 'd3';
import { formatPValue } from '@/utils/statistics';

export default {
  name: 'BoxPlotChart',
  props: {
    pathogenicDistances: {
      type: Array,
      required: true,
    },
    vusDistances: {
      type: Array,
      required: true,
    },
    pValueSignificant: {
      type: Boolean,
      default: false,
    },
    mannWhitneyResult: {
      type: Object,
      default: null,
    },
    width: {
      type: Number,
      default: 800,
    },
    height: {
      type: Number,
      default: 400,
    },
  },
  emits: ['variant-hover'],
  watch: {
    pathogenicDistances: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    vusDistances: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
  },
  mounted() {
    this.renderChart();
  },
  beforeUnmount() {
    // Clean up tooltip
    d3.select('body').select('.dna-distance-tooltip').remove();
  },
  methods: {
    renderChart() {
      if (!this.$refs.chartContainer) {
        return;
      }

      // Check if we have data to render
      if (this.pathogenicDistances.length === 0 && this.vusDistances.length === 0) {
        return;
      }

      // Clear previous chart
      d3.select(this.$refs.chartContainer).selectAll('*').remove();

      // Get container width
      let containerWidth = this.$refs.chartContainer.clientWidth;
      if (!containerWidth || containerWidth < 100) {
        containerWidth = this.width;
      }

      const margin = { top: 50, right: 40, bottom: 60, left: 70 };
      const width = containerWidth - margin.left - margin.right;
      const height = this.height - margin.top - margin.bottom;

      if (width <= 0 || height <= 0) {
        return;
      }

      const svg = d3
        .select(this.$refs.chartContainer)
        .append('svg')
        .attr('width', containerWidth)
        .attr('height', this.height)
        .style('display', 'block');

      const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

      // Prepare data - filter out groups with no data
      const groups = [
        { name: 'P/LP', data: this.pathogenicDistances, color: '#D32F2F' },
        { name: 'VUS', data: this.vusDistances, color: '#FBC02D' },
      ].filter((group) => group.data.length > 0);

      if (groups.length === 0) {
        return;
      }

      // Scales
      const x = d3
        .scaleBand()
        .domain(groups.map((grp) => grp.name))
        .range([0, width])
        .padding(0.4);

      const allDistances = [...this.pathogenicDistances, ...this.vusDistances].map(
        (v) => v.distance
      );
      const yMax = (d3.max(allDistances) || 30) * 1.15;

      const y = d3.scaleLinear().domain([0, yMax]).range([height, 0]);

      // Axes
      g.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .style('font-size', '12px');

      g.append('g').call(d3.axisLeft(y).ticks(10)).selectAll('text').style('font-size', '11px');

      // Y-axis label
      g.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', -45)
        .attr('x', -height / 2)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .text('Distance to DNA (Å)');

      // Create tooltip
      const tooltip = this.getOrCreateTooltip();

      // Draw violin + box plots for each group
      groups.forEach((group) => {
        this.drawViolinBoxPlot(g, group, x, y, tooltip, height);
      });

      // Add significance bracket if significant
      if (this.pValueSignificant && groups.length === 2) {
        this.drawSignificanceBracket(g, x, y, yMax);
      }

      // Title
      svg
        .append('text')
        .attr('x', containerWidth / 2)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('font-weight', 'bold')
        .text('DNA Distance by Pathogenicity Classification');
    },

    getOrCreateTooltip() {
      let tooltip = d3.select('body').select('.dna-distance-tooltip');
      if (tooltip.empty()) {
        tooltip = d3
          .select('body')
          .append('div')
          .attr('class', 'dna-distance-tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden')
          .style('background-color', 'rgba(0, 0, 0, 0.85)')
          .style('color', 'white')
          .style('padding', '8px 12px')
          .style('border-radius', '4px')
          .style('font-size', '12px')
          .style('pointer-events', 'none')
          .style('z-index', '1000')
          .style('max-width', '300px')
          .style('box-shadow', '0 2px 8px rgba(0,0,0,0.3)');
      }
      return tooltip;
    },

    drawViolinBoxPlot(g, group, x, y, tooltip, _height) {
      if (group.data.length === 0) return;

      const distances = group.data.map((v) => v.distance).sort((a, b) => a - b);
      const n = distances.length;

      const q1 = d3.quantile(distances, 0.25);
      const median = d3.quantile(distances, 0.5);
      const q3 = d3.quantile(distances, 0.75);
      const iqr = q3 - q1;
      const min = Math.max(distances[0], q1 - 1.5 * iqr);
      const max = Math.min(distances[n - 1], q3 + 1.5 * iqr);

      const boxWidth = x.bandwidth();
      const xPos = x(group.name);
      const centerX = xPos + boxWidth / 2;

      // Calculate kernel density for violin plot
      const bandwidth = iqr > 0 ? iqr / 1.34 : 1;
      const kde = this.kernelDensityEstimator(
        this.kernelEpanechnikov(bandwidth),
        y.ticks(40).map((t) => t)
      );
      const density = kde(distances);

      // Scale density to fit within the box width
      const maxDensity = d3.max(density, (d) => d[1]) || 1;
      const violinWidth = boxWidth * 0.9;
      const xScale = d3
        .scaleLinear()
        .domain([0, maxDensity])
        .range([0, violinWidth / 2]);

      // Draw violin shape
      const violinArea = d3
        .area()
        .x0((d) => centerX - xScale(d[1]))
        .x1((d) => centerX + xScale(d[1]))
        .y((d) => y(d[0]))
        .curve(d3.curveCatmullRom);

      g.append('path')
        .datum(density)
        .attr('d', violinArea)
        .attr('fill', group.color)
        .attr('fill-opacity', 0.15)
        .attr('stroke', group.color)
        .attr('stroke-width', 1)
        .attr('stroke-opacity', 0.5);

      // Box (narrower, overlaid on violin)
      const innerBoxWidth = boxWidth * 0.25;
      g.append('rect')
        .attr('x', centerX - innerBoxWidth / 2)
        .attr('y', y(q3))
        .attr('width', innerBoxWidth)
        .attr('height', y(q1) - y(q3))
        .attr('fill', group.color)
        .attr('fill-opacity', 0.5)
        .attr('stroke', group.color)
        .attr('stroke-width', 1.5);

      // Median line
      g.append('line')
        .attr('x1', centerX - innerBoxWidth / 2)
        .attr('x2', centerX + innerBoxWidth / 2)
        .attr('y1', y(median))
        .attr('y2', y(median))
        .attr('stroke', 'white')
        .attr('stroke-width', 2);

      // Whiskers
      g.append('line')
        .attr('x1', centerX)
        .attr('x2', centerX)
        .attr('y1', y(min))
        .attr('y2', y(q1))
        .attr('stroke', group.color)
        .attr('stroke-width', 1);

      g.append('line')
        .attr('x1', centerX)
        .attr('x2', centerX)
        .attr('y1', y(q3))
        .attr('y2', y(max))
        .attr('stroke', group.color)
        .attr('stroke-width', 1);

      // Individual points with tooltips
      this.drawDataPoints(g, group, x, y, tooltip, violinWidth);
    },

    drawDataPoints(g, group, x, y, tooltip, violinWidth) {
      const boxWidth = x.bandwidth();
      const xPos = x(group.name);
      const jitterWidth = violinWidth * 0.85;
      const pointClass = `point-${group.name.replace(/[^a-zA-Z0-9]/g, '-')}`;

      g.selectAll(`.${pointClass}`)
        .data(group.data)
        .enter()
        .append('circle')
        .attr('class', pointClass)
        .attr('cx', () => xPos + boxWidth / 2 + (Math.random() - 0.5) * jitterWidth)
        .attr('cy', (d) => y(d.distance))
        .attr('r', 4)
        .attr('fill', group.color)
        .attr('fill-opacity', 0.7)
        .attr('stroke', 'white')
        .attr('stroke-width', 1.5)
        .style('cursor', 'pointer')
        .on('mouseover', (event, d) => {
          d3.select(event.currentTarget)
            .attr('r', 6)
            .attr('fill-opacity', 1)
            .attr('stroke-width', 2);

          const variantLabel = d.protein || d.hgvs || d.label || `Position ${d.aaPosition}`;
          const classification = d.classificationVerdict || 'Unknown';

          tooltip
            .html(
              `<strong>${variantLabel}</strong><br/>` +
                `Distance: <strong>${d.distance.toFixed(2)} Å</strong><br/>` +
                `Position: ${d.aaPosition}<br/>` +
                `Classification: ${classification}<br/>` +
                `Category: ${this.getCategoryLabel(d.category)}`
            )
            .style('visibility', 'visible');

          this.$emit('variant-hover', d);
        })
        .on('mousemove', (event) => {
          tooltip.style('top', event.pageY - 10 + 'px').style('left', event.pageX + 15 + 'px');
        })
        .on('mouseout', (event) => {
          d3.select(event.currentTarget)
            .attr('r', 4)
            .attr('fill-opacity', 0.7)
            .attr('stroke-width', 1.5);

          tooltip.style('visibility', 'hidden');
          this.$emit('variant-hover', null);
        });
    },

    drawSignificanceBracket(g, x, y, yMax) {
      const bracketY = y(yMax * 0.95);

      g.append('line')
        .attr('x1', x('P/LP') + x.bandwidth() / 2)
        .attr('x2', x('VUS') + x.bandwidth() / 2)
        .attr('y1', bracketY)
        .attr('y2', bracketY)
        .attr('stroke', '#333')
        .attr('stroke-width', 1.5);

      g.append('line')
        .attr('x1', x('P/LP') + x.bandwidth() / 2)
        .attr('x2', x('P/LP') + x.bandwidth() / 2)
        .attr('y1', bracketY)
        .attr('y2', bracketY + 8)
        .attr('stroke', '#333')
        .attr('stroke-width', 1.5);

      g.append('line')
        .attr('x1', x('VUS') + x.bandwidth() / 2)
        .attr('x2', x('VUS') + x.bandwidth() / 2)
        .attr('y1', bracketY)
        .attr('y2', bracketY + 8)
        .attr('stroke', '#333')
        .attr('stroke-width', 1.5);

      g.append('text')
        .attr('x', (x('P/LP') + x('VUS') + x.bandwidth()) / 2)
        .attr('y', bracketY - 8)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text(`p = ${formatPValue(this.mannWhitneyResult.pValue)}`);
    },

    kernelDensityEstimator(kernel, X) {
      return (V) => X.map((x) => [x, d3.mean(V, (v) => kernel(x - v))]);
    },

    kernelEpanechnikov(bandwidth) {
      return (x) => (Math.abs((x /= bandwidth)) <= 1 ? (0.75 * (1 - x * x)) / bandwidth : 0);
    },

    getCategoryLabel(category) {
      if (category === 'close') return 'Close (<5Å)';
      if (category === 'medium') return 'Medium (5-10Å)';
      return 'Far (≥10Å)';
    },
  },
};
</script>

<style scoped>
.chart-container {
  width: 100%;
  min-height: 400px;
}
</style>
