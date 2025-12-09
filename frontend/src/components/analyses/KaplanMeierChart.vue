<template>
  <div class="kaplan-meier-container">
    <div class="export-controls">
      <button class="export-btn" title="Download as SVG" @click="exportSVG">
        <span class="export-icon">⬇</span> Export SVG
      </button>
    </div>
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'KaplanMeierChart',
  props: {
    survivalData: {
      type: Object,
      default: () => null,
    },
    width: {
      type: Number,
      default: 1200,
    },
    height: {
      type: Number,
      default: 450,
    },
    margin: {
      type: Object,
      default: () => ({ top: 60, right: 100, bottom: 60, left: 80 }),
    },
  },
  watch: {
    survivalData: {
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
    exportSVG() {
      const svgElement = this.$refs.chart.querySelector('svg');
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

      // Generate filename based on comparison type and endpoint
      const timestamp = new Date().toISOString().slice(0, 10);
      const comparison = this.survivalData?.comparison_type || 'survival';
      const endpoint =
        this.survivalData?.endpoint?.replace(/\s+/g, '-').toLowerCase() || 'analysis';
      const filename = `kaplan-meier-${comparison}-${endpoint}-${timestamp}.svg`;

      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },
    renderChart() {
      d3.select(this.$refs.chart).selectAll('*').remove();

      if (
        !this.survivalData ||
        !this.survivalData.groups ||
        this.survivalData.groups.length === 0
      ) {
        d3.select(this.$refs.chart)
          .append('div')
          .style('text-align', 'center')
          .style('padding', '40px')
          .style('color', '#666')
          .text('No survival data available');
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

      const groups = this.survivalData.groups;

      // Find max time across all groups for x-axis
      const maxTime = d3.max(groups, (g) => d3.max(g.survival_data, (d) => d.time));

      // X scale for time (years)
      const x = d3.scaleLinear().domain([0, maxTime]).range([0, svgWidth]).nice();

      // Y scale for survival probability (0-1)
      const y = d3.scaleLinear().domain([0, 1]).range([svgHeight, 0]);

      // Color scale for groups
      const colorScale = d3.scaleOrdinal(d3.schemeCategory10);

      // Add grid lines for easier reading
      // Horizontal grid lines (for survival probability percentages)
      svg
        .append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(y).ticks(10).tickSize(-svgWidth).tickFormat(''))
        .selectAll('line')
        .style('stroke', '#e0e0e0')
        .style('stroke-dasharray', '2,2');

      // Vertical grid lines (for time points)
      svg
        .append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${svgHeight})`)
        .call(d3.axisBottom(x).ticks(10).tickSize(-svgHeight).tickFormat(''))
        .selectAll('line')
        .style('stroke', '#e0e0e0')
        .style('stroke-dasharray', '2,2');

      // Draw survival curves for each group
      const allEventMarkers = []; // Collect all event markers to draw on top layer

      groups.forEach((group, groupIndex) => {
        const color = colorScale(groupIndex);
        const data = group.survival_data;

        // Create step function line generator
        const line = d3
          .line()
          .x((d) => x(d.time))
          .y((d) => y(d.survival_probability))
          .curve(d3.curveStepAfter);

        // Draw confidence interval band (shaded area)
        if (data.some((d) => d.ci_lower !== undefined && d.ci_upper !== undefined)) {
          const areaLower = d3
            .area()
            .x((d) => x(d.time))
            .y0((d) => y(d.ci_lower))
            .y1((d) => y(d.ci_upper))
            .curve(d3.curveStepAfter);

          svg
            .append('path')
            .datum(data)
            .attr('class', `confidence-band-${groupIndex}`)
            .attr('fill', color)
            .attr('fill-opacity', 0.15)
            .attr('stroke', 'none')
            .attr('d', areaLower);
        }

        // Draw the survival curve
        svg
          .append('path')
          .datum(data)
          .attr('class', `survival-curve-${groupIndex}`)
          .attr('fill', 'none')
          .attr('stroke', color)
          .attr('stroke-width', 2.5)
          .attr('d', line);

        // Add censoring markers (vertical ticks at censored time points)
        const censoredPoints = data.filter((d) => d.censored > 0);
        svg
          .selectAll(`.censored-marker-${groupIndex}`)
          .data(censoredPoints)
          .enter()
          .append('line')
          .attr('class', `censored-marker-${groupIndex}`)
          .attr('x1', (d) => x(d.time))
          .attr('x2', (d) => x(d.time))
          .attr('y1', (d) => y(d.survival_probability) - 8)
          .attr('y2', (d) => y(d.survival_probability) + 8)
          .attr('stroke', color)
          .attr('stroke-width', 2);

        // Collect event markers for this group (will be drawn on top layer)
        const eventPoints = data.filter((d) => d.events > 0 && d.time > 0);
        eventPoints.forEach((d) => {
          allEventMarkers.push({ data: d, color, groupIndex, groupName: group.name });
        });
      });

      // Add median survival lines (50% survival point) for each group
      groups.forEach((group, groupIndex) => {
        const color = colorScale(groupIndex);
        const data = group.survival_data;

        // Find the first time point where survival drops to or below 50%
        const medianPoint = data.find((d) => d.survival_probability <= 0.5);

        if (medianPoint) {
          const medianTime = medianPoint.time;

          // Draw vertical dotted line from x-axis to the curve
          svg
            .append('line')
            .attr('class', `median-vertical-${groupIndex}`)
            .attr('x1', x(medianTime))
            .attr('x2', x(medianTime))
            .attr('y1', y(0))
            .attr('y2', y(0.5))
            .attr('stroke', color)
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', '5,5')
            .attr('opacity', 0.7);

          // Draw horizontal dotted line from y-axis to the curve
          svg
            .append('line')
            .attr('class', `median-horizontal-${groupIndex}`)
            .attr('x1', 0)
            .attr('x2', x(medianTime))
            .attr('y1', y(0.5))
            .attr('y2', y(0.5))
            .attr('stroke', color)
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', '5,5')
            .attr('opacity', 0.7);

          // Add small circle at the intersection point
          svg
            .append('circle')
            .attr('class', `median-point-${groupIndex}`)
            .attr('cx', x(medianTime))
            .attr('cy', y(0.5))
            .attr('r', 4)
            .attr('fill', color)
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5)
            .attr('opacity', 0.8);

          // Add text label showing the median time (positioned above the point)
          svg
            .append('text')
            .attr('class', `median-label-${groupIndex}`)
            .attr('x', x(medianTime))
            .attr('y', y(0.5) - 10)
            .attr('text-anchor', 'middle')
            .attr('font-size', '11px')
            .attr('font-weight', 'bold')
            .attr('fill', color)
            .text(`${medianTime.toFixed(1)}y`);
        }
      });

      // Draw all event markers on top layer (after all curves are drawn)
      // This ensures they're always accessible for hovering
      allEventMarkers.forEach(({ data: d, color, groupIndex, groupName }) => {
        svg
          .append('circle')
          .attr('class', `event-marker-${groupIndex}`)
          .attr('cx', x(d.time))
          .attr('cy', y(d.survival_probability))
          .attr('r', 4)
          .attr('fill', color)
          .attr('stroke', '#fff')
          .attr('stroke-width', 1.5)
          .style('cursor', 'pointer')
          .on('mouseover', function (_event) {
            d3.select(this).attr('r', 6);

            // Build tooltip text with group name and confidence interval
            let tooltipText = `${groupName}: Time: ${d.time}y, S(t): ${d.survival_probability.toFixed(3)}`;
            if (d.ci_lower !== undefined && d.ci_upper !== undefined) {
              tooltipText += `, 95% CI: [${d.ci_lower.toFixed(3)}, ${d.ci_upper.toFixed(3)}]`;
            }
            tooltipText += `, n=${d.at_risk}`;

            svg
              .append('text')
              .attr('class', 'hover-text')
              .attr('x', x(d.time) + 10)
              .attr('y', y(d.survival_probability) - 10)
              .text(tooltipText)
              .attr('font-size', '12px')
              .attr('fill', '#333')
              .attr('font-weight', 'bold');
          })
          .on('mouseout', function () {
            d3.select(this).attr('r', 4);
            svg.selectAll('.hover-text').remove();
          });
      });

      // X axis
      svg
        .append('g')
        .attr('transform', `translate(0,${svgHeight})`)
        .call(d3.axisBottom(x).ticks(10))
        .selectAll('text')
        .style('font-size', '11px');

      // Y axis
      svg
        .append('g')
        .call(
          d3
            .axisLeft(y)
            .ticks(10)
            .tickFormat((d) => `${(d * 100).toFixed(0)}%`)
        )
        .selectAll('text')
        .style('font-size', '11px');

      // X-axis label
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', svgHeight + 50)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('font-weight', 'bold')
        .text('Time (years)');

      // Y-axis label
      svg
        .append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -svgHeight / 2)
        .attr('y', -60)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('font-weight', 'bold')
        .text('Renal Survival Probability');

      // Title
      const comparisonTitle = this.getComparisonTitle(this.survivalData.comparison_type);
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -40)
        .attr('text-anchor', 'middle')
        .style('font-size', '18px')
        .style('font-weight', 'bold')
        .text(`Renal Survival ${comparisonTitle}`);

      // Subtitle with endpoint
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -20)
        .attr('text-anchor', 'middle')
        .style('font-size', '13px')
        .style('fill', '#666')
        .text(`Endpoint: ${this.survivalData.endpoint}`);

      // Legend with group names and sample sizes (positioned inside chart in upper right)
      const legendX = svgWidth - 280; // Position from right edge
      const legendY = 20; // Position from top
      const legend = svg.append('g').attr('transform', `translate(${legendX}, ${legendY})`);

      // Add semi-transparent white background to legend
      const legendHeight = groups.length * 25 + 10;
      legend
        .append('rect')
        .attr('x', -5)
        .attr('y', -5)
        .attr('width', 270)
        .attr('height', legendHeight)
        .attr('fill', 'white')
        .attr('fill-opacity', 0.9)
        .attr('stroke', '#ddd')
        .attr('stroke-width', 1)
        .attr('rx', 4);

      groups.forEach((group, i) => {
        const yOffset = i * 25;
        const color = colorScale(i);

        legend
          .append('line')
          .attr('x1', 0)
          .attr('x2', 25)
          .attr('y1', yOffset + 10)
          .attr('y2', yOffset + 10)
          .attr('stroke', color)
          .attr('stroke-width', 2.5);

        legend
          .append('text')
          .attr('x', 30)
          .attr('y', yOffset + 14)
          .style('font-size', '12px')
          .text(`${group.name} (n=${group.n}, events=${group.events})`);
      });
    },

    getComparisonTitle(comparisonType) {
      const titles = {
        variant_type: 'By Variant Type',
        pathogenicity: 'By Pathogenicity Classification',
        disease_subtype: 'By Disease Subtype',
      };
      return titles[comparisonType] || comparisonType;
    },
  },
};
</script>

<style scoped>
.kaplan-meier-container {
  width: 100%;
  overflow-x: auto;
}

.export-controls {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
  padding-right: 10px;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
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
  font-size: 14px;
}
</style>
