<!-- HNF1B Protein Domain Lollipop Plot -->
<template>
  <v-card class="protein-viz-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="secondary"> mdi-protein </v-icon>
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
            <v-icon size="small"> mdi-open-in-new </v-icon>
          </v-btn>
        </template>
        <span>View in UniProt (P35680)</span>
      </v-tooltip>
      <v-spacer />
      <v-chip size="small" color="info">
        {{ snvVariants.length }} SNV{{ snvVariants.length !== 1 ? 's' : '' }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Legend -->
      <v-row class="mb-2">
        <v-col cols="12">
          <div class="legend-container">
            <v-chip size="small" color="orange-lighten-2">
              <v-icon left size="small"> mdi-square </v-icon>
              Dimerization
            </v-chip>
            <v-chip size="small" color="blue-lighten-2">
              <v-icon left size="small"> mdi-square </v-icon>
              POU-Specific
            </v-chip>
            <v-chip size="small" color="cyan-lighten-2">
              <v-icon left size="small"> mdi-square </v-icon>
              POU-Homeodomain
            </v-chip>
            <v-chip size="small" color="green-lighten-2">
              <v-icon left size="small"> mdi-square </v-icon>
              Transactivation
            </v-chip>
            <v-chip size="small" color="red-lighten-3">
              <v-icon left size="small"> mdi-circle </v-icon>
              Pathogenic
            </v-chip>
            <v-chip size="small" color="orange-lighten-3">
              <v-icon left size="small"> mdi-circle </v-icon>
              Likely Pathogenic
            </v-chip>
            <v-chip size="small" color="yellow-darken-1">
              <v-icon left size="small"> mdi-circle </v-icon>
              VUS
            </v-chip>
            <v-chip size="small" color="light-green-lighten-3">
              <v-icon left size="small"> mdi-circle </v-icon>
              Likely Benign
            </v-chip>
          </div>
        </v-col>
      </v-row>

      <!-- Info Alert for CNVs -->
      <v-alert v-if="cnvVariants.length > 0" type="warning" density="compact" class="mb-3">
        <v-icon size="small" class="mr-1"> mdi-alert </v-icon>
        {{ cnvVariants.length }} CNV(s) not shown in protein view. Switch to Gene View to see
        structural variants.
      </v-alert>

      <!-- Info Alert for Splice Variants -->
      <v-alert
        v-if="isCurrentVariantSpliceVariant"
        type="info"
        density="compact"
        variant="tonal"
        class="mb-3"
      >
        <v-icon size="small" class="mr-1"> mdi-information </v-icon>
        <strong>Splice site variant detected:</strong> {{ currentVariantTranscript }}
        <div class="text-caption mt-1">
          This variant affects RNA splicing and cannot be displayed in protein view. The exact
          protein effect depends on how splicing is disrupted (exon skipping, intron retention, or
          cryptic splice sites). Switch to Gene View to see the genomic location.
        </div>
      </v-alert>

      <!-- SVG Visualization -->
      <div ref="svgContainer" class="svg-container">
        <svg
          ref="proteinSvg"
          :width="svgWidth"
          :height="svgHeight"
          class="protein-visualization"
          @mouseleave="hideTooltip"
        >
          <!-- Zoom Group: All visualization content that should zoom/pan -->
          <g id="zoom-group">
            <!-- Protein backbone line -->
            <line
              :x1="margin.left"
              :y1="backboneY"
              :x2="svgWidth - margin.right"
              :y2="backboneY"
              stroke="#424242"
              stroke-width="4"
            />

            <!-- Amino acid scale markers removed - using domain boundaries instead -->

            <!-- Protein domains -->
            <g v-for="(domain, index) in domains" :key="`domain-${index}`">
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
                :x="
                  scaleAAPosition(domain.start) +
                  Math.max(scaleAAPosition(domain.end) - scaleAAPosition(domain.start), 1) / 2
                "
                :y="backboneY + 5"
                text-anchor="middle"
                class="domain-label"
              >
                {{ domain.shortName }}
              </text>
              <!-- Domain start position label (replaces scale markers) -->
              <text
                :x="scaleAAPosition(domain.start)"
                :y="backboneY + 25"
                text-anchor="middle"
                class="domain-boundary-label"
              >
                {{ domain.start }}
              </text>
              <!-- Domain end position label (replaces scale markers) -->
              <text
                :x="scaleAAPosition(domain.end)"
                :y="backboneY + 25"
                text-anchor="middle"
                class="domain-boundary-label"
              >
                {{ domain.end }}
              </text>
            </g>

            <!-- Lollipop stems and circles for variants -->
            <g v-for="(group, position) in groupedVariants" :key="`lollipop-${position}`">
              <!-- Stem (line from protein to lollipop) -->
              <!-- If variant is in a domain, stem starts from top of domain box -->
              <!-- If variant is outside domains, stem starts from backbone center -->
              <line
                :x1="scaleAAPosition(parseInt(position))"
                :y1="isPositionInDomain(position) ? backboneY - domainHeight / 2 : backboneY"
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
          </g>
        </svg>
      </div>

      <!-- Zoom Controls -->
      <v-row class="mt-3">
        <v-col cols="12" class="text-center">
          <v-btn-group density="compact">
            <v-btn size="small" @click="zoomIn">
              <v-icon>mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn size="small" @click="zoomOut">
              <v-icon>mdi-magnify-minus</v-icon>
            </v-btn>
            <v-btn size="small" @click="resetZoom">
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
      <v-card max-width="350" elevation="8">
        <v-card-text class="pa-3">
          <div v-if="tooltipContent.type === 'domain'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.name }}
            </div>
            <div class="text-body-2">
              <strong>Position:</strong> aa {{ tooltipContent.data.start }}-{{
                tooltipContent.data.end
              }}
            </div>
            <div class="text-body-2">
              <strong>Length:</strong>
              {{ tooltipContent.data.end - tooltipContent.data.start + 1 }} amino acids
            </div>
            <div v-if="tooltipContent.data.function" class="text-body-2 mt-1">
              <strong>Function:</strong> {{ tooltipContent.data.function }}
            </div>
          </div>
          <div v-else-if="tooltipContent.type === 'variant'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.simple_id || tooltipContent.data.variant_id }}
            </div>
            <div v-if="tooltipContent.data.protein" class="text-body-2">
              {{ extractPNotation(tooltipContent.data.protein) }}
            </div>
            <div v-if="tooltipContent.data.transcript" class="text-body-2 text-grey">
              {{ extractCNotation(tooltipContent.data.transcript) }}
            </div>
            <div v-if="tooltipContent.data.aaPosition" class="text-body-2">
              <strong>Position:</strong> aa {{ tooltipContent.data.aaPosition }}
            </div>
            <div class="mt-2">
              <v-chip :color="getVariantColor(tooltipContent.data)" size="small">
                {{ tooltipContent.data.classificationVerdict || 'Unknown' }}
              </v-chip>
            </div>
            <div v-if="tooltipContent.data.individualCount" class="text-body-2 mt-1">
              <strong>Individuals:</strong> {{ tooltipContent.data.individualCount }}
            </div>
            <div class="text-caption mt-2 text-grey">Click to view details</div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </v-card>
</template>

<script>
import * as d3 from 'd3';
import { extractCNotation, extractPNotation } from '@/utils/hgvs';
import { getReferenceGeneDomains } from '@/api';

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
      // D3 zoom properties
      d3Zoom: null, // D3 zoom behavior instance
      d3Transform: null, // Current D3 zoom transform
      // Loading state for API data
      loading: false,
      apiError: null,
      // Domain coordinates - fallback data (verified from UniProt P35680 2025-01-17)
      // Will be replaced with API data if available
      // Source: https://www.uniprot.org/uniprotkb/P35680/entry
      // RefSeq: NP_000449.1
      domains: [
        {
          name: 'Dimerization Domain',
          shortName: 'Dim',
          start: 1,
          end: 31, // Corrected from 32
          color: '#FFB74D',
          function: 'Mediates homodimer or heterodimer formation',
        },
        {
          name: 'POU-Specific Domain',
          shortName: 'POU-S',
          start: 8, // Corrected from 101
          end: 173, // Corrected from 157
          color: '#64B5F6',
          function: 'DNA binding (part 1) - IPR000327',
        },
        {
          name: 'POU Homeodomain',
          shortName: 'POU-H',
          start: 232, // Corrected from 183
          end: 305, // Corrected from 243
          color: '#4FC3F7',
          function: 'DNA binding (part 2) - IPR001356',
        },
        {
          name: 'Transactivation Domain',
          shortName: 'TAD',
          start: 314, // Corrected from 400
          end: 557,
          color: '#81C784',
          function: 'Transcriptional activation',
        },
      ],
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
  async mounted() {
    this.updateSVGWidth();
    window.addEventListener('resize', this.updateSVGWidth);
    this.initializeD3Zoom();
    window.addEventListener('keydown', this.handleKeyboardShortcuts);

    // Fetch protein domains from API
    await this.fetchProteinDomains();
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.updateSVGWidth);
    window.removeEventListener('keydown', this.handleKeyboardShortcuts);
  },
  methods: {
    async fetchProteinDomains() {
      try {
        this.loading = true;
        this.apiError = null;

        window.logService.info('Fetching HNF1B protein domains from API');
        const response = await getReferenceGeneDomains('HNF1B', 'GRCh38');

        if (response.data && response.data.domains && response.data.domains.length > 0) {
          // Map API domain data to component format
          this.domains = response.data.domains.map((domain) => ({
            name: domain.name,
            shortName: domain.short_name || domain.name.substring(0, 5),
            start: domain.start,
            end: domain.end,
            color: this.getDomainColor(domain.name),
            function: domain.function || '',
          }));

          // Update protein length from API if available
          if (response.data.length) {
            this.proteinLength = response.data.length;
          }

          window.logService.info('Successfully loaded protein domains from API', {
            domainCount: this.domains.length,
            proteinLength: this.proteinLength,
          });
        }
      } catch (error) {
        this.apiError = error.message;
        window.logService.warn('Failed to fetch protein domains from API, using fallback data', {
          error: error.message,
        });
        // Keep fallback domains from data()
      } finally {
        this.loading = false;
      }
    },
    getDomainColor(domainName) {
      // Map domain names to colors matching the original hardcoded values
      const colorMap = {
        'Dimerization Domain': '#FFB74D',
        'POU-Specific Domain': '#64B5F6',
        'POU Homeodomain': '#4FC3F7',
        'Transactivation Domain': '#81C784',
      };
      return colorMap[domainName] || '#9E9E9E'; // Default gray for unknown domains
    },
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
      const match = pNotation.match(
        /p\.([A-Z][a-z]{2})?(\d+)(_[A-Z][a-z]{2}\d+)?(del|dup|ins|Ter|[A-Z][a-z]{2}|\?)?/
      );
      if (match && match[2]) {
        return parseInt(match[2]);
      }

      return null;
    },
    isCNV(variant) {
      if (!variant || !variant.hg38) return false;
      return /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
    },
    isPositionInDomain(position) {
      // Check if the amino acid position falls within any protein domain
      const pos = parseInt(position);
      return this.domains.some((domain) => pos >= domain.start && pos <= domain.end);
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
      if (
        classification.includes('LIKELY_PATHOGENIC') ||
        classification.includes('LIKELY PATHOGENIC')
      ) {
        return '#FF9800'; // orange-lighten-3
      }
      if (classification.includes('UNCERTAIN') || classification.includes('VUS')) {
        return '#FBC02D'; // yellow-darken-1
      }
      if (classification.includes('LIKELY_BENIGN')) {
        return '#9CCC65'; // light-green-lighten-3
      }
      if (classification.includes('BENIGN')) {
        return '#66BB6A'; // green-lighten-3
      }
      return '#BDBDBD'; // grey
    },
    // HGVS extraction functions imported from utils/hgvs
    extractCNotation,
    extractPNotation,
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
      if (this.d3Zoom && this.$refs.proteinSvg) {
        const svg = d3.select(this.$refs.proteinSvg);
        const centerX = this.svgWidth / 2;
        const centerY = this.svgHeight / 2;

        // Get current transform
        const currentTransform = d3.zoomTransform(this.$refs.proteinSvg);

        // Calculate new scale
        const newScale = Math.min(currentTransform.k * 1.3, 10);

        // Calculate new transform centered on the viewport center
        const transform = d3.zoomIdentity
          .translate(centerX, centerY)
          .scale(newScale)
          .translate(-centerX, -centerY);

        svg.transition().duration(300).call(this.d3Zoom.transform, transform);
      }
    },
    zoomOut() {
      if (this.d3Zoom && this.$refs.proteinSvg) {
        const svg = d3.select(this.$refs.proteinSvg);
        const centerX = this.svgWidth / 2;
        const centerY = this.svgHeight / 2;

        // Get current transform
        const currentTransform = d3.zoomTransform(this.$refs.proteinSvg);

        // Calculate new scale
        const newScale = Math.max(currentTransform.k / 1.3, 1);

        // Calculate new transform centered on the viewport center
        const transform = d3.zoomIdentity
          .translate(centerX, centerY)
          .scale(newScale)
          .translate(-centerX, -centerY);

        svg.transition().duration(300).call(this.d3Zoom.transform, transform);
      }
    },
    resetZoom() {
      if (this.d3Zoom && this.$refs.proteinSvg) {
        const svg = d3.select(this.$refs.proteinSvg);
        this.d3Zoom.transform(svg.transition().duration(500), d3.zoomIdentity);
      }
    },
    initializeD3Zoom() {
      if (!this.$refs.proteinSvg) return;

      const svg = d3.select(this.$refs.proteinSvg);
      const g = svg.select('#zoom-group');

      // Create zoom behavior with constraints
      this.d3Zoom = d3
        .zoom()
        .scaleExtent([1, 10]) // Min 1x, Max 10x zoom
        .on('zoom', (event) => {
          this.d3Transform = event.transform;
          g.attr('transform', event.transform);
          this.zoomLevel = event.transform.k; // Update zoomLevel for display
        });

      // Apply zoom behavior to SVG
      svg.call(this.d3Zoom);

      // Constrain panning to prevent scrolling off-canvas
      this.d3Zoom.translateExtent([
        [0, 0],
        [this.svgWidth, this.svgHeight],
      ]);
    },
    handleKeyboardShortcuts(event) {
      // Only trigger if focused on body or SVG (not in input fields)
      const target = event.target;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (event.key === '+' || event.key === '=') {
        event.preventDefault();
        this.zoomIn();
      } else if (event.key === '-' || event.key === '_') {
        event.preventDefault();
        this.zoomOut();
      } else if (event.key === '0') {
        event.preventDefault();
        this.resetZoom();
      }
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

.domain-boundary-label {
  font-size: 9px;
  font-weight: 500;
  fill: #1565c0;
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
