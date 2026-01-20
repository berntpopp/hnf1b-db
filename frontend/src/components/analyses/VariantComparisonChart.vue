<template>
  <div class="variant-comparison-container">
    <div class="export-controls">
      <ChartExportMenu @export-png="handleExportPNG" @export-csv="handleExportCSV" />
      <button class="export-btn" title="Download as SVG" @click="exportSVG">
        <span class="export-icon">mdi-file-image</span> SVG
      </button>
    </div>
    <div ref="chart" />
  </div>
</template>

<script>
import * as d3 from 'd3';
import { addChartAccessibility } from '@/utils/chartAccessibility';
import { getAnimationDuration, getStaggerDelay } from '@/utils/chartAnimation';
import { exportToPNG, exportToCSV, getTimestamp } from '@/utils/export';
import ChartExportMenu from '@/components/common/ChartExportMenu.vue';

export default {
  name: 'VariantComparisonChart',
  components: {
    ChartExportMenu,
  },
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
      default: () => ({ top: 120, right: 30, bottom: 220, left: 80 }),
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
    // Clean up tooltip appended to body
    d3.selectAll('.variant-comparison-tooltip').remove();
  },
  methods: {
    getShortLabels() {
      // Return short labels for bar groups based on comparison type
      // Use shorter labels when showing all organ systems to prevent overlap
      const isAllSystems = this.organSystemFilter === 'all';

      const labelMap = {
        truncating_vs_non_truncating: { group1: 'T', group2: 'nT' },
        truncating_vs_non_truncating_excl_cnv: { group1: 'T', group2: 'nT' },
        cnv_vs_point_mutation: isAllSystems
          ? { group1: 'C', group2: 'nC' }
          : { group1: 'CNV', group2: 'non-CNV' },
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
    handleExportPNG() {
      const svg = this.$refs.chart.querySelector('svg');
      if (!svg) return;
      const filename = `variant-comparison-${this.comparisonType}-${this.organSystemFilter}-${getTimestamp()}`;
      exportToPNG(svg, filename, 2);
    },
    handleExportCSV() {
      const allPhenotypes = this.comparisonData?.phenotypes || [];
      const informativePhenotypes = this.filterUninformativePhenotypes(allPhenotypes);
      const data = this.filterPhenotypesByOrganSystem(
        informativePhenotypes,
        this.organSystemFilter
      );

      const csvData = data.map((d) => ({
        phenotype: d.hpo_label,
        hpo_id: d.hpo_id || '',
        group1_present: d.group1_present,
        group1_total: d.group1_total,
        group1_percentage: d.group1_percentage.toFixed(1),
        group2_present: d.group2_present,
        group2_total: d.group2_total,
        group2_percentage: d.group2_percentage.toFixed(1),
        p_value_fisher: d.p_value?.toFixed(4) ?? '',
        p_value_fdr: d.p_value_fdr?.toFixed(4) ?? '',
        effect_size_cohens_h: d.effect_size?.toFixed(3) ?? '',
        significant: d.significant ? 'yes' : 'no',
      }));

      const filename = `variant-comparison-${this.comparisonType}-${this.organSystemFilter}-${getTimestamp()}`;
      exportToCSV(
        csvData,
        [
          'phenotype',
          'hpo_id',
          'group1_present',
          'group1_total',
          'group1_percentage',
          'group2_present',
          'group2_total',
          'group2_percentage',
          'p_value_fisher',
          'p_value_fdr',
          'effect_size_cohens_h',
          'significant',
        ],
        filename
      );
    },
    exportSVG() {
      const svgElement = this.$refs.chart.querySelector('svg');
      if (!svgElement) {
        return;
      }

      // Clone the SVG to avoid modifying the original
      const clonedSvg = svgElement.cloneNode(true);

      // Add padding to prevent content cutoff (4mm ≈ 15px)
      const padding = 15;
      const originalWidth = parseFloat(svgElement.getAttribute('width')) || this.width;
      const originalHeight = parseFloat(svgElement.getAttribute('height')) || this.height;
      const newWidth = originalWidth + padding * 2;
      const newHeight = originalHeight + padding * 2;

      // Update SVG dimensions and viewBox
      clonedSvg.setAttribute('width', newWidth);
      clonedSvg.setAttribute('height', newHeight);
      clonedSvg.setAttribute('viewBox', `${-padding} ${-padding} ${newWidth} ${newHeight}`);

      // Add XML declaration and namespace for standalone SVG
      clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

      // Add white background for better compatibility with publication software
      const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      background.setAttribute('x', -padding);
      background.setAttribute('y', -padding);
      background.setAttribute('width', newWidth);
      background.setAttribute('height', newHeight);
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

      // Generate filename based on comparison type and filter
      const timestamp = new Date().toISOString().slice(0, 10);
      const filename = `variant-comparison-${this.comparisonType}-${this.organSystemFilter}-${timestamp}.svg`;

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
      // Clean up any existing tooltips from previous renders
      d3.selectAll('.variant-comparison-tooltip').remove();

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

      // Create root SVG and add accessibility attributes
      const rootSvg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

      const svg = rootSvg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

      // Apply filtering: first remove uninformative phenotypes, then filter by organ system
      const allPhenotypes = this.comparisonData.phenotypes;
      const informativePhenotypes = this.filterUninformativePhenotypes(allPhenotypes);
      const data = this.filterPhenotypesByOrganSystem(
        informativePhenotypes,
        this.organSystemFilter
      );

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

      // Add accessibility attributes
      const chartDescription = `Phenotype comparison chart. ${group1Name} (n=${this.comparisonData.group1_count}) vs ${group2Name} (n=${this.comparisonData.group2_count}). Showing prevalence of ${data.length} phenotypes.`;
      const uniqueId = this._uid || Math.random().toString(36).substring(2, 11);
      addChartAccessibility(
        rootSvg,
        `variant-comp-title-${uniqueId}`,
        `variant-comp-desc-${uniqueId}`,
        'Variant Type Phenotype Comparison',
        chartDescription
      );

      // Animation configuration
      const animDuration = getAnimationDuration(400);
      const staggerDelay = 20;
      let barIndex = 0;

      // Tooltip div - positioned to the right of cursor to avoid cutoff
      const tooltip = d3
        .select('body')
        .append('div')
        .attr('class', 'variant-comparison-tooltip')
        .style('position', 'fixed')
        .style('background-color', 'white')
        .style('border', '1px solid #ddd')
        .style('border-radius', '4px')
        .style('padding', '8px')
        .style('pointer-events', 'none')
        .style('opacity', 0)
        .style('font-size', '12px')
        .style('box-shadow', '0 2px 4px rgba(0,0,0,0.1)')
        .style('z-index', 10000)
        .style('max-width', '250px');

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
        const currentBarIndex = barIndex;
        barIndex += 4; // 4 bars per phenotype (2 groups x 2 segments)

        // Group 1 (e.g., Truncating) - "Yes" segment (bottom, stacked first)
        const bar1Yes = svg
          .append('rect')
          .attr('class', 'bar-group1-yes')
          .attr('aria-hidden', 'true')
          .attr('x', xPos)
          .attr('width', barWidth - 2)
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
              .style('left', event.clientX + 15 + 'px')
              .style('top', event.clientY - 10 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(200).style('opacity', 0);
          });

        // Animate bar from baseline
        if (animDuration > 0) {
          bar1Yes
            .attr('y', svgHeight)
            .attr('height', 0)
            .transition()
            .duration(animDuration)
            .delay(getStaggerDelay(currentBarIndex, staggerDelay))
            .attr('y', y(d.group1_percentage))
            .attr('height', svgHeight - y(d.group1_percentage));
        } else {
          bar1Yes
            .attr('y', y(d.group1_percentage))
            .attr('height', svgHeight - y(d.group1_percentage));
        }

        // Group 1 - "No" segment (on top of yes segment)
        const bar1No = svg
          .append('rect')
          .attr('class', 'bar-group1-no')
          .attr('aria-hidden', 'true')
          .attr('x', xPos)
          .attr('width', barWidth - 2)
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
              .style('left', event.clientX + 15 + 'px')
              .style('top', event.clientY - 10 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(200).style('opacity', 0);
          });

        // Animate bar from top
        if (animDuration > 0) {
          bar1No
            .attr('y', y(100))
            .attr('height', 0)
            .transition()
            .duration(animDuration)
            .delay(getStaggerDelay(currentBarIndex + 1, staggerDelay))
            .attr('height', y(d.group1_percentage) - y(100));
        } else {
          bar1No.attr('y', y(100)).attr('height', y(d.group1_percentage) - y(100));
        }

        // Group 2 (e.g., Non-truncating) - "Yes" segment
        const bar2Yes = svg
          .append('rect')
          .attr('class', 'bar-group2-yes')
          .attr('aria-hidden', 'true')
          .attr('x', xPos + barWidth + 2)
          .attr('width', barWidth - 2)
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
              .style('left', event.clientX + 15 + 'px')
              .style('top', event.clientY - 10 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(200).style('opacity', 0);
          });

        // Animate bar from baseline
        if (animDuration > 0) {
          bar2Yes
            .attr('y', svgHeight)
            .attr('height', 0)
            .transition()
            .duration(animDuration)
            .delay(getStaggerDelay(currentBarIndex + 2, staggerDelay))
            .attr('y', y(d.group2_percentage))
            .attr('height', svgHeight - y(d.group2_percentage));
        } else {
          bar2Yes
            .attr('y', y(d.group2_percentage))
            .attr('height', svgHeight - y(d.group2_percentage));
        }

        // Group 2 - "No" segment
        const bar2No = svg
          .append('rect')
          .attr('class', 'bar-group2-no')
          .attr('aria-hidden', 'true')
          .attr('x', xPos + barWidth + 2)
          .attr('width', barWidth - 2)
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
              .style('left', event.clientX + 15 + 'px')
              .style('top', event.clientY - 10 + 'px');
          })
          .on('mouseout', () => {
            tooltip.transition().duration(200).style('opacity', 0);
          });

        // Animate bar from top
        if (animDuration > 0) {
          bar2No
            .attr('y', y(100))
            .attr('height', 0)
            .transition()
            .duration(animDuration)
            .delay(getStaggerDelay(currentBarIndex + 3, staggerDelay))
            .attr('height', y(d.group2_percentage) - y(100));
        } else {
          bar2No.attr('y', y(100)).attr('height', y(d.group2_percentage) - y(100));
        }

        // Add group labels below each bar pair
        const shortLabels = this.getShortLabels();
        svg
          .append('text')
          .attr('x', xPos + barWidth / 2)
          .attr('y', svgHeight + 20)
          .attr('text-anchor', 'middle')
          .attr('font-size', '12px')
          .attr('font-weight', 'bold')
          .text(shortLabels.group1);

        svg
          .append('text')
          .attr('x', xPos + barWidth + 2 + barWidth / 2)
          .attr('y', svgHeight + 20)
          .attr('text-anchor', 'middle')
          .attr('font-size', '12px')
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
            .attr('font-size', '11px')
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
            .attr('font-size', '11px')
            .attr('font-weight', 'bold')
            .attr('fill', 'white')
            .text(`${d.group2_present}`)
            .style('pointer-events', 'none');
        }
      });

      // Add p-value and effect size annotations above each bar pair
      // Adapt display based on number of phenotypes
      const showAllAnnotations = data.length <= 15;
      const showDiagonal = data.length > 10; // Use diagonal layout when many phenotypes

      data.forEach((d) => {
        const xPos = x(d.hpo_label);
        const centerX = xPos + barGroupWidth / 2;

        // Only show p-value annotations for significant results when many phenotypes
        // or all annotations when few phenotypes
        if (!showAllAnnotations && !d.significant) return;

        // P-value text - use FDR-corrected p-value for display (matches R script)
        // The significance labeling uses qfdr (FDR-adjusted) not raw pfisher
        const pFdr = d.p_value_fdr;
        let pValueText = '';
        if (pFdr === null || pFdr === undefined) {
          pValueText = 'N/A';
        } else if (pFdr < 0.001) {
          pValueText = showDiagonal ? '***' : 'p<0.001***';
        } else if (pFdr < 0.01) {
          pValueText = showDiagonal ? '**' : `p=${pFdr.toFixed(3)}**`;
        } else if (pFdr < 0.05) {
          pValueText = showDiagonal ? '*' : `p=${pFdr.toFixed(3)}*`;
        } else {
          pValueText = showDiagonal ? '' : `p=${pFdr.toFixed(3)}`;
        }

        // Skip non-significant results in diagonal mode (no label to show)
        if (showDiagonal && pValueText === '') return;

        if (showDiagonal) {
          // Diagonal layout for many phenotypes - larger font, positioned above bars
          svg
            .append('text')
            .attr('x', centerX)
            .attr('y', -10)
            .attr('text-anchor', 'middle')
            .attr('font-size', '16px')
            .attr('fill', '#D32F2F')
            .attr('font-weight', 'bold')
            .text(pValueText);
        } else {
          // Horizontal layout for few phenotypes
          svg
            .append('text')
            .attr('x', centerX)
            .attr('y', -20)
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .attr('fill', d.significant ? '#D32F2F' : '#666')
            .attr('font-weight', d.significant ? 'bold' : 'normal')
            .text(pValueText);

          // Effect size (Cohen's h) - only show when few phenotypes
          if (d.effect_size !== null) {
            const h = d.effect_size;
            const label = h < 0.2 ? 'small' : h < 0.5 ? 'medium' : 'large';
            svg
              .append('text')
              .attr('x', centerX)
              .attr('y', -8)
              .attr('text-anchor', 'middle')
              .attr('font-size', '9px')
              .attr('fill', '#666')
              .text(`h=${h.toFixed(2)} (${label})`);
          }
        }
      });

      // X axis (phenotype labels)
      const xAxis = svg
        .append('g')
        .attr('transform', `translate(0,${svgHeight + 35})`)
        .call(d3.axisBottom(x).tickSize(0));

      xAxis
        .selectAll('text')
        .style('font-size', '12px')
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
        .style('font-size', '12px');

      // Title
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -90)
        .attr('text-anchor', 'middle')
        .style('font-size', '20px')
        .style('font-weight', 'bold')
        .text(`${group1Name} vs ${group2Name} - Phenotype Prevalence Comparison`);

      // Subtitle with group sizes
      svg
        .append('text')
        .attr('x', svgWidth / 2)
        .attr('y', -70)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
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
        .style('font-size', '14px')
        .style('font-weight', 'bold')
        .text('Prevalence (%)');

      // Legend - two-row layout above the chart (below subtitle)
      const legend = svg.append('g').attr('transform', `translate(${svgWidth / 2 - 150}, -50)`);

      const shortLabels = this.getShortLabels();

      // Row 1: Present/Absent indicators (centered)
      legend
        .append('rect')
        .attr('x', 0)
        .attr('y', 0)
        .attr('width', 14)
        .attr('height', 14)
        .attr('fill', colorYes);
      legend.append('text').attr('x', 18).attr('y', 11).style('font-size', '12px').text('Present');

      legend
        .append('rect')
        .attr('x', 100)
        .attr('y', 0)
        .attr('width', 14)
        .attr('height', 14)
        .attr('fill', colorNo);
      legend.append('text').attr('x', 118).attr('y', 11).style('font-size', '12px').text('Absent');

      // Row 2: Bar label explanations (on separate line to avoid overlap)
      legend
        .append('text')
        .attr('x', 200)
        .attr('y', 11)
        .style('font-size', '11px')
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

.export-controls {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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
