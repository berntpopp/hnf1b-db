<!-- HNF1B Protein Domain Lollipop Plot -->
<template>
  <v-card class="protein-viz-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon
        left
        color="secondary"
      >
        mdi-protein
      </v-icon>
      HNF1B Protein Domains (NP_000449.3, 557 aa)
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            icon
            size="x-small"
            variant="text"
            v-bind="props"
            href="https://www.uniprot.org/uniprotkb/P35680/entry"
            target="_blank"
            class="ml-1"
          >
            <v-icon size="small">
              mdi-open-in-new
            </v-icon>
          </v-btn>
        </template>
        <span>View in UniProt (P35680)</span>
      </v-tooltip>
      <v-spacer />
      <v-chip
        size="small"
        color="info"
      >
        {{ snvVariants.length }} SNV{{ snvVariants.length !== 1 ? 's' : '' }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Legend -->
      <v-row class="mb-2">
        <v-col cols="12">
          <div class="legend-container">
            <v-chip
              size="small"
              color="orange-lighten-2"
            >
              <v-icon
                left
                size="small"
              >
                mdi-square
              </v-icon>
              Dimerization
            </v-chip>
            <v-chip
              size="small"
              color="blue-lighten-2"
            >
              <v-icon
                left
                size="small"
              >
                mdi-square
              </v-icon>
              POU-Specific
            </v-chip>
            <v-chip
              size="small"
              color="cyan-lighten-2"
            >
              <v-icon
                left
                size="small"
              >
                mdi-square
              </v-icon>
              POU-Homeodomain
            </v-chip>
            <v-chip
              size="small"
              color="green-lighten-2"
            >
              <v-icon
                left
                size="small"
              >
                mdi-square
              </v-icon>
              Transactivation
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
          </div>
        </v-col>
      </v-row>

      <!-- Info Alert for CNVs -->
      <v-alert
        v-if="cnvVariants.length > 0"
        type="warning"
        density="compact"
        class="mb-3"
      >
        <v-icon
          size="small"
          class="mr-1"
        >
          mdi-alert
        </v-icon>
        {{ cnvVariants.length }} CNV(s) not shown in protein view. Switch to Gene View to see structural
        variants.
      </v-alert>

      <!-- Info Alert for Splice Variants -->
      <v-alert
        v-if="isCurrentVariantSpliceVariant"
        type="info"
        density="compact"
        variant="tonal"
        class="mb-3"
      >
        <v-icon
          size="small"
          class="mr-1"
        >
          mdi-information
        </v-icon>
        <strong>Splice site variant detected:</strong> {{ currentVariantTranscript }}
        <div class="text-caption mt-1">
          This variant affects RNA splicing and cannot be displayed in protein view. The exact protein effect depends on how splicing is disrupted (exon skipping, intron retention, or cryptic splice sites). Switch to Gene View to see the genomic location.
        </div>
      </v-alert>

      <!-- SVG Visualization -->
      <div
        ref="svgContainer"
        class="svg-container"
      >
        <svg
          ref="proteinSvg"
          :width="svgWidth"
          :height="svgHeight"
          class="protein-visualization"
          @mouseleave="hideTooltip"
        >
          <!-- Protein backbone line -->
          <line
            :x1="margin.left"
            :y1="backboneY"
            :x2="svgWidth - margin.right"
            :y2="backboneY"
            stroke="#424242"
            stroke-width="4"
          />

          <!-- Amino acid scale markers -->
          <g
            v-for="marker in scaleMarkers"
            :key="`marker-${marker}`"
          >
            <line
              :x1="scaleAAPosition(marker)"
              :y1="backboneY"
              :x2="scaleAAPosition(marker)"
              :y2="backboneY + 10"
              stroke="#757575"
              stroke-width="1"
            />
            <text
              :x="scaleAAPosition(marker)"
              :y="backboneY + 25"
              text-anchor="middle"
              class="scale-label"
            >
              {{ marker }}
            </text>
          </g>

          <!-- Protein domains -->
          <g
            v-for="(domain, index) in domains"
            :key="`domain-${index}`"
          >
            <rect
              :x="scaleAAPosition(domain.start)"
              :y="backboneY - domainHeight / 2"
              :width="Math.max(scaleAAPosition(domain.end) - scaleAAPosition(domain.start), 1)"
              :height="domainHeight"
              :fill="domain.color"
              :opacity="0.7"
              stroke="#424242"
              stroke-width="1.5"
              class="domain-rect"
              @mouseenter="showDomainTooltip($event, domain)"
              @mousemove="updateTooltipPosition($event)"
            />
            <text
              :x="scaleAAPosition(domain.start) + Math.max(scaleAAPosition(domain.end) - scaleAAPosition(domain.start), 1) / 2"
              :y="backboneY + 5"
              text-anchor="middle"
              class="domain-label"
            >
              {{ domain.shortName }}
            </text>
          </g>

          <!-- Lollipop stems and circles for variants -->
          <g
            v-for="(group, position) in groupedVariants"
            :key="`lollipop-${position}`"
          >
            <!-- Stem (line from protein to lollipop) -->
            <line
              :x1="scaleAAPosition(parseInt(position))"
              :y1="backboneY - domainHeight / 2"
              :x2="scaleAAPosition(parseInt(position))"
              :y2="backboneY - domainHeight / 2 - getLollipopHeight(group)"
              :stroke="getGroupColor(group)"
              :stroke-width="2"
            />
            <!-- Lollipop circles (stacked if multiple) -->
            <g
              v-for="(variant, vIndex) in group"
              :key="`variant-${variant.variant_id}-${vIndex}`"
            >
              <circle
                :cx="scaleAAPosition(parseInt(position))"
                :cy="backboneY - domainHeight / 2 - getLollipopHeight(group.slice(0, vIndex + 1))"
                :r="8"
                :fill="getVariantColor(variant)"
                :stroke="'#424242'"
                :stroke-width="1.5"
                class="lollipop-circle"
                @mouseenter="showVariantTooltip($event, variant)"
                @mousemove="updateTooltipPosition($event)"
                @click="handleVariantClick(variant)"
              />
            </g>
          </g>

          <!-- Functional sites (stars) -->
          <g
            v-for="site in functionalSites"
            :key="`site-${site.position}`"
          >
            <path
              :d="getStarPath(scaleAAPosition(site.position), backboneY - domainHeight / 2 - 5)"
              fill="#FFD700"
              stroke="#FF6F00"
              stroke-width="1"
              class="functional-site"
              @mouseenter="showSiteTooltip($event, site)"
              @mousemove="updateTooltipPosition($event)"
            />
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
          <div v-if="tooltipContent.type === 'domain'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.name }}
            </div>
            <div class="text-body-2">
              <strong>Position:</strong> aa {{ tooltipContent.data.start }}-{{ tooltipContent.data.end }}
            </div>
            <div class="text-body-2">
              <strong>Length:</strong> {{ tooltipContent.data.end - tooltipContent.data.start + 1 }} amino acids
            </div>
            <div
              v-if="tooltipContent.data.function"
              class="text-body-2 mt-1"
            >
              <strong>Function:</strong> {{ tooltipContent.data.function }}
            </div>
          </div>
          <div v-else-if="tooltipContent.type === 'variant'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.simple_id || tooltipContent.data.variant_id }}
            </div>
            <div
              v-if="tooltipContent.data.protein"
              class="text-body-2"
            >
              {{ extractPNotation(tooltipContent.data.protein) }}
            </div>
            <div
              v-if="tooltipContent.data.transcript"
              class="text-body-2 text-grey"
            >
              {{ extractCNotation(tooltipContent.data.transcript) }}
            </div>
            <div
              v-if="tooltipContent.data.aaPosition"
              class="text-body-2"
            >
              <strong>Position:</strong> aa {{ tooltipContent.data.aaPosition }}
            </div>
            <div class="mt-2">
              <v-chip
                :color="getVariantColor(tooltipContent.data)"
                size="small"
              >
                {{ tooltipContent.data.classificationVerdict || 'Unknown' }}
              </v-chip>
            </div>
            <div
              v-if="tooltipContent.data.individualCount"
              class="text-body-2 mt-1"
            >
              <strong>Individuals:</strong> {{ tooltipContent.data.individualCount }}
            </div>
            <div class="text-caption mt-2 text-grey">
              Click to view details
            </div>
          </div>
          <div v-else-if="tooltipContent.type === 'site'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.label }}
            </div>
            <div class="text-body-2">
              <strong>Position:</strong> aa {{ tooltipContent.data.position }}
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </v-card>
</template>

<script>
export default {
  name: 'HNF1BProteinVisualization',
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
      svgWidth: 1000, // Will be overridden by updateSVGWidth in mounted()
      svgHeight: 300,
      margin: { top: 60, right: 50, bottom: 50, left: 50 },
      domainHeight: 30,
      proteinLength: 557,
      tooltipVisible: false,
      tooltipX: 0,
      tooltipY: 0,
      tooltipContent: null,
      zoomLevel: 1,
      domains: [
        {
          name: 'Dimerization Domain',
          shortName: 'Dim',
          start: 1,
          end: 32,
          color: '#FFB74D',
          function: 'Mediates homodimer or heterodimer formation',
        },
        {
          name: 'POU-Specific Domain',
          shortName: 'POU-S',
          start: 101,
          end: 157,
          color: '#64B5F6',
          function: 'DNA binding (part 1)',
        },
        {
          name: 'POU Homeodomain',
          shortName: 'POU-H',
          start: 183,
          end: 243,
          color: '#4FC3F7',
          function: 'DNA binding (part 2)',
        },
        {
          name: 'Transactivation Domain',
          shortName: 'TAD',
          start: 400,
          end: 557,
          color: '#81C784',
          function: 'Transcriptional activation',
        },
      ],
      functionalSites: [],
    };
  },
  computed: {
    backboneY() {
      return this.svgHeight / 2;
    },
    scaleMarkers() {
      const markers = [];
      for (let i = 0; i <= this.proteinLength; i += 100) {
        markers.push(i);
      }
      if (!markers.includes(this.proteinLength)) {
        markers.push(this.proteinLength);
      }
      return markers;
    },
    variantsWithPositions() {
      // If currentVariantId is provided, show only that variant (used on variant detail page)
      // If no currentVariantId, show all variants (used on homepage)
      const filteredVariants = this.currentVariantId
        ? this.variants.filter((v) => v.variant_id === this.currentVariantId)
        : this.variants;

      return filteredVariants
        .map((v) => ({
          ...v,
          isCurrentVariant: v.variant_id === this.currentVariantId,
          aaPosition: this.extractAAPosition(v),
          isCNV: this.isCNV(v),
        }))
        .filter((v) => v.aaPosition !== null);
    },
    snvVariants() {
      return this.variantsWithPositions.filter((v) => !v.isCNV);
    },
    cnvVariants() {
      return this.variantsWithPositions.filter((v) => v.isCNV);
    },
    groupedVariants() {
      // Group variants by amino acid position
      const groups = {};
      this.snvVariants.forEach((variant) => {
        const pos = variant.aaPosition;
        if (!groups[pos]) {
          groups[pos] = [];
        }
        groups[pos].push(variant);
      });
      return groups;
    },
    isCurrentVariantSpliceVariant() {
      // Check if current variant is a splice site variant (has transcript but no protein notation)
      if (!this.currentVariantId) return false;

      const currentVariant = this.variants.find((v) => v.variant_id === this.currentVariantId);
      if (!currentVariant) return false;

      // Splice variants have transcript notation but no protein notation
      // Also check for splice site indicators: +/- positions or specific consequences
      const hasTranscript = currentVariant.transcript && currentVariant.transcript !== '-';
      const noProtein = !currentVariant.protein || currentVariant.protein === '-';
      const isSpliceSite = hasTranscript && /[+-]\d+/.test(currentVariant.transcript);

      return hasTranscript && noProtein && isSpliceSite;
    },
    currentVariantTranscript() {
      if (!this.currentVariantId) return '';
      const currentVariant = this.variants.find((v) => v.variant_id === this.currentVariantId);
      return currentVariant?.transcript || '';
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
        // Use full container width without minimum to prevent horizontal scrolling
        this.svgWidth = containerWidth > 0 ? containerWidth : 1000;
      }
    },
    scaleAAPosition(aaPosition) {
      const svgLength = this.svgWidth - this.margin.left - this.margin.right;
      const relativePosition = aaPosition / this.proteinLength;
      return this.margin.left + relativePosition * svgLength;
    },
    extractAAPosition(variant) {
      // Parse amino acid position from HGVS protein notation
      if (!variant.protein) return null;

      const pNotation = this.extractPNotation(variant.protein);
      if (!pNotation) return null;

      // Match various patterns:
      // - p.Arg177Ter (nonsense)
      // - p.Ser546Phe (missense)
      // - p.Met1? (unknown start)
      // - p.Arg177del (deletion)
      // - p.Arg177_Ser178del (deletion range - use start position)
      // - p.Arg177dup (duplication)
      // - p.Arg177_Ser178dup (duplication range - use start position)
      const match = pNotation.match(/p\.([A-Z][a-z]{2})?(\d+)(_[A-Z][a-z]{2}\d+)?(del|dup|ins|Ter|[A-Z][a-z]{2}|\?)?/);
      if (match && match[2]) {
        return parseInt(match[2]);
      }

      return null;
    },
    isCNV(variant) {
      if (!variant || !variant.hg38) return false;
      return /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
    },
    getLollipopHeight(variantGroup) {
      // Stack height based on number of variants at this position
      const baseHeight = 30;
      const stackIncrement = 12;
      return baseHeight + (variantGroup.length - 1) * stackIncrement;
    },
    getGroupColor(variantGroup) {
      // If any variant is current, use purple
      if (variantGroup.some((v) => v.isCurrentVariant)) {
        return '#9C27B0';
      }
      // Otherwise use the most pathogenic variant's color
      const mostPathogenic = variantGroup.reduce((prev, curr) => {
        const prevScore = this.getPathogenicityScore(prev);
        const currScore = this.getPathogenicityScore(curr);
        return currScore > prevScore ? curr : prev;
      });
      return this.getVariantColor(mostPathogenic);
    },
    getPathogenicityScore(variant) {
      const classification = variant.classificationVerdict?.toUpperCase() || '';
      if (classification.includes('PATHOGENIC') && !classification.includes('LIKELY')) return 5;
      if (classification.includes('LIKELY_PATHOGENIC')) return 4;
      if (classification.includes('UNCERTAIN') || classification.includes('VUS')) return 3;
      if (classification.includes('LIKELY_BENIGN')) return 2;
      if (classification.includes('BENIGN')) return 1;
      return 0;
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
    getStarPath(cx, cy) {
      // Create a 5-pointed star path
      const size = 6;
      const points = [];
      for (let i = 0; i < 10; i++) {
        const angle = (i * Math.PI) / 5 - Math.PI / 2;
        const radius = i % 2 === 0 ? size : size / 2;
        points.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
      }
      return `M${points.join('L')}Z`;
    },
    showDomainTooltip(event, domain) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'domain', data: domain };
      this.tooltipVisible = true;
    },
    showVariantTooltip(event, variant) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'variant', data: variant };
      this.tooltipVisible = true;
    },
    showSiteTooltip(event, site) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'site', data: site };
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
    zoomIn() {
      this.zoomLevel = Math.min(this.zoomLevel * 1.3, 5);
    },
    zoomOut() {
      this.zoomLevel = Math.max(this.zoomLevel / 1.3, 1);
    },
    resetZoom() {
      this.zoomLevel = 1;
    },
  },
};
</script>

<style scoped>
.protein-viz-card {
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
  overflow-x: hidden; /* Prevent horizontal scrolling - SVG fits container */
}

.protein-visualization {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #fafafa;
  display: block;
}

.scale-label {
  font-size: 10px;
  fill: #757575;
}

.domain-rect {
  cursor: help;
  transition: opacity 0.2s;
}

.domain-rect:hover {
  opacity: 1;
}

.domain-label {
  font-size: 11px;
  font-weight: 600;
  fill: #424242;
  pointer-events: none;
}

.lollipop-circle {
  cursor: pointer;
  transition: opacity 0.2s;
}

.lollipop-circle:hover {
  opacity: 0.9;
}

.functional-site {
  cursor: help;
  transition: transform 0.2s;
}

.functional-site:hover {
  transform: scale(1.3);
}

.custom-tooltip {
  pointer-events: none;
}
</style>
