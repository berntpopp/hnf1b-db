<!-- D3 Box Plot / Violin Plot Chart for DNA Distance Analysis -->
<template>
  <div class="box-plot-wrapper" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />
    <div ref="chartContainer" class="chart-container" aria-hidden="true" />
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
import * as d3 from 'd3';
import { ref, computed } from 'vue';
import { formatPValue } from '@/utils/statistics';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';

export default {
  name: 'BoxPlotChart',
  components: { ChartExportMenu },
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
    chartName: { type: String, default: 'DNA distance by pathogenicity' },
  },
  emits: ['variant-hover'],
  setup(props) {
    const svgEl = ref(null);

    function computeStats(distances) {
      if (!distances.length) return null;
      const sorted = [...distances].map((v) => v.distance).sort((a, b) => a - b);
      const n = sorted.length;
      const q = (p) => {
        const idx = (sorted.length - 1) * p;
        const lo = Math.floor(idx);
        const hi = Math.ceil(idx);
        return lo === hi ? sorted[lo] : sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
      };
      return {
        n,
        min: sorted[0],
        q1: q(0.25),
        median: q(0.5),
        q3: q(0.75),
        max: sorted[n - 1],
      };
    }

    const exportRows = computed(() => {
      const rows = [];
      const groups = [
        { label: 'P/LP', data: props.pathogenicDistances || [] },
        { label: 'VUS', data: props.vusDistances || [] },
      ];
      for (const g of groups) {
        const stats = computeStats(g.data);
        if (!stats) continue;
        rows.push({
          group: g.label,
          n: stats.n,
          min: stats.min.toFixed(2),
          q1: stats.q1.toFixed(2),
          median: stats.median.toFixed(2),
          q3: stats.q3.toFixed(2),
          max: stats.max.toFixed(2),
        });
      }
      return rows;
    });

    const exportColumns = [
      { key: 'group', label: 'Group' },
      { key: 'n', label: 'N' },
      { key: 'min', label: 'Min (Å)' },
      { key: 'q1', label: 'Q1 (Å)' },
      { key: 'median', label: 'Median (Å)' },
      { key: 'q3', label: 'Q3 (Å)' },
      { key: 'max', label: 'Max (Å)' },
    ];

    const summary = computed(() => {
      const rows = exportRows.value;
      if (!rows.length) return `${props.chartName}: no data.`;
      const parts = rows.map(
        (r) => `${r.group}: median ${r.median} Å, IQR ${r.q1}–${r.q3} Å, n=${r.n}`
      );
      let sig = '';
      if (props.mannWhitneyResult && typeof props.mannWhitneyResult.pValue === 'number') {
        const p = props.mannWhitneyResult.pValue;
        sig = ` Mann-Whitney p=${p < 0.001 ? '<0.001' : p.toFixed(3)}${props.pValueSignificant ? ' (significant)' : ''}.`;
      }
      return `${props.chartName}. ${parts.join('; ')}.${sig}`;
    });

    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    return { svgEl, exportRows, exportColumns, ...a11y };
  },
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
      this.svgEl = svg.node();

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
.box-plot-wrapper {
  width: 100%;
  position: relative;
}

.chart-container {
  width: 100%;
  min-height: 400px;
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
