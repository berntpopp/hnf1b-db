<template>
  <v-container fluid>
    <!-- Optional controls to filter displayed variants by classification -->
    <v-row v-if="showControls" class="mb-3">
      <v-col cols="12" sm="6">
        <v-select
          v-model="classificationSelect"
          :items="classificationOptions"
          label="Classification Filter"
          multiple
          chips
          outlined
        />
      </v-col>
    </v-row>
    <!-- Chart container -->
    <div ref="chart" />
  </v-container>
</template>

<script>
// Import d3 and the API module.
import * as d3 from 'd3';
import * as API from '@/api';

export default {
  name: 'ProteinLinearPlot',
  props: {
    showControls: { type: Boolean, default: false },
  },
  data() {
    return {
      protein: null, // Protein structure data.
      variants: [], // Variant (mutation) data.
      classificationSelect: [
        'Pathogenic',
        'Likely Pathogenic',
        'Uncertain Significance',
        'Likely Benign',
      ],
      classificationOptions: [
        'Pathogenic',
        'Likely Pathogenic',
        'Uncertain Significance',
        'Likely Benign',
      ],
    };
  },
  watch: {
    protein() {
      this.renderChart();
    },
    variants() {
      this.renderChart();
    },
    classificationSelect() {
      this.renderChart();
    },
  },
  mounted() {
    this.loadData();
    window.addEventListener('resize', this.renderChart);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.renderChart);
  },
  methods: {
    async loadData() {
      try {
        const [proteinRes, variantsRes] = await Promise.all([
          API.getProteins(),
          API.getVariantsSmallVariants(),
        ]);
        // Use the first protein from the response.
        this.protein = proteinRes.data[0];
        // Use the "small_variants" array from the response.
        this.variants = variantsRes.data.small_variants;
      } catch (error) {
        window.logService.error('Failed to load protein/variant data for plot', {
          error: error.message,
          status: error.response?.status,
        });
      }
    },
    // Helper: if protein_position is a range (e.g., "108-110"), return its average.
    parseProteinPosition(posStr) {
      if (typeof posStr === 'string' && posStr.includes('-')) {
        const parts = posStr.split('-').map(Number);
        return parts.reduce((a, b) => a + b, 0) / parts.length;
      }
      return Number(posStr);
    },
    renderChart() {
      if (!this.protein) return;
      d3.select(this.$refs.chart).selectAll('*').remove();

      // Legacy dimensions and multipliers.
      const viewBoxWidth = 800;
      const viewBoxHeight = 200;
      const margin = { top: 70, right: 50, bottom: 0, left: 50 };
      const length_factor = 1.3; // Multiplier for the protein length.
      const plotHeight = 120; // Drawing area height as in legacy.

      // Create SVG with fixed viewBox.
      const svg = d3
        .select(this.$refs.chart)
        .append('svg')
        .attr('viewBox', `0 0 ${viewBoxWidth} ${viewBoxHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .classed('svg-content', true)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      // Compute available drawing area.
      const proteinFeature = this.protein.features.protein[0];
      const proteinLength = proteinFeature.length;

      // Create x scale: from 0 to proteinLength mapped to [0, proteinLength * length_factor]
      const x = d3
        .scaleLinear()
        .domain([0, proteinLength])
        .range([0, proteinLength * length_factor]);

      // Create tooltip.
      const containerRect = this.$refs.chart.getBoundingClientRect();
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

      // Filter variants based on classificationSelect.
      let filteredVariants = this.variants;
      if (this.classificationSelect && this.classificationSelect.length > 0) {
        filteredVariants = this.variants.filter((v) =>
          this.classificationSelect.includes(v.verdict)
        );
      }

      // Define y scale as in legacy: domain [0, 50] maps to [plotHeight, 0]
      const y = d3.scaleLinear().domain([0, 50]).range([plotHeight, 0]);
      // Compute offset so that the top of a lollipop (y(cadd+15)) is shifted to the protein bar's vertical center.
      // The protein bar is drawn at y = plotHeight/2 - 10 (height = 20, so center = plotHeight/2).
      // For a default cadd score of 20, the legacy top is y(35). We want y(35)+offset === plotHeight/2.
      const offset = plotHeight / 2 - y(15);
      // Helper: new y value.
      const yNew = (val) => y(val) + offset;

      // Draw the lollipop stems and circles.
      filteredVariants.forEach((v) => {
        const pos = this.parseProteinPosition(v.protein_position);
        const xPos = x(pos);
        // If cadd_score is null, default to 20.
        const cadd = v.cadd_score != null ? v.cadd_score : 20;
        // Draw the stem line using the new yNew scale.
        svg
          .append('line')
          .attr('x1', xPos)
          .attr('y1', yNew(cadd + 15))
          .attr('x2', xPos)
          .attr('y2', yNew(15))
          .attr('stroke', 'grey')
          .attr('stroke-width', 2);

        // Draw the lollipop circle.
        svg
          .append('circle')
          .attr('cx', xPos)
          .attr('cy', yNew(cadd + 15))
          .attr('r', 6)
          .attr('fill', '#FE5F55')
          .attr('stroke', 'black')
          .on('mouseover', (event) => {
            d3.select(event.currentTarget).attr('r', 8);
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip
              .html(
                `Variant: <strong>${v.variant_id}</strong><br>` +
                  `Verdict: <strong>${v.verdict}</strong><br>` +
                  `c.: <strong>${v.c_dot}</strong><br>` +
                  `p.: <strong>${v.p_dot || 'N/A'}</strong><br>` +
                  `Pos: <strong>${v.protein_position}</strong><br>` +
                  `Individuals: <strong>${v.individual_count}</strong><br>` +
                  `CADD: <strong>${v.cadd_score || 'N/A'}</strong>`
              )
              .style('left', event.clientX - containerRect.left + 5 + 'px')
              .style('top', event.clientY - containerRect.top + 5 + 'px');
          })
          .on('mousemove', (event) => {
            const rect = this.$refs.chart.getBoundingClientRect();
            tooltip
              .style('left', event.clientX - rect.left + 5 + 'px')
              .style('top', event.clientY - rect.top + 5 + 'px');
          })
          .on('mouseout', (event) => {
            d3.select(event.currentTarget).attr('r', 6);
            tooltip.transition().duration(200).style('opacity', 0);
          });
      });

      // Draw the protein base as a rectangle (centered vertically).
      svg
        .append('rect')
        .attr('x', 0)
        .attr('y', plotHeight / 2 - 10)
        .attr('width', x(proteinLength))
        .attr('height', 20)
        .attr('fill', '#ddd')
        .attr('stroke', '#999');

      // Draw domain features (if available).
      if (this.protein.features.domain) {
        this.protein.features.domain.forEach((d) => {
          svg
            .append('rect')
            .attr('x', x(d.start_position))
            .attr('y', plotHeight / 2 - 15)
            .attr('width', x(d.length))
            .attr('height', 30)
            .attr('fill', '#90CAF9')
            .attr('stroke', '#555')
            .append('title')
            .text(d.description_short);
        });
      }

      // Add an x-axis label.
      svg
        .append('text')
        .attr('x', x(proteinLength) / 2)
        .attr('y', plotHeight + margin.bottom - 10)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .text('Protein Position');
    },
  },
};
</script>

<style scoped>
.svg-container {
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  vertical-align: top;
  overflow: hidden;
}
.svg-content {
  display: inline-block;
  position: absolute;
  top: 0;
  left: 0;
}
.tooltip {
  display: inline;
  position: fixed;
  pointer-events: none;
  font-size: 14px;
  color: #333;
}
</style>
