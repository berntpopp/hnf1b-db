<!-- 3D Protein Structure Viewer using NGL.js -->
<!-- Supports two modes: single variant (detail page) or all variants with panel (homepage) -->
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
      <v-alert type="info" density="compact" variant="tonal" class="mb-3">
        <v-icon size="small" class="mr-1"> mdi-information </v-icon>
        <strong>Structure coverage:</strong> Residues 90-308 (DNA-binding domain, gap at 187-230).
        Variants outside this region cannot be visualized in 3D.
      </v-alert>

      <!-- Loading state -->
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48" />
        <div class="mt-2 text-grey">Loading 3D structure...</div>
      </div>

      <!-- Error state -->
      <v-alert v-else-if="error" type="error" density="compact" class="mb-3">
        <v-icon size="small" class="mr-1"> mdi-alert </v-icon>
        {{ error }}
      </v-alert>

      <!-- Main Content: 3D Viewport + Optional Variant Panel -->
      <v-row v-show="!loading && !error" no-gutters>
        <!-- 3D Viewport Column -->
        <v-col :cols="showAllVariants ? 8 : 12">
          <StructureViewer
            ref="viewer"
            :representation="representation"
            :show-dna="showDNA"
            :color-by-domain="colorByDomain"
            :active-variant="activeVariant"
            :active-variant-position="activeVariantAAPosition"
            :distance-info="currentVariantDistanceInfo"
            :show-distance-line="showDistanceLine"
            @structure-ready="onStructureReady"
            @calculator-created="onCalculatorCreated"
          />
        </v-col>

        <!-- Variant List Panel (only in showAllVariants mode) -->
        <v-col v-if="showAllVariants" cols="4">
          <VariantPanel
            :variants="variantsInStructure"
            :selected-id="selectedVariantId"
            :hovered-id="hoveredVariantId"
            :distance-cache="variantDistanceCache"
            @select="selectVariant"
            @hover="hoverVariant"
            @unhover="unhoverVariant"
            @view-details="emitVariantClicked"
          />
        </v-col>
      </v-row>

      <!-- Controls Row -->
      <StructureControls
        v-if="!loading && !error"
        v-model:representation="representation"
        v-model:show-dna="showDNA"
        v-model:color-by-domain="colorByDomain"
        :show-distance-button="activeVariantInStructure && !!activeVariantDistanceInfo"
        :distance-formatted="activeVariantDistanceInfo?.distanceFormatted || ''"
        :show-distance-line="showDistanceLine"
        @reset-view="resetView"
        @toggle-distance="toggleDistanceLine"
      />

      <!-- Distance Info and Legends -->
      <DistanceDisplay
        v-if="!loading && !error"
        :distance-info="activeVariantDistanceInfo"
        :show-distance-line="showDistanceLine"
        :color-by-domain="colorByDomain"
        :variant="activeVariant"
        :variant-in-structure="activeVariantInStructure"
        :show-all-variants="showAllVariants"
        :selected-variant="selectedVariant"
        :selected-variant-in-structure="selectedVariantInStructure"
        @view-details="emitVariantClicked"
      />
    </v-card-text>
  </v-card>
</template>

<script>
import { STRUCTURE_START, STRUCTURE_END } from '@/utils/dnaDistanceCalculator';
import { getPathogenicityColor } from '@/utils/colors';
import { extractAAPosition } from '@/utils/proteinDomains';
import { extractPNotation } from '@/utils/hgvs';
import StructureViewer from './protein-structure/StructureViewer.vue';
import StructureControls from './protein-structure/StructureControls.vue';
import VariantPanel from './protein-structure/VariantPanel.vue';
import DistanceDisplay from './protein-structure/DistanceDisplay.vue';

export default {
  name: 'ProteinStructure3D',
  components: {
    StructureViewer,
    StructureControls,
    VariantPanel,
    DistanceDisplay,
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
      // For showAllVariants mode
      selectedVariantId: null,
      hoveredVariantId: null,
      // Cache for variant distances
      variantDistanceCache: {},
      // Reference to distance calculator (from StructureViewer)
      distanceCalculator: null,
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
      return extractAAPosition(this.currentVariant);
    },
    currentVariantInStructure() {
      return (
        this.currentVariantAAPosition && this.isPositionInStructure(this.currentVariantAAPosition)
      );
    },
    // All variants mode computed properties
    variantsInStructure() {
      return this.variants.filter((v) => {
        const pos = extractAAPosition(v);
        return pos && this.isPositionInStructure(pos);
      });
    },
    selectedVariant() {
      if (!this.selectedVariantId) return null;
      return this.variants.find((v) => v.variant_id === this.selectedVariantId);
    },
    selectedVariantAAPosition() {
      if (!this.selectedVariant) return null;
      return extractAAPosition(this.selectedVariant);
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
      return extractAAPosition(this.activeVariant);
    },
    activeVariantInStructure() {
      return (
        this.activeVariantAAPosition && this.isPositionInStructure(this.activeVariantAAPosition)
      );
    },
    activeVariantDistanceInfo() {
      return this.currentVariantDistanceInfo;
    },
  },
  watch: {
    currentVariantId() {
      if (!this.showAllVariants) {
        this.calculateActiveVariantDistance();
      }
    },
    selectedVariantId() {
      if (this.showAllVariants) {
        this.calculateActiveVariantDistance();
      }
    },
  },
  methods: {
    onStructureReady() {
      this.loading = false;
      this.structureLoaded = true;

      // Calculate distances for active variant
      if (!this.showAllVariants) {
        this.calculateActiveVariantDistance();
      }

      // Pre-calculate distances for all variants (for filtering/sorting)
      if (this.showAllVariants) {
        this.calculateAllVariantDistances();
      }
    },

    onCalculatorCreated(calculator) {
      this.distanceCalculator = calculator;
    },

    isPositionInStructure(aaPosition) {
      return aaPosition >= STRUCTURE_START && aaPosition <= STRUCTURE_END;
    },

    calculateActiveVariantDistance() {
      if (!this.distanceCalculator || !this.structureLoaded) {
        this.currentVariantDistanceInfo = null;
        return;
      }

      if (!this.activeVariantInStructure) {
        this.currentVariantDistanceInfo = null;
        return;
      }

      const distanceInfo = this.distanceCalculator.calculateResidueToHelixDistance(
        this.activeVariantAAPosition,
        true
      );

      this.currentVariantDistanceInfo = distanceInfo;

      // Reset distance line when variant changes
      this.showDistanceLine = false;
    },

    calculateAllVariantDistances() {
      if (!this.distanceCalculator) return;

      this.variantsInStructure.forEach((variant) => {
        const position = extractAAPosition(variant);
        if (position && this.isPositionInStructure(position)) {
          const info = this.distanceCalculator.calculateResidueToHelixDistance(position);
          if (info) {
            this.variantDistanceCache[variant.variant_id] = info;
          }
        }
      });
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

    toggleDistanceLine() {
      this.showDistanceLine = !this.showDistanceLine;
    },

    resetView() {
      if (this.$refs.viewer) {
        this.$refs.viewer.resetView();
      }
    },

    getVariantChipColor(variant) {
      return getPathogenicityColor(variant.classificationVerdict);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },
  },
};
</script>

<style scoped>
.protein-3d-card {
  margin-bottom: 16px;
}
</style>
