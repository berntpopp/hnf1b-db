<!-- D3 Box Plot / Violin Plot Chart for DNA Distance Analysis -->
<template>
  <div class="box-plot-wrapper">
    <div class="export-controls">
      <ChartExportMenu @export-png="handleExportPNG" @export-csv="handleExportCSV" />
      <button class="export-btn" title="Download as SVG" @click="exportSVG">
        <span class="export-icon">mdi-file-image</span> SVG
      </button>
    </div>
    <div ref="chartContainer" class="chart-container" />
  </div>
</template>

<script>
import * as d3 from 'd3';
import { formatPValue } from '@/utils/statistics';
import { addChartAccessibility } from '@/utils/chartAccessibility';
import { getAnimationDuration, getStaggerDelay } from '@/utils/chartAnimation';
import { exportToPNG, exportToCSV, getTimestamp } from '@/utils/export';
import ChartExportMenu from '@/components/common/ChartExportMenu.vue';

export default {
  name: 'BoxPlotChart',
  components: {
    ChartExportMenu,
  },
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
    handleExportPNG() {
      const svg = this.$refs.chartContainer?.querySelector('svg');
      if (!svg) return;
      const filename = `dna-distance-violin-plot-${getTimestamp()}`;
      exportToPNG(svg, filename, 2);
    },
    handleExportCSV() {
      const data = [
        ...this.pathogenicDistances.map((v) => ({
          classification: 'P/LP',
          protein_change: v.protein || v.label || '',
          aa_position: v.aaPosition,
          distance_angstroms: v.distance.toFixed(2),
          category: v.category,
          verdict: v.classificationVerdict || '',
        })),
        ...this.vusDistances.map((v) => ({
          classification: 'VUS',
          protein_change: v.protein || v.label || '',
          aa_position: v.aaPosition,
          distance_angstroms: v.distance.toFixed(2),
          category: v.category,
          verdict: v.classificationVerdict || '',
        })),
      ];

      const filename = `dna-distance-data-${getTimestamp()}`;
      exportToCSV(
        data,
        [
          'classification',
          'protein_change',
          'aa_position',
          'distance_angstroms',
          'category',
          'verdict',
        ],
        filename
      );
    },
    exportSVG() {
      const svgElement = this.$refs.chartContainer?.querySelector('svg');
      if (!svgElement) {
        return;
      }

      // Clone the SVG to avoid modifying the original
      const clonedSvg = svgElement.cloneNode(true);

      // Add XML declaration and namespace for standalone SVG
      clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

      // Add white background for better compatibility with publication software
      const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      background.setAttribute('width', '100%');
      background.setAttribute('height', '100%');
      background.setAttribute('fill', 'white');
      clonedSvg.insertBefore(background, clonedSvg.firstChild);

      // Serialize to string
      const serializer = new XMLSerializer();
      let svgString = serializer.serializeToString(clonedSvg);

      // Add XML declaration
      svgString = '<?xml version="1.0" encoding="UTF-8"?>\n' + svgString;

      // Create blob and download
      const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);

      // Generate filename
      const timestamp = new Date().toISOString().slice(0, 10);
      const filename = `dna-distance-violin-plot-${timestamp}.svg`;

      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },
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

      const rootSvg = d3
        .select(this.$refs.chartContainer)
        .append('svg')
        .attr('width', containerWidth)
        .attr('height', this.height)
        .style('display', 'block');

      const g = rootSvg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

      // Prepare data - filter out groups with no data
      const groups = [
        { name: 'P/LP', data: this.pathogenicDistances, color: '#D32F2F' },
        { name: 'VUS', data: this.vusDistances, color: '#FBC02D' },
      ].filter((group) => group.data.length > 0);

      // Add accessibility attributes
      const pathogenicN = this.pathogenicDistances.length;
      const vusN = this.vusDistances.length;
      const description = `DNA distance violin plot. Pathogenic/Likely Pathogenic: ${pathogenicN} variants. VUS: ${vusN} variants.${this.pValueSignificant ? ' Difference is statistically significant.' : ''}`;
      const uniqueId = this._uid || Math.random().toString(36).substring(2, 11);
      addChartAccessibility(
        rootSvg,
        `boxplot-title-${uniqueId}`,
        `boxplot-desc-${uniqueId}`,
        'DNA Distance by Pathogenicity',
        description
      );

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
      rootSvg
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

      // Animation config
      const animDuration = getAnimationDuration(600);

      // Draw violin shape
      const violinArea = d3
        .area()
        .x0((d) => centerX - xScale(d[1]))
        .x1((d) => centerX + xScale(d[1]))
        .y((d) => y(d[0]))
        .curve(d3.curveCatmullRom);

      // Zero-width violin for animation start
      const violinAreaStart = d3
        .area()
        .x0(() => centerX)
        .x1(() => centerX)
        .y((d) => y(d[0]))
        .curve(d3.curveCatmullRom);

      const violinPath = g
        .append('path')
        .datum(density)
        .attr('aria-hidden', 'true')
        .attr('fill', group.color)
        .attr('fill-opacity', 0.15)
        .attr('stroke', group.color)
        .attr('stroke-width', 1)
        .attr('stroke-opacity', 0.5);

      // Animate violin from zero width to full width
      if (animDuration > 0) {
        violinPath
          .attr('d', violinAreaStart)
          .transition()
          .duration(animDuration)
          .attr('d', violinArea);
      } else {
        violinPath.attr('d', violinArea);
      }

      // Box (narrower, overlaid on violin)
      const innerBoxWidth = boxWidth * 0.25;
      const boxRect = g
        .append('rect')
        .attr('aria-hidden', 'true')
        .attr('x', centerX - innerBoxWidth / 2)
        .attr('width', innerBoxWidth)
        .attr('fill', group.color)
        .attr('stroke', group.color)
        .attr('stroke-width', 1.5);

      // Animate box from center to full size
      if (animDuration > 0) {
        const boxCenterY = y((q1 + q3) / 2);
        boxRect
          .attr('y', boxCenterY)
          .attr('height', 0)
          .attr('fill-opacity', 0)
          .transition()
          .duration(animDuration)
          .delay(animDuration / 3)
          .attr('y', y(q3))
          .attr('height', y(q1) - y(q3))
          .attr('fill-opacity', 0.5);
      } else {
        boxRect
          .attr('y', y(q3))
          .attr('height', y(q1) - y(q3))
          .attr('fill-opacity', 0.5);
      }

      // Median line
      g.append('line')
        .attr('aria-hidden', 'true')
        .attr('x1', centerX - innerBoxWidth / 2)
        .attr('x2', centerX + innerBoxWidth / 2)
        .attr('y1', y(median))
        .attr('y2', y(median))
        .attr('stroke', 'white')
        .attr('stroke-width', 2);

      // Whiskers
      g.append('line')
        .attr('aria-hidden', 'true')
        .attr('x1', centerX)
        .attr('x2', centerX)
        .attr('y1', y(min))
        .attr('y2', y(q1))
        .attr('stroke', group.color)
        .attr('stroke-width', 1);

      g.append('line')
        .attr('aria-hidden', 'true')
        .attr('x1', centerX)
        .attr('x2', centerX)
        .attr('y1', y(q3))
        .attr('y2', y(max))
        .attr('stroke', group.color)
        .attr('stroke-width', 1);

      // Individual points with tooltips
      this.drawDataPoints(g, group, x, y, tooltip, violinWidth, animDuration);
    },

    drawDataPoints(g, group, x, y, tooltip, violinWidth, animDuration) {
      const boxWidth = x.bandwidth();
      const xPos = x(group.name);
      const jitterWidth = violinWidth * 0.85;
      const pointClass = `point-${group.name.replace(/[^a-zA-Z0-9]/g, '-')}`;

      const points = g
        .selectAll(`.${pointClass}`)
        .data(group.data)
        .enter()
        .append('circle')
        .attr('class', pointClass)
        .attr('aria-hidden', 'true')
        .attr('cx', () => xPos + boxWidth / 2 + (Math.random() - 0.5) * jitterWidth)
        .attr('cy', (d) => y(d.distance))
        .attr('r', 4)
        .attr('fill', group.color)
        .attr('stroke', 'white')
        .attr('stroke-width', 1.5)
        .style('cursor', 'pointer');

      // Animate points fade in with stagger
      if (animDuration > 0) {
        points
          .attr('fill-opacity', 0)
          .transition()
          .duration(animDuration / 2)
          .delay((d, i) => getStaggerDelay(i, 10) + animDuration / 2)
          .attr('fill-opacity', 0.7);
      } else {
        points.attr('fill-opacity', 0.7);
      }

      // Add event handlers
      points
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
}

.chart-container {
  width: 100%;
  min-height: 400px;
}

.export-controls {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.export-btn:hover {
  background-color: #1565c0;
}

.export-btn:active {
  background-color: #0d47a1;
}

.export-icon {
  font-size: 12px;
}
</style>
