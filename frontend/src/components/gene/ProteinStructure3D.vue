<!-- 3D Protein Structure Viewer using NGL.js -->
<!-- Supports two modes: single variant (detail page) or all variants with panel (homepage) -->
<!-- Smart container: owns UI/derived state, lays out the 4 sub-components, props-down/emits-up. -->
<template>
  <v-card class="protein-3d-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="secondary"> mdi-cube-outline </v-icon>
      HNF1B 3D Structure (PDB: 2H8R)
      <v-tooltip location="bottom" aria-label="View in RCSB PDB">
        <template #activator="{ props }">
          <v-btn
            icon
            size="x-small"
            variant="text"
            v-bind="props"
            href="https://www.rcsb.org/structure/2H8R"
            target="_blank"
            rel="noopener noreferrer"
            class="ml-1"
            aria-label="View in RCSB PDB"
          >
            <v-icon size="small"> mdi-open-in-new </v-icon>
          </v-btn>
        </template>
        <span>View in RCSB PDB</span>
      </v-tooltip>
      <v-spacer />
      <!-- Show current variant info if available (single variant mode) -->
      <v-chip
        v-if="!showAllVariants && currentVariant && currentVariantInStructure"
        size="small"
        :color="getVariantChipColor(currentVariant)"
      >
        {{ getVariantLabel(currentVariant) }}
      </v-chip>
      <!-- Show variant count (all variants mode) -->
      <v-chip v-if="showAllVariants && variantsInStructure.length > 0" size="small" color="primary">
        {{ variantsInStructure.length }} variants in structure
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Info Alert about structure coverage -->
      <v-alert
        type="info"
        variant="tonal"
        density="compact"
        rounded="lg"
        class="mb-3"
        title="Structure coverage"
        text="Residues 90–308 (DNA-binding domain, gap at 187–230). Variants outside this region cannot be visualized in 3D."
      />

      <!-- Unified variant filter + colour-by controls (all-variants view).
           Defaults to missense-only; shares the design + state shape with the
           protein and gene plots. -->
      <VariantPlotControls
        v-if="showAllVariants && !loading && !error"
        v-model="filterState"
        :variants="variantsInStructure"
        class="mb-3"
      />

      <!-- Main Content: 3D Viewport + Optional Variant Panel -->
      <v-row no-gutters>
        <!-- 3D Viewport Column — full width on mobile, 8/12 alongside the
             variant panel from md up so the panel stacks below on phones. -->
        <v-col cols="12" :md="showAllVariants ? 8 : 12">
          <StructureViewer
            ref="viewer"
            :active-variant="activeVariant"
            :active-variant-a-a-position="activeVariantAAPosition"
            :active-variant-in-structure="activeVariantInStructure"
            :representation="representation"
            :show-d-n-a="showDNA"
            :color-by-domain="colorByDomain"
            :show-distance-line="showDistanceLine"
            :variants="variants"
            :show-all-variants="showAllVariants"
            :coloring-mode="filterState.coloringMode"
            @loading="loading = $event"
            @loaded="structureLoaded = true"
            @error="error = $event"
            @distance-info="currentVariantDistanceInfo = $event"
            @distances-calculated="variantDistanceCache = $event"
            @reset-distance-line="showDistanceLine = false"
          />
        </v-col>

        <!-- Variant List Panel (only in showAllVariants mode) -->
        <v-col v-if="showAllVariants" v-show="!loading && !error" cols="12" md="4">
          <VariantPanel
            :variants="filteredAndSortedVariants"
            :total-in-structure="variantsInStructure.length"
            :selected-variant-id="selectedVariantId"
            :hovered-variant-id="hoveredVariantId"
            :sort-by="sortBy"
            :filter-distance="filterDistance"
            :coloring-mode="filterState.coloringMode"
            @select="selectVariant"
            @hover="hoverVariant"
            @unhover="unhoverVariant"
            @clear-filters="clearFilters"
            @update:sort-by="sortBy = $event"
            @update:filter-distance="filterDistance = $event"
          />
        </v-col>
      </v-row>

      <!-- Controls Row -->
      <StructureControls
        v-if="!loading && !error"
        :representation="representation"
        :show-d-n-a="showDNA"
        :color-by-domain="colorByDomain"
        :show-distance-line="showDistanceLine"
        :structure-loaded="structureLoaded"
        :has-active-variant-in-structure="activeVariantInStructure"
        :active-variant-distance-info="activeVariantDistanceInfo"
        @update:representation="representation = $event"
        @update:show-d-n-a="showDNA = $event"
        @update:color-by-domain="colorByDomain = $event"
        @reset="onReset"
        @toggle-distance-line="toggleDistanceLine"
      />

      <!-- Active Variant Distance Info + Legend -->
      <DistanceStatsCard
        v-if="!loading && !error"
        :active-variant-distance-info="activeVariantInStructure ? activeVariantDistanceInfo : null"
        :protein-domains="proteinDomains"
        :color-by-domain="colorByDomain"
      />

      <!-- Current variant not in structure warning (single variant mode) -->
      <v-alert
        v-if="!showAllVariants && currentVariant && !currentVariantInStructure"
        type="warning"
        variant="tonal"
        density="compact"
        rounded="lg"
        icon="mdi-map-marker-off"
        class="mt-3"
        title="Variant not in structure"
      >
        {{ currentVariant.protein || currentVariant.transcript }} is outside the PDB structure range
        (residues 90–308, gap at 187–230).
      </v-alert>

      <!-- Selected variant info (all variants mode) -->
      <v-alert
        v-if="showAllVariants && selectedVariant"
        :type="selectedVariantInStructure ? 'info' : 'warning'"
        :icon="selectedVariantInStructure ? 'mdi-cursor-default-click' : 'mdi-map-marker-off'"
        variant="tonal"
        density="compact"
        rounded="lg"
        class="mt-3"
      >
        <div class="d-flex align-center flex-wrap ga-2">
          <span> <strong>Selected:</strong> {{ getVariantLabel(selectedVariant) }} </span>
          <v-chip size="x-small" :color="getVariantChipColor(selectedVariant)">
            {{ selectedVariant.classificationVerdict || 'Unknown' }}
          </v-chip>
          <v-spacer />
          <v-btn
            size="x-small"
            variant="outlined"
            color="primary"
            @click="emitVariantClicked(selectedVariant)"
          >
            <v-icon size="x-small" start>mdi-open-in-new</v-icon>
            View Details
          </v-btn>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script>
import { STRUCTURE_START, STRUCTURE_END } from '@/utils/dnaDistanceCalculator';
import { getPathogenicityScore } from '@/utils/colors';
import {
  createDefaultFilterState,
  getVariantColorByMode,
  isVariantVisibleByFilters,
  withOnlyConsequence,
} from '@/utils/variantFilters';
import { extractPNotation } from '@/utils/hgvs';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';
import StructureViewer from '@/components/gene/protein-structure/StructureViewer.vue';
import StructureControls from '@/components/gene/protein-structure/StructureControls.vue';
import VariantPanel from '@/components/gene/protein-structure/VariantPanel.vue';
import DistanceStatsCard from '@/components/gene/protein-structure/DistanceStatsCard.vue';
import VariantPlotControls from '@/components/gene/VariantPlotControls.vue';

// HNF1B protein domains (from UniProt P35680)
// Note: PDB 2H8R only covers residues 90-308 (with gap 187-230)
const PROTEIN_DOMAINS = [
  {
    name: 'Dimerization',
    shortName: 'Dim',
    start: 1,
    end: 31,
    color: 0xffb74d, // Orange - not visible in structure (before res 90)
  },
  {
    name: 'POU-Specific',
    shortName: 'POU-S',
    start: 88,
    end: 173,
    color: 0xab47bc, // Purple - partially visible (90-173)
  },
  {
    name: 'POU-Homeodomain',
    shortName: 'POU-H',
    start: 232,
    end: 305,
    color: 0x26a69a, // Teal - fully visible
  },
  {
    name: 'Transactivation',
    shortName: 'TAD',
    start: 314,
    end: 557,
    color: 0x81c784, // Green - not visible in structure (after res 308)
  },
];

export default {
  name: 'ProteinStructure3D',
  components: {
    StructureViewer,
    StructureControls,
    VariantPanel,
    DistanceStatsCard,
    VariantPlotControls,
  },
  props: {
    variants: {
      type: Array,
      default: () => [],
    },
    currentVariantId: {
      type: String,
      default: null,
    },
    showAllVariants: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['variant-clicked'],
  data() {
    return {
      loading: true,
      error: null,
      representation: 'cartoon',
      structureLoaded: false,
      showDNA: true,
      showDistanceLine: false,
      colorByDomain: false,
      currentVariantDistanceInfo: null,
      proteinDomains: PROTEIN_DOMAINS,
      // For showAllVariants mode
      selectedVariantId: null,
      hoveredVariantId: null,
      // Sorting and filtering. The 3D structure is most informative for
      // missense variants (point substitutions that map to a single residue
      // in the DNA-binding domain), so the unified variant controls default to
      // showing missense only; users can widen via the chips / "All".
      sortBy: 'position',
      filterState: withOnlyConsequence(createDefaultFilterState(), 'missense'),
      filterDistance: null,
      // Cache for variant distances (built by the viewer, keyed by variant_id)
      variantDistanceCache: {},
    };
  },
  computed: {
    // Single variant mode computed properties
    currentVariant() {
      if (!this.currentVariantId) return null;
      return this.variants.find((v) => v.variant_id === this.currentVariantId);
    },
    currentVariantAAPosition() {
      if (!this.currentVariant) return null;
      return this.extractAAPosition(this.currentVariant);
    },
    currentVariantInStructure() {
      return (
        this.currentVariantAAPosition && this.isPositionInStructure(this.currentVariantAAPosition)
      );
    },
    // All variants mode computed properties
    variantsInStructure() {
      return this.variants.filter((v) => {
        const pos = this.extractAAPosition(v);
        return pos && this.isPositionInStructure(pos);
      });
    },
    selectedVariant() {
      if (!this.selectedVariantId) return null;
      return this.variants.find((v) => v.variant_id === this.selectedVariantId);
    },
    selectedVariantAAPosition() {
      if (!this.selectedVariant) return null;
      return this.extractAAPosition(this.selectedVariant);
    },
    selectedVariantInStructure() {
      return (
        this.selectedVariantAAPosition && this.isPositionInStructure(this.selectedVariantAAPosition)
      );
    },
    // Unified computed properties for active variant (works for both modes)
    activeVariant() {
      if (this.showAllVariants) {
        return this.selectedVariant;
      }
      return this.currentVariant;
    },
    activeVariantAAPosition() {
      if (!this.activeVariant) return null;
      return this.extractAAPosition(this.activeVariant);
    },
    activeVariantInStructure() {
      return (
        this.activeVariantAAPosition && this.isPositionInStructure(this.activeVariantAAPosition)
      );
    },
    activeVariantDistanceInfo() {
      return this.currentVariantDistanceInfo;
    },
    // Filtered and sorted variants for display in panel.
    // Each variant carries a resolved `_distanceInfo` (from the viewer's cache)
    // so the presentational panel needs no NGL access.
    filteredAndSortedVariants() {
      let variants = this.variantsInStructure.map((v) => ({
        ...v,
        _distanceInfo: this.variantDistanceCache[v.variant_id] || null,
      }));

      // Apply the unified pathogenicity + consequence filters (AND-logic).
      variants = variants.filter((v) => isVariantVisibleByFilters(v, this.filterState));

      // Apply distance filter
      if (this.filterDistance) {
        variants = variants.filter((v) => {
          const category = v._distanceInfo ? v._distanceInfo.category : null;
          return category === this.filterDistance;
        });
      }

      // Apply sorting
      variants.sort((a, b) => {
        if (this.sortBy === 'position') {
          return (this.extractAAPosition(a) || 0) - (this.extractAAPosition(b) || 0);
        }
        if (this.sortBy === 'distance') {
          const distA = a._distanceInfo ? a._distanceInfo.distance : Infinity;
          const distB = b._distanceInfo ? b._distanceInfo.distance : Infinity;
          return distA - distB;
        }
        if (this.sortBy === 'pathogenicity') {
          return this.getPathogenicityScoreValue(b) - this.getPathogenicityScoreValue(a);
        }
        return 0;
      });

      return variants;
    },
  },
  methods: {
    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },

    isPositionInStructure(aaPosition) {
      return aaPosition >= STRUCTURE_START && aaPosition <= STRUCTURE_END;
    },

    getVariantChipColor(variant) {
      // Mode-aware (classification ⇄ consequence) to match the colour-by toggle.
      return getVariantColorByMode(variant, this.filterState);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    getPathogenicityScoreValue(variant) {
      return getPathogenicityScore(variant.classificationVerdict);
    },

    // Variant selection methods for showAllVariants mode
    selectVariant(variant) {
      this.selectedVariantId = variant.variant_id;
    },

    hoverVariant(variant) {
      this.hoveredVariantId = variant.variant_id;
    },

    unhoverVariant() {
      this.hoveredVariantId = null;
    },

    emitVariantClicked(variant) {
      this.$emit('variant-clicked', variant);
    },

    clearFilters() {
      // Reset to all-visible (widening past the missense-only default) and
      // clear the distance filter.
      this.filterState = createDefaultFilterState();
      this.filterDistance = null;
    },

    onReset() {
      if (this.$refs.viewer) {
        this.$refs.viewer.resetView();
      }
    },

    toggleDistanceLine() {
      this.showDistanceLine = !this.showDistanceLine;
    },
  },
};
</script>

<style scoped>
.protein-3d-card {
  margin-bottom: 16px;
}
</style>
