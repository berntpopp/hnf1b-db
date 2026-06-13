<!-- HNF1B Protein Domain Lollipop Plot -->
<template>
  <v-card class="protein-viz-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="secondary"> mdi-protein </v-icon>
      HNF1B Protein Domains (NP_000449.3, 557 aa)
      <v-tooltip location="bottom" aria-label="View protein in UniProt database">
        <template #activator="{ props }">
          <v-btn
            icon
            size="x-small"
            variant="text"
            v-bind="props"
            href="https://www.uniprot.org/uniprotkb/P35680/entry"
            target="_blank"
            rel="noopener noreferrer"
            class="ml-1"
            aria-label="View in UniProt (P35680) - opens in new tab"
          >
            <v-icon size="small" aria-hidden="true"> mdi-open-in-new </v-icon>
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
      <!-- Variant filter + colour-by controls (all-variants view only) -->
      <v-row v-if="!currentVariantId" class="mb-1">
        <v-col cols="12">
          <VariantPlotControls v-model="filterState" :variants="snvVariants" class="mb-2" />

          <!-- Domain filter chips (spatial filter, orthogonal to type/classification) -->
          <div class="vpc-row vpc-row--filter">
            <span class="vpc-label">Domain</span>
            <div class="vpc-chips">
              <v-chip
                v-for="d in domainFilterOptions"
                :key="d.value"
                size="small"
                :color="d.color"
                :variant="activeDomain === d.value ? 'flat' : 'tonal'"
                class="domain-chip"
                :data-testid="`domain-chip-${d.value}`"
                @click="toggleDomain(d.value)"
              >
                {{ d.label }}
              </v-chip>
              <v-btn
                v-if="activeDomain"
                class="all-btn"
                size="x-small"
                variant="text"
                color="primary"
                @click="activeDomain = null"
              >
                Clear
              </v-btn>
            </div>
          </div>

          <!-- Filtered count indicator -->
          <div
            v-if="filteredSnvVariants.length !== snvVariants.length"
            class="filter-indicator mt-2"
          >
            <v-icon size="small" color="primary" class="mr-1"> mdi-filter </v-icon>
            <span class="text-body-2">
              Showing {{ filteredSnvVariants.length }} of {{ snvVariants.length }} SNVs
            </span>
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
          <!-- Visible range coordinate labels -->
          <text :x="margin.left" :y="svgHeight - 10" text-anchor="start" class="coordinate-label">
            {{ visibleStart }} aa
          </text>
          <text
            :x="svgWidth - margin.right"
            :y="svgHeight - 10"
            text-anchor="end"
            class="coordinate-label"
          >
            {{ visibleEnd }} aa
          </text>

          <!-- Zoom Group: All visualization content -->
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
                :opacity="isDomainActive(domain) ? 1 : 0.7"
                :stroke="isDomainActive(domain) ? '#1976D2' : '#424242'"
                :stroke-width="isDomainActive(domain) ? 3 : 1.5"
                class="domain-rect"
                @mouseenter="showDomainTooltip($event, domain)"
                @mousemove="updateTooltipPosition($event)"
                @click="handleDomainClick(domain)"
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
                :y="backboneY + 25 + getBoundaryLabelOffset(domain, 'start')"
                text-anchor="middle"
                class="domain-boundary-label"
              >
                {{ domain.start }}
              </text>
              <!-- Domain end position label (replaces scale markers) -->
              <text
                :x="scaleAAPosition(domain.end)"
                :y="backboneY + 25 + getBoundaryLabelOffset(domain, 'end')"
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
          <v-btn-group density="compact" aria-label="Zoom and pan controls">
            <v-btn
              size="small"
              :disabled="visibleStart <= 1"
              aria-label="Pan left towards N-terminus"
              @click="panLeft"
            >
              <v-icon aria-hidden="true">mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn size="small" aria-label="Zoom in" @click="zoomIn">
              <v-icon aria-hidden="true">mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn size="small" aria-label="Zoom out" @click="zoomOut">
              <v-icon aria-hidden="true">mdi-magnify-minus</v-icon>
            </v-btn>
            <v-btn size="small" aria-label="Reset zoom to full view" @click="resetZoom">
              <v-icon aria-hidden="true">mdi-magnify</v-icon>
              Reset
            </v-btn>
            <v-btn
              size="small"
              :disabled="visibleEnd >= proteinLength"
              aria-label="Pan right towards C-terminus"
              @click="panRight"
            >
              <v-icon aria-hidden="true">mdi-chevron-right</v-icon>
            </v-btn>
          </v-btn-group>
          <div v-if="zoomLevel > 1" class="zoom-indicator mt-1">
            <span class="text-caption text-grey">
              Viewing aa {{ visibleStart }}-{{ visibleEnd }} ({{ Math.round(zoomLevel * 10) / 10 }}x
              zoom)
            </span>
          </div>
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
            <div class="text-caption mt-2 text-grey">
              <v-icon size="small" left> mdi-filter </v-icon>
              Click to filter variants in this domain
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
import {
  getConsequenceHexColor,
  getPathogenicityHexColor,
  getPathogenicityScore,
} from '@/utils/colors';
import {
  COLORING_MODES,
  createDefaultFilterState,
  getVariantColorByMode,
  isVariantVisibleByFilters,
} from '@/utils/variantFilters';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';
import { calculateTooltipPosition } from '@/utils/tooltip';
import { isVariantCNV } from '@/utils/geneVisualization';
import VariantPlotControls from '@/components/gene/VariantPlotControls.vue';

// Amino-acid boundaries used by the spatial "Domain" filter. Kept in sync with
// the fallback domains in data() / UniProt P35680.
const DOMAIN_BOUNDARIES = {
  Dimerization: { start: 1, end: 31 },
  'POU-Specific': { start: 8, end: 173 },
  'POU-Homeodomain': { start: 232, end: 305 },
  Transactivation: { start: 314, end: 557 },
};

// Maps the full domain names (used by the SVG domain rects) to the compact
// filter values used by the domain chips / activeDomain state.
const DOMAIN_NAME_TO_VALUE = {
  'Dimerization Domain': 'Dimerization',
  'POU-Specific Domain': 'POU-Specific',
  'POU Homeodomain': 'POU-Homeodomain',
  'Transactivation Domain': 'Transactivation',
};

export default {
  name: 'HNF1BProteinVisualization',
  components: { VariantPlotControls },
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
      // Visible range for semantic zoom (amino acid positions)
      visibleStart: 1,
      visibleEnd: 557,
      // Filter state: pathogenicity + consequence multi-select + colour-by mode
      filterState: createDefaultFilterState(),
      // Domain filter (spatial, single-select): null or a domain value
      activeDomain: null,
      // D3 zoom properties (kept for panning support)
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
    filteredSnvVariants() {
      // On the single-variant detail view (currentVariantId set), snvVariants
      // is already the single current variant — never hide it behind filters.
      if (this.currentVariantId) {
        return this.snvVariants;
      }

      // AND-logic across pathogenicity + consequence (shared util), then the
      // orthogonal spatial domain filter.
      let result = this.snvVariants.filter((v) => isVariantVisibleByFilters(v, this.filterState));

      if (this.activeDomain) {
        const bounds = DOMAIN_BOUNDARIES[this.activeDomain];
        if (bounds) {
          result = result.filter((v) => v.aaPosition >= bounds.start && v.aaPosition <= bounds.end);
        }
      }

      return result;
    },
    domainFilterOptions() {
      return [
        { value: 'Dimerization', label: 'Dimerization', color: 'orange-lighten-2' },
        { value: 'POU-Specific', label: 'POU-Specific', color: 'blue-lighten-2' },
        { value: 'POU-Homeodomain', label: 'POU-Homeodomain', color: 'cyan-lighten-2' },
        { value: 'Transactivation', label: 'Transactivation', color: 'green-lighten-2' },
      ];
    },
    groupedVariants() {
      // Group filtered variants by amino acid position
      const groups = {};
      this.filteredSnvVariants.forEach((variant) => {
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
    toggleDomain(value) {
      // Single-select spatial filter: clicking the active domain clears it.
      this.activeDomain = this.activeDomain === value ? null : value;
    },
    handleDomainClick(domain) {
      const filterValue = DOMAIN_NAME_TO_VALUE[domain.name] || domain.shortName;
      this.toggleDomain(filterValue);
    },
    isDomainActive(domain) {
      if (!this.activeDomain) return false;
      const filterValue = DOMAIN_NAME_TO_VALUE[domain.name] || domain.shortName;
      return this.activeDomain === filterValue;
    },
    getBoundaryLabelOffset(domain, boundaryType) {
      // Check if this boundary label would overlap with an adjacent domain's label
      // and return a vertical offset to stagger them
      // Only offset the START label of the later domain to avoid both being offset
      const OVERLAP_THRESHOLD = 30; // Minimum AA distance to avoid overlap

      // Only offset start labels, not end labels
      if (boundaryType !== 'start') {
        return 0;
      }

      const currentPos = domain.start;

      for (const otherDomain of this.domains) {
        if (otherDomain.name === domain.name) continue;

        // Check if current start is close to another domain's end
        const distance = currentPos - otherDomain.end;
        if (distance > 0 && distance < OVERLAP_THRESHOLD) {
          // This start label is close to another domain's end - offset it down
          return 12;
        }
      }

      return 0; // No offset needed
    },
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
      // Scale position based on visible range (for semantic zoom)
      const svgLength = this.svgWidth - this.margin.left - this.margin.right;
      const visibleRange = this.visibleEnd - this.visibleStart;
      const relativePosition = (aaPosition - this.visibleStart) / visibleRange;
      return this.margin.left + relativePosition * svgLength;
    },
    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },
    isCNV(variant) {
      return isVariantCNV(variant);
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
      // If any variant is current, use purple (highlight wins over colour mode).
      if (variantGroup.some((v) => v.isCurrentVariant)) {
        return '#9C27B0';
      }
      if (this.filterState.coloringMode === COLORING_MODES.CONSEQUENCE) {
        // Colour the stem by the most frequent consequence in the stack.
        const counts = {};
        let representative = variantGroup[0];
        let best = 0;
        for (const v of variantGroup) {
          const key = v.molecular_consequence || '';
          counts[key] = (counts[key] || 0) + 1;
          if (counts[key] > best) {
            best = counts[key];
            representative = v;
          }
        }
        return getConsequenceHexColor(representative.molecular_consequence);
      }
      // Classification mode: use the most pathogenic variant's colour.
      const mostPathogenic = variantGroup.reduce((prev, curr) => {
        const prevScore = getPathogenicityScore(prev.classificationVerdict);
        const currScore = getPathogenicityScore(curr.classificationVerdict);
        return currScore > prevScore ? curr : prev;
      });
      return getPathogenicityHexColor(mostPathogenic.classificationVerdict);
    },
    getVariantColor(variant) {
      // Mode-aware fill (classification ⇄ consequence). The current-variant
      // highlight is applied on the lollipop stem (getGroupColor), so the
      // per-circle / tooltip chip colour stays true to the colour mode.
      return getVariantColorByMode(variant, this.filterState);
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
      const pos = calculateTooltipPosition(event);
      this.tooltipX = pos.x;
      this.tooltipY = pos.y;
    },
    hideTooltip() {
      this.tooltipVisible = false;
      this.tooltipContent = null;
    },
    handleVariantClick(variant) {
      this.$emit('variant-clicked', variant);
    },
    zoomIn() {
      // Semantic zoom: reduce visible range to spread out variants
      const currentRange = this.visibleEnd - this.visibleStart;
      const center = (this.visibleStart + this.visibleEnd) / 2;
      const newRange = Math.max(currentRange / 1.5, 50); // Min 50 AA visible

      this.visibleStart = Math.max(1, Math.round(center - newRange / 2));
      this.visibleEnd = Math.min(this.proteinLength, Math.round(center + newRange / 2));
      this.zoomLevel = this.proteinLength / (this.visibleEnd - this.visibleStart);
    },
    zoomOut() {
      // Semantic zoom: increase visible range
      const currentRange = this.visibleEnd - this.visibleStart;
      const center = (this.visibleStart + this.visibleEnd) / 2;
      const newRange = Math.min(currentRange * 1.5, this.proteinLength);

      this.visibleStart = Math.max(1, Math.round(center - newRange / 2));
      this.visibleEnd = Math.min(this.proteinLength, Math.round(center + newRange / 2));
      this.zoomLevel = this.proteinLength / (this.visibleEnd - this.visibleStart);

      // If we're near full range, snap to full
      if (this.visibleEnd - this.visibleStart > this.proteinLength * 0.9) {
        this.visibleStart = 1;
        this.visibleEnd = this.proteinLength;
        this.zoomLevel = 1;
      }
    },
    resetZoom() {
      // Reset to full protein view
      this.visibleStart = 1;
      this.visibleEnd = this.proteinLength;
      this.zoomLevel = 1;
    },
    panLeft() {
      // Pan left (toward N-terminus)
      const range = this.visibleEnd - this.visibleStart;
      const panAmount = Math.round(range * 0.2);
      if (this.visibleStart > 1) {
        this.visibleStart = Math.max(1, this.visibleStart - panAmount);
        this.visibleEnd = this.visibleStart + range;
      }
    },
    panRight() {
      // Pan right (toward C-terminus)
      const range = this.visibleEnd - this.visibleStart;
      const panAmount = Math.round(range * 0.2);
      if (this.visibleEnd < this.proteinLength) {
        this.visibleEnd = Math.min(this.proteinLength, this.visibleEnd + panAmount);
        this.visibleStart = this.visibleEnd - range;
      }
    },
    initializeD3Zoom() {
      if (!this.$refs.proteinSvg) return;

      const svg = d3.select(this.$refs.proteinSvg);
      let dragStartX = null;
      let dragStartVisibleStart = null;
      let dragStartVisibleEnd = null;

      // Create drag behavior for panning
      const drag = d3
        .drag()
        .on('start', (event) => {
          dragStartX = event.x;
          dragStartVisibleStart = this.visibleStart;
          dragStartVisibleEnd = this.visibleEnd;
          svg.style('cursor', 'grabbing');
        })
        .on('drag', (event) => {
          if (dragStartX === null) return;

          // Calculate how much to pan based on drag distance
          const svgLength = this.svgWidth - this.margin.left - this.margin.right;
          const visibleRange = dragStartVisibleEnd - dragStartVisibleStart;
          const pixelsPerAA = svgLength / visibleRange;
          const dragDelta = dragStartX - event.x; // Invert: drag left = move right in sequence
          const aaDelta = Math.round(dragDelta / pixelsPerAA);

          // Apply pan with bounds checking
          let newStart = dragStartVisibleStart + aaDelta;
          let newEnd = dragStartVisibleEnd + aaDelta;

          // Clamp to protein bounds
          if (newStart < 1) {
            newStart = 1;
            newEnd = newStart + visibleRange;
          }
          if (newEnd > this.proteinLength) {
            newEnd = this.proteinLength;
            newStart = newEnd - visibleRange;
          }

          this.visibleStart = Math.max(1, newStart);
          this.visibleEnd = Math.min(this.proteinLength, newEnd);
        })
        .on('end', () => {
          dragStartX = null;
          dragStartVisibleStart = null;
          dragStartVisibleEnd = null;
          svg.style('cursor', 'grab');
        });

      // Apply drag behavior
      svg.call(drag);
      svg.style('cursor', 'grab');

      // Add wheel zoom handler separately
      svg.on('wheel.zoom', (event) => {
        event.preventDefault();
        const direction = event.deltaY < 0 ? 'in' : 'out';
        if (direction === 'in') {
          this.zoomIn();
        } else {
          this.zoomOut();
        }
      });
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
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        this.panLeft();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        this.panRight();
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

.legend-chip {
  cursor: pointer;
  transition: all 0.2s ease;
}

.legend-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.filter-indicator {
  display: flex;
  align-items: center;
  color: rgb(var(--v-theme-primary));
}

/* Domain row — mirrors the .vpc-row layout in VariantPlotControls so the
   "Domain" label/chips align with the Classification/Type rows above. */
.vpc-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 28px;
}

.vpc-label {
  flex: 0 0 auto;
  width: 92px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-top: 4px;
}

.vpc-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
}

.domain-chip {
  cursor: pointer;
  font-weight: 500;
}

.all-btn {
  min-width: 0;
  padding: 0 8px;
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
  cursor: grab;
}

.protein-visualization:active {
  cursor: grabbing;
}

.scale-label {
  font-size: 10px;
  fill: #757575;
}

.coordinate-label {
  font-size: 11px;
  fill: #757575;
  font-weight: 500;
}

.zoom-indicator {
  text-align: center;
}

.domain-rect {
  cursor: pointer;
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
