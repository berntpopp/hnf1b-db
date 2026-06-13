<!-- Presentational variant list panel (all-variants mode). -->
<!-- Filter/sort selects + variant v-list + empty state. -->
<!-- Distances are resolved by the parent and attached to each variant as _distanceInfo. -->
<template>
  <div class="variant-panel">
    <div class="variant-panel-header">
      <span class="text-subtitle-2">Variants in Structure</span>
      <v-chip size="x-small" color="primary" class="ml-2">
        {{ variants.length }}
        <template v-if="variants.length !== totalInStructure"> / {{ totalInStructure }} </template>
      </v-chip>
    </div>

    <!-- Filter and Sort Controls -->
    <div class="variant-panel-controls">
      <!-- Sort Control -->
      <v-select
        :model-value="sortBy"
        :items="sortOptions"
        label="Sort by"
        density="compact"
        hide-details
        variant="outlined"
        class="sort-select"
        @update:model-value="$emit('update:sortBy', $event)"
      />

      <!-- Pathogenicity Filter -->
      <v-select
        :model-value="filterPathogenicity"
        :items="pathogenicityOptions"
        label="Pathogenicity"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        class="filter-select"
        @update:model-value="$emit('update:filterPathogenicity', $event)"
      />

      <!-- Distance Filter -->
      <v-select
        :model-value="filterDistance"
        :items="distanceOptions"
        label="DNA Distance"
        density="compact"
        hide-details
        variant="outlined"
        clearable
        class="filter-select"
        @update:model-value="$emit('update:filterDistance', $event)"
      />
    </div>

    <v-list density="compact" class="variant-list">
      <v-list-item
        v-for="variant in variants"
        :key="variant.variant_id"
        :class="{
          'variant-item-active': selectedVariantId === variant.variant_id,
          'variant-item-hover': hoveredVariantId === variant.variant_id,
        }"
        @click="$emit('select', variant)"
        @mouseenter="$emit('hover', variant)"
        @mouseleave="$emit('unhover')"
      >
        <template #prepend>
          <v-avatar :color="getVariantChipColor(variant)" size="28">
            <span class="text-white text-caption">{{ extractAAPosition(variant) }}</span>
          </v-avatar>
        </template>
        <v-list-item-title class="text-body-2">
          {{ getVariantLabel(variant) }}
        </v-list-item-title>
        <v-list-item-subtitle class="text-caption d-flex align-center">
          <span>{{ variant.classificationVerdict || 'Unknown' }}</span>
          <v-chip
            v-if="getVariantDistanceCategory(variant)"
            size="x-small"
            :color="getDistanceChipColor(getVariantDistanceCategory(variant))"
            class="ml-2"
          >
            {{ getVariantDistanceFormatted(variant) }}
          </v-chip>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
    <div v-if="variants.length === 0" class="text-center py-4 text-grey">
      <v-icon size="large" color="grey-lighten-1">mdi-alert-circle-outline</v-icon>
      <div class="text-caption mt-1">
        {{
          totalInStructure === 0 ? 'No variants in structure range' : 'No variants match filters'
        }}
      </div>
      <v-btn
        v-if="totalInStructure > 0 && (filterPathogenicity || filterDistance)"
        size="x-small"
        variant="text"
        color="primary"
        class="mt-2"
        @click="$emit('clear-filters')"
      >
        Clear Filters
      </v-btn>
    </div>
  </div>
</template>

<script>
import { extractPNotation } from '@/utils/hgvs';
import { getPathogenicityColor } from '@/utils/colors';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';

export default {
  name: 'VariantPanel',
  props: {
    // Already filtered + sorted variants, each carrying a resolved `_distanceInfo`.
    variants: {
      type: Array,
      default: () => [],
    },
    // Total count of variants in the structure range (pre-filter), for the "n / m" chip.
    totalInStructure: {
      type: Number,
      default: 0,
    },
    selectedVariantId: {
      type: String,
      default: null,
    },
    hoveredVariantId: {
      type: String,
      default: null,
    },
    sortBy: {
      type: String,
      default: 'position',
    },
    filterPathogenicity: {
      type: String,
      default: null,
    },
    filterDistance: {
      type: String,
      default: null,
    },
  },
  emits: [
    'select',
    'hover',
    'unhover',
    'clear-filters',
    'update:sortBy',
    'update:filterPathogenicity',
    'update:filterDistance',
  ],
  data() {
    return {
      sortOptions: [
        { title: 'Position', value: 'position' },
        { title: 'Distance to DNA', value: 'distance' },
        { title: 'Pathogenicity', value: 'pathogenicity' },
      ],
      pathogenicityOptions: [
        { title: 'Pathogenic', value: 'PATHOGENIC' },
        { title: 'Likely Pathogenic', value: 'LIKELY_PATHOGENIC' },
        { title: 'VUS', value: 'VUS' },
        { title: 'Likely Benign', value: 'LIKELY_BENIGN' },
        { title: 'Benign', value: 'BENIGN' },
      ],
      distanceOptions: [
        { title: 'Close (<5 Å)', value: 'close' },
        { title: 'Medium (5-10 Å)', value: 'medium' },
        { title: 'Far (>10 Å)', value: 'far' },
      ],
    };
  },
  methods: {
    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },

    getVariantChipColor(variant) {
      return getPathogenicityColor(variant.classificationVerdict);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    getVariantDistanceCategory(variant) {
      const info = variant._distanceInfo;
      return info ? info.category : null;
    },

    getVariantDistanceFormatted(variant) {
      const info = variant._distanceInfo;
      return info ? `${info.distanceFormatted} Å` : null;
    },

    getDistanceChipColor(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },
  },
};
</script>

<style scoped>
/* Variant panel styles */
.variant-panel {
  height: 500px;
  border: 1px solid #e0e0e0;
  border-left: none;
  border-radius: 0 4px 4px 0;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
}

.variant-panel-header {
  padding: 12px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
}

.variant-panel-controls {
  padding: 8px 12px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sort-select,
.filter-select {
  font-size: 12px;
}

.variant-list {
  flex: 1;
  overflow-y: auto;
  background-color: transparent;
}

.variant-item-active {
  background-color: #e3f2fd !important;
  border-left: 3px solid #1976d2;
}

.variant-item-hover {
  background-color: #f5f5f5;
}
</style>
