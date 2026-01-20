<template>
  <div class="stacked-bar-chart-container">
    <!-- The div where the chart will be rendered -->
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';
import { addChartAccessibility, generateBarChartDescription } from '@/utils/chartAccessibility';

/**
 * Unique ID counter for generating unique ARIA IDs.
 * Incremented each time a new StackedBarChart component renders.
 */
let chartIdCounter = 0;

/**
 * CKD stage HPO IDs to aggregate into a single "Chronic Kidney Disease" entry.
 * HP:0012622 - Chronic kidney disease (parent term)
 * HP:0012623 - Stage 1 chronic kidney disease
 * HP:0012624 - Stage 2 chronic kidney disease
 * HP:0012625 - Stage 3 chronic kidney disease
 * HP:0012626 - Stage 4 chronic kidney disease
 * HP:0003774 - Stage 5 chronic kidney disease (ESRD)
 */
const CKD_HPO_IDS = [
  'HP:0012622', // Chronic kidney disease
  'HP:0012623', // Stage 1
  'HP:0012624', // Stage 2
  'HP:0012625', // Stage 3
  'HP:0012626', // Stage 4
  'HP:0003774', // Stage 5 (ESRD)
];

export default {
  name: 'StackedBarChart',
  props: {
    /**
     * The data to be plotted.
     * Expected format (array from /by-feature endpoint):
     * [
     *   {
     *     label: string,
     *     count: number,
     *     details: {
     *       hpo_id: string,
     *       present_count: number,
     *       absent_count: number,
     *       not_reported_count: number
     *     }
     *   },
     *   ...
     * ]
     */
    chartData: {
      type: Array,
      default: () => [],
    },
    displayLimit: {
      type: Number,
      default: 20,
    },
    width: {
      type: Number,
      default: 1000,
    },
    height: {
      type: Number,
      default: 600,
    },
    margin: {
      type: Object,
      default: () => ({ top: 40, right: 150, bottom: 200, left: 300 }),
    },
    // Color palette for the subgroups: Present, Absent, Not Reported
    colorRange: {
      type: Array,
      default: () => ['#4CAF50', '#F44336', '#9E9E9E'], // Green, Red, Gray
    },
  },
  watch: {
    chartData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    displayLimit() {
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
    /**
     * Aggregate CKD stages into a single entry.
     * - Present: any CKD stage reported as present
     * - Absent: CKD explicitly reported as absent (and no stage present)
     * - Not Reported: no CKD data at all
     */
    aggregateCKDStages(data) {
      const ckdEntries = [];
      const nonCkdEntries = [];

      // Separate CKD and non-CKD entries
      data.forEach((d) => {
        if (CKD_HPO_IDS.includes(d.details?.hpo_id)) {
          ckdEntries.push(d);
        } else {
          nonCkdEntries.push(d);
        }
      });

      // If no CKD entries, return original data
      if (ckdEntries.length === 0) {
        return data;
      }

      // Calculate total phenopackets from one of the entries
      // (present + absent + not_reported should equal total)
      const sampleEntry = ckdEntries[0];
      const totalPhenopackets =
        (sampleEntry.details?.present_count || 0) +
        (sampleEntry.details?.absent_count || 0) +
        (sampleEntry.details?.not_reported_count || 0);

      // Find unique phenopackets with any CKD stage present
      // Since we don't have phenopacket-level data, we use max present count
      // as a conservative estimate (accounts for patients with multiple stages)
      const maxPresent = Math.max(...ckdEntries.map((d) => d.details?.present_count || 0));

      // For absent: sum up all absent counts from CKD entries
      // Note: There may be multiple entries with same HPO ID but different labels
      // (e.g., "chronic kidney disease, not specified" vs "Chronic kidney disease")
      const ckdAbsent = ckdEntries.reduce((sum, d) => sum + (d.details?.absent_count || 0), 0);

      // Not reported: total minus those with any CKD data
      const ckdNotReported = totalPhenopackets - maxPresent - ckdAbsent;

      // Create aggregated CKD entry
      const aggregatedCkd = {
        label: 'Chronic Kidney Disease',
        count: maxPresent,
        percentage: totalPhenopackets > 0 ? (maxPresent / totalPhenopackets) * 100 : 0,
        details: {
          hpo_id: 'HP:0012622 (aggregated)',
          present_count: maxPresent,
          absent_count: ckdAbsent,
          not_reported_count: Math.max(0, ckdNotReported),
        },
      };

      // Insert aggregated CKD entry in sorted position based on present count
      const result = [...nonCkdEntries];
      const insertIndex = result.findIndex((d) => (d.details?.present_count || 0) < maxPresent);
      if (insertIndex === -1) {
        result.push(aggregatedCkd);
      } else {
        result.splice(insertIndex, 0, aggregatedCkd);
      }

      return result;
    },

    renderChart() {
      // Remove any existing chart content.
      d3.select(this.$refs.chart).selectAll('*').remove();

      if (!this.chartData || this.chartData.length === 0) {
        d3.select(this.$refs.chart)
          .append('div')
          .style('text-align', 'center')
          .style('padding', '40px')
          .style('color', '#666')
          .text('No data available');
        return;
      }

      const { width, height, margin } = this;
      const svgWidth = width - margin.left - margin.right;
      const svgHeight = height - margin.top - margin.bottom;

      // Generate unique IDs for accessibility
      const chartId = ++chartIdCounter;
      const titleId = `stacked-bar-chart-title-${chartId}`;
      const descId = `stacked-bar-chart-desc-${chartId}`;

      // Append the SVG element.
      const rootSvg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

      const svg = rootSvg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

      // Aggregate CKD stages into a single entry
      const aggregatedData = this.aggregateCKDStages(this.chartData);

      // Transform the API data into horizontal bar chart format (flip x/y)
      // Take only the top N features
      const limitedData = aggregatedData.slice(0, this.displayLimit);

      const data = limitedData.map((d) => ({
        group: d.label,
        hpo_id: d.details?.hpo_id || '',
        present: d.details?.present_count || 0,
        absent: d.details?.absent_count || 0,
        not_reported: d.details?.not_reported_count || 0,
      }));

      // Add accessibility attributes to the SVG
      const descriptionData = data.map((d) => ({
        label: d.group,
        present: d.present,
        absent: d.absent,
      }));
      const description = generateBarChartDescription(descriptionData);
      addChartAccessibility(rootSvg, titleId, descId, 'Phenotype Prevalence Chart', description);

      // Define subgroups and groups.
      const subgroups = ['present', 'absent', 'not_reported'];
      const subgroupLabels = { present: 'Present', absent: 'Absent', not_reported: 'Not Reported' };
      const groups = data.map((d) => d.group);

      // HORIZONTAL BAR CHART: Y axis for phenotypes, X axis for counts
      const y = d3.scaleBand().domain(groups).range([0, svgHeight]).padding(0.2);

      const maxX = d3.max(data, (d) => d.present + d.absent + d.not_reported);
      const x = d3.scaleLinear().domain([0, maxX]).range([0, svgWidth]).nice();

      // Add Y axis (phenotype labels)
      const yAxis = svg.append('g').call(d3.axisLeft(y));

      // Wrap long phenotype labels and set font size
      yAxis
        .selectAll('text')
        .style('font-size', '13px')
        .call(this.wrapText, margin.left - 10);

      // Add X axis (counts)
      svg
        .append('g')
        .attr('transform', `translate(0, ${svgHeight})`)
        .call(d3.axisBottom(x).ticks(10))
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', 40)
        .attr('fill', 'black')
        .attr('text-anchor', 'middle')
        .style('font-weight', 'bold')
        .text('Number of Phenopackets');

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
        .style('border-radius', '5px')
        .style('pointer-events', 'none')
        .style('z-index', '1000')
        .style('box-shadow', '0 2px 4px rgba(0,0,0,0.2)');

      // Show the horizontal bars.
      svg
        .append('g')
        .selectAll('g')
        .data(stackedData)
        .join('g')
        .attr('fill', (d) => color(d.key))
        .selectAll('rect')
        .data((d) => d)
        .join('rect')
        .attr('y', (d) => y(d.data.group))
        .attr('x', (d) => x(d[0]))
        .attr('width', (d) => x(d[1]) - x(d[0]))
        .attr('height', y.bandwidth())
        .attr('stroke', 'white')
        .attr('stroke-width', 1)
        .attr('aria-hidden', 'true')
        .on('mouseover', function (event, d) {
          const subgroupName = d3.select(this.parentNode).datum().key;
          const subgroupValue = d.data[subgroupName];
          const subgroupLabel = subgroupLabels[subgroupName];

          // Calculate penetrance (present / (present + absent))
          const present = d.data.present;
          const absent = d.data.absent;
          const totalReported = present + absent;
          const penetrance =
            totalReported > 0 ? ((present / totalReported) * 100).toFixed(1) : 'N/A';

          tooltip
            .html(
              `<strong>${d.data.group}</strong><br/>${subgroupLabel}: <strong>${subgroupValue}</strong><br/>Penetrance: <strong>${penetrance}%</strong> (${present}/${totalReported} reported)<br/><em>${d.data.hpo_id}</em>`
            )
            .transition()
            .duration(200)
            .style('opacity', 1);
          d3.select(this).style('stroke', 'black').style('stroke-width', 2);
        })
        .on('mousemove', (event) => {
          const rect = this.$refs.chart.getBoundingClientRect();
          tooltip
            .style('left', event.clientX - rect.left + 10 + 'px')
            .style('top', event.clientY - rect.top - 28 + 'px');
        })
        .on('mouseleave', function () {
          tooltip.transition().duration(200).style('opacity', 0);
          d3.select(this).style('stroke', 'white').style('stroke-width', 1);
        });

      // Add legend
      const legend = svg.append('g').attr('transform', `translate(${svgWidth + 20}, 0)`);

      const legendData = subgroups.map((key) => ({
        key,
        label: subgroupLabels[key],
      }));

      const legendItems = legend
        .selectAll('.legend-item')
        .data(legendData)
        .enter()
        .append('g')
        .attr('class', 'legend-item')
        .attr('transform', (d, i) => `translate(0, ${i * 25})`);

      legendItems
        .append('rect')
        .attr('width', 18)
        .attr('height', 18)
        .attr('fill', (d) => color(d.key))
        .attr('stroke', 'white')
        .attr('stroke-width', 1);

      legendItems
        .append('text')
        .attr('x', 24)
        .attr('y', 9)
        .attr('dy', '0.35em')
        .style('font-size', '12px')
        .text((d) => d.label);
    },

    /**
     * Wrap long text labels to fit within a specified width
     */
    wrapText(text, width) {
      text.each(function () {
        const textElement = d3.select(this);
        const words = textElement.text().split(/\s+/).reverse();
        let word;
        let line = [];
        let lineNumber = 0;
        const lineHeight = 1.1;
        const y = textElement.attr('y');
        const dy = parseFloat(textElement.attr('dy') || 0);
        let tspan = textElement
          .text(null)
          .append('tspan')
          .attr('x', -10)
          .attr('y', y)
          .attr('dy', dy + 'em');

        while ((word = words.pop())) {
          line.push(word);
          tspan.text(line.join(' '));
          if (tspan.node().getComputedTextLength() > width) {
            line.pop();
            tspan.text(line.join(' '));
            line = [word];
            tspan = textElement
              .append('tspan')
              .attr('x', -10)
              .attr('y', y)
              .attr('dy', ++lineNumber * lineHeight + dy + 'em')
              .text(word);
          }
        }
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
  position: relative;
}
.tooltip {
  pointer-events: none;
  font-size: 14px;
  color: #333;
}
</style>
