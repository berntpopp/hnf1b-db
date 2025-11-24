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
    comparisonType: {
      type: String,
      default: 'truncating_vs_non_truncating',
    },
    organSystemFilter: {
      type: String,
      default: 'all',
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
      default: () => ({ top: 120, right: 30, bottom: 180, left: 80 }),
    },
  },
  watch: {
    comparisonData: {
      handler() {
        this.renderChart();
      },
      deep: true,
    },
    organSystemFilter: {
      handler() {
        this.renderChart();
      },
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
    getShortLabels() {
      // Return short labels for bar groups based on comparison type
      const labelMap = {
        truncating_vs_non_truncating: { group1: 'T', group2: 'nT' },
        cnv_vs_point_mutation: { group1: 'CNV', group2: 'non-CNV' },
        cnv_deletion_vs_duplication: { group1: 'DEL', group2: 'DUP' },
      };
      return labelMap[this.comparisonType] || { group1: 'G1', group2: 'G2' };
    },
    getOrganSystemKeywords(system) {
      // Map organ systems to keyword patterns for flexible filtering
      // Uses general anatomical terms rather than exact phenotype names
      const keywordMap = {
        renal: ['renal', 'kidney', 'nephro', 'urinary', 'glomerular', 'chronic kidney disease'],
        metabolic: ['magnesemia', 'kalemia', 'uricemia', 'gout'],
        neurological: ['brain', 'neuro', 'behavioral', 'behaviour', 'seizure', 'cognitive'],
        pancreatic: ['pancrea', 'diabetes', 'mody', 'parathyroid', 'exocrine'],
      };
      return keywordMap[system] || [];
    },
    matchesOrganSystem(label, system) {
      // Check if a phenotype label matches keywords for an organ system
      const keywords = this.getOrganSystemKeywords(system);
      const lowerLabel = label.toLowerCase();
      return keywords.some((keyword) => lowerLabel.includes(keyword));
    },
    filterPhenotypesByOrganSystem(phenotypes, system) {
      if (system === 'all') return phenotypes;

      // Special handling for "other" - phenotypes that don't match any defined system
      if (system === 'other') {
        const systems = ['renal', 'metabolic', 'neurological', 'pancreatic'];
        return phenotypes.filter((p) => {
          // Include phenotype if it doesn't match ANY organ system
          return !systems.some((sys) => this.matchesOrganSystem(p.hpo_label, sys));
        });
      }

      return phenotypes.filter((p) => this.matchesOrganSystem(p.hpo_label, system));
    },
    filterUninformativePhenotypes(phenotypes) {
      // Remove CKD stage phenotypes - these are only reported for specific cases
      // and always have p=1 which is not informative for comparison
      const ckdStagePatterns = [
        'stage 1 chronic kidney disease',
        'stage 2 chronic kidney disease',
        'stage 3 chronic kidney disease',
        'stage 4 chronic kidney disease',
        'stage 5 chronic kidney disease',
        'chronic kidney disease, not specified',
      ];
      return phenotypes.filter((p) => {
        const lowerLabel = p.hpo_label.toLowerCase();
        return !ckdStagePatterns.some((pattern) => lowerLabel.includes(pattern));
      });
    },
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

      // Apply filtering: first remove uninformative phenotypes, then filter by organ system
      const allPhenotypes = this.comparisonData.phenotypes;
      const informativePhenotypes = this.filterUninformativePhenotypes(allPhenotypes);
      const data = this.filterPhenotypesByOrganSystem(informativePhenotypes, this.organSystemFilter);

      // If no phenotypes match the filter, show a message
      if (data.length === 0) {
        d3.select(this.$refs.chart)
          .append('div')
          .style('text-align', 'center')
          .style('padding', '40px')
          .style('color', '#666')
          .text(`No phenotypes found for ${this.organSystemFilter} organ system`);
        return;
      }

      const group1Name = this.comparisonData.group1_name;
      const group2Name = this.comparisonData.group2_name;

      // Tooltip div
      const tooltip = d3
        .select(this.$refs.chart)
        .append('div')
        .style('position', 'absolute')
        .style('background-color', 'white')
        .style('border', '1px solid #ddd')
        .style('border-radius', '4px')
        .style('padding', '8px')
        .style('pointer-events', 'none')
        .style('opacity', 0)
        .style('font-size', '12px')
        .style('box-shadow', '0 2px 4px rgba(0,0,0,0.1)')
        .style('z-index', 1000);

      // Color scale for yes/no only
      const colorYes = '#FF9800'; // Orange for phenotype present
      const colorNo = '#1976D2'; // Dark blue for phenotype absent

      // X scale for phenotypes (categorical) - now horizontal axis
      const x = d3
        .scaleBand()
        .domain(data.map((d) => d.hpo_label))
        .range([0, svgWidth])
        .padding(0.1);

      // Y scale for percentages (0-100) - now vertical axis
      const y = d3.scaleLinear().domain([0, 100]).range([svgHeight, 0]);

      // Width of each bar group
      const barGroupWidth = x.bandwidth();
      const barWidth = barGroupWidth / 2; // Two bars per phenotype (T and nT)

      // Draw bars for each phenotype
      data.forEach((d) => {
        const xPos = x(d.hpo_label);

        // Group 1 (e.g., Truncating) - "Yes" segment (bottom, stacked first)
        svg
          .append('rect')
          .attr('class', 'bar-group1-yes')
          .attr('x', xPos)
          .attr('y', y(d.group1_percentage))
          .attr('width', barWidth - 2)
          .attr('height', svgHeight - y(d.group1_percentage))
          .attr('fill', colorYes)
          .attr('opacity', 0.9)
          .on('mouseover', (event) => {
            tooltip.transition().duration(200).style('opacity', 0.95);
            tooltip
              .html(
                `<strong>${group1Name}</strong><br/>` +
                  `<strong>${d.hpo_label}</strong><br/>` +
                  `Phenotype: <strong>Present</strong><br/>` +
                  `Count: <strong>${d.group1_present}</strong> / ${d.group1_total}<br/>` +
                  `Percentage: <strong>${d.group1_percentage.toFixed(1)}%</strong>`
              )
              .style('left', event.pageX + 10 + 'px')
              .style('top', event.pageY - 28 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(500).style('opacity', 0);
          });

        // Group 1 - "No" segment (on top of yes segment)
        svg
          .append('rect')
          .attr('class', 'bar-group1-no')
          .attr('x', xPos)
          .attr('y', y(100))
          .attr('width', barWidth - 2)
          .attr('height', y(d.group1_percentage) - y(100))
          .attr('fill', colorNo)
          .attr('opacity', 0.9)
          .on('mouseover', (event) => {
            const noCount = d.group1_absent;
            const noPercentage = 100 - d.group1_percentage;
            tooltip.transition().duration(200).style('opacity', 0.95);
            tooltip
              .html(
                `<strong>${group1Name}</strong><br/>` +
                  `<strong>${d.hpo_label}</strong><br/>` +
                  `Phenotype: <strong>Absent</strong><br/>` +
                  `Count: <strong>${noCount}</strong> / ${d.group1_total}<br/>` +
                  `Percentage: <strong>${noPercentage.toFixed(1)}%</strong>`
              )
              .style('left', event.pageX + 10 + 'px')
              .style('top', event.pageY - 28 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(500).style('opacity', 0);
          });

        // Group 2 (e.g., Non-truncating) - "Yes" segment
        svg
          .append('rect')
          .attr('class', 'bar-group2-yes')
          .attr('x', xPos + barWidth + 2)
          .attr('y', y(d.group2_percentage))
          .attr('width', barWidth - 2)
          .attr('height', svgHeight - y(d.group2_percentage))
          .attr('fill', colorYes)
          .attr('opacity', 0.9)
          .on('mouseover', (event) => {
            tooltip.transition().duration(200).style('opacity', 0.95);
            tooltip
              .html(
                `<strong>${group2Name}</strong><br/>` +
                  `<strong>${d.hpo_label}</strong><br/>` +
                  `Phenotype: <strong>Present</strong><br/>` +
                  `Count: <strong>${d.group2_present}</strong> / ${d.group2_total}<br/>` +
                  `Percentage: <strong>${d.group2_percentage.toFixed(1)}%</strong>`
              )
              .style('left', event.pageX + 10 + 'px')
              .style('top', event.pageY - 28 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(500).style('opacity', 0);
          });

        // Group 2 - "No" segment
        svg
          .append('rect')
          .attr('class', 'bar-group2-no')
          .attr('x', xPos + barWidth + 2)
          .attr('y', y(100))
          .attr('width', barWidth - 2)
          .attr('height', y(d.group2_percentage) - y(100))
          .attr('fill', colorNo)
          .attr('opacity', 0.9)
          .on('mouseover', (event) => {
            const noCount = d.group2_absent;
            const noPercentage = 100 - d.group2_percentage;
            tooltip.transition().duration(200).style('opacity', 0.95);
            tooltip
              .html(
                `<strong>${group2Name}</strong><br/>` +
                  `<strong>${d.hpo_label}</strong><br/>` +
                  `Phenotype: <strong>Absent</strong><br/>` +
                  `Count: <strong>${noCount}</strong> / ${d.group2_total}<br/>` +
                  `Percentage: <strong>${noPercentage.toFixed(1)}%</strong>`
              )
              .style('left', event.pageX + 10 + 'px')
              .style('top', event.pageY - 28 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(500).style('opacity', 0);
          });

        // Add group labels below each bar pair
        const shortLabels = this.getShortLabels();
        svg
          .append('text')
          .attr('x', xPos + barWidth / 2)
          .attr('y', svgHeight + 20)
          .attr('text-anchor', 'middle')
          .attr('font-size', '11px')
          .attr('font-weight', 'bold')
          .text(shortLabels.group1);

        svg
          .append('text')
          .attr('x', xPos + barWidth + 2 + barWidth / 2)
          .attr('y', svgHeight + 20)
          .attr('text-anchor', 'middle')
          .attr('font-size', '11px')
          .attr('font-weight', 'bold')
          .text(shortLabels.group2);

        // Add count labels inside bars if there's enough space
        // Group 1 "yes" label
        if (d.group1_percentage > 15) {
          svg
            .append('text')
            .attr('x', xPos + barWidth / 2)
            .attr('y', y(d.group1_percentage / 2))
            .attr('text-anchor', 'middle')
            .attr('dy', '.35em')
            .attr('font-size', '10px')
            .attr('font-weight', 'bold')
            .attr('fill', 'white')
            .text(`${d.group1_present}`)
            .style('pointer-events', 'none');
        }

        // Group 2 "yes" label
        if (d.group2_percentage > 15) {
          svg
            .append('text')
            .attr('x', xPos + barWidth + 2 + barWidth / 2)
            .attr('y', y(d.group2_percentage / 2))
            .attr('text-anchor', 'middle')
            .attr('dy', '.35em')
            .attr('font-size', '10px')
            .attr('font-weight', 'bold')
            .attr('fill', 'white')
            .text(`${d.group2_present}`)
            .style('pointer-events', 'none');
        }
      });

      // Add p-value and effect size annotations above each bar pair
      // Only show when there are few enough phenotypes to avoid overlap
      const showAnnotations = data.length <= 15;
      data.forEach((d) => {
        const xPos = x(d.hpo_label);
        const centerX = xPos + barGroupWidth / 2;

        // Only show p-value annotations for significant results when many phenotypes
        // or all annotations when few phenotypes
        if (!showAnnotations && !d.significant) return;

        // P-value text - use FDR-corrected p-value for display (matches R script)
        // The significance labeling uses qfdr (FDR-adjusted) not raw pfisher
        const pFdr = d.p_value_fdr;
        let pValueText = '';
        if (pFdr === null || pFdr === undefined) {
          pValueText = 'N/A';
        } else if (pFdr < 0.001) {
          pValueText = 'p<0.001***';
        } else if (pFdr < 0.01) {
          pValueText = `p=${pFdr.toFixed(3)}**`;
        } else if (pFdr < 0.05) {
          pValueText = `p=${pFdr.toFixed(3)}*`;
        } else {
          pValueText = `p=${pFdr.toFixed(3)}`;
        }

        svg
          .append('text')
          .attr('x', centerX)
          .attr('y', -20)
          .attr('text-anchor', 'middle')
          .attr('font-size', '9px')
          .attr('fill', d.significant ? '#D32F2F' : '#666')
          .attr('font-weight', d.significant ? 'bold' : 'normal')
          .text(pValueText);

        // Effect size (Cohen's h) - only show when few phenotypes
        if (d.effect_size !== null && showAnnotations) {
          const h = d.effect_size;
          const label = h < 0.2 ? 'small' : h < 0.5 ? 'medium' : 'large';
          svg
            .append('text')
            .attr('x', centerX)
            .attr('y', -8)
            .attr('text-anchor', 'middle')
            .attr('font-size', '8px')
            .attr('fill', '#666')
            .text(`h=${h.toFixed(2)} (${label})`);
        }
      });

      // X axis (phenotype labels)
      const xAxis = svg
        .append('g')
        .attr('transform', `translate(0,${svgHeight + 35})`)
        .call(d3.axisBottom(x).tickSize(0));

      xAxis
        .selectAll('text')
        .style('font-size', '10px')
        .style('text-anchor', 'end')
        .attr('transform', 'rotate(-45)')
        .attr('dx', '-0.5em')
        .attr('dy', '0.5em');

      // Y axis (percentage)
      svg
        .append('g')
        .call(
          d3
            .axisLeft(y)
            .ticks(10)
            .tickFormat((d) => `${d}%`)
        )
        .selectAll('text')
        .style('font-size', '11px');

      // Title
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -90)
        .attr('text-anchor', 'middle')
        .style('font-size', '18px')
        .style('font-weight', 'bold')
        .text(`${group1Name} vs ${group2Name} - Phenotype Prevalence Comparison`);

      // Subtitle with group sizes
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -70)
        .attr('text-anchor', 'middle')
        .style('font-size', '13px')
        .style('fill', '#666')
        .text(
          `${group1Name}: n=${this.comparisonData.group1_count} | ${group2Name}: n=${this.comparisonData.group2_count}`
        );

      // Y-axis label
      svg
        .append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -svgHeight / 2)
        .attr('y', -50)
        .attr('text-anchor', 'middle')
        .style('font-size', '13px')
        .style('font-weight', 'bold')
        .text('Prevalence (%)');

      // Legend - two-row layout above the chart (below subtitle)
      const legend = svg.append('g').attr('transform', `translate(${svgWidth / 2 - 150}, -50)`);

      const shortLabels = this.getShortLabels();

      // Row 1: Present/Absent indicators (centered)
      legend.append('rect').attr('x', 0).attr('y', 0).attr('width', 12).attr('height', 12).attr('fill', colorYes);
      legend.append('text').attr('x', 16).attr('y', 10).style('font-size', '11px').text('Present');

      legend.append('rect').attr('x', 100).attr('y', 0).attr('width', 12).attr('height', 12).attr('fill', colorNo);
      legend.append('text').attr('x', 116).attr('y', 10).style('font-size', '11px').text('Absent');

      // Row 2: Bar label explanations (on separate line to avoid overlap)
      legend
        .append('text')
        .attr('x', 200)
        .attr('y', 10)
        .style('font-size', '10px')
        .style('fill', '#666')
        .text(`${shortLabels.group1} = ${group1Name}  |  ${shortLabels.group2} = ${group2Name}`);
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
