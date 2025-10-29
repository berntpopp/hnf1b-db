<!-- HNF1B Gene Structure Visualization -->
<template>
  <v-card class="gene-viz-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon
        left
        color="primary"
      >
        mdi-dna
      </v-icon>
      HNF1B Gene Structure (NM_000458.4)
      <v-spacer />
      <v-chip
        size="small"
        color="info"
      >
        {{ variantsWithPositions.length }} variant{{ variantsWithPositions.length !== 1 ? 's' : '' }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Legend -->
      <v-row class="mb-2">
        <v-col cols="12">
          <div class="legend-container">
            <v-chip
              size="small"
              color="blue"
            >
              <v-icon
                left
                size="small"
              >
                mdi-square
              </v-icon>
              Exon (click to zoom)
            </v-chip>
            <v-chip
              size="small"
              color="grey"
            >
              <v-icon
                left
                size="small"
              >
                mdi-minus
              </v-icon>
              Intron
            </v-chip>
            <v-chip
              size="small"
              color="red-lighten-3"
            >
              <v-icon
                left
                size="small"
              >
                mdi-circle
              </v-icon>
              Pathogenic
            </v-chip>
            <v-chip
              size="small"
              color="orange-lighten-3"
            >
              <v-icon
                left
                size="small"
              >
                mdi-circle
              </v-icon>
              Likely Pathogenic
            </v-chip>
            <v-chip
              size="small"
              color="yellow-lighten-3"
            >
              <v-icon
                left
                size="small"
              >
                mdi-circle
              </v-icon>
              VUS
            </v-chip>
            <v-chip
              v-if="currentVariantId"
              size="small"
              color="purple"
            >
              <v-icon
                left
                size="small"
              >
                mdi-star
              </v-icon>
              Current
            </v-chip>
          </div>
        </v-col>
      </v-row>

      <!-- SVG Visualization -->
      <div
        ref="svgContainer"
        class="svg-container"
      >
        <svg
          ref="geneSvg"
          :width="svgWidth"
          :height="svgHeight"
          class="gene-visualization"
          @mouseleave="hideTooltip"
        >
          <!-- Chromosome label -->
          <text
            :x="margin.left"
            :y="20"
            class="chromosome-label"
          >
            Chromosome 17q12 • HNF1B (TCF2) • chr17:37,686,430-37,745,059 (58.6 kb)
          </text>

          <!-- Gene coordinates (showing visible range) -->
          <text
            :x="margin.left"
            :y="svgHeight - 10"
            class="coordinate-label"
          >
            {{ formatCoordinate(visibleGeneStart) }}
          </text>
          <text
            :x="svgWidth - margin.right"
            :y="svgHeight - 10"
            text-anchor="end"
            class="coordinate-label"
          >
            {{ formatCoordinate(visibleGeneEnd) }}
          </text>
          <!-- Zoom indicator -->
          <text
            v-if="zoomedExon"
            :x="svgWidth / 2"
            :y="svgHeight - 10"
            text-anchor="middle"
            class="zoom-indicator-label"
          >
            Zoomed to Exon {{ zoomedExon.number }} ({{ zoomedExon.size }} bp) - Click exon again or Reset to zoom out
          </text>

          <!-- Intron line (backbone) -->
          <line
            :x1="margin.left"
            :y1="centerY"
            :x2="svgWidth - margin.right"
            :y2="centerY"
            stroke="#9E9E9E"
            stroke-width="3"
          />

          <!-- Exons -->
          <g
            v-for="exon in exons"
            :key="`exon-${exon.number}`"
          >
            <rect
              :x="scalePosition(exon.start)"
              :y="centerY - exonHeight / 2"
              :width="Math.max(scalePosition(exon.end) - scalePosition(exon.start), 2)"
              :height="exonHeight"
              :fill="getExonColor(exon)"
              :stroke="zoomedExon?.number === exon.number ? '#FF6F00' : '#1565C0'"
              :stroke-width="zoomedExon?.number === exon.number ? 4 : 2"
              class="exon-rect"
              :class="{ 'exon-zoomed': zoomedExon?.number === exon.number }"
              @mouseenter="showExonTooltip($event, exon)"
              @mousemove="updateTooltipPosition($event)"
              @click="handleExonClick(exon)"
            />
            <text
              :x="scalePosition(exon.start) + (scalePosition(exon.end) - scalePosition(exon.start)) / 2"
              :y="centerY - exonHeight / 2 - 8"
              text-anchor="middle"
              class="exon-label"
            >
              E{{ exon.number }}
            </text>
          </g>

          <!-- CNV deletions (background bars) -->
          <g
            v-for="(cnv, index) in cnvVariants"
            :key="`cnv-${index}`"
          >
            <rect
              v-if="cnv.start && cnv.end && getCNVDisplayCoords(cnv).width > 0"
              :x="getCNVDisplayCoords(cnv).x"
              :y="centerY + exonHeight / 2 + 10 + (index % 3) * 15"
              :width="getCNVDisplayCoords(cnv).width"
              :height="12"
              :fill="getCNVColor(cnv)"
              :opacity="0.6"
              stroke="#D32F2F"
              stroke-width="1"
              class="cnv-rect"
              @mouseenter="showVariantTooltip($event, cnv)"
              @mousemove="updateTooltipPosition($event)"
              @click="handleVariantClick(cnv)"
            />
          </g>

          <!-- SNV markers -->
          <g
            v-for="(variant, index) in snvVariants"
            :key="`snv-${index}`"
          >
            <!-- Connecting line -->
            <line
              v-if="variant.position"
              :x1="scalePosition(variant.position)"
              :y1="centerY - exonHeight / 2"
              :x2="scalePosition(variant.position)"
              :y2="centerY - exonHeight / 2 - 30 - (index % 3) * 10"
              :stroke="variant.isCurrentVariant ? '#9C27B0' : '#BDBDBD'"
              :stroke-width="variant.isCurrentVariant ? 2 : 1"
              stroke-dasharray="2,2"
            />
            <!-- Variant marker circle -->
            <circle
              v-if="variant.position"
              :cx="scalePosition(variant.position)"
              :cy="centerY - exonHeight / 2 - 30 - (index % 3) * 10"
              :r="variant.isCurrentVariant ? 15 : 5"
              :fill="getVariantColor(variant)"
              :stroke="variant.isCurrentVariant ? '#9C27B0' : '#424242'"
              :stroke-width="variant.isCurrentVariant ? 5 : 1"
              :opacity="variant.isCurrentVariant ? 1 : 0.7"
              class="variant-circle"
              :class="{ 'current-variant': variant.isCurrentVariant }"
              @mouseenter="showVariantTooltip($event, variant)"
              @mousemove="updateTooltipPosition($event)"
              @click="handleVariantClick(variant)"
            />
            <!-- Star icon for current variant -->
            <text
              v-if="variant.position && variant.isCurrentVariant"
              :x="scalePosition(variant.position)"
              :y="centerY - exonHeight / 2 - 30 - (index % 3) * 10 + 6"
              text-anchor="middle"
              class="variant-star-icon"
              fill="white"
              font-size="16"
              font-weight="bold"
              pointer-events="none"
            >
              ★
            </text>
            <!-- Variant label for current variant -->
            <text
              v-if="variant.position && variant.isCurrentVariant"
              :x="scalePosition(variant.position)"
              :y="centerY - exonHeight / 2 - 70"
              text-anchor="middle"
              class="variant-label-text"
              fill="#9C27B0"
              font-size="14"
              font-weight="bold"
              pointer-events="none"
            >
              {{ variant.simple_id || variant.variant_id }}
            </text>
            <!-- Protein notation for current variant -->
            <text
              v-if="variant.position && variant.isCurrentVariant && variant.protein"
              :x="scalePosition(variant.position)"
              :y="centerY - exonHeight / 2 - 55"
              text-anchor="middle"
              class="variant-protein-text"
              fill="#757575"
              font-size="11"
              pointer-events="none"
            >
              {{ extractPNotation(variant.protein) }}
            </text>
          </g>
        </svg>
      </div>

      <!-- Zoom Controls -->
      <v-row class="mt-3">
        <v-col
          cols="12"
          class="text-center"
        >
          <v-btn-group density="compact">
            <v-btn
              size="small"
              @click="zoomIn"
            >
              <v-icon>mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn
              size="small"
              @click="zoomOut"
            >
              <v-icon>mdi-magnify-minus</v-icon>
            </v-btn>
            <v-btn
              size="small"
              @click="resetZoom"
            >
              <v-icon>mdi-magnify</v-icon>
              Reset
            </v-btn>
          </v-btn-group>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Floating Tooltip -->
    <div
      v-if="tooltipVisible && tooltipContent"
      :style="{
        position: 'fixed',
        left: tooltipX + 'px',
        top: tooltipY + 'px',
        zIndex: 9999,
      }"
      class="custom-tooltip"
    >
      <v-card
        max-width="350"
        elevation="8"
      >
        <v-card-text class="pa-3">
          <div v-if="tooltipContent.type === 'exon'">
            <div class="text-h6 mb-2">
              Exon {{ tooltipContent.data.number }}
            </div>
            <div class="text-body-2">
              <strong>Position:</strong> chr17:{{ formatCoordinate(tooltipContent.data.start) }}-{{
                formatCoordinate(tooltipContent.data.end)
              }}
            </div>
            <div class="text-body-2">
              <strong>Size:</strong> {{ tooltipContent.data.size }} bp
            </div>
            <div
              v-if="tooltipContent.data.domain"
              class="text-body-2"
            >
              <strong>Domain:</strong> {{ tooltipContent.data.domain }}
            </div>
            <div class="text-caption mt-2 text-grey">
              <v-icon
                size="small"
                left
              >
                mdi-magnify-plus-outline
              </v-icon>
              Click to zoom to this exon
            </div>
          </div>
          <div v-else-if="tooltipContent.type === 'variant'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.simple_id || tooltipContent.data.variant_id }}
            </div>
            <div
              v-if="tooltipContent.data.transcript"
              class="text-body-2"
            >
              {{ extractCNotation(tooltipContent.data.transcript) }}
            </div>
            <div
              v-if="tooltipContent.data.protein"
              class="text-body-2"
            >
              {{ extractPNotation(tooltipContent.data.protein) }}
            </div>
            <div class="mt-2">
              <v-chip
                :color="getVariantColor(tooltipContent.data)"
                size="small"
              >
                {{ tooltipContent.data.classificationVerdict || 'Unknown' }}
              </v-chip>
            </div>
            <div class="text-caption mt-2 text-grey">
              Click to view details
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </v-card>
</template>

<script>
export default {
  name: 'HNF1BGeneVisualization',
  props: {
    variants: {
      type: Array,
      default: () => [],
    },
    currentVariantId: {
      type: String,
      default: null,
    },
  },
  emits: ['variant-clicked'],
  data() {
    return {
      svgWidth: 1000,
      svgHeight: 250,
      margin: { top: 40, right: 50, bottom: 40, left: 50 },
      exonHeight: 40,
      geneStart: 37680000, // chr17 coordinates (GRCh38) - adjusted to show actual variant positions
      geneEnd: 37750000, // 70kb range covering all HNF1B coding variants
      tooltipVisible: false,
      tooltipX: 0,
      tooltipY: 0,
      tooltipContent: null,
      zoomLevel: 1,
      zoomedExon: null, // Track which exon is zoomed in
      exons: [
        // HNF1B coding exons (GRCh38 coordinates from UCSC NM_000458.4)
        // Note: Gene is on minus strand, so exon 1 is at higher genomic coordinates
        { number: 1, start: 37744540, end: 37745059, size: 519, domain: '5\' UTR' },
        { number: 2, start: 37739439, end: 37739639, size: 200, domain: null },
        { number: 3, start: 37733556, end: 37733821, size: 265, domain: 'POU-S' },
        { number: 4, start: 37731594, end: 37731830, size: 236, domain: 'POU-H' },
        { number: 5, start: 37710502, end: 37710663, size: 161, domain: 'POU-H' },
        { number: 6, start: 37704916, end: 37705049, size: 133, domain: null },
        { number: 7, start: 37700982, end: 37701177, size: 195, domain: 'Transactivation' },
        { number: 8, start: 37699075, end: 37699194, size: 119, domain: 'Transactivation' },
        { number: 9, start: 37686430, end: 37687392, size: 962, domain: '3\' UTR' },
      ],
    };
  },
  computed: {
    centerY() {
      return (this.svgHeight - this.margin.top - this.margin.bottom) / 2 + this.margin.top;
    },
    visibleGeneStart() {
      if (this.zoomedExon) {
        // Add padding around exon (200bp on each side)
        return Math.max(this.zoomedExon.start - 200, this.geneStart);
      }
      return this.geneStart;
    },
    visibleGeneEnd() {
      if (this.zoomedExon) {
        // Add padding around exon (200bp on each side)
        return Math.min(this.zoomedExon.end + 200, this.geneEnd);
      }
      return this.geneEnd;
    },
    variantsWithPositions() {
      return this.variants
        .filter((v) => v.variant_id === this.currentVariantId) // Only show current variant
        .map((v) => ({
          ...v,
          isCurrentVariant: true,
          position: this.extractVariantPosition(v),
          isCNV: this.isCNV(v),
        }))
        .filter((v) => v.position !== null);
    },
    snvVariants() {
      return this.variantsWithPositions.filter((v) => !v.isCNV);
    },
    cnvVariants() {
      return this.variantsWithPositions
        .filter((v) => v.isCNV)
        .map((v) => {
          const cnvDetails = this.getCNVDetails(v);
          return {
            ...v,
            start: cnvDetails?.start ? parseInt(cnvDetails.start) : null,
            end: cnvDetails?.end ? parseInt(cnvDetails.end) : null,
            cnvType: cnvDetails?.type,
          };
        })
        .filter((v) => v.start && v.end);
    },
  },
  mounted() {
    this.updateSVGWidth();
    window.addEventListener('resize', this.updateSVGWidth);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.updateSVGWidth);
  },
  methods: {
    updateSVGWidth() {
      if (this.$refs.svgContainer) {
        const containerWidth = this.$refs.svgContainer.clientWidth;
        // Ensure minimum width to prevent scaling issues
        this.svgWidth = Math.max(containerWidth, 800);
      }
    },
    scalePosition(genomicPosition) {
      // Use visible range when zoomed, full range otherwise
      const geneLength = this.visibleGeneEnd - this.visibleGeneStart;
      const svgLength = this.svgWidth - this.margin.left - this.margin.right;
      const relativePosition = (genomicPosition - this.visibleGeneStart) / geneLength;
      return this.margin.left + relativePosition * svgLength;
    },
    extractVariantPosition(variant) {
      // For CNVs, return the midpoint
      if (this.isCNV(variant)) {
        const details = this.getCNVDetails(variant);
        if (details) {
          return (parseInt(details.start) + parseInt(details.end)) / 2;
        }
      }

      // Parse from HG38 coordinate
      if (variant.hg38) {
        // Format: "chr17-36098063-C-T" or "17:36459258-37832869:DEL"
        const snvMatch = variant.hg38.match(/chr\d+-(\d+)-/);
        if (snvMatch) return parseInt(snvMatch[1]);

        const cnvMatch = variant.hg38.match(/:(\d+)-(\d+):/);
        if (cnvMatch) return (parseInt(cnvMatch[1]) + parseInt(cnvMatch[2])) / 2;
      }

      return null;
    },
    isCNV(variant) {
      if (!variant || !variant.hg38) return false;
      return /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
    },
    getCNVDetails(variant) {
      if (!variant || !variant.hg38) return null;
      const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
      if (match) {
        return {
          chromosome: match[1],
          start: match[2],
          end: match[3],
          type: match[4],
        };
      }
      return null;
    },
    getExonColor(exon) {
      if (exon.domain?.includes('POU')) return '#42A5F5'; // Blue
      if (exon.domain?.includes('Transactivation')) return '#66BB6A'; // Green
      if (exon.domain?.includes('UTR')) return '#BDBDBD'; // Grey
      return '#1E88E5'; // Default blue
    },
    getVariantColor(variant) {
      const classification = variant.classificationVerdict?.toUpperCase() || '';
      if (classification.includes('PATHOGENIC') && !classification.includes('LIKELY')) {
        return '#EF5350'; // red-lighten-3
      }
      if (classification.includes('LIKELY_PATHOGENIC') || classification.includes('LIKELY PATHOGENIC')) {
        return '#FF9800'; // orange-lighten-3
      }
      if (classification.includes('UNCERTAIN') || classification.includes('VUS')) {
        return '#FFEB3B'; // yellow-lighten-3
      }
      if (classification.includes('LIKELY_BENIGN')) {
        return '#9CCC65'; // light-green-lighten-3
      }
      if (classification.includes('BENIGN')) {
        return '#66BB6A'; // green-lighten-3
      }
      return '#BDBDBD'; // grey
    },
    getCNVColor(cnv) {
      if (cnv.cnvType === 'DEL') return '#EF5350'; // Red for deletion
      if (cnv.cnvType === 'DUP') return '#42A5F5'; // Blue for duplication
      return '#9E9E9E'; // Grey for unknown
    },
    getCNVDisplayCoords(cnv) {
      // Clamp CNV coordinates to visible gene region to prevent negative widths
      // CNVs can span beyond gene boundaries (e.g., whole gene deletions)
      const clampedStart = Math.max(cnv.start, this.geneStart);
      const clampedEnd = Math.min(cnv.end, this.geneEnd);

      const x = this.scalePosition(clampedStart);
      const width = this.scalePosition(clampedEnd) - x;

      return {
        x: Math.max(x, this.margin.left), // Ensure x is within left margin
        width: Math.max(width, 0), // Ensure width is non-negative
      };
    },
    formatCoordinate(pos) {
      return parseInt(pos).toLocaleString();
    },
    extractCNotation(transcript) {
      if (!transcript) return '';
      const match = transcript.match(/:(.+)$/);
      return match && match[1] ? match[1] : transcript;
    },
    extractPNotation(protein) {
      if (!protein) return '';
      const match = protein.match(/:(.+)$/);
      return match && match[1] ? match[1] : protein;
    },
    showExonTooltip(event, exon) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'exon', data: exon };
      this.tooltipVisible = true;
    },
    showVariantTooltip(event, variant) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'variant', data: variant };
      this.tooltipVisible = true;
    },
    updateTooltipPosition(event) {
      this.tooltipX = event.clientX + 15;
      this.tooltipY = event.clientY + 15;
    },
    hideTooltip() {
      this.tooltipVisible = false;
      this.tooltipContent = null;
    },
    handleVariantClick(variant) {
      this.$emit('variant-clicked', variant);
    },
    handleExonClick(exon) {
      // Toggle zoom: if already zoomed to this exon, zoom out
      if (this.zoomedExon?.number === exon.number) {
        this.zoomedExon = null;
      } else {
        this.zoomedExon = exon;
      }
    },
    zoomIn() {
      this.zoomLevel = Math.min(this.zoomLevel * 1.3, 5);
    },
    zoomOut() {
      this.zoomLevel = Math.max(this.zoomLevel / 1.3, 1);
    },
    resetZoom() {
      this.zoomLevel = 1;
      this.zoomedExon = null; // Also reset exon zoom
    },
  },
};
</script>

<style scoped>
.gene-viz-card {
  margin-bottom: 16px;
}

.legend-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.svg-container {
  width: 100%;
  overflow-x: auto;
}

.gene-visualization {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #fafafa;
  display: block;
}

.chromosome-label {
  font-size: 14px;
  font-weight: 600;
  fill: #424242;
}

.coordinate-label {
  font-size: 11px;
  fill: #757575;
}

.exon-label {
  font-size: 10px;
  font-weight: 600;
  fill: #1565c0;
  pointer-events: none;
}

.exon-rect {
  cursor: pointer;
  transition: all 0.3s ease;
}

.exon-rect:hover {
  opacity: 0.8;
  filter: brightness(1.1);
}

.exon-rect.exon-zoomed {
  filter: drop-shadow(0 0 6px rgba(255, 111, 0, 0.8));
  animation: pulse-zoom 2s ease-in-out infinite;
}

@keyframes pulse-zoom {
  0%, 100% {
    filter: drop-shadow(0 0 6px rgba(255, 111, 0, 0.8));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(255, 111, 0, 1));
  }
}

.zoom-indicator-label {
  font-size: 11px;
  font-weight: 600;
  fill: #ff6f00;
}

.variant-circle {
  cursor: pointer;
  transition: opacity 0.2s;
}

.variant-circle:hover {
  opacity: 0.9;
}

.current-variant {
  filter: drop-shadow(0 0 8px rgba(156, 39, 176, 0.6));
}

.cnv-rect {
  cursor: pointer;
  transition: opacity 0.2s;
}

.cnv-rect:hover {
  opacity: 0.9;
}

.custom-tooltip {
  pointer-events: none;
}
</style>
