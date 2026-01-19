<!-- Distance Display Component -->
<!-- Shows distance alerts, legends, and variant warnings -->
<template>
  <div>
    <!-- Active Variant Distance Info -->
    <v-alert
      v-if="variantInStructure && distanceInfo"
      :type="getDistanceAlertType(distanceInfo.category)"
      density="compact"
      variant="tonal"
      class="mt-3"
    >
      <v-icon size="small" class="mr-1"> mdi-ruler </v-icon>
      <strong>Distance to DNA:</strong>
      <!-- Use HTML entity for Angstrom symbol -->
      <span v-html="distanceInfo.distanceFormatted + ' &#8491;'" />
      ({{ getDistanceCategoryLabel(distanceInfo.category) }})
      <span class="text-caption ml-2">
        Closest DNA atom: {{ distanceInfo.closestDNAAtom?.label }}
      </span>
    </v-alert>

    <!-- Legend Row -->
    <v-row class="mt-2">
      <v-col cols="12">
        <div class="legend-container">
          <span class="text-caption text-grey mr-2">Pathogenicity:</span>
          <v-chip size="x-small" color="red-lighten-1" class="mr-1"> Pathogenic </v-chip>
          <v-chip size="x-small" color="orange-lighten-1" class="mr-1"> Likely Pathogenic </v-chip>
          <v-chip size="x-small" color="yellow-darken-1" class="mr-1"> VUS </v-chip>
          <v-chip size="x-small" color="light-green-lighten-1" class="mr-1"> Likely Benign </v-chip>
          <v-chip size="x-small" color="grey-lighten-1"> Unknown </v-chip>
        </div>
        <!-- Domain Legend (shown when domain coloring is enabled) -->
        <div v-if="colorByDomain" class="legend-container mt-2">
          <span class="text-caption text-grey mr-2">Domains:</span>
          <v-chip size="x-small" style="background-color: #ab47bc; color: white" class="mr-1">
            POU-S (90-173)
          </v-chip>
          <v-chip size="x-small" style="background-color: #26a69a; color: white" class="mr-1">
            POU-H (232-305)
          </v-chip>
          <v-chip size="x-small" style="background-color: #9e9e9e" class="mr-1"> Linker </v-chip>
          <span class="text-caption text-grey-darken-1 ml-2"> (Gap: 187-230 not resolved) </span>
        </div>
      </v-col>
    </v-row>

    <!-- Current variant not in structure warning (single variant mode) -->
    <v-alert
      v-if="!showAllVariants && variant && !variantInStructure"
      type="warning"
      density="compact"
      variant="tonal"
      class="mt-3"
    >
      <v-icon size="small" class="mr-1"> mdi-map-marker-off </v-icon>
      <strong>Current variant not in structure:</strong>
      {{ variant.protein || variant.transcript }} is outside the PDB structure range (residues
      90-308, gap at 187-230).
    </v-alert>

    <!-- Selected variant info (all variants mode) -->
    <v-alert
      v-if="showAllVariants && selectedVariant"
      :type="selectedVariantInStructure ? 'info' : 'warning'"
      density="compact"
      variant="tonal"
      class="mt-3"
    >
      <v-icon size="small" class="mr-1">
        {{ selectedVariantInStructure ? 'mdi-cursor-default-click' : 'mdi-map-marker-off' }}
      </v-icon>
      <strong>Selected:</strong> {{ getVariantLabel(selectedVariant) }}
      <v-chip size="x-small" :color="getVariantChipColor(selectedVariant)" class="ml-2">
        {{ selectedVariant.classificationVerdict || 'Unknown' }}
      </v-chip>
      <v-btn
        v-if="selectedVariant"
        size="x-small"
        variant="outlined"
        color="primary"
        class="ml-3"
        @click="$emit('view-details', selectedVariant)"
      >
        <v-icon size="x-small" left>mdi-open-in-new</v-icon>
        View Details
      </v-btn>
    </v-alert>
  </div>
</template>

<script>
import { getPathogenicityColor } from '@/utils/colors';
import { extractPNotation } from '@/utils/hgvs';
import './styles.css';

export default {
  name: 'DistanceDisplay',
  props: {
    /** Distance calculation result */
    distanceInfo: {
      type: Object,
      default: null,
    },
    /** Whether distance line is shown */
    showDistanceLine: {
      type: Boolean,
      default: false,
    },
    /** Whether domain coloring is enabled */
    colorByDomain: {
      type: Boolean,
      default: false,
    },
    /** Current variant object (for warnings) */
    variant: {
      type: Object,
      default: null,
    },
    /** Whether the variant is in the structure range */
    variantInStructure: {
      type: Boolean,
      default: false,
    },
    /** Whether in showAllVariants mode */
    showAllVariants: {
      type: Boolean,
      default: false,
    },
    /** Selected variant in showAllVariants mode */
    selectedVariant: {
      type: Object,
      default: null,
    },
    /** Whether selected variant is in structure */
    selectedVariantInStructure: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['view-details'],
  methods: {
    getDistanceAlertType(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },

    getDistanceCategoryLabel(category) {
      if (category === 'close') return 'Close to DNA - likely functional impact';
      if (category === 'medium') return 'Medium distance';
      return 'Far from DNA';
    },

    getVariantChipColor(variant) {
      return getPathogenicityColor(variant?.classificationVerdict);
    },

    getVariantLabel(variant) {
      if (!variant) return '';
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },
  },
};
</script>
